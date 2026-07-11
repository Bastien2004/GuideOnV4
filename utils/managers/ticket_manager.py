"""
utils/managers/ticket_manager.py — CRUD du système de tickets.

API publique principale :
    # Panels
    await get_panel(guild_id, panel_id) -> dict | None
    await get_panel_by_message(guild_id, message_id) -> dict | None
    await list_panels(guild_id) -> list[dict]
    await all_panels() -> list[dict]                # tous serveurs (boot views)
    await create_panel(...) -> dict
    await update_panel(guild_id, panel_id, **fields) -> dict | None
    await delete_panel(guild_id, panel_id) -> bool

    # Compteurs panel (atomiques)
    await reserve_ticket_number(guild_id, panel_id) -> str | None   # "00001"
    await incr_open_count(guild_id, panel_id) -> None
    await decr_open_count(guild_id, panel_id) -> None
    await incr_deleted_count(guild_id, panel_id) -> None

    # Tickets (direct DB)
    await get_ticket(channel_id) -> dict | None
    await create_ticket(...) -> dict
    await update_ticket(channel_id, **fields) -> dict | None
    await delete_ticket(channel_id) -> bool          # + incr deleted_count
    await count_open_tickets(guild_id) -> int
    await count_user_tickets_on_panel(guild_id, panel_id, user_id) -> int

    # Lectures sync (cache panels)
    is_staff_sync(guild_id, panel_id, user_role_ids) -> bool
    get_panel_sync(guild_id, panel_id) -> dict | None
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import case, delete, func, select, update
from sqlalchemy.orm import selectinload

from utils.db.models.ticket import Ticket, TicketPanel, TicketPanelStaffRole
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

# guild_id -> ({panel_id: panel_dict}, monotonic_timestamp)
_panel_cache: dict[int, tuple[dict[str, dict], float]] = {}
_lock = asyncio.Lock()


# ══════════════════════════════════════════════════════════════════════════
# 🔧 Helpers internes
# ══════════════════════════════════════════════════════════════════════════

# Champs de TicketPanel modifiables via update_panel (on protège id/panel_id/
# guild_id/compteurs qui ont leur propre chemin).
_PANEL_EDITABLE = {
    "channel_id",
    "message_id",
    "title",
    "panel_message",
    "ticket_category_id",
    "transcript_channel_id",
    "closed_category_id",
    "ping_role_id",
    "role_ban_ticket_id",
}

# Champs de Ticket modifiables via update_ticket.
_TICKET_EDITABLE = {
    "pseudo",
    "original_name",
    "raison",
    "closed",
    "last_rename_at",
    "welcome_message_id",
}


def _invalidate_guild(guild_id: int) -> None:
    """Vire l'entrée de cache d'une guilde (après écriture sur un panel)."""
    _panel_cache.pop(guild_id, None)


async def _load_guild_panels(guild_id: int) -> dict[str, dict]:
    """Charge tous les panels d'une guilde depuis la DB → {panel_id: dict}."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(TicketPanel)
                .where(TicketPanel.guild_id == guild_id)
                .options(selectinload(TicketPanel.staff_roles))
            )
        ).scalars().all()
    return {p.panel_id: p.to_dict() for p in rows}


async def _get_guild_panels_cached(guild_id: int) -> dict[str, dict]:
    """Renvoie {panel_id: dict} depuis le cache, ou recharge si périmé."""
    now = time.monotonic()
    cached = _panel_cache.get(guild_id)
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return cached[0]
    panels = await _load_guild_panels(guild_id)
    _panel_cache[guild_id] = (panels, now)
    return panels


# ══════════════════════════════════════════════════════════════════════════
# 📖 PANELS — lectures async
# ══════════════════════════════════════════════════════════════════════════

async def get_panel(guild_id: int, panel_id: str) -> dict | None:
    """Un panel par son panel_id métier. Passe par le cache."""
    panels = await _get_guild_panels_cached(guild_id)
    return panels.get(panel_id)


async def get_panel_by_message(guild_id: int, message_id: int) -> dict | None:
    """Un panel par l'ID du message Discord (pour edit/delete par lien)."""
    panels = await _get_guild_panels_cached(guild_id)
    for p in panels.values():
        if p.get("message_id") == message_id:
            return p
    return None


async def list_panels(guild_id: int) -> list[dict]:
    """Tous les panels d'une guilde (pour /ticket panel_list)."""
    panels = await _get_guild_panels_cached(guild_id)
    return list(panels.values())


async def all_panels() -> list[dict]:
    """
    Tous les panels de tous les serveurs (pour réenregistrer les vues
    persistantes au setup_hook). Lecture directe DB, pas de cache.
    """
    async with get_session() as session:
        rows = (
            await session.execute(
                select(TicketPanel).options(selectinload(TicketPanel.staff_roles))
            )
        ).scalars().all()
    return [p.to_dict() for p in rows]


