"""
utils/managers/mod_sanction_manager.py — Sanctions de modération.

Gère à la fois la mutation Discord (timeout/kick/ban/unban) et la
persistance DB (table mod_sanctions) pour warn/mute/kick/ban/tempban/
softban. Les cogs délèguent ici, puis mappent SanctionError vers
error_container/warning_container.

Historique 100% consultatif : get_user_history/get_user_stats ne font
que lire, jamais déclencher d'action.

Mute : timeout natif Discord (member.timeout), borné par la limite dure
de Discord (28 jours). Ban : bannissement permanent, sans purge par
défaut. Softban : bannissement permanent AVEC purge des messages
récents à la création — contrairement à un "vrai" softban classique, il
n'y a PAS de débannissement automatique ensuite (débanni uniquement via
/mod unban, comme un ban normal). Tempban : ban temporaire, expiration
traitée par cogs/events/mod_tempban_scheduler.py (boucle périodique).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import discord
from sqlalchemy import select

from utils.db.models.mod_sanction import (
    DEFAULT_SOFTBAN_PURGE_SECONDS,
    ModSanctionConfig,
    Sanction,
    SanctionType,
)
from utils.db.session import get_session
from utils.id_sanction import sanction_id

log = logging.getLogger(__name__)

# ============================================================
# 🔒 Bornes de sécurité
# ============================================================

MIN_REASON_LENGTH = 3
MAX_REASON_LENGTH = 500

MIN_MUTE_SECONDS = 60
MAX_MUTE_SECONDS = 2_419_200  # 28 jours — limite dure de Discord

MIN_TEMPBAN_SECONDS = 3_600
MAX_TEMPBAN_SECONDS = 31_536_000

MIN_SOFTBAN_PURGE_SECONDS = 0
MAX_SOFTBAN_PURGE_SECONDS = 604_800  # 7 jours — limite dure de l'API Discord


SANCTION_LABELS: dict[SanctionType, tuple[str, str]] = {
    SanctionType.WARN: ("⚠️", "Avertissement"),
    SanctionType.MUTE: ("🔇", "Mute"),
    SanctionType.KICK: ("👢", "Expulsion"),
    SanctionType.BAN: ("🔨", "Bannissement"),
    SanctionType.TEMPBAN: ("⏳", "Bannissement temporaire"),
    SanctionType.SOFTBAN: ("🧹", "Softban"),
}


class SanctionError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime) -> datetime:
    """Traite un datetime naïf comme UTC (SQLite ne persiste pas toujours la tz)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _validate_reason(reason: str) -> str:
    reason = reason.strip()
    if len(reason) < MIN_REASON_LENGTH:
        raise SanctionError(f"La raison doit contenir au moins **{MIN_REASON_LENGTH} caractères**.", warning=True)
    if len(reason) > MAX_REASON_LENGTH:
        raise SanctionError(f"La raison doit contenir au maximum **{MAX_REASON_LENGTH} caractères**.", warning=True)
    return reason


def _validate_mute_duration(duration_seconds: int) -> int:
    if duration_seconds < MIN_MUTE_SECONDS or duration_seconds > MAX_MUTE_SECONDS:
        raise SanctionError(
            f"La durée du mute doit être entre **{MIN_MUTE_SECONDS}s** et **{MAX_MUTE_SECONDS}s**.", warning=True,
        )
    return duration_seconds


def _validate_tempban_duration(duration_seconds: int) -> int:
    if duration_seconds < MIN_TEMPBAN_SECONDS or duration_seconds > MAX_TEMPBAN_SECONDS:
        raise SanctionError(
            f"La durée du tempban doit être entre **{MIN_TEMPBAN_SECONDS}s** et **{MAX_TEMPBAN_SECONDS}s**.",
            warning=True,
        )
    return duration_seconds


# ============================================================
# 💾 Persistance
# ============================================================

