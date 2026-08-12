"""
utils/perm_staff.py - Vérification des permissions Staff GuideON.

Hiérarchie : super-admin et DEV sont aussi considérés Staff.

Refonte multi-serveurs, phase 15 (nettoyage legacy) : is_staff lisait
auparavant get_ids("DEV")/get_ids("STAFF_GUIDEON") depuis l'ancienne
table permission_entries, gelée depuis la phase 4 — même bug que
utils/perm_alpha.py et utils/perm_dev.py (voir PHASE_15.md). Corrigé ici
de la même façon : has_grade() sur les grades RBAC equipe_guideon.dev /
equipe_guideon.staff. Note : check_staff n'a aucun appelant actif dans le
codebase au moment de cette phase (vérifié par grep) — corrigé quand même
par cohérence, pour rester correct le jour où ce helper sera câblé à une
commande.
"""
from __future__ import annotations

import discord
from discord import Interaction

from utils.container_universel import error_container, send_ephemeral
from utils.createur import is_creator
from utils.managers.permission_rbac_manager import has_grade


async def is_staff(interaction: discord.Interaction) -> bool:
    """True si l'utilisateur est Staff GuideON (ou DEV, ou super-admin)."""
    uid = interaction.user.id
    return (
        is_creator(uid)
        or await has_grade(uid, "equipe_guideon.dev")
        or await has_grade(uid, "equipe_guideon.staff")
    )


async def check_staff(interaction: Interaction, action: str = "effectuer cette action") -> bool:
    """Vérifie les permissions Staff GuideON, sinon répond une erreur éphémère."""
    if await is_staff(interaction):
        return True
    msg = f"Vous devez être membre du **Staff GuideON** pour {action}."
    await send_ephemeral(interaction, error_container(msg))
    return False