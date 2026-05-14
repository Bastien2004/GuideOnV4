"""
Décorateurs et checks de permissions.

Centralise toute la logique d'autorisation pour ne pas l'éparpiller dans les cogs.

Usage :
    @app_commands.command(...)
    @is_guild_admin()
    async def ma_commande(interaction): ...
"""
from __future__ import annotations

import discord
from discord import app_commands

from utils.settings import settings


def is_guild_admin():
    """L'utilisateur doit avoir les perms admin sur le serveur."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None or not isinstance(interaction.user, discord.Member):
            return False
        return interaction.user.guild_permissions.administrator

    return app_commands.check(predicate)


def is_dev():
    """Réservé aux serveurs dev/support."""

    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        return interaction.guild.id in {settings.guild_dev_id, settings.guild_support_id}

    return app_commands.check(predicate)


def is_in_alpha():
    """Limite la commande au serveur Alpha."""

    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.guild is not None and interaction.guild.id == settings.guild_alpha_id

    return app_commands.check(predicate)


def is_in_anniv():
    """Limite la commande au serveur Anniversaire."""

    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.guild is not None and interaction.guild.id == settings.guild_anniv_id

    return app_commands.check(predicate)


def has_perm(**perms: bool):
    """Wrapper plus lisible que app_commands.checks.has_permissions."""
    return app_commands.checks.has_permissions(**perms)
