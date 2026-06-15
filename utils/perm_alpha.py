"""
utils/perm_alpha.py — Vérification des permissions du système Alpha.

Hiérarchie :
    CREATOR / DEV      ──┐
    OP_ALPHA             ├──> is_op_alpha     (Admins / SM Alpha)
    MODO_PLUS_ALPHA      ├──> is_modo_plus    (Modo+ et au-dessus)
    MODO_ALPHA           └──> is_modo         (Modo et au-dessus)
"""

from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container
from utils.permission import get_ids
from utils.createur import is_creator


# ============================================================
# 📁 Fonctions
# ============================================================

def is_op_alpha(interaction: discord.Interaction) -> bool:
    """True si OP Alpha (ou supérieur : DEV ou CREATOR)."""
    uid = interaction.user.id
    return (is_creator(uid) or uid in get_ids("DEV") or uid in get_ids("OP_ALPHA"))


def is_modo_plus(interaction: discord.Interaction) -> bool:
    """True si Modo+ Alpha ou supérieur."""
    uid = interaction.user.id
    return is_op_alpha(interaction) or uid in get_ids("MODO_PLUS_ALPHA")


def is_modo(interaction: discord.Interaction) -> bool:
    """True si Modo Alpha ou supérieur."""
    uid = interaction.user.id
    return is_modo_plus(interaction) or uid in get_ids("MODO_ALPHA")


async def _send_error(interaction: Interaction, msg: str) -> None:
    """Envoie une erreur éphémère à l'utilisateur."""
    if interaction.response.is_done():
        await interaction.followup.send(view=error_container(msg), ephemeral=True)
    else:
        await interaction.response.send_message(view=error_container(msg), ephemeral=True)


async def check_op_alpha(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérification OP Alpha + Gestion d'erreur manque de permissions."""
    if is_op_alpha(interaction):
        return True
    await _send_error(interaction, f"Vous devez être **Opérateur** pour {action}.")
    return False


async def check_modo_plus(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérification MODO+ Alpha + Gestion d'erreur manque de permissions."""
    if is_modo_plus(interaction):
        return True
    await _send_error(interaction, f"Vous devez être **Modérateur +** pour {action}.")
    return False


async def check_modo(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérification MODO Alpha + Gestion d'erreur manque de permissions."""
    if is_modo(interaction):
        return True
    await _send_error(interaction, f"Vous devez être **Modérateur** pour {action}.")
    return False