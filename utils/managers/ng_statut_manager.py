"""
utils/managers/ng_statut_manager.py — Statuts secondaires définissables
librement par serveur NG (ex: builder, journaliste, avocat, équipe com...).

Remplace le dict figé à 3 entrées (SECONDARY_STATUSES, utils/db/models/
alpha_staff.py) : chaque serveur NG définit ses propres statuts via
/ngstaff config → Statuts (voir views/ngstaff/config_statuts_view.py),
sans toucher au code. Généralise aussi le besoin spécifique de Builder
(pseudo_jeu_builder) en un flag `requires_second_pseudo` réutilisable par
n'importe quel statut (Paul, 2026-08-22).

`has_stafflist_category` (Paul, 2026-08-22, retour utilisateur) : indépendant
de `requires_second_pseudo` — permet à N'IMPORTE QUEL statut (builder, com,
affilié, journaliste, avocat...) d'avoir sa propre section dans
/ngstaff stafflist, pas seulement ceux qui exigent un pseudo secondaire.
Un statut avec l'un OU l'autre flag obtient une section dédiée (voir
views/ngstaff/stafflist_view.py) — ça préserve le comportement existant de
Builder sans rien casser.

Deux niveaux :
  - "Définitions" (ng_statut_defs) : la liste des statuts possibles pour un
    serveur donné, avec leur rôle Discord, emoji, etc. Cache TTL 60s par
    serveur, comme ng_rank_config_manager.
  - "Attributions" (ng_staff_statuts) : qui détient quel statut. Pas de
    cache ici — c'est ng_staff_manager (list_staff/get_staff_member) qui
    appelle list_member_statuts_bulk une fois et enrichit ses propres
    dicts avec une clé "statuts", pour éviter le N+1 côté appelants.

API publique :
    await list_statut_defs(server) -> list[dict]                     # triés par position
    await get_statut_def(server, key) -> dict | None
    await create_statut_def(server, key, label, ...) -> dict
    await update_statut_def(server, key, **fields) -> dict
    await delete_statut_def(server, key) -> bool

    await list_member_statuts_bulk(server) -> dict[int, list[dict]]  # discord_id -> statuts
    await get_member_statuts(server, discord_id) -> list[dict]
    await grant_statut(server, discord_id, key, second_pseudo=None) -> dict
    await revoke_statut(server, discord_id, key) -> bool
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import delete, select

from utils.db.models.ng_statut import NGStaffStatut, NGStatutDef
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60

_defs_cache: dict[str, tuple[list[dict], float]] = {}
_lock = asyncio.Lock()


class NGStatutError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


# ════════════════════════════════════════════════════════════
# 📖 Définitions — lecture (cache)
# ════════════════════════════════════════════════════════════

def _is_valid(server: str) -> bool:
    cached = _defs_cache.get(server)
    return cached is not None and (time.monotonic() - cached[1]) < CACHE_TTL_SECONDS


def _invalidate(server: str) -> None:
    _defs_cache.pop(server, None)


async def list_statut_defs(server: str) -> list[dict]:
    """Statuts définis pour ce serveur, triés par position d'affichage."""
    if _is_valid(server):
        return list(_defs_cache[server][0])

    async with get_session() as session:
        rows = (await session.execute(
            select(NGStatutDef).where(NGStatutDef.server == server).order_by(NGStatutDef.position, NGStatutDef.id)
        )).scalars().all()
    defs = [r.to_dict() for r in rows]

    _defs_cache[server] = (defs, time.monotonic())
    return list(defs)


async def get_statut_def(server: str, key: str) -> dict | None:
    defs = await list_statut_defs(server)
    for d in defs:
        if d["key"] == key:
            return dict(d)
    return None


async def get_statut_def_by_id(statut_def_id: int) -> dict | None:
    """Résolution directe par id (utilisée quand on ne connaît que statut_def_id)."""
    async with get_session() as session:
        row = await session.get(NGStatutDef, statut_def_id)
    return row.to_dict() if row is not None else None


# ════════════════════════════════════════════════════════════
# ✍️ Définitions — écriture
# ════════════════════════════════════════════════════════════

def _slugify_key(raw: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in raw.strip().lower())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")[:32]


