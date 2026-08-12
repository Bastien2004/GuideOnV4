"""
utils/ng_server_check.py — Garde-fou "Discord NG" pour les commandes /ngstaff.

Complète utils/perm_check.py (RBAC) : ce module ne s'occupe que de la
première étape du flow décrit §5 du prompt de refonte (option a, retenue) —
détecter si l'interaction vient bien d'un Discord NG enregistré dans
ng_servers avant même de vérifier un grade (qui dépend lui-même du nom du
serveur détecté, d'où le flow en deux temps plutôt qu'un décorateur unique) :

    async def ngstaff_rank(interaction):
        server = await require_ng_server(interaction)
        if not server:
            return  # message déjà envoyé
        if not await has_grade_check(interaction, f"staff_{server.name}.op"):
            return  # message déjà envoyé
        ...
"""
from __future__ import annotations

import discord

from utils.container_universel import error_container, send_ephemeral
from utils.db.models.ng_server import NGServer
from utils.managers.ng_server_manager import get_server_by_guild

__all__ = ["require_ng_server"]


async def require_ng_server(interaction: discord.Interaction) -> NGServer | None:
    """
    Résout le NGServer associé à interaction.guild_id.

    Retourne le NGServer si l'interaction vient d'un Discord NG connu du
    cache ng_servers, sinon envoie un message d'erreur éphémère et
    retourne None (le code appelant doit `return` immédiatement dans ce cas).
    """
    guild_id = interaction.guild_id
    server = get_server_by_guild(guild_id) if guild_id is not None else None
    if server is None:
        await send_ephemeral(
            interaction,
            error_container(
                "Cette commande n'est disponible **que sur les Discord NationsGlory**."
            ),
        )
        return None
    return server