# ══════════════════════════════════════════════════════════════════════════
# ✍️ PANELS — écritures async
# ══════════════════════════════════════════════════════════════════════════

async def create_panel(
    *,
    guild_id: int,
    panel_id: str,
    channel_id: int,
    message_id: int | None,
    title: str,
    panel_message: str,
    ticket_category_id: int,
    transcript_channel_id: int,
    staff_role_ids: list[int],
    closed_category_id: int | None = None,
    ping_role_id: int | None = None,
    role_ban_ticket_id: int | None = None,
    counter: int = 1,
) -> dict:
    """Crée un panel + ses rôles staff. Renvoie le dict du panel."""
    async with _lock:
        async with get_session() as session:
            panel = TicketPanel(
                panel_id=panel_id,
                guild_id=guild_id,
                channel_id=channel_id,
                message_id=message_id,
                title=title,
                panel_message=panel_message,
                ticket_category_id=ticket_category_id,
                transcript_channel_id=transcript_channel_id,
                closed_category_id=closed_category_id,
                ping_role_id=ping_role_id,
                role_ban_ticket_id=role_ban_ticket_id,
                counter=counter,
            )
            for rid in dict.fromkeys(staff_role_ids):  # dédoublonne, garde l'ordre
                panel.staff_roles.append(TicketPanelStaffRole(role_id=rid))
            session.add(panel)
            await session.flush()
            result = panel.to_dict()
        _invalidate_guild(guild_id)
    log.info("Panel ticket créé : guild=%s panel_id=%s", guild_id, panel_id)
    return result


async def update_panel(
    guild_id: int,
    panel_id: str,
    *,
    staff_role_ids: list[int] | None = None,
    **fields,
) -> dict | None:
    """
    Met à jour les champs d'un panel. Si `staff_role_ids` est fourni, remplace
    intégralement la liste des rôles staff. Renvoie le dict à jour, ou None si
    le panel n'existe pas.
    """
    clean = {k: v for k, v in fields.items() if k in _PANEL_EDITABLE}

    async with _lock:
        async with get_session() as session:
            panel = (
                await session.execute(
                    select(TicketPanel)
                    .where(
                        TicketPanel.guild_id == guild_id,
                        TicketPanel.panel_id == panel_id,
                    )
                    .options(selectinload(TicketPanel.staff_roles))
                )
            ).scalar_one_or_none()

            if panel is None:
                return None

            for k, v in clean.items():
                setattr(panel, k, v)

            if staff_role_ids is not None:
                panel.staff_roles.clear()
                await session.flush()  # applique le delete-orphan avant le réajout
                for rid in dict.fromkeys(staff_role_ids):
                    panel.staff_roles.append(TicketPanelStaffRole(role_id=rid))

            await session.flush()
            result = panel.to_dict()
        _invalidate_guild(guild_id)
    return result


async def delete_panel(guild_id: int, panel_id: str) -> bool:
    """Supprime un panel (cascade DB : staff_roles + tickets). True si existait."""
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(TicketPanel).where(
                    TicketPanel.guild_id == guild_id,
                    TicketPanel.panel_id == panel_id,
                )
            )
            deleted = result.rowcount > 0
        _invalidate_guild(guild_id)
    if deleted:
        log.info("Panel ticket supprimé : guild=%s panel_id=%s", guild_id, panel_id)
    return deleted


# ══════════════════════════════════════════════════════════════════════════
# 🔢 COMPTEURS PANEL — UPDATE SQL atomiques (anti race condition)
# ══════════════════════════════════════════════════════════════════════════

def _format_ticket_number(n: int) -> str:
    """Format V3 : 00001 ; au-delà de 99999 → 00000.<surplus>."""
    return str(n).zfill(5) if n <= 99999 else f"00000.{n - 99999}"


async def reserve_ticket_number(guild_id: int, panel_id: str) -> str | None:
    """
    Réserve atomiquement le prochain numéro de ticket d'un panel.

    Fait `UPDATE ... SET counter = counter + 1` puis lit la valeur AVANT
    incrément (le numéro à utiliser). Atomique : deux appels concurrents ne
    peuvent pas obtenir le même numéro. Renvoie None si le panel n'existe pas.
    """
    async with get_session() as session:
        # On incrémente et on récupère la NOUVELLE valeur du compteur.
        result = await session.execute(
            update(TicketPanel)
            .where(
                TicketPanel.guild_id == guild_id,
                TicketPanel.panel_id == panel_id,
            )
            .values(counter=TicketPanel.counter + 1)
            .returning(TicketPanel.counter)
        )
        row = result.first()
        if row is None:
            return None
        new_counter = row[0]
    _invalidate_guild(guild_id)
    # Le numéro réservé est la valeur AVANT incrément.
    return _format_ticket_number(new_counter - 1)


