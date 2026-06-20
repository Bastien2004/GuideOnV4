"""
cogs/dev/debug_cmd.py — Outil de diagnostic pour une commande GuideOn.

Combine 3 sources : CommandControl (activée/maintenance, DB), les stats
d'usage (command_stats_daily), et deux registres STATIQUES tenus à la main
ci-dessous (cooldown, permission) — ces deux informations ne sont PAS
stockées en DB (le cooldown est un décorateur en dur par fichier, et le
système de permission dépend de 3 mécanismes différents selon les
commandes : admin Discord natif, permission interne au bot, permission
boutique). Pas d'introspection magique : si une commande est absente d'un
registre, on affiche clairement « Non renseigné(e) » plutôt que de deviner.

Pour ajouter une commande manquante aux registres : édite _COOLDOWNS et/ou
_PERMISSIONS ci-dessous.
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

from utils.managers.command_toggle_manager import get_all_commands
from utils.managers.command_stats_manager import (
    get_command_last_used,
    get_command_today_count,
    get_command_total,
)

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# 📋 Registre statique — cooldowns
# ════════════════════════════════════════════════════════════
# Extrait depuis les décorateurs @app_commands.checks.cooldown(rate, per)
# de chaque fichier au moment de l'écriture de cette commande. À tenir à
# jour manuellement si un cooldown change — pas de lecture dynamique
# possible (discord.py ne stocke pas rate/per comme attribut lisible).
_COOLDOWNS: dict[str, tuple[int, int]] = {
    "alpha_derank": (1, 10),
    "alpha_event_list": (1, 10),
    "alpha_event_regle": (1, 10),
    "alpha_event_start": (1, 10),
    "alpha_index": (1, 20),
    "alpha_nous_rejoindre": (1, 20),
    "alpha_rank": (1, 10),
    "alpha_regle_interne": (1, 20),
    "alpha_stafflist": (1, 10),
    "alpha_test": (1, 10),
    "birthday_add": (1, 15),
    "birthday_config": (1, 10),
    "birthday_list": (1, 10),
    "birthday_next": (1, 10),
    "config_autorole": (1, 10),
    "config_bienvenue": (1, 10),
    "config_role_all": (1, 15),
    "config_role_reaction": (1, 10),
    "dev_config_alpha": (1, 5),
    "dev_debug_cmd": (1, 10),
    "dev_delete_message": (1, 10),
    "dev_edit_stafflist_alpha": (1, 5),
    "dev_guild_info": (1, 10),
    "dev_health": (1, 10),
    "dev_join_serv": (1, 10),
    "dev_kick": (1, 10),
    "dev_maintenance": (1, 10),
    "dev_permissions": (1, 10),
    "dev_stat_cmd": (1, 10),
    "dev_stat_server": (1, 10),
    "giveaway_blacklist": (1, 5),
    "giveaway_create": (1, 10),
    "giveaway_list": (1, 5),
    "giveaway_manage": (1, 5),
    "id_command": (1, 10),
    "info": (1, 10),
    "invite_classement": (1, 10),
    "invite_config": (1, 15),
    "invite_gestion": (1, 10),
    "invite_user": (1, 5),
    "ng_autel": (1, 10),
    "ng_claim": (1, 10),
    "ng_classement": (1, 10),
    "ng_convert": (1, 10),
    "ng_country": (1, 10),
    "ng_dynmaps": (1, 10),
    "ng_info": (1, 10),
    "ng_lvl": (1, 10),
    "ng_mmr": (1, 10),
    "ng_onu": (1, 10),
    "ng_pillage": (1, 10),
    "ng_profil": (1, 10),
    "ng_rd": (1, 10),
    "ng_sanction": (1, 10),
    "ng_serveur_stat": (1, 10),
    "ng_skin": (1, 3),
    "ng_version": (1, 10),
    "ping_command": (1, 10),
    "report": (1, 10),
    "ticket_add": (1, 10),
    "ticket_ban": (1, 15),
    "ticket_close": (1, 10),
    "ticket_delete": (1, 10),
    "ticket_panel_create": (1, 15),
    "ticket_panel_delete": (1, 15),
    "ticket_panel_edit": (1, 10),
    "ticket_panel_list": (1, 15),
    "ticket_remove": (1, 10),
    "ticket_rename": (1, 10),
    "ticket_unban": (1, 15),
    "ticket_wakeup": (1, 10),
    "timestamp_command": (1, 10),
    "wiki": (1, 5),
}


# ════════════════════════════════════════════════════════════
# 📋 Registre statique — permissions
# ════════════════════════════════════════════════════════════
# type ∈ {"discord_admin", "interne", "boutique", "aucune"}
#   discord_admin : permission Administrator Discord native (groupe CONFIG)
#   interne       : permission interne au bot, voir utils.permission /
#                   utils.perm_dev / utils.perm_alpha (DEV → DEV,
#                   ALPHA → OP_ALPHA, etc.)
#   boutique      : palier boutique du bot (ex: Gold+, VIP)
#   aucune        : pas de restriction (commande publique)
# detail : libellé affiché (rôle interne, palier boutique...), None si non
#          pertinent (ex: "aucune").
#
# Dérivé par groupe à l'écriture de cette commande (CONFIG → discord_admin,
# DEV → interne/DEV, ALPHA → interne/OP_ALPHA, NG → aucune). Le reste
# (BIRTHDAY, GIVEAWAY, INVITE, TICKET, commandes globales) est volontairement
# laissé "Non renseigné" — à compléter manuellement.
_PERMISSIONS: dict[str, tuple[str, str | None]] = {
    # ── ALPHA → interne, OP_ALPHA ──
    "alpha_derank": ("interne", "OP_ALPHA"),
    "alpha_event_list": ("interne", "OP_ALPHA"),
    "alpha_event_regle": ("interne", "OP_ALPHA"),
    "alpha_event_start": ("interne", "OP_ALPHA"),
    "alpha_index": ("interne", "OP_ALPHA"),
    "alpha_nous_rejoindre": ("interne", "OP_ALPHA"),
    "alpha_rank": ("interne", "OP_ALPHA"),
    "alpha_regle_interne": ("interne", "OP_ALPHA"),
    "alpha_stafflist": ("interne", "OP_ALPHA"),
    "alpha_test": ("interne", "OP_ALPHA"),
    # ── CONFIG → Administrator Discord ──
    "config_autorole": ("discord_admin", "Administrateur (Discord)"),
    "config_bienvenue": ("discord_admin", "Administrateur (Discord)"),
    "config_role_all": ("discord_admin", "Administrateur (Discord)"),
    "config_role_reaction": ("discord_admin", "Administrateur (Discord)"),
    # ── DEV → interne, DEV ──
    "dev_config_alpha": ("interne", "DEV"),
    "dev_debug_cmd": ("interne", "DEV"),
    "dev_delete_message": ("interne", "DEV"),
    "dev_edit_stafflist_alpha": ("interne", "DEV"),
    "dev_guild_info": ("interne", "DEV"),
    "dev_health": ("interne", "DEV"),
    "dev_join_serv": ("interne", "DEV"),
    "dev_kick": ("interne", "DEV"),
    "dev_maintenance": ("interne", "DEV"),
    "dev_permissions": ("interne", "DEV"),
    "dev_stat_cmd": ("interne", "DEV"),
    "dev_stat_server": ("interne", "DEV"),
    # ── NG → aucune ──
    "ng_autel": ("aucune", None),
    "ng_claim": ("aucune", None),
    "ng_classement": ("aucune", None),
    "ng_convert": ("aucune", None),
    "ng_country": ("aucune", None),
    "ng_dynmaps": ("aucune", None),
    "ng_info": ("aucune", None),
    "ng_lvl": ("aucune", None),
    "ng_mmr": ("aucune", None),
    "ng_onu": ("aucune", None),
    "ng_pillage": ("aucune", None),
    "ng_profil": ("aucune", None),
    "ng_rd": ("aucune", None),
    "ng_sanction": ("aucune", None),
    "ng_serveur_stat": ("aucune", None),
    "ng_skin": ("aucune", None),
    "ng_version": ("aucune", None),
}

_PERMISSION_TYPE_LABELS = {
    "discord_admin": "Permission Discord",
    "interne": "Permission interne",
    "boutique": "Palier boutique",
    "aucune": "Aucune (publique)",
}


def _format_cooldown(command_name: str) -> str:
    cd = _COOLDOWNS.get(command_name)
    if cd is None:
        return "*Non renseigné*"
    rate, per = cd
    return f"{rate} / {per}s"


def _format_permissions(command_name: str) -> str:
    entry = _PERMISSIONS.get(command_name)
    if entry is None:
        return "*Non renseignée*"
    perm_type, detail = entry
    label = _PERMISSION_TYPE_LABELS.get(perm_type, perm_type)
    if detail:
        return f"{label} — {detail}"
    return label


# ════════════════════════════════════════════════════════════
# 🧩 Construction de la vue
# ════════════════════════════════════════════════════════════

def _build_debug_view(
    command_name: str,
    *,
    enabled: bool,
    total: int,
    today: int,
    last_used_str: str,
) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 🔍 Debug Commande"))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"**Commande :** `{command_name}`"))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Activée :** {'Oui' if enabled else 'Non'}\n"
        f"**Maintenance :** {'Non' if enabled else 'Oui'}\n"
        f"**Cooldown :** {_format_cooldown(command_name)}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(
        f"**Utilisations :**\n"
        f"• Total : {total}\n"
        f"• Aujourd'hui : {today}"
    ))
    c.add_item(Separator())

    c.add_item(TextDisplay(f"**Dernière utilisation :**\n• {last_used_str}"))
    c.add_item(Separator())

    c.add_item(TextDisplay(f"**Permissions :**\n• {_format_permissions(command_name)}"))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(c)
    return view


# ════════════════════════════════════════════════════════════
# 🧭 Commande : /dev debug_cmd
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="debug_cmd", description="🔍 [DEV] Diagnostic complet d'une commande")
@app_commands.describe(commande="Nom interne de la commande (ex: alpha_rank, dev_kick)")
async def debug_cmd(interaction: Interaction, commande: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**debugger** une commande"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_debug_cmd"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_debug_cmd")

    command_name = commande.strip()

    # 🔎 Vérification que la commande existe (connue du système de
    # maintenance OU des registres statiques OU déjà utilisée au moins
    # une fois). Évite de fournir un faux diagnostic pour un nom inventé.
    all_toggles = await get_all_commands()
    total = await get_command_total(command_name)
    known = (
        command_name in all_toggles
        or command_name in _COOLDOWNS
        or command_name in _PERMISSIONS
        or total > 0
    )
    if not known:
        return await interaction.followup.send(
            view=error_container(
                f"Commande `{command_name}` **inconnue** (absente du système de maintenance, "
                f"des registres internes, et jamais utilisée)."
            ),
            ephemeral=True,
        )

    enabled = all_toggles.get(command_name, True)
    today = await get_command_today_count(command_name)
    last_used = await get_command_last_used(command_name)
    last_used_str = last_used.strftime("%d/%m/%Y") if last_used else "*Jamais utilisée*"

    view = _build_debug_view(
        command_name,
        enabled=enabled,
        total=total,
        today=today,
        last_used_str=last_used_str,
    )

    await interaction.followup.send(view=view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@debug_cmd.error
async def debug_cmd_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)