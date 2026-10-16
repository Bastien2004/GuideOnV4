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
from utils.perm_check import has_grade_check


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
@app_commands.command(name="test", description="🧪 [DEV] Commande de test Alpha")
async def test_alpha(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "utiliser cette commande de **dev**"):
        return
    
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