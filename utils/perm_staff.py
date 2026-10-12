"""
utils/perm_staff.py - Vérification des permissions Staff GuideOn.
"""

from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.createur import is_creator
from utils.managers.permission_rbac_manager import has_grade


async def is_staff(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur fait parti de l'équipe GuideOn."""

    uid = interaction.user.id
    return (
        is_creator(uid)
        or await has_grade(uid, "equipe_guideon.dev")
        or await has_grade(uid, "equipe_guideon.staff")
    )


async def check_staff(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions Staff GuideOn."""

    if await is_staff(interaction):
        return True
    
    msg = f"Vous devez faire partie de l'**équipe GuideOn** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False