async def _persist_sanction(
    *,
    guild_id: int,
    user_id: int,
    moderator_id: int,
    type_: SanctionType,
    reason: str,
    duration_seconds: int | None = None,
    expires_at: datetime | None = None,
    dm_sent: bool = False,
) -> dict:
    """Insère une nouvelle sanction en DB avec un id court unique."""
    async with get_session() as session:
        new_id = sanction_id()
        for _ in range(5):
            if await session.get(Sanction, new_id) is None:
                break
            new_id = sanction_id()
        else:
            raise SanctionError("Impossible de générer un identifiant de sanction unique, réessayez.")

        row = Sanction(
            id=new_id,
            guild_id=guild_id,
            user_id=user_id,
            moderator_id=moderator_id,
            type=type_,
            reason=reason,
            duration_seconds=duration_seconds,
            expires_at=expires_at,
            active=(type_ in (SanctionType.MUTE, SanctionType.BAN, SanctionType.TEMPBAN, SanctionType.SOFTBAN)),
            dm_sent=dm_sent,
        )
        session.add(row)
        await session.flush()
        result = row.to_dict()

    log.info(
        "[MOD_SANCTION] %s créée id=%s guild=%s user=%s moderator=%s",
        type_.value, result["id"], guild_id, user_id, moderator_id,
    )
    return result


async def revoke_sanction(sanction_id_: str, revoked_by: int, revoked_reason: str | None = None) -> dict:
    """Marque une sanction comme révoquée (partie DB de unwarn/unmute/unban)."""
    async with get_session() as session:
        row = await session.get(Sanction, sanction_id_)
        if row is None:
            raise SanctionError("Sanction introuvable.", warning=True)
        if row.revoked_at is not None:
            raise SanctionError("Cette sanction a déjà été révoquée.", warning=True)

        row.active = False
        row.revoked_at = _utcnow()
        row.revoked_by = revoked_by
        row.revoked_reason = revoked_reason
        await session.flush()
        result = row.to_dict()

    log.info("[MOD_SANCTION] Révoquée id=%s par=%s", sanction_id_, revoked_by)
    return result


# ============================================================
# ⚖️ Sanctions
# ============================================================

async def warn(guild_id: int, user_id: int, moderator_id: int, reason: str, *, dm_sent: bool = False) -> dict:
    """Application d'un warn."""
    reason = _validate_reason(reason)
    return await _persist_sanction(
        guild_id=guild_id, user_id=user_id, moderator_id=moderator_id,
        type_=SanctionType.WARN, reason=reason, dm_sent=dm_sent,
    )


async def unwarn(sanction_id_: str, moderator_id: int, reason: str | None = None) -> dict:
    """Révoque un warn précis par son ID (un membre peut avoir plusieurs warns)."""
    existing = await get_sanction(sanction_id_)
    if existing is None or existing["type"] != SanctionType.WARN.value:
        raise SanctionError("Aucun **warn** ne correspond à cet identifiant.", warning=True)
    return await revoke_sanction(sanction_id_, moderator_id, reason)


async def mute(
    guild_id: int, member: discord.Member, moderator_id: int, reason: str, duration_seconds: int,
    *, dm_sent: bool = False,
) -> dict:
    """Mute via timeout natif Discord (max 28 jours)."""
    reason = _validate_reason(reason)
    duration_seconds = _validate_mute_duration(duration_seconds)
    expires_at = _utcnow() + timedelta(seconds=duration_seconds)

    try:
        await member.timeout(expires_at, reason=reason)
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission de rendre ce membre **muet** (rôle trop haut).") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec timeout guild=%s user=%s", guild_id, member.id)
        raise SanctionError("Erreur Discord lors du **mute**.") from None

    return await _persist_sanction(
        guild_id=guild_id, user_id=member.id, moderator_id=moderator_id,
        type_=SanctionType.MUTE, reason=reason, duration_seconds=duration_seconds,
        expires_at=expires_at, dm_sent=dm_sent,
    )


