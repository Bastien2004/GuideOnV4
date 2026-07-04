"""
utils/perm_staff.py - Vérification des permissions Staff GuideON.

Hiérarchie : super-admin et DEV sont aussi considérés Staff.
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.permission import get_ids
from utils.createur import is_creator


def is_staff(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est Staff GuideON (ou DEV, ou super-admin)."""
    uid = interaction.user.id
    return (
        is_creator(uid)
        or uid in get_ids("DEV")
        or uid in get_ids("STAFF_GUIDEON")
    )


async def check_staff(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions Staff GuideON, sinon répond une erreur éphémère."""
    if is_staff(interaction):
        return True
    msg = f"Vous devez être membre du **Staff GuideON** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False