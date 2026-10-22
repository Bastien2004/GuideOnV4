"""
Commande /ticket panel_delete — Permet de supprimer un panel de ticket existant.
"""

from __future__ import annotations

import logging
import re

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_admin import check_admin
from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error

from utils.managers import ticket_manager as tm
from views._components.confirm_view import ConfirmView
from views.ticket.panel_picker import build_panel_picker_view

log = logging.getLogger(__name__)

_MESSAGE_ID_RE = re.compile(r"/(\d+)$")
_ACTION = "**supprimer** un __panel de tickets__"


# ============================================================
# 🧩 Confirmation + suppression (flux direct ET sélecteur)
# ============================================================

async def _confirm_and_delete(interaction: discord.Interaction, guild_id: int, panel: dict, *, fresh: bool) -> None:
    """Affiche la confirmation puis supprime le panel si confirmé.

    `fresh=True` : `interaction` vient du sélecteur (menu déroulant), pas
    encore répondue → la ConfirmView est affichée via `response.send_message`.
    `fresh=False` : `interaction` vient du flux par lien direct, déjà
    deferred plus haut → la ConfirmView est affichée via `followup.send`.
    Dans les deux cas, le message final (succès/annulation) part en
    `followup.send`, ce qui fonctionne après l'un ou l'autre.
    """
    confirm = ConfirmView(
        owner_id=interaction.user.id,
        question=(
            f"Supprimer le panel **{panel['title']}** ?\n"
            "-# Le panel sera supprimé de notre base de données de façon définitive."
        ),
        confirm_label="Supprimer",
    )
    if fresh:
        await interaction.response.send_message(view=confirm, ephemeral=True)
    else:
        await interaction.followup.send(view=confirm, ephemeral=True)
    await confirm.wait()

    if not confirm.confirmed:
        return

    # 🗑️ Suppression du message Discord
    channel = interaction.guild.get_channel(panel.get("channel_id", 0))
    if channel and panel.get("message_id"):
        try:
            msg = await channel.fetch_message(panel["message_id"])
            await msg.delete()
        except (discord.NotFound, discord.HTTPException, discord.Forbidden):
            pass

    # 📂 Suppression DB
    await tm.delete_panel(guild_id, panel["panel_id"])

    await interaction.followup.send(
        view=success_container(f"Le panel **{panel['title']}** a été supprimé."),
        ephemeral=True,
    )


# ============================================================
# 🧭 Commande principale : /ticket panel_delete
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="panel_delete", description="🗑️ Supprimer un panel de tickets")
@app_commands.describe(
    lien_panel="Lien du message panel (optionnel — laissez vide pour choisir dans une liste)"
)
async def ticket_panel_delete(interaction: discord.Interaction, lien_panel: str | None = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification administrateur.
    if not await check_admin(interaction, _ACTION):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_panel_delete"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_panel_delete")

    # 📦 Récupération des données.
    guild_id = interaction.guild_id

    # 🔗 Lien fourni : flux direct (inchangé).
    if lien_panel:
        match = _MESSAGE_ID_RE.search(lien_panel.strip())
        if not match:
            return await interaction.followup.send(
                view=error_container(
                    "__Lien de message__ **invalide**. Copiez le lien **direct** du panel, "
                    "ou laissez le champ vide pour choisir dans une liste."
                ),
                ephemeral=True,
            )
        message_id = int(match.group(1))

        panel = await tm.get_panel_by_message(guild_id, message_id)
        if not panel:
            return await interaction.followup.send(
                view=error_container("**Aucun panel** ne __correspond__ à ce message."),
                ephemeral=True,
            )

        await _confirm_and_delete(interaction, guild_id, panel, fresh=False)
        return

    # 📋 Pas de lien fourni : sélecteur de panel (menu déroulant natif).
    panels = await tm.list_panels(guild_id)
    if not panels:
        return await interaction.followup.send(
            view=error_container("**Aucun panel** n'est configuré sur ce serveur."),
            ephemeral=True,
        )

    async def on_pick(pick_interaction: discord.Interaction, panel: dict) -> None:
        if not await check_admin(pick_interaction, _ACTION):
            return
        await _confirm_and_delete(pick_interaction, guild_id, panel, fresh=True)

    picker_view = build_panel_picker_view(
        interaction.guild, panels,
        title="🗑️ Supprimer un panel",
        description="Choisissez le panel à supprimer dans la liste.",
        on_pick=on_pick,
    )
    await interaction.followup.send(view=picker_view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_panel_delete.error
async def ticket_panel_delete_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)