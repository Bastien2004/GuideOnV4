"""
utils/managers/mod_permission_manager.py — Gestion des permissions des commandes /mod.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from sqlalchemy import delete, select

from utils.db.models.mod_permission import ModPermissionRole
from utils.db.session import get_session

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60


@dataclass(frozen=True)
class PermissionKey:
    """Gestion des permissions."""

    key: str
    label: str
    description: str
    category: str


# ============================================================
# 🔑 Registre des clés de permission
# ============================================================

PERMISSION_KEYS: list[PermissionKey] = [
    # ---- Actions : sanctions ----
    PermissionKey("mod_warn", "Warn", "Donner un avertissement à un membre.", "action"),
    PermissionKey("mod_mute", "Mute", "Rendre un membre muet temporairement.", "action"),
    PermissionKey("mod_unmute", "Unmute", "Lever le mute d'un membre avant son expiration.", "action"),
    PermissionKey("mod_kick", "Kick", "Expulser un membre du serveur.", "action"),
    PermissionKey("mod_ban", "Ban)", "Bannir définitivement un membre du serveur.", "action"),
    PermissionKey("mod_tempban", "Tempban", "Bannir un membre pour une durée déterminée.", "action"),
    PermissionKey("mod_unban", "Unban", "Révoquer un bannissement.", "action"),
    PermissionKey("mod_softban", "Softban", "Bannir un membre en supprimant ses derniers messages.", "action"),
    PermissionKey("mod_historique", "Historique", "Consulter l'historique des sanctions d'un membre.", "action"),
    PermissionKey("mod_rename", "Rename", "Modifier le pseudo d'un membre.", "action"),

    # ---- Actions : outils ponctuels ----
    PermissionKey("mod_clear", "Clear", "Supprimer des messages en masse dans un salon.", "action"),
    PermissionKey("mod_lock", "Lock / Unlock", "Verrouiller ou déverrouiller un salon textuel.", "action"),
    PermissionKey("mod_voice_manage", "Gestion vocale", "Mute/déplacer/expulser tous les membres d'un vocal.", "action"),

    # ---- Config : panneaux ----
    PermissionKey("config_sanctions", "Config. sanctions", "Réglages du système de sanctions.", "config"),
    PermissionKey("config_logs", "Config. logs", "Configuration du système de logs.", "config"),
]

_KEYS_BY_ID: dict[str, PermissionKey] = {pk.key: pk for pk in PERMISSION_KEYS}

_cache: dict[tuple[int, str], tuple[list[int], float]] = {}


def get_permission_key(key: str) -> PermissionKey | None:
    """Retourne la définition d'une clé de permission, None si inconnue."""
    return _KEYS_BY_ID.get(key)


def keys_by_category(category: str) -> list[PermissionKey]:
    """Toutes les clés d'une catégorie ("action" ou "config")."""
    return [pk for pk in PERMISSION_KEYS if pk.category == category]


# ============================================================
# 📖 Lecture
# ============================================================

async def get_roles(guild_id: int, key: str) -> list[int]:
    """Rôles Discord assignés à une clé de permission sur un serveur (cache 60s)."""
    cache_key = (guild_id, key)
    cached = _cache.get(cache_key)
    now = time.monotonic()
    if cached is not None and (now - cached[1]) < CACHE_TTL_SECONDS:
        return list(cached[0])

    async with get_session() as session:
        rows = (
            await session.execute(
                select(ModPermissionRole.role_id).where(
                    ModPermissionRole.guild_id == guild_id,
                    ModPermissionRole.permission_key == key,
                )
            )
        ).scalars().all()

    role_ids = list(rows)
    _cache[cache_key] = (role_ids, now)
    return role_ids


async def get_all_for_guild(guild_id: int) -> dict[str, list[int]]:
    """{permission_key: [role_id, ...]} pour toutes les clés connues d'un serveur."""
    async with get_session() as session:
        rows = (
            await session.execute(
                select(ModPermissionRole.permission_key, ModPermissionRole.role_id).where(
                    ModPermissionRole.guild_id == guild_id
                )
            )
        ).all()

    out: dict[str, list[int]] = {pk.key: [] for pk in PERMISSION_KEYS}
    for key, role_id in rows:
        out.setdefault(key, []).append(role_id)
    return out


# ============================================================
# ✍️ Écriture
# ============================================================

async def set_roles(guild_id: int, key: str, role_ids: list[int]) -> list[int]:
    """Remplace l'ensemble des rôles autorisés pour une (guild_id, clé) donnée."""
    deduped = list(dict.fromkeys(role_ids))

    async with get_session() as session:
        await session.execute(
            delete(ModPermissionRole).where(
                ModPermissionRole.guild_id == guild_id,
                ModPermissionRole.permission_key == key,
            )
        )
        for role_id in deduped:
            session.add(ModPermissionRole(guild_id=guild_id, permission_key=key, role_id=role_id))

    _cache[(guild_id, key)] = (deduped, time.monotonic())
    log.info("[MOD_PERM] Rôles mis à jour guild=%s clé=%s -> %s", guild_id, key, deduped)
    return deduped


async def clear_roles(guild_id: int, key: str) -> None:
    """Retire tous les rôles d'une clé (retour au deny-by-default : admin only)."""
    await set_roles(guild_id, key, [])


# ============================================================
# 🛡️ Vérification
# ============================================================

async def has_permission(member, key: str) -> bool:
    """
    True si `member` (discord.Member) peut utiliser la commande/le panneau
    identifié par `key`. Un Administrateur Discord passe toujours. Sinon,
    True si le membre a au moins un des rôles assignés à cette clé pour son
    serveur. Deny-by-default : si aucun rôle n'est configuré pour cette clé,
    seul un Administrateur peut l'utiliser.
    """
    if member.guild_permissions.administrator:
        return True

    allowed_role_ids = await get_roles(member.guild.id, key)
    if not allowed_role_ids:
        return False

    member_role_ids = {role.id for role in member.roles}
    return any(role_id in member_role_ids for role_id in allowed_role_ids)