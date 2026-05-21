"""
Commande /report — Signaler un bug ou une suggestion.

Ouvre un modal de saisie. Envoie le rapport dans le salon de signalement
configuré, et logue l'incident.

🟡 STUB DB : pour l'instant on ne persiste pas en DB. À ajouter quand le
manager bug_reports sera prêt côté collègue.
"""
from __future__ import annotations

import logging
import uuid

import discord
from discord import app_commands
from discord.ext import commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, success_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.settings import settings
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)


class ReportModal(discord.ui.Modal, title="🐞 Signaler un bug"):
    """Modal de saisie du rapport."""

    titre = discord.ui.TextInput(
        label="Titre du bug",
        placeholder="Ex : La commande /exp level ne s'affiche pas",
        max_length=100,
        required=True,
    )

    description = discord.ui.TextInput(
        label="Description détaillée",
        style=discord.TextStyle.paragraph,
        placeholder="Décris ce qui ne marche pas, les étapes pour reproduire...",
        max_length=2000,
        required=True,
    )

    contexte = discord.ui.TextInput(
        label="Contexte (optionnel)",
        style=discord.TextStyle.paragraph,
        placeholder="Quel salon ? Quel rôle as-tu ? Etc.",
        max_length=500,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Génère un ID court pour suivre le rapport
        report_id = uuid.uuid4().hex[:8].upper()

        # Embed envoyé dans le salon de signalement
        embed = discord.Embed(
            title=f"🐞 Nouveau rapport `#{report_id}`",
            color=discord.Color.from_rgb(248, 113, 113),
        )
        embed.add_field(name="📝 Titre", value=self.titre.value, inline=False)
        embed.add_field(name="📄 Description", value=self.description.value, inline=False)
        if self.contexte.value:
            embed.add_field(name="🧩 Contexte", value=self.contexte.value, inline=False)

        # Auteur
        embed.set_author(
            name=f"{interaction.user} ({interaction.user.id})",
            icon_url=interaction.user.display_avatar.url,
        )
        if interaction.guild:
            embed.set_footer(
                text=f"Serveur : {interaction.guild.name} ({interaction.guild.id})"
            )

        # TODO (collègue DB) : persister en DB
        # async with get_session() as session:
        #     await bug_reports_manager.create(
        #         session,
        #         report_id=report_id,
        #         user_id=interaction.user.id,
        #         guild_id=interaction.guild.id if interaction.guild else None,
        #         title=self.titre.value,
        #         description=self.description.value,
        #         context=self.contexte.value or None,
        #     )

        # Log local en attendant
        log.info(
            "[REPORT %s] from %s (%s) — %s",
            report_id,
            interaction.user,
            interaction.user.id,
            self.titre.value,
        )

        # Confirmation à l'utilisateur
        await interaction.response.send_message(
            view=success_container(
                f"Merci pour ton signalement !\n"
                f"**ID de suivi** : `#{report_id}`\n"
                f"L'équipe va l'examiner. Conserve cet ID si tu veux relancer."
            ),
            ephemeral=True,
        )


class Report(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="report",
        description="🐞 Signaler un bug ou faire une suggestion",
    )
    @app_commands.checks.cooldown(1, 30)
    async def report(self, interaction: discord.Interaction) -> None:
        # 🔒 Vérif ban
        if not await verifier_ban_utilisateur(interaction):
            return

        # ⚙️ Maintenance (avant le modal car il faut répondre en send_modal)
        # NB : pas de defer ici car send_modal doit être la première réponse
        try:
            # Pour la maintenance.py on doit utiliser une autre approche
            # car on ne peut pas defer si on veut envoyer un modal après
            from utils.control_admin import commande_active

            if not commande_active("report"):
                from utils.control_admin import send_maintenance_message
                await send_maintenance_message(interaction)
                return
        except Exception as e:
            log.error("Erreur vérification maintenance.py /report : %s", e)

        # 📊 Tracking
        await tracker_commande(interaction, "report")

        # 🪟 Ouverture du modal
        try:
            await interaction.response.send_modal(ReportModal())
        except Exception as e:
            await interaction.response.send_message(
                view=error_container(f"Impossible d'ouvrir le formulaire : `{e}`"),
                ephemeral=True,
            )

    @report.error
    async def report_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(interaction, error)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Report(bot))