"""
cogs/alpha/stafflist.py — Gère l'affichage de la liste du staff Alpha.
"""

from __future__ import annotations

import logging
import discord
from discord import app_commands, Interaction
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha

from utils.managers.alpha_staff_manager import list_staff
from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message
from utils.db.models.alpha_staff import GRADES_ORDER, GRADE_LABELS, GRADE_EMOJIS

log = logging.getLogger(__name__)

MESSAGE_KEY = "stafflist"


# ============================================================
# 🧩 Création de l'interface
# ============================================================

def build_stafflist_view(members: list[dict]) -> LayoutView:
    view = LayoutView(timeout=None)

    # ── Header ────────────────────────────────────────────────
    header = Container()
    header.add_item(TextDisplay("# <:AlphaStaff:1493512964337307698> Effectif Staff Alpha"))
    view.add_item(header)

    # ── Un Container par grade présent ────────────────────────
    for grade in GRADES_ORDER:
        grade_members = [m for m in members if m["grade"] == grade]
        if not grade_members:
            continue

        emoji = GRADE_EMOJIS.get(grade, "•")
        label = GRADE_LABELS.get(grade, grade.replace("_", " ").title())

        c = Container()
        c.add_item(TextDisplay(f"## {emoji} {label}"))
        c.add_item(Separator())

        block = ""
        for m in grade_members:
            block += (
                f"{m['skin_head_emoji']} "
                f"**{m['pseudo_jeu']}** — <@{m['discord_id']}> — `{m['discord_id']}`\n"
            )

        c.add_item(TextDisplay(block.rstrip()))
        c.add_item(Separator())
        view.add_item(c)

    # ── Footer ────────────────────────────────────────────────
    footer = Container()
    footer.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(footer)

    return view


# ============================================================
# 🔄 Fonction de mise à jour (réutilisable par d'autres commandes) 
# ============================================================

async def refresh_staff_message(bot: discord.Client, guild_id: int) -> None:
    """Rafraîchit la liste des staffs depuis la DB."""

    cfg = await load_rank_config(guild_id)
    channel_id = cfg.get("content_stafflist_channel_id")
    if not channel_id:
        log.warning("[STAFFLIST ALPHA] Refresh_staff_message : salon non configuré pour guild=%d", guild_id)
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            log.warning("[STAFFLIST ALPHA] Refresh_staff_message : salon %d introuvable", channel_id)
            return

    members = await list_staff()
    view = build_stafflist_view(members)

    cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None

    if cfg and cfg.message_id:
        try:
            existing = await channel.fetch_message(cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing:
            await existing.edit(view=view)
        else:
            sent = await channel.send(view=view)
            await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)
    except discord.HTTPException:
        log.exception("[STAFFLIST ALPHA] Refresh_staff_message : erreur HTTP | guild=%d", guild_id)


# ============================================================
# 🧭 Commande : /alpha stafflist
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="stafflist", description="📋 Crée ou met à jour la liste du staff Alpha")
async def stafflist(interaction: Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission OP Alpha.
    if not await check_op_alpha(interaction, "**créer** ou **mettre à jour** la liste du staff"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_stafflist"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_stafflist")

    # 📋 Récupèration de la configuration.
    rank_cfg = await load_rank_config(interaction.guild_id)
    channel_id = rank_cfg.get("content_stafflist_channel_id")
    if not channel_id:
        return await interaction.followup.send(
            view=error_container(
                "Le salon n'est pas configuré.\n"
                "Utilisez `/dev config_alpha` → **Contenu Discord** pour le définir."
            ),
            ephemeral=True,
        )

    # 💻 Récupération du salon
    channel = interaction.client.get_channel(channel_id)
    if channel is None:
        try:
            channel = await interaction.client.fetch_channel(channel_id)
        except (discord.NotFound, discord.HTTPException):
            return await interaction.followup.send(
                view=error_container("Salon **introuvable** (ID invalide ou bot sans accès)."),
                ephemeral=True,
            )

    guild_id = interaction.guild_id
    members = await list_staff()
    view = build_stafflist_view(members)

    # 🔍 Récupération message existant
    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None

    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    # 🚀 Édition ou création
    try:
        if existing:
            await existing.edit(view=view)
            return await interaction.followup.send(
                view=success_container(f"Liste du staff **mise à jour** dans {channel.mention} !"),
                ephemeral=True,
            )

        sent = await channel.send(view=view)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)
        return await interaction.followup.send(
            view=success_container(f"Liste du staff **créée** dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[STAFFLIST ALPHA] Erreur /alpha stafflist | guild=%s", guild_id)
        return await interaction.followup.send(
            view=error_container("Une erreur Discord est survenue."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@stafflist.error
async def stafflist_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)