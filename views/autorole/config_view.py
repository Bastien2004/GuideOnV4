"""
views/autorole/config_view.py — Interface /config autorole (V4, full CV2).

Porté de la V3 (views/AutoRoleView.py). Page unique, 100% Components V2
(LayoutView + Container + TextDisplay + Section + Separator + ActionRow).
AUCUN embed.

Fonctionnalités (fidèles V3) :
- Toggle ON/OFF du système.
- 3 slots de rôles. Slot 3 réservé Gold+ (verrouillé sinon → send_gold_error).
- Saisie par modal d'ID de rôle, avec validations (existe, sous le bot dans la
  hiérarchie, pas default/bot/integration).
- Bouton « Retirer le rôle » par slot configuré.

Améliorations V4 :
- Builder async branché sur autorole_manager (cache + DB).
- Garde author_id + Administrateur (sécurité : seul l'auteur de la commande agit).

Compat cog : create_autorole_view(guild_id, bot, author_id) -> LayoutView | None
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import (
    ActionRow,
    Button,
    Container,
    LayoutView,
    Modal,
    Section,
    Separator,
    TextDisplay,
    TextInput,
)

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.container_universel import error_container
from utils.managers.autorole_manager import (
    load_autorole_config,
    save_autorole_config,
)

log = logging.getLogger(__name__)

# (numéro de slot, emoji, label, gold_only)
SLOT_CONFIG = [
    (1, "🎯", "Rôle automatique 1", False),
    (2, "🎯", "Rôle automatique 2", False),
    (3, "⭐", "Rôle automatique 3", True),  # Gold uniquement
]

DOC_URL = "https://guideonbot.guideon.dev/"


# ======================================================
# ==================== BUILDER =========================
# ======================================================

async def create_autorole_view(
    guild_id: int, bot, author_id: Optional[int] = None
) -> Optional[LayoutView]:
    """Construit la vue de config autorole pour un serveur (ou None si introuvable)."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        return None

    cfg = await load_autorole_config(guild_id)
    gold = is_gold(guild_id)

    view = LayoutView(timeout=600)
    container = Container()
    container.add_item(TextDisplay("# 🎭 Configuration Auto-Rôle"))
    container.add_item(Separator())

    # ── Toggle ON/OFF ──
    enabled = cfg.get("auto_role_active", False)
    toggle_btn = Button(
        label="✅ Activé" if enabled else "❌ Désactivé",
        style=ButtonStyle.success if enabled else ButtonStyle.danger,
    )
    toggle_btn.callback = _cb_toggle(guild_id, bot, author_id)
    container.add_item(Section(
        TextDisplay(
            "**🔘 Statut du système**\n"
            "-# Active ou désactive l'attribution automatique de rôles à l'arrivée"
        ),
        accessory=toggle_btn,
    ))
    container.add_item(Separator())

    # ── Slots ──
    for slot_num, emoji, label, gold_only in SLOT_CONFIG:
        key = f"role_id_{slot_num}"
        role_id = cfg.get(key)
        role = guild.get_role(role_id) if role_id else None

        if gold_only and not gold:
            # Slot Gold verrouillé
            lock_btn = Button(label="Gold+ requis", style=ButtonStyle.secondary, emoji="🔒")
            lock_btn.callback = _cb_gold_lock(author_id)
            container.add_item(Section(
                TextDisplay(f"**{emoji} {label}** ✨\n-# Réservé aux serveurs Gold+"),
                accessory=lock_btn,
            ))
        else:
            if role:
                role_display = role.mention
            elif role_id:
                role_display = "`⚠️ Rôle supprimé`"
            else:
                role_display = "`Non configuré`"
            gold_hint = " ✨" if gold_only else ""

            set_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="✏️")
            set_btn.callback = _cb_set_role(guild_id, bot, author_id, key)
            container.add_item(Section(
                TextDisplay(f"**{emoji} {label}{gold_hint}**\n-# {role_display}"),
                accessory=set_btn,
            ))

            if role_id:
                remove_btn = Button(
                    label="Retirer le rôle", style=ButtonStyle.danger, emoji="🗑️"
                )
                remove_btn.callback = _cb_remove_role(guild_id, bot, author_id, key)
                container.add_item(ActionRow(remove_btn))

        container.add_item(Separator())

    # ── Footer ──
    container.add_item(ActionRow(Button(
        label="Documentation", style=ButtonStyle.link, url=DOC_URL, emoji="📚"
    )))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideON Studio"))

    view.add_item(container)
    return view


