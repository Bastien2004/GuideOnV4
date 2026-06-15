"""
Commande /ticket panel_list — Permet de lister les panel de ticket existant sur un serveur.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande
from utils.control_admin import verifier_commande

from utils.perm_admin import check_admin
from utils.error_handler import handle_app_command_error
from utils.managers import ticket_manager as tm

log = logging.getLogger(__name__)

MAX_PANELS_DISPLAY = 17

# ============================================================
# 🧭 Commande principale : /ticket panel_list
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 15)
@app_commands.command(name="panel_list", description="📋 Lister les panels de tickets du serveur")
async def ticket_panel_list(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Vérification administrateur.
    if not await check_admin(interaction, "**lister** les __panels de tickets__"):
        return
    
    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return
    
    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ticket_panel_list"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "ticket_panel_list")

    # 📦 Récupération des données.
    panels = await tm.list_panels(interaction.guild_id)

    # 🧩 Construction de la view.
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 📋 Liste des panels de tickets"))
    container.add_item(Separator())

    if not panels:
        container.add_item(TextDisplay("*Aucun panel configuré sur ce serveur.*"))
    else:
        shown = panels[:MAX_PANELS_DISPLAY]
        for p in shown:
            title = p.get("title", p["panel_id"])
            created = max(0, p.get("counter", 1) - 1)
            opened = p.get("open_tickets_count", 0)
            treated = p.get("deleted_tickets_count", 0)
            container.add_item(TextDisplay(
                f"**{title}** — `{p['panel_id']}`\n"
                f"📍 Salon : <#{p.get('channel_id', 0)}> | "
                f"📁 Catégorie : <#{p.get('ticket_category_id', 0)}>\n"
                f"🎫 Créés : **{created}** · 🟢 En cours : **{opened}** · "
                f"✅ Traités : **{treated}**"
            ))
            container.add_item(Separator())

        if len(panels) > MAX_PANELS_DISPLAY:
            container.add_item(TextDisplay(
                f"-# … et **{len(panels) - MAX_PANELS_DISPLAY}** autre(s) panel(s) non affiché(s)."
            ))

    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)

    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@ticket_panel_list.error
async def ticket_panel_list_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)