"""
utils/managers/mod_channel_lock_manager.py — Verrouillage/déverrouillage d'un salon textuel.

Action de modération ponctuelle (comme mod_clear/mod_voice_manage) : pas de
sanction enregistrée, seulement un log via utils.managers.mod_log_manager.log_channel_action.

Fournit deux opérations distinctes (/mod lock et /mod unlock) qui, en plus de
modifier la permission send_messages pour @everyone :
  - préfixent (lock) / retirent (unlock) un emoji cadenas dans le nom du salon
  - postent un message d'annonce dans le salon lui-même
"""
from __future__ import annotations

import discord

LOCK_EMOJI = "🔒"
UNLOCK_EMOJI = "🔓"


class LockError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


# ============================================================
# 🔍 Lecture d'état
# ============================================================

def is_locked(channel: discord.TextChannel) -> bool:
    """True si @everyone n'a plus la permission d'envoyer des messages dans ce salon."""
    overwrite = channel.overwrites_for(channel.guild.default_role)
    return overwrite.send_messages is False


def _has_lock_prefix(name: str) -> bool:
    return name.startswith(LOCK_EMOJI)


def _add_lock_prefix(name: str) -> str:
    """Ajoute 🔒 en début de nom si absent. Discord limite à 100 caractères."""
    if _has_lock_prefix(name):
        return name
    return (LOCK_EMOJI + name)[:100]


def _remove_lock_prefix(name: str) -> str:
    """Retire 🔒 (et un éventuel séparateur simple) en début de nom si présent."""
    if not _has_lock_prefix(name):
        return name
    return name[len(LOCK_EMOJI):]


# ============================================================
# 🔒 Lock
# ============================================================

async def lock_channel(
    channel: discord.TextChannel,
    moderator: discord.Member,
    *,
    reason: str | None = None,
) -> None:
    """
    Verrouille le salon pour @everyone, préfixe son nom avec 🔒 et poste
    un message d'annonce dans le salon.

    Chaque étape est isolée : un échec sur le rename ou l'annonce n'annule pas
    le verrouillage effectif (source de vérité = permission send_messages).
    """
    if is_locked(channel):
        raise LockError("Ce salon est déjà **verrouillé**.", warning=True)

    everyone = channel.guild.default_role
    overwrite = channel.overwrites_for(everyone)
    overwrite.send_messages = False

    audit_reason = f"/mod lock par {moderator} — {reason}" if reason else f"/mod lock par {moderator}"

    # 1. La permission — c'est ce qui compte vraiment.
    try:
        await channel.set_permissions(everyone, overwrite=overwrite, reason=audit_reason)
    except discord.Forbidden as exc:
        raise LockError("Le bot n'a pas la permission de modifier ce salon.") from exc
    except discord.HTTPException as exc:
        raise LockError("Une erreur Discord est survenue pendant le verrouillage.") from exc

    # 2. Rename cosmétique — best-effort.
    try:
        new_name = _add_lock_prefix(channel.name)
        if new_name != channel.name:
            await channel.edit(name=new_name, reason=audit_reason)
    except (discord.Forbidden, discord.HTTPException):
        pass

    # 3. Annonce publique — best-effort.
    try:
        await channel.send(
            f"🔒 **Salon verrouillé** par {moderator.mention}"
            + (f"\n> {reason}" if reason else ""),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except (discord.Forbidden, discord.HTTPException):
        pass


# ============================================================
# 🔓 Unlock
# ============================================================

async def unlock_channel(
    channel: discord.TextChannel,
    moderator: discord.Member,
    *,
    reason: str | None = None,
) -> None:
    """
    Déverrouille le salon pour @everyone, retire le 🔒 du nom et poste un
    message d'annonce.
    """
    if not is_locked(channel):
        raise LockError("Ce salon n'est pas **verrouillé**.", warning=True)

    everyone = channel.guild.default_role
    overwrite = channel.overwrites_for(everyone)
    overwrite.send_messages = None  # reset : hérite de la catégorie/serveur

    audit_reason = f"/mod unlock par {moderator} — {reason}" if reason else f"/mod unlock par {moderator}"

    try:
        await channel.set_permissions(everyone, overwrite=overwrite, reason=audit_reason)
    except discord.Forbidden as exc:
        raise LockError("Le bot n'a pas la permission de modifier ce salon.") from exc
    except discord.HTTPException as exc:
        raise LockError("Une erreur Discord est survenue pendant le déverrouillage.") from exc

    try:
        new_name = _remove_lock_prefix(channel.name)
        if new_name != channel.name:
            await channel.edit(name=new_name, reason=audit_reason)
    except (discord.Forbidden, discord.HTTPException):
        pass

    try:
        await channel.send(
            f"🔓 **Salon déverrouillé** par {moderator.mention}"
            + (f"\n> {reason}" if reason else ""),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except (discord.Forbidden, discord.HTTPException):
        pass