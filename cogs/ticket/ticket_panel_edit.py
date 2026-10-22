"""
Commande /ticket panel_edit — Permet de modifier un panel de ticket existant.
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
from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.managers import ticket_manager as tm
from views.ticket.panel_picker import build_panel_picker_view
from views.ticket.panel_setup_view import build_edit_ctx, build_setup_view

log = logging.getLogger(__name__)

_MESSAGE_ID_RE = re.compile(r"/(\d+)$")
_ACTION = "**modifier** un __panel de tickets__"


# ============================================================
# 🧭 Commande principale : /ticket panel_edit
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="panel_edit", description="✏️ Modifier un panel de tickets existant")
@app_commands.describe(
    lien_panel="Lien du message panel (optionnel — laissez vide pour choisir dans une liste)"
)
async def ticket_panel_edit(interaction: discord.Interaction, lien_panel: str | None = None) -> None:

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
    if not await verifier_commande(interaction, "ticket_panel_edit"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_panel_edit")


    # 📦 Récupération des données.
    guild_id = interaction.guild_id

    # 🔗 Lien fourni : flux direct (inchangé, juste re-factorisé via build_edit_ctx).
    if lien_panel:
        match = _MESSAGE_ID_RE.search(lien_panel.strip())
        if not match:
            return await interaction.followup.send(
                view=error_container(
                    "__Lien__ de message **invalide**. Copiez le lien **direct** du panel "
                    "(clic droit sur le message → Copier le lien), ou laissez le champ vide "
                    "pour choisir dans une liste."
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

        try:
            view = build_setup_view(interaction.guild, build_edit_ctx(panel))
            await interaction.followup.send(view=view, ephemeral=True)
        except Exception:
            log.exception("**Ouverture** interface `panel_edit` échouée (guild=%s)", guild_id)
            await interaction.followup.send(
                view=error_container("**Impossible** d'ouvrir l'__interface d'édition__."),
                ephemeral=True,
            )
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
        try:
            view = build_setup_view(pick_interaction.guild, build_edit_ctx(panel))
            await pick_interaction.response.edit_message(view=view)
        except Exception:
            log.exception(
                "**Ouverture** interface `panel_edit` (sélecteur) échouée (guild=%s)", guild_id
            )
            await pick_interaction.response.send_message(
                view=error_container("**Impossible** d'ouvrir l'__interface d'édition__."),
                ephemeral=True,
            )

    picker_view = build_panel_picker_view(
        interaction.guild, panels,
        title="✏️ Modifier un panel",
        description="Choisissez le panel à modifier dans la liste.",
        on_pick=on_pick,
    )
    await interaction.followup.send(view=picker_view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_panel_edit.error
async def ticket_panel_edit_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)