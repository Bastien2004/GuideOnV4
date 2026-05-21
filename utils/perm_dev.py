"""
utils/perm_dev.py - Vérification des permissions développeur.

⚠️ Différence avec la V3 : on NE fige PLUS les IDs à l'import
(AUTHORIZED_IDS = set(get_ids("DEV")) était évalué une seule fois au démarrage
et ne voyait jamais les ajouts/retraits). On lit le cache à CHAQUE appel, donc
les changements via /dev permissions sont pris en compte immédiatement.

Les super-admins (utils.super_admins.SUPER_ADMIN_IDS) sont TOUJOURS dev.
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container
from utils.permission import get_ids
from utils.createur import is_super_admin


def is_dev(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est développeur (groupe DEV ou super-admin)."""
    uid = interaction.user.id
    return is_super_admin(uid) or uid in get_ids("DEV")


async def check_dev(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions développeur, sinon répond une erreur éphémère."""
    if is_dev(interaction):
        return True
    msg = f"Vous devez être **Développeur** pour {action}."
    if interaction.response.is_done():
        await interaction.followup.send(view=error_container(msg), ephemeral=True)
    else:
        await interaction.response.send_message(view=error_container(msg), ephemeral=True)
    return False