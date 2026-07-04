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
    """True si l'utilisateur est Administrateur sur le serveur."""
    member = _get_member(interaction)
    if member is None:
        return False
    return member.guild_permissions.administrator


async def check_admin(interaction: discord.Interaction, action: str = "effectuer cette action",) -> bool:
    """
    Vérifie les permissions admin et gère le cas MP.
    """
    if interaction.guild is None:
        msg = "Cette commande ne peut être __utilisée__ que dans un **serveur Discord**."
        await send_ephemeral(interaction, error_container(msg))
        return False

    if is_admin(interaction):
        return True

    msg = f"Vous devez être **Administrateur** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False