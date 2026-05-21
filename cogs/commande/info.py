"""
Commande /info — Présentation du bot GuideON.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction, app_commands
from discord.ext import commands
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)

COMMUNITY_INVITE_URL = "https://discord.com/invite/p22xkCPDnq"


# ============================================================
# 🧩 View Info
# ============================================================

class InfoView(LayoutView):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

        container = Container()

        container.add_item(TextDisplay("# <:GuideON:1490361480980332676> __GuideON — Bot Discord__"))
        container.add_item(Separator())

        container.add_item(
            TextDisplay(
                "👋 **Bienvenue !**\n\n"
                "Je suis **GuideON**, un bot Discord français conçu pour\n"
                "**simplifier, sécuriser et enrichir** la __gestion__ de ton serveur.\n\n"
                "Que tu gères une **communauté classique** ou un serveur\n"
                "**NationsGlory**, je t'accompagne au quotidien."
            )
        )
        container.add_item(Separator())

        container.add_item(
            TextDisplay(
                "⚙️ __**Fonctionnalités principales :**__\n\n"

                "• 🎮 Commandes dédiées à NationsGlory\n"
                "• 📜 Logs complets et personnalisables\n"
                "• 🎟️ Système de tickets avancé\n"
                "• 👋 Messages de bienvenue intelligents\n"
                "• 🛡️ Outils de modération & sécurité\n"
                "• 🧩 Modules premium & personnalisés\n"
                "• 📦 Et plein d'autres systèmes très cool"
            )
        )
        container.add_item(Separator())

        container.add_item(
            TextDisplay(
                "📚 **__Besoin d'aide__ ?**\n\n"

                "• Consulte toutes les commandes avec **`/wiki`**\n"
                "• Rejoins-nous sur notre serveur Discord\n"
                "• Passe par notre nouveau site"
            )
        )
        container.add_item(Separator())

        wiki_btn = Button(
            label="📖 Accéder au wiki",
            style=ButtonStyle.link,
            url="https://guideonbot.guideon.dev/documentation",
        )

        discord_btn = Button(
            label="🤝 Nous rejoindre",
            style=ButtonStyle.link,
            url=COMMUNITY_INVITE_URL,
        )

        container.add_item(ActionRow(wiki_btn, discord_btn))
        container.add_item(Separator())

        container.add_item(TextDisplay("-# GuideOn Studio"))

        self.add_item(container)


# ============================================================
# 🎛 Cog
# ============================================================

class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="info", description="❔ Découvrir GuideON")
    async def info(self, interaction: Interaction) -> None:

        # 🛡️ Vérification ban utilisateur
        if not await verifier_ban_utilisateur(interaction):
            return

        # ⚙️ Vérification activation commande
        if not await verifier_commande(interaction, "info"):
            return

        # 📊 Tracking commande
        await tracker_commande(interaction, "info")

        # 🚀 Envoi
        await interaction.response.send_message(view=InfoView(self.bot))


    # ============================================================
    # 📨 Message automatique à l'arrivée sur un nouveau serveur
    # ============================================================

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:
        view = InfoView(self.bot)

        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                try:
                    await channel.send(view=view)
                    log.info("Message de présentation envoyé dans #%s (%s)", channel.name, guild.name)
                    return
                except discord.HTTPException as e:
                    log.warning("Échec envoi présentation dans #%s : %s", channel.name, e)

        log.warning("Aucun salon disponible pour envoyer la présentation sur %s", guild.name)


    # ============================================================
    # ❌ Gestion erreurs
    # ============================================================

    @info.error
    async def info_error(self, interaction: Interaction, error: app_commands.AppCommandError,) -> None:
        await handle_app_command_error(interaction, error)


# ============================================================
# 🔌 Setup
# ============================================================
async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Info(bot))