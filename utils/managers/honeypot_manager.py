"""
utils/managers/honeypot_manager.py — Config du système HoneyPot / "Piège".

Ne contient QUE la persistance (config par serveur + liste d'exemptions) —
la création/suppression du salon Discord et l'envoi du message d'avertissement
vivent dans views/mod/piege_config_view.py (comme
views/join_to_create/join_to_create_config_view.py sépare déjà persistance
et appels Discord). La réaction au déclenchement (kick + purge) vit dans
cogs/events/honeypot_listener.py, qui réutilise directement
utils.managers.mod_sanction_manager.kick (alimente /mod historique sans
plomberie supplémentaire) et utils.managers.mod_clear_manager.clear_messages.

Cache simple par guild_id, invalidé à l'écriture — même pattern que
utils.managers.join_to_create_manager (avant son évolution multi-lignes) et
utils.managers.mod_automod_nolink_manager.
"""
from __future__ import annotations

from utils.db.models.honeypot import HoneypotConfig
from utils.db.session import get_session

DEFAULT_CONFIG: dict = {
    "channel_id": None,
    "enabled": False,
    "ignored_role_ids": [],
    "ignored_member_ids": [],
}

_config_cache: dict[int, dict] = {}


def _invalidate(guild_id: int) -> None:
    _config_cache.pop(guild_id, None)


async def load_config(guild_id: int) -> dict:
    if guild_id in _config_cache:
        return _config_cache[guild_id].copy()

    async with get_session() as session:
        row = await session.get(HoneypotConfig, guild_id)
        cfg = row.to_dict() if row is not None else {**DEFAULT_CONFIG, "guild_id": guild_id}

    _config_cache[guild_id] = cfg
    return cfg.copy()


async def save_config(guild_id: int, partial: dict) -> dict:
    allowed = set(DEFAULT_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with get_session() as session:
        row = await session.get(HoneypotConfig, guild_id)
        if row is None:
            merged = {**DEFAULT_CONFIG, **clean}
            row = HoneypotConfig(guild_id=guild_id, **merged)
            session.add(row)
        else:
            for key, value in clean.items():
                setattr(row, key, value)
        await session.flush()
        result = row.to_dict()

    _config_cache[guild_id] = result
    return result.copy()


async def set_channel(guild_id: int, channel_id: int | None) -> dict:
    """Enregistre (ou efface, si None) le salon-piège. N'active PAS enabled
    automatiquement ni ne le désactive — l'appelant (view) décide, cf.
    _cb_create_channel / _cb_delete_channel."""
    return await save_config(guild_id, {"channel_id": channel_id})


async def set_enabled(guild_id: int, enabled: bool) -> dict:
    return await save_config(guild_id, {"enabled": enabled})


# ============================================================
# 🚫 Exemptions (rôles + membres ignorés par le piège)
# ============================================================

async def add_ignored_role(guild_id: int, role_id: int) -> dict:
    cfg = await load_config(guild_id)
    roles = list(cfg["ignored_role_ids"])
    if role_id not in roles:
        roles.append(role_id)
    return await save_config(guild_id, {"ignored_role_ids": roles})


async def remove_ignored_role(guild_id: int, role_id: int) -> dict:
    cfg = await load_config(guild_id)
    roles = [r for r in cfg["ignored_role_ids"] if r != role_id]
    return await save_config(guild_id, {"ignored_role_ids": roles})


async def add_ignored_member(guild_id: int, member_id: int) -> dict:
    cfg = await load_config(guild_id)
    members = list(cfg["ignored_member_ids"])
    if member_id not in members:
        members.append(member_id)
    return await save_config(guild_id, {"ignored_member_ids": members})


async def remove_ignored_member(guild_id: int, member_id: int) -> dict:
    cfg = await load_config(guild_id)
    members = [m for m in cfg["ignored_member_ids"] if m != member_id]
    return await save_config(guild_id, {"ignored_member_ids": members})


def is_ignored(cfg: dict, member) -> bool:
    """True si `member` (discord.Member) est exempté du piège par la config
    déjà chargée — rôle OU id membre dans les listes d'exemption. Prend
    `cfg` déjà chargé (pas guild_id) : appelé sur le chemin on_message,
    load_config() est déjà fait une fois par l'appelant (cf. listener)."""
    if member.id in cfg["ignored_member_ids"]:
        return True
    member_role_ids = {r.id for r in getattr(member, "roles", [])}
    return bool(member_role_ids & set(cfg["ignored_role_ids"]))
