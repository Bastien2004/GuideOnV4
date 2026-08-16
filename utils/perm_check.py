"""
utils/perm_check.py — Vérification des permissions RBAC.

# 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "permission", "action"):
        return

Exemple : 

# 🔐 Vérification des permissions.
if not await has_grade_check(interaction, "staff_alpha.op", "envoyer le tutoriel"):
    return

"""

from __future__ import annotations

import discord
from discord import app_commands

from utils.container_universel import error_container, send_ephemeral
from utils.managers.permission_rbac_manager import has_grade

__all__ = ["has_grade_check", "requires_grade"]


# ============================================================
# 🔩 Fonctions utilitaires
# ============================================================

def _build_denied_message(grade_slug: str, action: str | None) -> str:
    """Construit le message d'erreur de permission."""

    if action:
        head = f"Vous n'avez pas la permission pour **{action}**."

    else:
        head = "Permission insuffisante."
    return f"{head}\n-# Grade requis : `{grade_slug}`"


async def has_grade_check(interaction: discord.Interaction, grade_slug: str, action: str | None = None) -> bool:
    """Vérifie que l'utilisateur à la permission suffisante."""

    if await has_grade(interaction.user.id, grade_slug):
        return True
    
    await send_ephemeral(interaction, error_container(_build_denied_message(grade_slug, action)))

    return False