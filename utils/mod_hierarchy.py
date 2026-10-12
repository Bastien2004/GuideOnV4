"""
utils/mod_hierarchy.py — Vérifications de hiérarchie avant toute sanction.
"""

from __future__ import annotations

import discord


def validate_sanction_target(interaction: discord.Interaction, target: discord.Member) -> str | None:
    """Vérifie que la cible peut être sanctionnée."""

    moderator = interaction.user
    guild = interaction.guild

    if target.bot:
        return "Il est impossible de sanctionner un **bot**."

    if target.id == moderator.id:
        return "Vous ne pouvez pas vous sanctionner **vous-même**."

    if guild.owner_id is not None and target.id == guild.owner_id:
        return "Impossible de sanctionner le **propriétaire** du serveur."

    if isinstance(moderator, discord.Member) and not moderator.guild_permissions.administrator:
        if target.top_role >= moderator.top_role:
            return "Ce membre a un rôle **égal ou supérieur** au vôtre."

    if guild.me is not None and target.top_role >= guild.me.top_role:
        return "Permissions insuffisantes pour appliquer la sanction."

    return None