"""
cogs/commande/id.py — Affiche les informations d'un utilisateur depuis son identifiant.
"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container

from views.user.user_view import build_user_view, extract_id


# ============================================================
# 👤 Commande principale : /id
# ============================================================

class UserID(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="id", description="👤 Récupère les informations d’un utilisateur via son ID ou sa mention")
    @app_commands.describe(user_id="L’ID ou la mention de l’utilisateur")
    async def id_command(self, interaction: discord.Interaction, user_id: str):

        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "id_cmd"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "id_cmd")

        # 🔍 Extraction ID.
        uid = extract_id(user_id)

        if uid is None:
            return await interaction.followup.send(
                view=error_container(
                    "Format **invalide**.\n"
                    "Merci de fournir un **ID Discord** ou une **mention** __valide__."
                ),
                ephemeral=True
            )

        # 🌐 Récupération utilisateur.
        try:
            user = await self.bot.fetch_user(uid)

        except discord.NotFound:
            return await interaction.followup.send(
                view=error_container("**Aucun utilisateur** trouvé avec cet __ID__."),
                ephemeral=True
            )

        except discord.HTTPException as e:
            return await interaction.followup.send(
                view=error_container(f"Erreur **réseau** Discord :\n`{e}`"),
                ephemeral=True
            )

        # 🧩 Construction view.
        view = build_user_view(user)

        # 🚀 Envoi.
        await interaction.followup.send(view=view)

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @id_command.error
    async def id_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(UserID(bot))