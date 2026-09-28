"""
utils/perm_admin.py — Vérification des permissions administrateur.
"""
from __future__ import annotations

import discord
from utils.container_universel import error_container, send_ephemeral


# ============================================================
# 🧩 Fonctions
# ============================================================

def _get_member(interaction: discord.Interaction) -> discord.Member | None:
    """Récupère interaction.user en Member. None si hors serveur."""
    if interaction.guild is None:
        return None

    if isinstance(interaction.user, discord.Member):
        return interaction.user

    return interaction.guild.get_member(interaction.user.id)


def is_admin(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est Administrateur ou propriétaire du serveur."""

    member = _get_member(interaction)

    if member is None or interaction.guild is None:
        return False

    return (
        member.guild_permissions.administrator
        or member.id == interaction.guild.owner_id
    )

async def check_admin(interaction: discord.Interaction, action: str = "effectuer cette action") -> bool: