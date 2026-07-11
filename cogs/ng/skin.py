"""
Commande /ng skin — Statistiques des serveurs NationsGlory.
"""

import logging

import discord
from discord import app_commands, Interaction, ButtonStyle, MediaGalleryItem
from discord.ui import LayoutView, Container, TextDisplay, Button, Separator, Section, ActionRow, MediaGallery

from utils.control_admin import verifier_commande
from utils.botbancmd import verifier_ban_utilisateur
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error

from utils.fullskin import get_all_skins

log = logging.getLogger(__name__)

# ============================================================
# 🧩 Création de l'interface
# ============================================================

async def create_skin_view(pseudo: str, mode: str = "corps_3d") -> LayoutView:

    view = LayoutView(timeout=1000)
    container = Container()
    skins = get_all_skins(pseudo)

    titles = {
        "tete_2d": "Tête (2D)",
        "tete_3d": "Tête (3D)",
        "corps_2d": "Corps (2D)",
        "corps_3d": "Corps (3D)"
    }

    container.add_item(TextDisplay(f"# <:skin:1495443741287256206> Skin de {pseudo}"))
    container.add_item(Separator())
    container.add_item(TextDisplay(f"-# Affichage : **{titles.get(mode)}**"))

    container.add_item(
        MediaGallery(
            MediaGalleryItem(skins[mode])
        )
    )

    container.add_item(Separator())

    nav_row = ActionRow()
    modes_config = [
        ("👤 Corps 3D", "corps_3d"),
        ("👤 Corps 2D", "corps_2d"),
        ("🎭 Tête 3D", "tete_3d"),
        ("🎭 Tête 2D", "tete_2d"),
    ]

    for label, m in modes_config:
        is_active = (mode == m)
        btn = Button(
            label=label,
            style=ButtonStyle.primary if is_active else ButtonStyle.secondary,
            disabled=is_active
        )

        async def make_callback(target_mode=m):
            async def callback(inter: Interaction):
                try:
                    new_view = await create_skin_view(pseudo, target_mode)
                    await inter.response.edit_message(content=None, view=new_view)
                except Exception as e:
                    log.error(
                        "Erreur bouton navigation skin (pseudo=%s, mode=%s): %s",
                        pseudo, target_mode, e, exc_info=True,
                    )
            return callback

        btn.callback = await make_callback(m)
        nav_row.add_item(btn)

    container.add_item(nav_row)
    container.add_item(Separator())

    download_btn = Button(
        label="Télécharger",
        style=ButtonStyle.link,
        url=skins[mode],
        emoji="📥"
    )

    container.add_item(Section(
        TextDisplay(f"**{titles.get(mode)}**\n-# Télécharger ce rendu"),
        accessory=download_btn
    ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🧮 Commande principale : /ng skin
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 3)
@app_commands.command(name="skin", description="🧥 Récupère le skin d'un joueur NationsGlory")
@app_commands.describe(pseudo="Pseudo EXACT du joueur dans NationsGlory")
async def skin(interaction: discord.Interaction, pseudo: str):

    # 🔒 Vérification ban bot.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer()
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ng_skin"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ng_skin")

    # 🧩 Création et envoi de l'interface.
    try:
        view = await create_skin_view(pseudo, mode="corps_3d")
        await interaction.followup.send(view=view)

    except Exception as e:
        log.error("Erreur création vue skin (pseudo=%s): %s", pseudo, e, exc_info=True)
        await interaction.followup.send(
            view=error_container(f"Impossible d'envoyer l'interface : `{e}`"),
            ephemeral=True
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@skin.error
async def skin_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await handle_app_command_error(interaction, error)