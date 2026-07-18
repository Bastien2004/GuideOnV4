"""
utils/guild_info.py — Détection des modules configurés et dérivation des
informations bot (date d'ajout, permissions) pour un serveur, extrait de
cogs/dev/guild_info.py — même traitement que utils/alpha_rank_logic.py /
utils/delete_message.py.
"""
from __future__ import annotations

from dataclasses import dataclass

import discord

from utils.managers.alpha_rank_config_manager import get_rank_config_obj
from utils.managers.ticket_manager import list_panels
from utils.managers.birthday_manager import load_birthday_config
from utils.managers.alpha_nota_manager import load_nota_config


@dataclass
class GuildInfoData:
    """Informations dérivées (hors champs bruts de discord.Guild), prêtes
    pour views/dev/guild_info_view.py."""
    bot_joined_at: str
    modules: dict[str, bool]
    bot_perms_label: str


# ============================================================
# 📁 Détection des modules configurés
# ============================================================

async def detect_modules(guild_id: int) -> dict[str, bool]:
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


# ============================================================
# 🔍 Orchestration — extrait de cogs/dev/guild_info.py
# ============================================================

async def gather_guild_info(guild: discord.Guild) -> GuildInfoData:
    """Rassemble les informations dérivées nécessaires à l'affichage : date
    d'ajout du bot, permissions du bot sur ce serveur, modules détectés."""

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
    modules = await detect_modules(guild.id)

    return GuildInfoData(
        bot_joined_at=bot_joined_at,
        modules=modules,
        bot_perms_label=bot_perms_label,
    )