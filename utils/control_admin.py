"""
utils/control_admin.py — Gestion du système de maintenance des commandes.
"""

from __future__ import annotations

import logging

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.container_universel import send_ephemeral
from utils.managers.command_toggle_manager import is_command_enabled

# ============================================================
# 📂 Constantes
# ============================================================

log = logging.getLogger(__name__)


# ============================================================
# 🛡️ Vérification commande activée
# ============================================================

async def verifier_commande(interaction: discord.Interaction, nom_commande: str) -> bool:
    """Vérifie si la commande est activée."""

    if await is_command_enabled(nom_commande):
        return True

    await send_maintenance_message(interaction)

    log.debug("[DEV MAINTENANCE] Commande désactivée : %s | user=%s", nom_commande, interaction.user.id)
    return False


# ============================================================
# 🧱 View maintenance
# ============================================================

def build_maintenance_view() -> LayoutView:
    """Construit le message de maintenance."""

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# <:maintenance:1547700517050916925> Commande en maintenance"))
    container.add_item(Separator())
    container.add_item(
        TextDisplay(
            "Cette commande est **temporairement désactivée** par l'__équipe développeur__.\n"
            "Pour toutes **informations supplémentaires**, contactez nous."
        )
    )
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📤 Envoi sécurisé
# ============================================================

async def send_maintenance_message(interaction: discord.Interaction) -> None:
    """Envoie le message de maintenance."""

    try:
        await send_ephemeral(interaction, build_maintenance_view())

    except discord.HTTPException:
        log.exception("[DEV MAINTENANCE] Impossible d'envoyer le message de maintenance")