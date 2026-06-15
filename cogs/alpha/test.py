"""
cogs/alpha/test.py — Système de test de fonctionnalité du module Alpha.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container
from utils.createur import is_creator


# ============================================================
# 🧱 View
# ============================================================

def build_test_view() -> LayoutView:
    view = LayoutView(timeout=None)

    c = Container()
    c.add_item(TextDisplay("# 🧪 Test réussi"))
    c.add_item(Separator())
    c.add_item(TextDisplay("La commande **`/alpha test`** fonctionne correctement."))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view


# ============================================================
# 🧭 Commande
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="test", description="🧪 Commande de test Alpha")
async def test_alpha(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Créateurs uniquement.
    if not is_creator(interaction.user.id):
        return await interaction.response.send_message(view=error_container("Cette commande est réservée aux **créateurs**."), ephemeral=True)
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_test"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_test")

    # ✅ Envoi du message de test.
    await interaction.followup.send(view=build_test_view(), ephemeral=True)


# ============================================================
# ❌ Erreurs
# ============================================================

@test_alpha.error
async def test_alpha_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)