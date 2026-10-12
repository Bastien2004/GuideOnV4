"""
utils/perm_dev.py - Vérification des permissions développeur.
"""

from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.createur import is_creator
from utils.managers.permission_rbac_manager import has_grade


async def is_dev(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est développeur."""

    uid = interaction.user.id
    return is_creator(uid) or await has_grade(uid, "equipe_guideon.dev")


async def check_dev(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions développeur."""

    if await is_dev(interaction):
        return True
    
    msg = f"Vous devez être **développeur** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False