async def unmute(member: discord.Member, moderator_id: int, reason: str | None = None) -> dict:
    """Lève le mute (timeout) d'un membre avant son expiration naturelle."""
    active = await get_active_mute_sanction(member.guild.id, member.id)
    if active is None:
        raise SanctionError("Ce membre n'a aucun **mute actif**.", warning=True)

    try:
        await member.timeout(None, reason=reason or "Levée de mute anticipée")
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission de **démuter** ce membre.") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec unmute guild=%s user=%s", member.guild.id, member.id)
        raise SanctionError("Erreur Discord lors de la levée du **mute**.") from None

    return await revoke_sanction(active["id"], moderator_id, reason)


async def kick(guild_id: int, member: discord.Member, moderator_id: int, reason: str, *, dm_sent: bool = False) -> dict:
    """Expulsion simple."""
    reason = _validate_reason(reason)

    try:
        await member.kick(reason=reason)
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission d'**expulser** ce membre.") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec kick guild=%s user=%s", guild_id, member.id)
        raise SanctionError("Erreur Discord lors de l'**expulsion**.") from None

    return await _persist_sanction(
        guild_id=guild_id, user_id=member.id, moderator_id=moderator_id,
        type_=SanctionType.KICK, reason=reason, dm_sent=dm_sent,
    )


async def ban(
    guild: discord.Guild, target: discord.abc.Snowflake, moderator_id: int, reason: str,
    *, dm_sent: bool = False, delete_message_seconds: int = 0,
) -> dict:
    """Bannissement permanent, sans purge de messages par défaut."""
    reason = _validate_reason(reason)
    if delete_message_seconds < MIN_SOFTBAN_PURGE_SECONDS or delete_message_seconds > MAX_SOFTBAN_PURGE_SECONDS:
        raise SanctionError(
            f"La purge de messages doit être entre **0** et **{MAX_SOFTBAN_PURGE_SECONDS}s** (7 jours).",
            warning=True,
        )

    try:
        await guild.ban(target, reason=reason, delete_message_seconds=delete_message_seconds)
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission de **bannir** ce membre.") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec ban guild=%s user=%s", guild.id, target.id)
        raise SanctionError("Erreur Discord lors du **ban**.") from None

    return await _persist_sanction(
        guild_id=guild.id, user_id=target.id, moderator_id=moderator_id,
        type_=SanctionType.BAN, reason=reason, dm_sent=dm_sent,
    )


async def tempban(
    guild: discord.Guild, target: discord.abc.Snowflake, moderator_id: int, reason: str, duration_seconds: int,
    *, dm_sent: bool = False,
) -> dict:
    """Ban temporaire — levé automatiquement par cogs/events/mod_tempban_scheduler.py."""
    reason = _validate_reason(reason)
    duration_seconds = _validate_tempban_duration(duration_seconds)
    expires_at = _utcnow() + timedelta(seconds=duration_seconds)

    try:
        await guild.ban(target, reason=reason, delete_message_seconds=0)
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission de **bannir** ce membre.") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec tempban guild=%s user=%s", guild.id, target.id)
        raise SanctionError("Erreur Discord lors du **tempban**.") from None

    return await _persist_sanction(
        guild_id=guild.id, user_id=target.id, moderator_id=moderator_id,
        type_=SanctionType.TEMPBAN, reason=reason, duration_seconds=duration_seconds,
        expires_at=expires_at, dm_sent=dm_sent,
    )


async def unban(guild: discord.Guild, user_id: int, moderator_id: int, reason: str | None = None) -> dict:
    """Lève un ban (permanent, softban ou temporaire) avant son expiration naturelle."""
    active = await get_active_ban_sanction(guild.id, user_id)
    if active is None:
        raise SanctionError("Ce membre n'a aucun **ban actif** enregistré par ce système.", warning=True)

    try:
        await guild.unban(discord.Object(id=user_id), reason=reason or "Levée de ban anticipée")
    except discord.NotFound:
        log.warning("[MOD_SANCTION] unban: ban déjà absent côté Discord (guild=%s user=%s)", guild.id, user_id)
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission de **débannir**.") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec unban guild=%s user=%s", guild.id, user_id)
        raise SanctionError("Erreur Discord lors du **débannissement**.") from None

    return await revoke_sanction(active["id"], moderator_id, reason)


