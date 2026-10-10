"""
views/eco/config_view.py — Interface de configuration du système d'économie (/eco config).
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Container, Section, Separator, TextDisplay

from utils.container_universel import error_container
from utils.perm_admin import is_admin
from utils.managers.eco_manager import format_amount, load_eco_config, save_eco_config

from views._components.base_view import BaseLayoutView
from views._components.text_modal import TextModal

log = logging.getLogger(__name__)

MAX_DAILY_AMOUNT = 1_000_000


# ============================================================
# 📑 Fonctions (UI)
# ============================================================

def _state_btn(active: bool) -> Button:
    """Gestion bouton d'état ON/OFF."""
    return Button(
        label="Activé" if active else "Désactivé",
        style=ButtonStyle.success if active else ButtonStyle.danger,
        emoji="<:valider:1495444292867723284>" if active else "<:annuler:1495444256754761979>",
    )


# ============================================================
# 🧩 Construction de l'interface
# ============================================================

async def create_eco_config_view(guild_id: int, bot, author_id: Optional[int] = None) -> Optional[BaseLayoutView]:
    """Construit l'interface de configuration."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[ECO] Guild %s introuvable dans le cache", guild_id)
        return None

    cfg = await load_eco_config(guild_id)
    daily_amount = cfg.get("daily_amount", 200)
    leaderboard_enabled = cfg.get("leaderboard_enabled", True)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay("# 💰 Configuration Économie"))
    container.add_item(Separator())

    btn_daily = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
    btn_daily.callback = _cb_edit_daily_amount(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**🎁 Montant du /eco daily**\n-# Somme reçue par réclamation (cooldown de 24h).\n"
            f"-# Actuel : **{format_amount(daily_amount)}**"
        ),
        accessory=btn_daily,
    ))
    container.add_item(Separator())

    btn_lb = _state_btn(leaderboard_enabled)
    btn_lb.callback = _cb_toggle_leaderboard(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**🏆 Classement (/eco leaderboard)**\n"
            "-# Autorise ou masque le classement des soldes sur ce serveur."
        ),
        accessory=btn_lb,
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 CallBack
# ============================================================

def _guard(author_id: Optional[int]):
    """Vérification auteur + administrateur."""
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** de la commande peut utiliser ce __menu__."),
                ephemeral=True,
            )
            return False
        if not is_admin(interaction):
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur** pour effectuer cette **action**."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    """Met à jour l'interface."""
    new_view = await create_eco_config_view(guild_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_toggle_leaderboard(guild_id, bot, author_id):
    """Gère le bouton d'activation du leaderboard."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_eco_config(guild_id)).get("leaderboard_enabled", True)
        await save_eco_config(guild_id, {"leaderboard_enabled": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_edit_daily_amount(guild_id, bot, author_id):
    """Gère le bouton d'édition du montant du /eco daily."""
    check = _guard(author_id)
    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        current = (await load_eco_config(guild_id)).get("daily_amount", 200)

        async def on_submit(inter: Interaction, value: str):
            value = value.strip()
            try:
                n = int(value)
            except ValueError:
                await inter.response.send_message(
                    view=error_container("Le montant doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n <= 0:
                await inter.response.send_message(
                    view=error_container("Le montant doit être **strictement positif**."),
                    ephemeral=True,
                )
                return
            if n > MAX_DAILY_AMOUNT:
                await inter.response.send_message(
                    view=error_container(
                        f"Le montant doit être **inférieur ou égal à {format_amount(MAX_DAILY_AMOUNT)}**."
                    ),
                    ephemeral=True,
                )
                return
            await save_eco_config(guild_id, {"daily_amount": n})
            await _rerender(inter, guild_id, bot, author_id)

        modal = TextModal(
            title="🎁 Montant du /eco daily",
            label="Montant ($)",
            placeholder="Ex : 200",
            default=str(current),
            min_length=1,
            max_length=9,
            style=discord.TextStyle.short,
            on_submit=on_submit,
        )
        await interaction.response.send_modal(modal)
    return cb


# ============================================================
# 🧩 Class principale
# ============================================================

class EcoConfigView:
    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot):
        view = await create_eco_config_view(guild_id, bot, author_id)

        if view is None:
            return error_container("**Impossible** de charger la __configuration__ (serveur introuvable).")
        return view
