"""
Commande /user — Affiche le profil d'un membre du serveur, choisi via le
menu déroulant natif de Discord (paramètre membre: discord.Member).

Résultat identique à /id <id_discord>, réutilise la même vue de profil
(views/user/user_view.py). Discord résout et valide déjà le membre
lui-même — pas besoin de fetch_user ni de gestion NotFound/HTTPException
ici, contrairement à /id qui accepte un ID/mention en texte libre.

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

from views.user.user_view import build_user_view


# ============================================================
# 👤 Commande principale : /user
# ============================================================

class UserLookup(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="user", description="👤 Affiche le profil d'un membre du serveur.")
    @app_commands.describe(membre="Le membre dont afficher le profil")
    async def user_command(self, interaction: discord.Interaction, membre: discord.Member):

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

        # 🧩 Construction + envoi (même vue que /id).
        view = build_user_view(membre)
        await interaction.followup.send(view=view)

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