async def softban(
    guild: discord.Guild, member: discord.Member, moderator_id: int, reason: str,
    *, dm_sent: bool = False, purge_seconds: int | None = None,
) -> dict:
    """
    Bannissement permanent AVEC purge des messages récents à la création.

    Contrairement à un softban "classique", le membre n'est PAS débanni
    ensuite : c'est un ban permanent comme `ban()`, seule la purge de
    messages à la création le distingue. Levée uniquement via /mod unban.
    """
    reason = _validate_reason(reason)

    if purge_seconds is None:
        cfg = await load_sanction_config(guild.id)
        purge_seconds = cfg["softban_purge_seconds"]
    if purge_seconds < MIN_SOFTBAN_PURGE_SECONDS or purge_seconds > MAX_SOFTBAN_PURGE_SECONDS:
        raise SanctionError(
            f"La purge de messages doit être entre **0** et **{MAX_SOFTBAN_PURGE_SECONDS}s** (7 jours).",
            warning=True,
        )

    try:
        await guild.ban(member, reason=reason, delete_message_seconds=purge_seconds)
    except discord.Forbidden:
        raise SanctionError("Le bot n'a pas la permission d'effectuer un **softban**.") from None
    except discord.HTTPException:
        log.exception("[MOD_SANCTION] Échec softban guild=%s user=%s", guild.id, member.id)
        raise SanctionError("Erreur Discord lors du **softban**.") from None

    return await _persist_sanction(
        guild_id=guild.id, user_id=member.id, moderator_id=moderator_id,
        type_=SanctionType.SOFTBAN, reason=reason, dm_sent=dm_sent,
    )


# ============================================================
# 📖 Lecture — historique / casier judiciaire
# ============================================================

async def get_sanction(sanction_id_: str) -> dict | None:
    async with get_session() as session:
        row = await session.get(Sanction, sanction_id_)
        return row.to_dict() if row is not None else None


async def get_user_history(guild_id: int, user_id: int, limit: int = 100) -> list[dict]:
    """Historique complet d'un membre, du plus récent au plus ancien."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Sanction)
                .where(Sanction.guild_id == guild_id, Sanction.user_id == user_id)
                .order_by(Sanction.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return [r.to_dict() for r in rows]


async def get_user_stats(guild_id: int, user_id: int) -> dict:
    """Compteur par type de sanction pour un membre (résumé du casier)."""
    history = await get_user_history(guild_id, user_id, limit=10_000)
    stats = {t.value: 0 for t in SanctionType}
    for entry in history:
        stats[entry["type"]] += 1
    return stats


async def get_active_mute_sanction(guild_id: int, user_id: int) -> dict | None:
    """Mute actif et non-expiré d'un membre, None sinon."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Sanction).where(
                    Sanction.guild_id == guild_id,
                    Sanction.user_id == user_id,
                    Sanction.type == SanctionType.MUTE,
                    Sanction.active.is_(True),
                ).order_by(Sanction.created_at.desc())
            )
        ).scalars().all()

    now = _utcnow()
    for row in rows:
        if row.expires_at is not None and _as_aware(row.expires_at) > now:
            return row.to_dict()
    return None


