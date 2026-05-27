"""
Commande /ping — Affiche la latence du bot.
"""

import discord

from discord import app_commands
from discord.ext import commands

from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error


# ============================================================
# 🎨 Statut latence
# ============================================================

def get_latency_status(latency_ms: int) -> tuple[str, str]:
    """Retourne l'emoji + statut selon la latence."""

    if latency_ms < 100:
        return "🟢", "Excellente"

    if latency_ms < 250:
        return "🟡", "Correcte"

    return "🔴", "Dégradée"


# ============================================================
# 🧩 Construction view CV2
# ============================================================

def build_ping_view(latency_ms: int) -> LayoutView:
    """Construction de la view ping."""

    emoji, status = get_latency_status(latency_ms)
    view = LayoutView(timeout=None)
    container = Container()

    # Header
    container.add_item(TextDisplay("# <:notifier:1495444487206604833> Pong !"))
    container.add_item(Separator())

    # Informations ping
    container.add_item(
        TextDisplay(
            "## 📡 Statut du bot\n"
            f"**Latence :** `{latency_ms} ms`\n"
            f"**État :** {emoji} {status}"
        )
    )

    container.add_item(Separator())

    # Footer
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)

    return view


# ============================================================
# 🏓 Commande principale
# ============================================================

class Ping(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="ping", description="🏓 Affiche la latence du bot.")
    async def ping_command(self, interaction: discord.Interaction):

        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "ping_command"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "ping_command")

        # 📡 Calcul latence.
        latency_ms = round(self.bot.latency * 1000)

        # 🧩 Construction view.
        view = build_ping_view(latency_ms)

        # 🚀 Envoi.
        await interaction.followup.send(view=view, ephemeral=True)

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @ping_command.error
    async def ping_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))