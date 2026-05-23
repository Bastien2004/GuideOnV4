"""
views/ticket/_helpers.py — Helpers partagés du système de tickets.
"""
from __future__ import annotations

import time
import discord

from utils.managers import ticket_manager as tm

# ============================================================
# ⚙️ Constantes (reprises de la V3)
# ============================================================

TICKET_COOLDOWN_SECONDS = 30      # anti-spam ouverture
RENAME_COOLDOWN_SECONDS = 600     # cooldown renommage (rate-limit Discord)
WAKEUP_COOLDOWN_SECONDS = 3600    # cooldown relance par staff

# Tickets simultanés par utilisateur (par panel)
MAX_TICKETS_USER_DEFAULT = 1
MAX_TICKETS_USER_VIP = 2

# Tickets ouverts par panel
MAX_TICKETS_PANEL_DEFAULT = 50
MAX_TICKETS_PANEL_GOLD = 100


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