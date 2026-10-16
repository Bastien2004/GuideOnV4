"""
views/ticket/_helpers.py — Helpers partagés du système de tickets.
"""

from __future__ import annotations

import time
import discord

from utils.managers import ticket_manager as tm
from utils.ticket_limits import MAX_CHANNELS_PER_CATEGORY, RENAME_COOLDOWN_SECONDS

# NOTE : toutes les constantes numériques du système (cooldowns, maximums,
# longueurs de champs…) vivent désormais dans utils/ticket_limits.py — seule
# source de vérité, pour pouvoir les rééquilibrer facilement au même endroit.
# Ce fichier ne garde que des fonctions utilitaires.


# ============================================================
# 🏷️ Nom de salon (préfixe closed-)
# ============================================================

def closed_name(original: str) -> str:
    """Nom de salon fermé."""

    return f"closed-{original}"[:100]


def strip_closed_prefix(name: str) -> str:
    """Retire le préfixe closed- pour retrouver le nom d'origine."""

    return name[len("closed-"):] if name.startswith("closed-") else name


async def try_rename(channel: discord.abc.GuildChannel, new_name: str) -> bool:
    """Tente de renommer un salon."""

    if channel.name == new_name:
        return True
    try:
        await channel.edit(name=new_name)
        return True
    except discord.HTTPException:
        return False


def rename_cooldown_remaining(ticket: dict) -> int:
    """Secondes restantes avant de pouvoir renommer (rate-limit Discord)."""

    last = ticket.get("last_rename_at", 0) or 0
    remaining = RENAME_COOLDOWN_SECONDS - (int(time.time()) - last)
    return max(0, remaining)


# ============================================================
# 🛡️ Vérifications de permission staff
# ============================================================

def _member_role_ids(user: discord.abc.User) -> list[int]:
    """IDs de rôles d'un membre."""

    roles = getattr(user, "roles", None)
    if not roles:
        return []
    return [r.id for r in roles]


async def is_staff(interaction: discord.Interaction, ticket: dict, guild_id: int) -> bool:
    """True si l'utilisateur est admin OU possède un rôle staff du panel du ticket."""

    member = interaction.user
    if isinstance(member, discord.Member) and member.guild_permissions.administrator:
        return True

    panel_id = ticket.get("panel_id", "")
    role_ids = _member_role_ids(member)
    if not panel_id or not role_ids:
        return False

    sync_result = tm.is_staff_sync(guild_id, panel_id, role_ids)
    if sync_result is not None:
        return sync_result

    panel = await tm.get_panel(guild_id, panel_id)
    if not panel:
        return False
    staff = set(panel.get("staff_roles", []))
    return any(rid in staff for rid in role_ids)


async def is_staff_or_creator(interaction: discord.Interaction, ticket: dict, guild_id: int) -> bool:
    """True si l'utilisateur est le créateur du ticket OU staff."""

    if ticket and ticket.get("creator_id") == interaction.user.id:
        return True
    return await is_staff(interaction, ticket or {}, guild_id)


# ============================================================
# 📁 Choix de la catégorie de destination (avec secours)
# ============================================================

def _category_has_room(category) -> bool:
    """True si `category` est une CategoryChannel valide et pas pleine."""

    return (
        isinstance(category, discord.CategoryChannel)
        and len(category.channels) < MAX_CHANNELS_PER_CATEGORY
    )


def pick_ticket_category(
    guild: discord.Guild, panel: dict
) -> tuple[discord.CategoryChannel | None, bool]:
    """
    Choisit la catégorie où créer/rouvrir un ticket pour ce panel.

    Essaie d'abord `ticket_category_id` (catégorie principale). Si elle est
    pleine (cap Discord de MAX_CHANNELS_PER_CATEGORY salons) OU introuvable
    (supprimée, mal configurée), retombe sur `backup_category_id` si elle a
    été configurée ET qu'elle a elle aussi de la place.

    Renvoie (catégorie, secours_utilisé) :
      - (CategoryChannel, False) : catégorie principale disponible.
      - (CategoryChannel, True)  : principale indisponible, secours utilisé.
      - (None, False)            : aucune catégorie disponible nulle part —
        l'appelant doit refuser l'action avec un message clair plutôt que de
        laisser Discord échouer avec une erreur brute (salon plein).
    """
    primary = guild.get_channel(panel.get("ticket_category_id"))
    if _category_has_room(primary):
        return primary, False

    backup_id = panel.get("backup_category_id")
    backup = guild.get_channel(backup_id) if backup_id else None
    if _category_has_room(backup):
        return backup, True

    return None, False