async def get_active_ban_sanction(guild_id: int, user_id: int) -> dict | None:
    """Ban actif (permanent, softban ou temporaire non-expiré) d'un membre, None sinon."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Sanction).where(
                    Sanction.guild_id == guild_id,
                    Sanction.user_id == user_id,
                    Sanction.type.in_((SanctionType.BAN, SanctionType.SOFTBAN, SanctionType.TEMPBAN)),
                    Sanction.active.is_(True),
                ).order_by(Sanction.created_at.desc())
            )
        ).scalars().all()

    now = _utcnow()
    for row in rows:
        if row.type in (SanctionType.BAN, SanctionType.SOFTBAN):
            return row.to_dict()
        if row.expires_at is not None and _as_aware(row.expires_at) > now:
            return row.to_dict()
    return None


# ============================================================
# 📋 Listes serveur — sélection dans les interfaces (unmute/unwarn)
# ============================================================

async def get_active_mutes(guild_id: int) -> list[dict]:
    """Mutes actifs et non-expirés de tout le serveur (liste pour /mod unmute)."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Sanction).where(
                    Sanction.guild_id == guild_id,
                    Sanction.type == SanctionType.MUTE,
                    Sanction.active.is_(True),
                ).order_by(Sanction.created_at.desc())
            )
        ).scalars().all()

    now = _utcnow()
    return [r.to_dict() for r in rows if r.expires_at is not None and _as_aware(r.expires_at) > now]


async def get_active_warns(guild_id: int) -> list[dict]:
    """Warns actifs (non révoqués) de tout le serveur (liste pour /mod unwarn)."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Sanction).where(
                    Sanction.guild_id == guild_id,
                    Sanction.type == SanctionType.WARN,
                    Sanction.revoked_at.is_(None),
                ).order_by(Sanction.created_at.desc())
            )
        ).scalars().all()
    return [r.to_dict() for r in rows]


# ============================================================
# ⏰ Scheduler tempban (cogs/events/mod_tempban_scheduler.py)
# ============================================================

async def get_due_tempbans() -> list[dict]:
    """Tempbans actifs dont l'expiration est dépassée."""
    now = _utcnow()
    async with get_session() as session:
        rows = (
            await session.execute(
                select(Sanction).where(
                    Sanction.type == SanctionType.TEMPBAN,
                    Sanction.active.is_(True),
                )
            )
        ).scalars().all()
    return [r.to_dict() for r in rows if r.expires_at is not None and _as_aware(r.expires_at) <= now]


async def mark_tempban_expired(sanction_id_: str) -> None:
    """Marque un tempban comme terminé (expiration naturelle, pas une révocation staff)."""
    async with get_session() as session:
        row = await session.get(Sanction, sanction_id_)
        if row is not None and row.active:
            row.active = False
            await session.flush()
    log.info("[MOD_SANCTION] Tempban expiré id=%s", sanction_id_)


# ============================================================
# ⚙️ Config sanctions (par serveur)
# ============================================================

DEFAULT_SANCTION_CONFIG: dict = {"softban_purge_seconds": DEFAULT_SOFTBAN_PURGE_SECONDS}

_config_cache: dict[int, dict] = {}


async def load_sanction_config(guild_id: int) -> dict:
    if guild_id in _config_cache:
        return _config_cache[guild_id].copy()

    async with get_session() as session:
        row = await session.get(ModSanctionConfig, guild_id)
        cfg = row.to_dict() if row is not None else DEFAULT_SANCTION_CONFIG.copy()

    _config_cache[guild_id] = cfg
    return cfg.copy()


async def save_sanction_config(guild_id: int, partial: dict) -> dict:
    allowed = set(DEFAULT_SANCTION_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    if "softban_purge_seconds" in clean:
        value = clean["softban_purge_seconds"]
        if value < MIN_SOFTBAN_PURGE_SECONDS or value > MAX_SOFTBAN_PURGE_SECONDS:
            raise SanctionError(
                f"La purge de messages doit être entre **0** et **{MAX_SOFTBAN_PURGE_SECONDS}s** (7 jours).",
                warning=True,
            )

    async with get_session() as session:
        row = await session.get(ModSanctionConfig, guild_id)
        if row is None:
            merged = {**DEFAULT_SANCTION_CONFIG, **clean}
            row = ModSanctionConfig(guild_id=guild_id, **merged)
            session.add(row)
        else:
            for key, value in clean.items():
                setattr(row, key, value)
        await session.flush()
        result = row.to_dict()

    _config_cache[guild_id] = result
    return result.copy()