"""
utils/perm_mod.py — Vérification des permissions granulaires du système /mod.

Contrairement à perm_admin/perm_staff/perm_dev (rôles fixes, bot-wide),
ce module vérifie une clé de permission configurable PAR SERVEUR via
utils.managers.mod_permission_manager (/mod permissions).
"""
from __future__ import annotations

import discord

from utils.container_universel import error_container, send_ephemeral
from utils.managers.mod_permission_manager import get_permission_key, has_permission


def _get_member(interaction: discord.Interaction) -> discord.Member | None:
    """Récupère interaction.user en Member. None si hors serveur."""
    if interaction.guild is None:
        return None
    if isinstance(interaction.user, discord.Member):
        return interaction.user
    return interaction.guild.get_member(interaction.user.id)


async def check_mod_permission(interaction: discord.Interaction, key: str) -> bool:
    """
    Vérifie que l'utilisateur a la permission d'utiliser la commande/le
    panneau identifié par `key`. Gère le cas hors-serveur et répond une
    erreur éphémère en cas de refus.
    """
    if interaction.guild is None:
        msg = "Cette commande ne peut être __utilisée__ que dans un **serveur Discord**."
        await send_ephemeral(interaction, error_container(msg))
        return False

    member = _get_member(interaction)
    if member is None:
        await send_ephemeral(interaction, error_container("Membre **introuvable** sur ce serveur."))
        return False

    if await has_permission(member, key):
        return True

    permission_key = get_permission_key(key)
    label = permission_key.label if permission_key is not None else key
    msg = (
        f"Vous n'avez pas la permission d'utiliser **{label}**.\n"
        f"-# Un administrateur peut l'autoriser via `/mod permissions`."
    )
    await send_ephemeral(interaction, error_container(msg))
    return False
