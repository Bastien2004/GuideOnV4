"""
Commande /user — Sélectionne un membre via un menu déroulant et affiche son
profil (résultat identique à /id <id_discord>).

Reste en commands.Cog, comme /id : commande racine autonome, pas une
sous-commande d'un groupe.
"""
from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.error_handler import handle_app_command_error

from views.user.user_picker_view import UserLookupView


# ============================================================
# 👤 Commande principale : /user
# ============================================================

class UserLookup(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="user", description="👤 Sélectionne un membre via un menu déroulant et affiche son profil.")
    async def user_command(self, interaction: discord.Interaction):

        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "user_command"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "user_command")

        # 🧩 Envoi du menu de sélection.
        view = UserLookupView(owner_id=interaction.user.id, bot=self.bot)
        await interaction.followup.send(view=view, ephemeral=True)

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @user_command.error
    async def user_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(UserLookup(bot))