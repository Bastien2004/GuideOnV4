"""
utils/perm_dev.py - Vérification des permissions développeur.
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.permission import get_ids
from utils.createur import is_creator


def is_dev(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est développeur (groupe DEV ou super-admin)."""
    uid = interaction.user.id
    return is_creator(uid) or uid in get_ids("DEV")


async def check_dev(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions développeur, sinon répond une erreur éphémère."""
    if is_dev(interaction):
        return True
    msg = f"Vous devez être **développeur** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False