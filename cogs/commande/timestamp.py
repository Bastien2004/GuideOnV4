"""
Commande /timestamp — Génère un timestamp Discord.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, info_container
from utils.control_admin import verifier_commande

from utils.error_handler import handle_app_command_error
from utils.track_commande import tracker_commande

PARIS_TZ = ZoneInfo("Europe/Paris")


# ============================================================
# 👤 Commande principale : /timestamp
# ============================================================

class Timestamp(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="timestamp", description="🕒 Convertit une date en timestamp Discord",)
    @app_commands.describe(jour="Jour (1-31)", mois="Mois (1-12)", annee="Année (ex: 2026)", heure="Heure (0-23)", minute="Minute (0-59)",)
    async def timestamp(self, interaction: discord.Interaction, jour: app_commands.Range[int, 1, 31], mois: app_commands.Range[int, 1, 12], annee: app_commands.Range[int, 2020, 2099], heure: app_commands.Range[int, 0, 23] = 0, minute: app_commands.Range[int, 0, 59] = 0) -> None:
        
        # 🛡️ Vérification ban utilisateur.
        if not await verifier_ban_utilisateur(interaction):
            return

        # 🕒 Defer.
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # ⚙️ Vérification maintenance.
        if not await verifier_commande(interaction, "timestamp"):
            return

        # 📊 Tracking.
        await tracker_commande(interaction, "timestamp")

        # 🧮 Calcul timestamp.
        try:
            dt = datetime(annee, mois, jour, heure, minute, tzinfo=PARIS_TZ)
            ts = int(dt.timestamp())

            formats = [
                ("Date courte", f"<t:{ts}:d>", "d"),
                ("Date longue", f"<t:{ts}:D>", "D"),
                ("Heure courte", f"<t:{ts}:t>", "t"),
                ("Heure longue", f"<t:{ts}:T>", "T"),
                ("Date + heure courte", f"<t:{ts}:f>", "f"),
                ("Date + heure longue", f"<t:{ts}:F>", "F"),
                ("Relatif", f"<t:{ts}:R>", "R"),
            ]

            lignes = [f"**Timestamp Unix** : `{ts}`\n"]
            for label, rendu, code in formats:
                lignes.append(f"**{label}** ({code}) : {rendu}\n`<t:{ts}:{code}>`")

            await interaction.followup.send(
                view=info_container("\n\n".join(lignes)),
                ephemeral=True,
            )

        except ValueError as e:
            await interaction.followup.send(
                view=error_container(f"Date invalide : `{e}`"),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.followup.send(
                view=error_container(f"Erreur : `{e}`"),
                ephemeral=True,
            )


    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @timestamp.error
    async def timestamp_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        await handle_app_command_error(interaction, error)


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Timestamp(bot))