# ======================================================
# ===================== CALLBACKS ======================
# ======================================================

def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'auteur de la commande peut utiliser ce menu."),
                ephemeral=True,
            )
            return False
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."),
                ephemeral=True,
            )
            return False
        return True
    return check


async def _rerender(interaction: Interaction, guild_id: int, bot, author_id):
    new_view = await create_autorole_view(guild_id, bot, author_id)
    if new_view is None:
        await interaction.response.send_message(
            view=error_container("Serveur introuvable."), ephemeral=True
        )
        return
    if interaction.response.is_done():
        await interaction.edit_original_response(view=new_view)
    else:
        await interaction.response.edit_message(view=new_view)


def _cb_toggle(guild_id, bot, author_id):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        current = (await load_autorole_config(guild_id)).get("auto_role_active", False)
        await save_autorole_config(guild_id, {"auto_role_active": not current})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


def _cb_gold_lock(author_id):
    # Pas de garde auteur ici : on informe simplement de la limite Gold.
    async def cb(interaction: Interaction):
        await send_gold_error(interaction)
    return cb


def _cb_set_role(guild_id, bot, author_id, key):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await interaction.response.send_modal(
            SetRoleModal(guild_id, bot, author_id, key)
        )
    return cb


def _cb_remove_role(guild_id, bot, author_id, key):
    check = _guard(author_id)

    async def cb(interaction: Interaction):
        if not await check(interaction):
            return
        await save_autorole_config(guild_id, {key: None})
        await _rerender(interaction, guild_id, bot, author_id)
    return cb


# ======================================================
# ======================= MODAL ========================
# ======================================================

class SetRoleModal(Modal, title="✏️ Définir un rôle automatique"):
    def __init__(self, guild_id: int, bot, author_id: Optional[int], key: str):
        super().__init__()
        self.guild_id = guild_id
        self.bot = bot
        self.author_id = author_id
        self.key = key

        self.role_input = TextInput(
            label="ID du rôle",
            placeholder="Ex : 987654321098765432",
            required=True,
            max_length=20,
        )
        self.add_item(self.role_input)

    async def on_submit(self, interaction: Interaction):
        guild = interaction.guild
        value = self.role_input.value.strip()

        if not value.isdigit():
            return await interaction.response.send_message(
                view=error_container("L'ID doit être un nombre entier."), ephemeral=True
            )

        role = guild.get_role(int(value))
        if not isinstance(role, discord.Role):
            return await interaction.response.send_message(
                view=error_container("Rôle introuvable sur ce serveur."), ephemeral=True
            )

        if role.position >= guild.me.top_role.position:
            return await interaction.response.send_message(
                view=error_container(
                    "Ce rôle est au-dessus ou au même niveau que mon rôle.\n"
                    "-# Placez mon rôle plus haut dans la hiérarchie."
                ),
                ephemeral=True,
            )

        if role.is_default() or role.is_bot_managed() or role.is_integration():
            return await interaction.response.send_message(
                view=error_container(
                    "Ce type de rôle ne peut pas être utilisé "
                    "(rôle par défaut, bot ou intégration)."
                ),
                ephemeral=True,
            )

        await save_autorole_config(self.guild_id, {self.key: role.id})
        await _rerender(interaction, self.guild_id, self.bot, self.author_id)