async def create_statut_def(
    server: str,
    label: str,
    *,
    key: str | None = None,
    emoji: str | None = None,
    role_id: int | None = None,
    requires_second_pseudo: bool = False,
    has_stafflist_category: bool = False,
) -> dict:
    """
    Crée un nouveau statut pour ce serveur. `key` auto-dérivée de `label`
    si non fournie (slug technique, immuable une fois créé — comme
    NGServer.name). Lève NGStatutError si la clé existe déjà pour ce serveur.
    """
    label = label.strip()
    if not label:
        raise NGStatutError("Le libellé du statut ne peut pas être vide.", warning=True)

    final_key = _slugify_key(key or label)
    if not final_key:
        raise NGStatutError("Impossible de dériver une clé technique valide de ce libellé.", warning=True)

    async with _lock:
        existing = await get_statut_def(server, final_key)
        if existing is not None:
            raise NGStatutError(f"Un statut `{final_key}` existe déjà pour ce serveur.", warning=True)

        async with get_session() as session:
            current = (await session.execute(
                select(NGStatutDef.position).where(NGStatutDef.server == server)
            )).scalars().all()
            next_position = (max(current) + 1) if current else 0

            row = NGStatutDef(
                server=server, key=final_key, label=label, emoji=emoji or None,
                role_id=role_id, requires_second_pseudo=requires_second_pseudo,
                has_stafflist_category=has_stafflist_category,
                position=next_position,
            )
            session.add(row)
            await session.flush()
            result = row.to_dict()

        _invalidate(server)

    log.info("[NG STATUT] %s : statut créé key=%s label=%s", server, final_key, label)
    return result


async def update_statut_def(server: str, key: str, **fields: object) -> dict:
    """Upsert partiel sur un statut existant. Lève NGStatutError si introuvable."""
    allowed = {"label", "emoji", "role_id", "requires_second_pseudo", "has_stafflist_category", "position"}
    clean = {k: v for k, v in fields.items() if k in allowed}

    async with _lock:
        async with get_session() as session:
            row = (await session.execute(
                select(NGStatutDef).where(NGStatutDef.server == server, NGStatutDef.key == key)
            )).scalar_one_or_none()
            if row is None:
                raise NGStatutError(f"Statut `{key}` introuvable pour ce serveur.", warning=True)
            for k, v in clean.items():
                setattr(row, k, v)
            await session.flush()
            result = row.to_dict()

        _invalidate(server)

    # 🔄 Les dicts membres mis en cache par ng_staff_manager embarquent une
    # copie de "statuts" (label/emoji/role_id/requires_second_pseudo) — à
    # invalider aussi, sinon staleness jusqu'à 60s (Paul, 2026-08-22).
    from utils.managers.ng_staff_manager import invalidate_cache as _invalidate_staff_cache
    _invalidate_staff_cache(server)

    return result


async def delete_statut_def(server: str, key: str) -> bool:
    """
    Supprime un statut et TOUTES les attributions associées (ON DELETE
    CASCADE sur ng_staff_statuts.statut_def_id) — les membres qui l'avaient
    le perdent silencieusement (pas de retrait de rôle Discord automatique
    ici : le rôle reste tant qu'un /ngstaff derank ou une resync manuelle
    n'est pas fait, cf. apply_staff_roles qui se base sur la config actuelle
    au moment du rank/derank, pas sur un évènement de suppression de statut).
    """
    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(NGStatutDef).where(NGStatutDef.server == server, NGStatutDef.key == key)
            )
            deleted = result.rowcount > 0
        if deleted:
            _invalidate(server)

    if deleted:
        # 🔄 Idem update_statut_def : les membres qui avaient ce statut en
        # cache (ng_staff_manager) doivent le voir disparaître immédiatement,
        # pas après expiration du TTL (Paul, 2026-08-22).
        from utils.managers.ng_staff_manager import invalidate_cache as _invalidate_staff_cache
        _invalidate_staff_cache(server)
        log.info("[NG STATUT] %s : statut supprimé key=%s", server, key)
    return deleted


# ════════════════════════════════════════════════════════════
# 📖 Attributions — lecture
# ════════════════════════════════════════════════════════════

async def list_member_statuts_bulk(server: str) -> dict[int, list[dict]]:
    """
    Charge en UNE requête les statuts de TOUS les membres d'un serveur —
    évite le N+1 quand on enrichit list_staff(server) (potentiellement des
    dizaines de membres).
    """
    async with get_session() as session:
        rows = (await session.execute(
            select(NGStaffStatut, NGStatutDef)
            .join(NGStatutDef, NGStaffStatut.statut_def_id == NGStatutDef.id)
            .where(NGStaffStatut.server == server)
            .order_by(NGStatutDef.position, NGStatutDef.id)
        )).all()

    by_member: dict[int, list[dict]] = {}
    for staff_statut, statut_def in rows:
        by_member.setdefault(staff_statut.discord_id, []).append({
            "key": statut_def.key,
            "label": statut_def.label,
            "emoji": statut_def.emoji,
            "role_id": statut_def.role_id,
            "requires_second_pseudo": statut_def.requires_second_pseudo,
            "has_stafflist_category": statut_def.has_stafflist_category,
            "second_pseudo": staff_statut.second_pseudo,
        })
    return by_member


async def get_member_statuts(server: str, discord_id: int) -> list[dict]:
    by_member = await list_member_statuts_bulk(server)
    return by_member.get(discord_id, [])


