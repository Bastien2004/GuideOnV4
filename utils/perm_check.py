"""
utils/perm_check.py — Vérification des permissions RBAC (ex-perm_alpha.py,
généralisé multi-serveurs).

Deux façons d'utiliser :

1. Décorateur `@requires_grade("staff_alpha.op")` sur une app_command — refuse
   automatiquement avec un message éphémère si le grade n'est pas résolu au
   moment du check Discord.

2. Helper inline `has_grade_check(interaction, grade_slug)` pour le flow en
   deux temps recommandé par le prompt de refonte (§5, option a) quand le
   grade dépend d'un serveur NG détecté à l'exécution :

       async def ngstaff_rank(interaction):
           server = await require_ng_server(interaction)
           if not server:
               return
           if not await has_grade_check(interaction, f"staff_{server.name}.op"):
               return  # message déjà envoyé
           ...

`require_ng_server` vit dans utils.ng_server_check (à créer si besoin lors du
câblage des commandes /ngstaff — hors scope de ce module, qui ne couvre que
la brique RBAC générique).
"""
from __future__ import annotations

import discord
from discord import app_commands

from utils.container_universel import error_container, send_ephemeral
from utils.managers.permission_rbac_manager import has_grade

__all__ = ["has_grade_check", "requires_grade"]


async def has_grade_check(interaction: discord.Interaction, grade_slug: str) -> bool:
    """
    Check inline sans décorateur. Retourne True si autorisé, sinon envoie un
    message d'erreur éphémère et retourne False.
    """
    if await has_grade(interaction.user.id, grade_slug):
        return True
    await send_ephemeral(
        interaction, error_container(f"Permission insuffisante ({grade_slug}).")
    )
    return False


def requires_grade(grade_slug: str):
    """
    Décorateur pour les app_commands à grade fixe (connu à l'écriture du
    code, pas dépendant d'un serveur NG résolu à l'exécution — dans ce
    dernier cas, utiliser `has_grade_check` en flow deux temps, voir §5 du
    prompt de refonte).
    """

    async def predicate(interaction: discord.Interaction) -> bool:
        if await has_grade(interaction.user.id, grade_slug):
            return True
        await send_ephemeral(
            interaction, error_container(f"Permission insuffisante ({grade_slug}).")
        )
        return False

    return app_commands.check(predicate)
