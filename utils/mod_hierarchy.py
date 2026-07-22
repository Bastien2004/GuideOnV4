"""
utils/mod_hierarchy.py — Vérifications de hiérarchie avant toute sanction.

Centralise les garde-fous communs à warn/mute/kick/ban/tempban/softban :
pas de bot, pas d'auto-sanction, pas le propriétaire du serveur, hiérarchie
de rôles (cible < modérateur, sauf Administrateur) ET (cible < bot, dans
tous les cas — sinon Discord refuse silencieusement l'action).
"""
from __future__ import annotations

import discord


def validate_sanction_target(interaction: discord.Interaction, target: discord.Member) -> str | None:
    """
    Retourne un message d'erreur (str) si `target` ne peut pas être
    sanctionné par l'auteur de l'interaction, None si tout est en ordre.
    """
    moderator = interaction.user
    guild = interaction.guild

    if target.bot:
        return "Impossible de sanctionner un **bot**."

    if target.id == moderator.id:
        return "Vous ne pouvez pas vous sanctionner **vous-même**."

    if guild.owner_id is not None and target.id == guild.owner_id:
        return "Impossible de sanctionner le **propriétaire** du serveur."

    if isinstance(moderator, discord.Member) and not moderator.guild_permissions.administrator:
        if target.top_role >= moderator.top_role:
            return "Ce membre a un rôle **égal ou supérieur** au vôtre."

    if guild.me is not None and target.top_role >= guild.me.top_role:
        return "Ce membre a un rôle **égal ou supérieur** à celui du bot — impossible d'agir sur lui."

    return None