async def has_statut(server: str, discord_id: int, key: str) -> bool:
    statuts = await get_member_statuts(server, discord_id)
    return any(s["key"] == key for s in statuts)


# ════════════════════════════════════════════════════════════
# ✍️ Attributions — écriture
# ════════════════════════════════════════════════════════════

async def grant_statut(server: str, discord_id: int, key: str, *, second_pseudo: str | None = None) -> dict:
    """
    Attribue un statut à un membre. Lève NGStatutError si le statut n'existe
    pas pour ce serveur ou s'il est déjà attribué.

    `requires_second_pseudo` n'est OBLIGATOIRE que si le membre a déjà un
    grade (Paul, 2026-08-23, retour utilisateur) : le cas d'usage réel est
    un membre du STAFF qui est *aussi* builder avec un second compte dédié
    (pseudo différent de son pseudo staff) — c'est ce second pseudo qui a
    besoin d'être distingué. Pour un membre SANS grade (builder non-staff),
    son pseudo IG habituel (`pseudo_jeu`) EST déjà son pseudo builder : lui
    imposer un second champ en plus n'a pas de sens et n'était qu'une gêne.
    `second_pseudo`, si fourni quand même, reste enregistré normalement.
    """
    statut_def = await get_statut_def(server, key)
    if statut_def is None:
        raise NGStatutError(f"Le statut `{key}` n'existe pas pour ce serveur.", warning=True)

    if statut_def["requires_second_pseudo"]:
        # Import local : évite un cycle avec ng_staff_manager (qui importe
        # déjà ce module pour enrichir ses membres en "statuts").
        from utils.managers.ng_staff_manager import get_staff_member as _get_staff_member
        member = await _get_staff_member(server, discord_id)
        has_grade = bool(member and member.get("grade"))
        if has_grade and not (second_pseudo and second_pseudo.strip()):
            raise NGStatutError(
                f"Le statut **{statut_def['label']}** nécessite un pseudo secondaire "
                "(`pseudo_jeu_builder` / second compte dédié) pour un membre du **staff** "
                "— pas pour un membre sans grade, dont le pseudo IG suffit déjà.",
            )

    async with _lock:
        async with get_session() as session:
            existing = await session.scalar(
                select(NGStaffStatut).where(
                    NGStaffStatut.discord_id == discord_id,
                    NGStaffStatut.statut_def_id == statut_def["id"],
                )
            )
            if existing is not None:
                raise NGStatutError(f"Ce membre a déjà le statut **{statut_def['label']}**.", warning=True)

            row = NGStaffStatut(
                server=server, discord_id=discord_id, statut_def_id=statut_def["id"],
                second_pseudo=second_pseudo.strip() if second_pseudo else None,
            )
            session.add(row)
            await session.flush()
            result = row.to_dict()

    # 🔄 Voir update_statut_def : ng_staff_manager met en cache une copie de
    # "statuts" par membre — sans cette invalidation, le statut fraîchement
    # accordé resterait invisible jusqu'à 60s dans list_staff/get_staff_member
    # (stafflist, dashboard d'édition, /ngstaff rank suivant...).
    from utils.managers.ng_staff_manager import invalidate_cache as _invalidate_staff_cache
    _invalidate_staff_cache(server)

    log.info("[NG STATUT] %s : statut %s accordé à discord_id=%s", server, key, discord_id)
    return result


async def revoke_statut(server: str, discord_id: int, key: str) -> bool:
    """Retire un statut à un membre. Retourne False si le membre ne l'avait pas."""
    statut_def = await get_statut_def(server, key)
    if statut_def is None:
        return False

    async with _lock:
        async with get_session() as session:
            result = await session.execute(
                delete(NGStaffStatut).where(
                    NGStaffStatut.discord_id == discord_id,
                    NGStaffStatut.statut_def_id == statut_def["id"],
                )
            )
            revoked = result.rowcount > 0

    if revoked:
        from utils.managers.ng_staff_manager import invalidate_cache as _invalidate_staff_cache
        _invalidate_staff_cache(server)
        log.info("[NG STATUT] %s : statut %s retiré à discord_id=%s", server, key, discord_id)
    return revoked


async def revoke_all_statuts(server: str, discord_id: int) -> int:
    """Retire TOUS les statuts d'un membre (derank complet). Retourne le nombre retiré."""
    async with _lock:
        async with get_session() as session:
            def_ids = (await session.execute(
                select(NGStatutDef.id).where(NGStatutDef.server == server)
            )).scalars().all()
            if not def_ids:
                return 0
            result = await session.execute(
                delete(NGStaffStatut).where(
                    NGStaffStatut.discord_id == discord_id,
                    NGStaffStatut.statut_def_id.in_(def_ids),
                )
            )

    if result.rowcount:
        from utils.managers.ng_staff_manager import invalidate_cache as _invalidate_staff_cache
        _invalidate_staff_cache(server)
    return result.rowcount