async def _bump_counter(guild_id: int, panel_id: str, column, delta: int) -> None:
    """Incrément/décrément atomique générique d'un compteur de panel.

    Pour un décrément on borne à 0 via un CASE SQL standard (portable
    Postgres/SQLite, contrairement à GREATEST qui est spécifique Postgres).
    """
    if delta < 0:
        new_value = case((column + delta < 0, 0), else_=column + delta)
    else:
        new_value = column + delta
    async with get_session() as session:
        await session.execute(
            update(TicketPanel)
            .where(
                TicketPanel.guild_id == guild_id,
                TicketPanel.panel_id == panel_id,
            )
            .values({column: new_value})
        )
    _invalidate_guild(guild_id)


async def incr_open_count(guild_id: int, panel_id: str) -> None:
    """+1 sur open_tickets_count (ouverture d'un ticket)."""
    await _bump_counter(guild_id, panel_id, TicketPanel.open_tickets_count, +1)


async def decr_open_count(guild_id: int, panel_id: str) -> None:
    """-1 sur open_tickets_count (fermeture/suppression), borné à 0."""
    await _bump_counter(guild_id, panel_id, TicketPanel.open_tickets_count, -1)


async def incr_deleted_count(guild_id: int, panel_id: str) -> None:
    """+1 sur deleted_tickets_count (ticket traité jusqu'à suppression)."""
    await _bump_counter(guild_id, panel_id, TicketPanel.deleted_tickets_count, +1)


# ══════════════════════════════════════════════════════════════════════════
# 🎟️ TICKETS — toujours en direct DB (jamais cachés)
# ══════════════════════════════════════════════════════════════════════════

async def get_ticket(channel_id: int) -> dict | None:
    """Un ticket par son channel_id (= PK)."""
    async with get_session() as session:
        ticket = await session.get(Ticket, channel_id)
        return ticket.to_dict() if ticket is not None else None


async def create_ticket(
    *,
    channel_id: int,
    guild_id: int,
    panel_id: str,
    creator_id: int,
    ticket_number: str,
    original_name: str,
    pseudo: str | None = None,
    raison: str | None = None,
    opened_at: int = 0,
    welcome_message_id: int | None = None,
) -> dict:
    """
    Crée un ticket ET incrémente open_tickets_count du panel, dans la même
    transaction (atomique). Résout le panel_fk depuis le panel_id métier.
    """
    async with get_session() as session:
        panel = (
            await session.execute(
                select(TicketPanel.id).where(
                    TicketPanel.guild_id == guild_id,
                    TicketPanel.panel_id == panel_id,
                )
            )
        ).scalar_one_or_none()
        if panel is None:
            raise ValueError(
                f"Panel introuvable pour create_ticket "
                f"(guild={guild_id}, panel_id={panel_id})"
            )

        ticket = Ticket(
            channel_id=channel_id,
            guild_id=guild_id,
            panel_fk=panel,
            panel_id=panel_id,
            creator_id=creator_id,
            pseudo=pseudo,
            ticket_number=ticket_number,
            original_name=original_name,
            raison=raison,
            closed=False,
            opened_at=opened_at,
            last_rename_at=0,
            welcome_message_id=welcome_message_id,
        )
        session.add(ticket)

        # incrément open_count dans la MÊME transaction
        await session.execute(
            update(TicketPanel)
            .where(TicketPanel.id == panel)
            .values(open_tickets_count=TicketPanel.open_tickets_count + 1)
        )
        await session.flush()
        result = ticket.to_dict()

    _invalidate_guild(guild_id)
    return result


async def update_ticket(channel_id: int, **fields) -> dict | None:
    """Met à jour des champs d'un ticket. Renvoie le dict à jour, ou None."""
    clean = {k: v for k, v in fields.items() if k in _TICKET_EDITABLE}
    async with get_session() as session:
        ticket = await session.get(Ticket, channel_id)
        if ticket is None:
            return None
        for k, v in clean.items():
            setattr(ticket, k, v)
        await session.flush()
        return ticket.to_dict()


