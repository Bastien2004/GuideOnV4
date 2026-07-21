"""
utils/managers/mod_permission_manager.py — Permissions granulaires /mod.

Chaque commande ou panneau de configuration de moderation est identifie par
une cle de permission (PERMISSION_KEYS ci-dessous). Un serveur assigne un ou
plusieurs roles Discord a chaque cle via /mod permissions. Tant qu'aucun role
n'est assigne a une cle, seul un Administrateur Discord peut l'utiliser
(deny-by-default — verifie par utils.perm_mod.check_mod_permission, pas ici).

La liste PERMISSION_KEYS s'enrichit au fil des vagues de construction du
systeme de moderation : chaque nouvelle commande /mod ajoute sa propre cle.
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
    """Une clé de permission /mod : une commande ou un panneau de config."""

    key: str
    label: str
    description: str
    category: str  # "action" | "config"


# ============================================================
# 🔑 Registre des clés de permission
# ============================================================
# Vague 1a (permissions + sanctions + historique + outils ponctuels).
# D'autres clés seront ajoutées au fil des vagues suivantes.

PERMISSION_KEYS: list[PermissionKey] = [
    # ---- Actions : sanctions ----
    PermissionKey("mod_warn", "Avertir (warn)", "Donner un avertissement à un membre.", "action"),
    PermissionKey("mod_mute", "Rendre muet (mute)", "Rendre un membre muet temporairement.", "action"),
    PermissionKey("mod_kick", "Expulser (kick)", "Expulser un membre du serveur.", "action"),
    PermissionKey("mod_ban", "Bannir (ban)", "Bannir un membre du serveur.", "action"),
    PermissionKey("mod_softban", "Softban", "Bannir puis débannir immédiatement (purge messages).", "action"),
    PermissionKey("mod_sanction_revoke", "Révoquer une sanction", "Annuler une sanction active (unmute, unban...).", "action"),
    PermissionKey("mod_historique", "Voir l'historique", "Consulter le casier judiciaire d'un membre.", "action"),
    # ---- Actions : outils ponctuels ----
    PermissionKey("mod_clear", "Clear", "Supprimer des messages en masse dans un salon.", "action"),
    PermissionKey("mod_lock", "Lock / Unlock salon", "Verrouiller ou déverrouiller un salon textuel.", "action"),
    PermissionKey("mod_voice_manage", "Gestion vocale de masse", "Mute/déplacer/expulser tous les membres d'un vocal.", "action"),
    # ---- Config : panneaux ----
    # NB : /mod permissions (ce panneau lui-même) N'A PAS de clé ici — il reste
    # verrouillé sur Administrateur Discord en dur (utils.perm_admin.check_admin),
    # jamais délégable via lui-même. Sinon un rôle non-admin pourrait s'auto-
    # accorder n'importe quelle autre permission (escalade de privilège).
    PermissionKey("config_sanctions", "Config. sanctions", "Réglages généraux du système de sanctions.", "config"),
    PermissionKey("config_logs", "Config. logs", "Réglages des salons de logs (chercheur/expert/espion).", "config"),
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
    deduped = list(dict.fromkeys(role_ids))  # dédoublonne en préservant l'ordre

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
