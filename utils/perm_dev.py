"""
utils/perm_dev.py - Vérification des permissions développeur.

Refonte multi-serveurs, phase 15 (nettoyage legacy) : is_dev lisait
auparavant get_ids("DEV") depuis l'ancienne table permission_entries,
gelée depuis la phase 4 (date à laquelle /dev permissions a basculé sur
le RBAC, permission_grade_members). Un membre promu DEV via /dev
permissions après la phase 4 n'était donc PAS reconnu par check_dev —
bug de staleness identique à celui corrigé sur utils/perm_alpha.py (voir
PHASE_15.md), avec un impact bien plus large : check_dev gate 14 commandes
[DEV] (cogs/dev/gold.py, kick.py, botban.py, vip.py, stat_server.py,
guild_info.py, delete_message.py, debug_cmd.py, stat_cmd.py, health.py,
maintenance.py, join_serv.py) + /ngstaff nota_debug + /alpha nota_debug/
nota_force. Corrigé ici de la même façon : has_grade(uid,
"equipe_guideon.dev") au lieu de get_ids("DEV").
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.createur import is_creator
from utils.managers.permission_rbac_manager import has_grade


async def is_dev(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est développeur (grade RBAC equipe_guideon.dev, ou super-admin)."""
    uid = interaction.user.id
    return is_creator(uid) or await has_grade(uid, "equipe_guideon.dev")


async def check_dev(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions développeur, sinon répond une erreur éphémère."""
    if await is_dev(interaction):
        return True
    msg = f"Vous devez être **développeur** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False