async def delete_ticket(channel_id: int) -> bool:
    """
    Supprime un ticket. Incrémente deleted_tickets_count et décrémente
    open_tickets_count du panel, dans la même transaction. True si le ticket
    existait.

    La décrémentation a lieu ICI, à la suppression définitive, quel que soit
    l'état `closed` du ticket. Par design (voir views/ticket/lifecycle.py::
    _close_ticket), fermer un ticket ne touche PAS open_tickets_count : un
    ticket fermé mais pas encore supprimé continue d'occuper un "slot" tant
    que son salon Discord existe encore. C'est uniquement la suppression
    définitive du salon (donc de cette ligne en DB) qui doit libérer le slot.

    ⚠️ Avant correction, un garde `if was_open` limitait ce décrément au cas
    où le ticket était encore ouvert (closed=False) au moment du delete — or
    en pratique AUCUN chemin du code ne permet de supprimer un ticket encore
    ouvert (/ticket delete et le bouton de suppression exigent tous les deux
    que le ticket soit déjà fermé). Ce garde empêchait donc systématiquement
    la décrémentation réelle, et open_tickets_count ne faisait que croître.
    """
    async with get_session() as session:
        ticket = await session.get(Ticket, channel_id)
        if ticket is None:
            return False

        guild_id = ticket.guild_id
        panel_fk = ticket.panel_fk

        await session.delete(ticket)

        # deleted +1 ; open -1 (borné à 0) — toujours, à la suppression définitive.
        values = {
            "deleted_tickets_count": TicketPanel.deleted_tickets_count + 1,
            "open_tickets_count": case(
                (TicketPanel.open_tickets_count - 1 < 0, 0),
                else_=TicketPanel.open_tickets_count - 1,
            ),
        }
        await session.execute(
            update(TicketPanel).where(TicketPanel.id == panel_fk).values(**values)
        )

    _invalidate_guild(guild_id)
    log.info("Ticket supprimé : channel=%s guild=%s", channel_id, guild_id)
    return True


# ══════════════════════════════════════════════════════════════════════════
# 📊 COMPTAGES (direct DB)
# ══════════════════════════════════════════════════════════════════════════

async def count_open_tickets(guild_id: int) -> int:
    """Nombre de tickets non fermés sur toute la guilde."""
    async with get_session() as session:
        return (
            await session.scalar(
                select(func.count())
                .select_from(Ticket)
                .where(Ticket.guild_id == guild_id, Ticket.closed.is_(False))
            )
        ) or 0


async def count_user_tickets_on_panel(
    guild_id: int, panel_id: str, user_id: int
) -> int:
    """Tickets non fermés ouverts par un user sur un panel donné."""
    async with get_session() as session:
        return (
            await session.scalar(
                select(func.count())
                .select_from(Ticket)
                .where(
                    Ticket.guild_id == guild_id,
                    Ticket.panel_id == panel_id,
                    Ticket.creator_id == user_id,
                    Ticket.closed.is_(False),
                )
            )
        ) or 0


async def all_tickets(closed: bool | None = None) -> list[dict]:
    """
    Tous les tickets de tous les serveurs (pour réenregistrer les vues
    persistantes au boot). Lecture directe DB, pas de cache.

    closed=None  → tous les tickets
    closed=False → uniquement les tickets ouverts
    closed=True  → uniquement les tickets fermés
    """
    async with get_session() as session:
        stmt = select(Ticket)
        if closed is not None:
            stmt = stmt.where(Ticket.closed.is_(closed))
        rows = (await session.execute(stmt)).scalars().all()
    return [t.to_dict() for t in rows]


# ══════════════════════════════════════════════════════════════════════════
# ⚡ LECTURES SYNC (cache panels) — compat V3, pas d'await
# ══════════════════════════════════════════════════════════════════════════

def get_panel_sync(guild_id: int, panel_id: str) -> dict | None:
    """
    Lecture sync d'un panel depuis le cache. Renvoie None si pas en cache
    (cache froid ou panel inconnu) — l'appelant doit alors retomber sur l'async.
    """
    cached = _panel_cache.get(guild_id)
    if cached is None:
        return None
    return cached[0].get(panel_id)


def is_staff_sync(
    guild_id: int, panel_id: str, user_role_ids: list[int] | set[int]
) -> bool | None:
    """
    True si l'un des rôles de l'utilisateur est staff sur ce panel.

    Renvoie None si le panel n'est pas en cache (l'appelant doit alors vérifier
    en async via get_panel). Lecture pure cache, aucune I/O.
    """
    panel = get_panel_sync(guild_id, panel_id)
    if panel is None:
        return None
    staff = set(panel.get("staff_roles", []))
    return any(rid in staff for rid in user_role_ids)


async def warm_cache() -> None:
    """Préchauffe le cache de tous les serveurs (optionnel, au boot)."""
    panels = await all_panels()
    by_guild: dict[int, dict[str, dict]] = {}
    for p in panels:
        by_guild.setdefault(p["guild_id"], {})[p["panel_id"]] = p
    now = time.monotonic()
    for gid, pmap in by_guild.items():
        _panel_cache[gid] = (pmap, now)
    log.info("Cache tickets préchauffé : %d serveurs", len(by_guild))