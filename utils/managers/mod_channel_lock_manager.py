"""
utils/managers/mod_channel_lock_manager.py — Verrouillage/déverrouillage d'un salon textuel.
"""

from __future__ import annotations

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.managers import mod_channel_lock_exemption_manager as exemption_mgr
from utils.managers import mod_permission_manager

LOCK_EMOJI = "🔒"
UNLOCK_EMOJI = "🔓"


class LockError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


# ============================================================
# 📢 Annonces de verouillage
# ============================================================

def _build_announcement(*, is_lock: bool, moderator: discord.Member, reason: str | None) -> LayoutView:
    """Container V2 stylisé pour l'annonce publique dans le salon."""

    view = LayoutView(timeout=None)
    container = Container()

    if is_lock:
        title = f"# {LOCK_EMOJI} Salon verrouillé"
        body = (
            "Ce salon vient d'être **verrouillé** par le staff.\n"
            "-# Les envois de messages sont désactivés jusqu'à son déverrouillage."
        )
    else:
        title = f"# {UNLOCK_EMOJI} Salon déverrouillé"
        body = (
            "Ce salon vient d'être **déverrouillé** par le staff.\n"
            "-# Les échanges peuvent reprendre normalement."
        )

    container.add_item(TextDisplay(title))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))
    container.add_item(Separator())
    container.add_item(TextDisplay(f"**👤 Modérateur**\n-# {moderator.mention}"))
    if reason:
        container.add_item(TextDisplay(f"**📝 Raison**\n-# « {reason} »"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


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
# 🛡️ Exemption des rôles autorisés à /mod lock
# ============================================================

async def _grant_role_exemptions(channel: discord.TextChannel, guild_id: int, *, audit_reason: str) -> None:
    role_ids = await mod_permission_manager.get_roles(guild_id, "mod_lock")
    for role_id in role_ids:
        role = channel.guild.get_role(role_id)
        if role is None:
            continue
        existing = channel.overwrites_for(role)
        if existing.send_messages is not None:
            continue
        existing.send_messages = True
        try:
            await channel.set_permissions(role, overwrite=existing, reason=audit_reason)
            await exemption_mgr.record_exemption(guild_id, channel.id, role_id)
        except (discord.Forbidden, discord.HTTPException):
            pass


async def _revoke_role_exemptions(channel: discord.TextChannel, *, audit_reason: str) -> None:
    role_ids = await exemption_mgr.clear_exemptions(channel.id)
    for role_id in role_ids:
        role = channel.guild.get_role(role_id)
        if role is None:
            continue
        overwrite = channel.overwrites_for(role)
        if overwrite.send_messages is not True:
            continue
        overwrite.send_messages = None
        try:
            if overwrite.is_empty():
                await channel.set_permissions(role, overwrite=None, reason=audit_reason)
            else:
                await channel.set_permissions(role, overwrite=overwrite, reason=audit_reason)
        except (discord.Forbidden, discord.HTTPException):
            pass


# ============================================================
# 🔒 Lock
# ============================================================

async def lock_channel(channel: discord.TextChannel, moderator: discord.Member, *, reason: str | None = None) -> None:
    """Exécution d'un vérouillage."""

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

    try:
        await _grant_role_exemptions(channel, channel.guild.id, audit_reason=audit_reason)
    except Exception:
        pass

    # 2. Rename cosmétique — best-effort.
    try:
        new_name = _add_lock_prefix(channel.name)
        if new_name != channel.name:
            await channel.edit(name=new_name, reason=audit_reason)
    except (discord.Forbidden, discord.HTTPException):
        pass

    # 3. Annonce publique stylisée — best-effort.
    try:
        await channel.send(
            view=_build_announcement(is_lock=True, moderator=moderator, reason=reason),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except (discord.Forbidden, discord.HTTPException):
        pass


# ============================================================
# 🔓 Unlock
# ============================================================

async def unlock_channel(channel: discord.TextChannel, moderator: discord.Member, *, reason: str | None = None) -> None:
    """Dévérouillage d'un salon."""

    if not is_locked(channel):
        raise LockError("Ce salon n'est pas **verrouillé**.", warning=True)

    everyone = channel.guild.default_role
    overwrite = channel.overwrites_for(everyone)
    overwrite.send_messages = None

    audit_reason = f"/mod unlock par {moderator} — {reason}" if reason else f"/mod unlock par {moderator}"

    try:
        await channel.set_permissions(everyone, overwrite=overwrite, reason=audit_reason)
    except discord.Forbidden as exc:
        raise LockError("Le bot n'a pas la permission de modifier ce salon.") from exc
    except discord.HTTPException as exc:
        raise LockError("Une erreur Discord est survenue pendant le déverrouillage.") from exc

    # 1bis. Retire les exemptions de rôle posées par le /mod lock correspondant.
    try:
        await _revoke_role_exemptions(channel, audit_reason=audit_reason)
    except Exception:
        pass

    try:
        new_name = _remove_lock_prefix(channel.name)
        if new_name != channel.name:
            await channel.edit(name=new_name, reason=audit_reason)
    except (discord.Forbidden, discord.HTTPException):
        pass

    try:
        await channel.send(
            view=_build_announcement(is_lock=False, moderator=moderator, reason=reason),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except (discord.Forbidden, discord.HTTPException):
        pass