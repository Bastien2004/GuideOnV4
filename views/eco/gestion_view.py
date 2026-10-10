"""
views/eco/gestion_view.py — Interface de gestion du solde d'un membre (/eco gestion).
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.container_universel import error_container
from utils.perm_admin import is_admin
from utils.managers.eco_manager import (
    admin_add,
    admin_remove,
    format_amount,
    get_balance,
    get_transaction_history,
)

from views._components.base_view import BaseLayoutView

log = logging.getLogger(__name__)

MAX_GESTION_AMOUNT = 1_000_000_000
HISTORY_PREVIEW_LIMIT = 3

_TYPE_LABELS = {
    "daily": ("Daily", "🎁"),
    "admin_add": ("Ajout admin", "<:plus:1495444111505752154>"),
    "admin_remove": ("Retrait admin", "<:moins:1508532114465882285>"),
}


# ============================================================
# 📑 Fonctions (UI)
# ============================================================

def _format_history_line(entry: dict) -> str:
    label, emoji = _TYPE_LABELS.get(entry["type"], (entry["type"], "•"))
    amount = entry["amount"]
    sign = "+" if amount >= 0 else ""
    actor = f" · par <@{entry['actor_id']}>" if entry.get("actor_id") else ""
    reason = f" — _{entry['reason']}_" if entry.get("reason") else ""
    return f"-# {emoji} {label} : **{sign}{format_amount(amount)}**{actor}{reason}"


# ============================================================
# 🧩 Construction de l'interface
# ============================================================

async def create_gestion_view(
    guild_id: int, target_id: int, bot, author_id: Optional[int] = None
) -> Optional[BaseLayoutView]:
    """Construction de l'interface de gestion du solde d'un membre."""

    guild = bot.get_guild(guild_id)
    if guild is None:
        log.error("[ECO] Guild %s introuvable dans le cache", guild_id)
        return None

    target = guild.get_member(target_id)
    target_display = target.mention if target else f"`utilisateur {target_id}`"

    balance = await get_balance(guild_id, target_id)
    history = await get_transaction_history(guild_id, target_id, limit=HISTORY_PREVIEW_LIMIT)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    container.add_item(TextDisplay("# <:investment:1558435075698327562> Gestion Économie"))
    container.add_item(Separator())

    container.add_item(TextDisplay(
        f"### 📊 Solde {target_display} :\n"
        f"-# ⇝ Solde actuel : **{format_amount(balance['balance'])}**"
    ))
    container.add_item(Separator())

    if history:
        container.add_item(TextDisplay(
            "### 🧾 __Dernières actions__ :\n" + "\n".join(_format_history_line(h) for h in history)
        ))
        container.add_item(Separator())

    btn_add = Button(label="Ajouter", style=ButtonStyle.success, emoji="<:plus:1495444111505752154>")
    btn_add.callback = _cb_modify(guild_id, target_id, bot, author_id, add=True)

    btn_remove = Button(label="Retirer", style=ButtonStyle.secondary, emoji="<:moins:1508532114465882285>")
    btn_remove.callback = _cb_modify(guild_id, target_id, bot, author_id, add=False)

    container.add_item(ActionRow(btn_add, btn_remove))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 📑 CallBack
# ============================================================

def _guard(author_id: Optional[int]):
    """Sécurisation des boutons (auteur + admin)."""
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'**auteur** de la commande peut utiliser ce __menu__."),
                ephemeral=True,
            )
            return False
        if not is_admin(interaction):
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur** pour effectuer cette action."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, target_id: int, bot, author_id):
    """Met à jour l'interface."""
    new_view = await create_gestion_view(guild_id, target_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur **introuvable**."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


class EcoAmountReasonModal(discord.ui.Modal):
    """Saisie du montant (+ raison optionnelle) pour /eco gestion.

    Même convention que EditContainerModal/AddButtonModal (medialink) :
    plusieurs TextInput sur un seul discord.ui.Modal, pas besoin d'étendre
    le TextModal générique (1 seul champ) pour ce cas précis.
    """

    def __init__(self, *, title: str, on_submit_amount) -> None:
        super().__init__(title=title)
        self._on_submit_amount = on_submit_amount

        self.amount_input = discord.ui.TextInput(
            label="Montant ($)",
            placeholder="Ex : 500",
            min_length=1,
            max_length=10,
            required=True,
        )
        self.reason_input = discord.ui.TextInput(
            label="Raison (optionnelle)",
            placeholder="Ex : récompense event Halloween",
            style=discord.TextStyle.short,
            required=False,
            max_length=200,
        )
        self.add_item(self.amount_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self._on_submit_amount(interaction, self.amount_input.value, self.reason_input.value)


def _cb_modify(guild_id, target_id, bot, author_id, *, add: bool):
    """Gère les boutons d'ajout et de retrait d'argent."""

    check = _guard(author_id)
    action_label = "Ajouter" if add else "Retirer"

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return

        async def on_submit(inter: Interaction, raw_amount: str, raw_reason: str):
            raw_amount = raw_amount.strip()
            try:
                n = int(raw_amount)
            except ValueError:
                await inter.response.send_message(
                    view=error_container("Le __montant__ doit être un **nombre entier**."),
                    ephemeral=True,
                )
                return
            if n <= 0:
                await inter.response.send_message(
                    view=error_container("Le montant doit être **strictement positif**."),
                    ephemeral=True,
                )
                return
            if n > MAX_GESTION_AMOUNT:
                await inter.response.send_message(
                    view=error_container(
                        f"Le montant doit être **inférieur ou égal à {format_amount(MAX_GESTION_AMOUNT)}**."
                    ),
                    ephemeral=True,
                )
                return

            reason = raw_reason.strip() or None
            if add:
                await admin_add(guild_id, target_id, n, actor_id=inter.user.id, reason=reason)
            else:
                # Pas d'erreur si n > solde dispo : admin_remove() clampe à 0
                # (pas de dette en V1, cf. utils.managers.eco_manager).
                await admin_remove(guild_id, target_id, n, actor_id=inter.user.id, reason=reason)
            await _rerender(inter, guild_id, target_id, bot, author_id)

        modal = EcoAmountReasonModal(title=f"{action_label} de l'argent", on_submit_amount=on_submit)
        await interaction.response.send_modal(modal)
    return cb


# ============================================================
# 🧩 Class principale
# ============================================================

class EcoGestionView:

    @classmethod
    async def create(cls, guild_id: int, target_id: int, author_id: int, bot) -> BaseLayoutView:
        view = await create_gestion_view(guild_id, target_id, bot, author_id)

        if view is None:
            return error_container("**Impossible** de charger l'interface de __gestion__.")
        return view
