"""
utils/perm_dev.py — Vérification des permissions développeur.
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.permission import is_dev as get_dev_ids
from utils.container_universel import error_container

# ============================================================
# 📋 Constantes
# ============================================================

AUTHORIZED_IDS = set(get_dev_ids())

# ============================================================
# 🔍 Vérification développeur
# ============================================================

def is_dev_user(interaction: discord.Interaction) -> bool:
    """Retourne True si l'utilisateur fait partie des développeurs autorisés."""
    return interaction.user.id in AUTHORIZED_IDS

# ============================================================
# 🔒 Vérification permissions développeur
# ============================================================

async def check_dev(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions développeur."""
    if is_dev_user(interaction):
        return True

    msg = f"Vous devez être **Développeur** pour {action}."

    if interaction.response.is_done():
        await interaction.followup.send(view=error_container(msg), ephemeral=True)
    else:
        await interaction.response.send_message(view=error_container(msg), ephemeral=True)

    return False
