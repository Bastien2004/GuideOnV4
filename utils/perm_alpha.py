"""
utils/perm_alpha.py - Vérification des permissions OP Alpha.

Hiérarchie : super-admin et DEV sont aussi considérés OP Alpha.
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container
from utils.permission import get_ids
from utils.createur import is_super_admin


def is_op_alpha(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est OP Alpha (ou DEV, ou super-admin)."""
    uid = interaction.user.id
    return (
        is_super_admin(uid)
        or uid in get_ids("DEV")
        or uid in get_ids("OP_ALPHA")
    )


async def check_op_alpha(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions OP Alpha, sinon répond une erreur éphémère."""
    if is_op_alpha(interaction):
        return True
    msg = f"Vous devez être **OP Alpha** pour {action}."
    if interaction.response.is_done():
        await interaction.followup.send(view=error_container(msg), ephemeral=True)
    else:
        await interaction.response.send_message(view=error_container(msg), ephemeral=True)
    return False