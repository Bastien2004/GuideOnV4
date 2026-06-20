"""
cogs/dev/guild_info.py — Informations détaillées sur un serveur où GuideOn est présent.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

from utils.managers.alpha_rank_config_manager import get_rank_config_obj
from utils.managers.ticket_manager import list_panels
from utils.managers.birthday_manager import load_birthday_config
from utils.managers.alpha_nota_manager import load_nota_config

log = logging.getLogger(__name__)


# ============================================================
# 📁  Fonctions utilitaires
# ============================================================

def _check(ok: bool) -> str:
    return "✓" if ok else "✗"


async def _detect_modules(guild_id: int) -> dict[str, bool]:
    """Détecte quels modules sont configurés/activés pour cette guild."""
    alpha_cfg = await get_rank_config_obj(guild_id)
    panels = await list_panels(guild_id)
    birthday_cfg = await load_birthday_config(guild_id)
    nota_cfg = await load_nota_config(guild_id)

    return {
        "Alpha": alpha_cfg is not None,
        "Tickets": len(panels) > 0,
        "Anniversaires": bool(birthday_cfg.get("enabled")),
        "Notations": bool(nota_cfg.get("enabled")),
    }


def _build_guild_info_view(
    guild: discord.Guild,
    *,
    bot_joined_at: str,
    modules: dict[str, bool],
    bot_perms_label: str,
) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 🏠 Informations Serveur"))
    c.add_item(Separator())

    owner_mention = f"<@{guild.owner_id}>" if guild.owner_id else "*Inconnu*"

    c.add_item(TextDisplay(
        f"**Nom :**\n{guild.name}\n\n"
        f"**ID :**\n`{guild.id}`\n\n"
        f"**Propriétaire :**\n{owner_mention}\n\n"
        f"**Membres :**\n{guild.member_count or 0}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Créé :**\n{discord.utils.format_dt(guild.created_at, style='D')}\n\n"
        f"**Ajout du bot :**\n{bot_joined_at}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Salons :**\n{len(guild.channels)}\n\n"
        f"**Rôles :**\n{len(guild.roles)}\n\n"
        f"**Boost :**\nNiveau {guild.premium_tier} ({guild.premium_subscription_count} boosts)"
    ))
    c.add_item(Separator())

    modules_lines = "\n".join(f"{_check(v)} {name}" for name, v in modules.items())
    c.add_item(TextDisplay(f"**Modules :**\n{modules_lines}"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Bot Permissions :**\n{bot_perms_label}\n\n"
        f"**Shard :**\n{guild.shard_id if guild.shard_id is not None else 0}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view


# ════════════════════════════════════════════════════════════
# 🧭 Commande : /dev guild_info
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="guild_info", description="🏠 [DEV] Informations détaillées sur un serveur")
@app_commands.describe(id_serveur="ID du serveur cible")
async def guild_info(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "consulter les **informations** d'un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_guild_info"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_guild_info")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."),
            ephemeral=True,
        )

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."),
            ephemeral=True,
        )

    # ── Date d'ajout du bot ────────────────────────────────────
    bot_joined_at = (
        discord.utils.format_dt(guild.me.joined_at, style="D")
        if guild.me and guild.me.joined_at
        else "*Inconnue*"
    )

    # ── Permissions du bot ──────────────────────────────────────
    if guild.me is not None:
        perms = guild.me.guild_permissions
        bot_perms_label = "✓ Administrator" if perms.administrator else f"`{perms.value}` (pas Administrator)"
    else:
        bot_perms_label = "*Indisponible*"

    # ── Modules détectés ──────────────────────────────────────
    modules = await _detect_modules(guild.id)

    view = _build_guild_info_view(
        guild,
        bot_joined_at=bot_joined_at,
        modules=modules,
        bot_perms_label=bot_perms_label,
    )

    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@guild_info.error
async def guild_info_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)