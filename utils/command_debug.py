"""
utils/command_debug.py — Registres statiques des commandes.
"""

from __future__ import annotations

from dataclasses import dataclass

from utils.managers.command_toggle_manager import get_all_commands
from utils.managers.command_stats_manager import (
    get_command_last_used,
    get_command_today_count,
    get_command_total,
)


# ============================================================
# 📋 Registre statique — cooldowns
# ============================================================

_COOLDOWNS: dict[str, tuple[int, int]] = {
    # ── ALPHA ──
    "alpha_event_list": (1, 10),
    "alpha_event_regle": (1, 15),
    "alpha_event_start": (1, 15),
    "alpha_index": (1, 20),
    "alpha_nous_rejoindre": (1, 20),
    "alpha_regle_interne": (1, 20),
    "alpha_test": (1, 10),
    # ── BIRTHDAY ──
    "birthday_add": (1, 15),
    "birthday_config": (1, 10),
    "birthday_list": (1, 10),
    "birthday_next": (1, 10),
    # ── GLOBALES ──
    "id_cmd": (1, 10),
    "info_cmd": (1, 15),
    "ping_cmd": (1, 10),
    "report_cmd": (1, 10),
    "timestamp_cmd": (1, 10),
    "user_cmd": (1, 10),
    "wiki_cmd": (1, 5),
    # ── CONFIG ──
    "config_auto_fil": (1, 10),
    "config_autorole": (1, 10),
    "config_bienvenue": (1, 10),
    "config_join_to_create": (1, 10),
    "config_role_all": (1, 15),
    "config_role_reaction": (1, 10),
    # ── DELTA ──
    "delta_test": (1, 10),
    # ── DEV ──
    "dev_avatar_bot": (1, 10),
    "dev_botban": (1, 10),
    "dev_command_visibility": (1, 10),
    "dev_database": (1, 10),
    "dev_debug_cmd": (1, 10),
    "dev_delete_message": (1, 10),
    "dev_gold": (1, 10),
    "dev_guild_info": (1, 10),
    "dev_health": (1, 10),
    "dev_join_serv": (1, 10),
    "dev_kick": (1, 10),
    "dev_maintenance": (1, 10),
    "dev_permissions": (1, 10),
    "dev_setngversion": (1, 10),
    "dev_stat_cmd": (1, 10),
    "dev_stat_server": (1, 10),
    "dev_vip": (1, 10),
    # ── ECO ──
    "eco_balance": (1, 10),
    "eco_config": (1, 10),
    "eco_daily": (1, 10),
    "eco_gestion": (1, 10),
    "eco_leaderboard": (1, 10),
    # ── EXP ──
    "exp_config": (1, 15),
    "exp_gestion": (1, 10),
    "exp_info": (1, 10),
    "exp_leaderboard": (1, 10),
    "exp_level": (1, 5),
    # ── GIVEAWAY ──
    "giveaway_blacklist": (1, 10),
    "giveaway_create": (1, 10),
    "giveaway_list": (1, 10),
    "giveaway_manage": (1, 10),
    # ── INVITE ──
    "invite_classement": (1, 10),
    "invite_config": (1, 10),
    "invite_gestion": (1, 10),
    "invite_user": (1, 10),
    # ── IRIS ──
    "iris_reglement": (1, 20),
    "iris_test": (1, 10),
    # ── MEDIALINK ──
    "medialink_config": (1, 10),
    # ── MOD ──
    "config_logs": (1, 10),
    "mod_ban": (1, 10),
    "mod_clear": (1, 10),
    "mod_config": (1, 10),
    "mod_historique": (1, 10),
    "mod_kick": (1, 10),
    "mod_lock": (1, 10),
    "mod_mute": (1, 5),
    "mod_permissions": (1, 10),
    "mod_piege": (1, 10),
    "mod_purge": (1, 10),
    "mod_rename": (1, 10),
    "mod_softban": (1, 10),
    "mod_tempban": (1, 10),
    "mod_unban": (1, 10),
    "mod_unlock": (1, 10),
    "mod_unmute": (1, 10),
    "mod_voice_manage": (1, 10),
    "mod_warn": (1, 5),
    # ── NG ──
    "ng_autel": (1, 10),
    "ng_convert": (1, 10),
    "ng_dynmaps": (1, 10),
    "ng_info": (1, 10),
    "ng_onu": (1, 10),
    "ng_rd": (1, 10),
    "ng_sanction": (1, 10),
    "ng_skin": (1, 3),
    "ng_version": (1, 10),
    # ── NGSTAFF ──
    "ngstaff_config": (1, 5),
    "ngstaff_derank": (1, 10),
    "ngstaff_edit_stafflist": (1, 5),
    "ngstaff_nota_debug": (1, 10),
    "ngstaff_rank": (1, 10),
    "ngstaff_stafflist": (1, 10),
    # ── QR ──
    "qr_generate": (1, 10),
    "qr_list": (1, 10),
    "qr_scan": (1, 10),
    # ── RAPPEL ──
    "rappel_create": (1, 10),
    "rappel_delete": (1, 10),
    "rappel_list": (1, 10),
    # ── TICKET ──
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
}


# ============================================================
# 📋 Registre statique — permissions
# ============================================================

_PERMISSIONS: dict[str, tuple[str, str | None]] = {
    # ── ALPHA ──
    "alpha_event_list": ("interne", "staff_alpha.moderateur_plus (+ réservé au Discord Alpha)"),
    "alpha_event_regle": ("interne", "staff_alpha.moderateur_plus (+ réservé au Discord Alpha)"),
    "alpha_event_start": ("interne", "staff_alpha.moderateur_plus (+ réservé au Discord Alpha)"),
    "alpha_index": ("interne", "staff_alpha.op (+ réservé au Discord Alpha)"),
    "alpha_nous_rejoindre": ("interne", "staff_alpha.op (+ réservé au Discord Alpha)"),
    "alpha_regle_interne": ("interne", "staff_alpha.op (+ réservé au Discord Alpha)"),
    "alpha_test": ("interne", "equipe_guideon.dev"),
    # ── BIRTHDAY ──
    "birthday_add": ("aucune", None),
    "birthday_config": ("discord_admin", "Administrateur (Discord)"),
    "birthday_list": ("boutique", "Palier VIP"),
    "birthday_next": ("boutique", "Palier VIP"),
    # ── GLOBALES ──
    "id_cmd": ("aucune", None),
    "info_cmd": ("aucune", None),
    "ping_cmd": ("aucune", None),
    "report_cmd": ("aucune", None),
    "timestamp_cmd": ("aucune", None),
    "user_cmd": ("aucune", None),
    "wiki_cmd": ("aucune", None),
    # ── CONFIG ──
    "config_auto_fil": ("discord_admin", "Administrateur (Discord)"),
    "config_autorole": ("discord_admin", "Administrateur (Discord)"),
    "config_bienvenue": ("discord_admin", "Administrateur (Discord)"),
    "config_join_to_create": ("discord_admin", "Administrateur (Discord)"),
    "config_role_all": ("discord_admin", "Administrateur (Discord)"),
    "config_role_reaction": ("discord_admin", "Administrateur (Discord)"),
    # ── DELTA ──
    "delta_test": ("interne", "equipe_guideon.dev"),
    # ── DEV ──
    "dev_avatar_bot": ("interne", "equipe_guideon.dev"),
    "dev_botban": ("interne", "equipe_guideon.dev"),
    "dev_command_visibility": ("interne", "equipe_guideon.dev"),
    "dev_database": ("interne", "equipe_guideon.dev"),
    "dev_debug_cmd": ("interne", "equipe_guideon.dev"),
    "dev_delete_message": ("interne", "equipe_guideon.dev"),
    "dev_gold": ("interne", "equipe_guideon.dev"),
    "dev_guild_info": ("interne", "equipe_guideon.dev"),
    "dev_health": ("interne", "equipe_guideon.dev"),
    "dev_join_serv": ("interne", "equipe_guideon.dev"),
    "dev_kick": ("interne", "equipe_guideon.dev"),
    "dev_maintenance": ("interne", "equipe_guideon.dev"),
    "dev_permissions": ("interne", "DEV (développeur)"),
    "dev_setngversion": ("interne", "equipe_guideon.dev"),
    "dev_stat_cmd": ("interne", "equipe_guideon.dev"),
    "dev_stat_server": ("interne", "equipe_guideon.dev"),
    "dev_vip": ("interne", "equipe_guideon.dev"),
    # ── ECO ──
    "eco_balance": ("aucune", None),
    "eco_config": ("discord_admin", "Administrateur (Discord)"),
    "eco_daily": ("aucune", None),
    "eco_gestion": ("discord_admin", "Administrateur (Discord)"),
    "eco_leaderboard": ("aucune", None),
    # ── EXP ──
    "exp_config": ("discord_admin", "Administrateur (Discord)"),
    "exp_gestion": ("discord_admin", "Administrateur (Discord)"),
    "exp_info": ("aucune", None),
    "exp_leaderboard": ("aucune", None),
    "exp_level": ("aucune", None),
    # ── GIVEAWAY ──
    "giveaway_blacklist": ("discord_admin", "Administrateur (Discord)"),
    "giveaway_create": ("discord_admin", "Administrateur (Discord)"),
    "giveaway_list": ("boutique", "Palier Gold"),
    "giveaway_manage": ("interne", "Administrateur (Discord) ou créateur du giveaway"),
    # ── INVITE ──
    "invite_classement": ("aucune", None),
    "invite_config": ("discord_admin", "Administrateur (Discord)"),
    "invite_gestion": ("discord_admin", "Administrateur (Discord)"),
    "invite_user": ("aucune", None),
    # ── IRIS ──
    "iris_reglement": ("interne", "staff_iris.op (+ réservé au Discord Iris)"),
    "iris_test": ("interne", "equipe_guideon.dev"),
    # ── MEDIALINK ──
    "medialink_config": ("discord_admin", "Administrateur (Discord)"),
    # ── MOD ──
    "config_logs": ("interne", "Permission mod : config_logs"),
    "mod_ban": ("interne", "Permission mod : mod_ban"),
    "mod_clear": ("interne", "Permission mod : mod_clear"),
    "mod_config": ("discord_admin", "Administrateur (Discord)"),
    "mod_historique": ("interne", "Permission mod : mod_historique"),
    "mod_kick": ("interne", "Permission mod : mod_kick"),
    "mod_lock": ("interne", "Permission mod : mod_lock"),
    "mod_mute": ("interne", "Permission mod : mod_mute"),
    "mod_permissions": ("discord_admin", "Administrateur (Discord)"),
    "mod_piege": ("discord_admin", "Administrateur (Discord)"),
    "mod_purge": ("interne", "Permission mod : mod_purge"),
    "mod_rename": ("interne", "Permission mod : mod_rename"),
    "mod_softban": ("interne", "Permission mod : mod_softban"),
    "mod_tempban": ("interne", "Permission mod : mod_tempban"),
    "mod_unban": ("interne", "Permission mod : mod_unban"),
    "mod_unlock": ("interne", "Permission mod : mod_lock (clé partagée avec /mod lock)"),
    "mod_unmute": ("interne", "Permission mod : mod_unmute"),
    "mod_voice_manage": ("interne", "Permission mod : mod_voice_manage"),
    "mod_warn": ("interne", "Permission mod : mod_warn"),
    # ── NG ──
    "ng_autel": ("aucune", None),
    "ng_convert": ("aucune", None),
    "ng_dynmaps": ("aucune", None),
    "ng_info": ("aucune", None),
    "ng_onu": ("aucune", None),
    "ng_rd": ("aucune", None),
    "ng_sanction": ("aucune", None),
    "ng_skin": ("aucune", None),
    "ng_version": ("aucune", None),
    # ── NGSTAFF ──
    "ngstaff_config": ("interne", "staff_<serveur>.op (dynamique selon le serveur NG)"),
    "ngstaff_derank": ("interne", "staff_<serveur>.op (dynamique selon le serveur NG)"),
    "ngstaff_edit_stafflist": ("interne", "staff_<serveur>.op (dynamique selon le serveur NG)"),
    "ngstaff_nota_debug": ("interne", "equipe_guideon.dev"),
    "ngstaff_rank": ("interne", "staff_<serveur>.op (dynamique selon le serveur NG)"),
    "ngstaff_stafflist": ("interne", "staff_<serveur>.op (dynamique selon le serveur NG)"),
    # ── QR ──
    "qr_generate": ("aucune", None),
    "qr_list": ("aucune", None),
    "qr_scan": ("aucune", None),
    # ── RAPPEL ──
    "rappel_create": ("aucune", None),
    "rappel_delete": ("aucune", None),
    "rappel_list": ("aucune", None),
    # ── TICKET ──
    "ticket_add": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_ban": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_close": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_delete": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_panel_create": ("discord_admin", "Administrateur (Discord)"),
    "ticket_panel_delete": ("discord_admin", "Administrateur (Discord)"),
    "ticket_panel_edit": ("discord_admin", "Administrateur (Discord)"),
    "ticket_panel_list": ("discord_admin", "Administrateur (Discord)"),
    "ticket_remove": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_rename": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_unban": ("interne", "Staff ticket (rôles du panel)"),
    "ticket_wakeup": ("interne", "Staff ticket (rôles du panel)"),
}

_PERMISSION_TYPE_LABELS = {
    "discord_admin": "Permission Discord",
    "interne": "Permission interne",
    "boutique": "Palier boutique",
    "aucune": "Aucune (publique)",
}


def format_cooldown(command_name: str) -> str:
    cd = _COOLDOWNS.get(command_name)
    if cd is None:
        return "*Non renseigné*"
    rate, per = cd
    return f"{rate} / {per}s"


def format_permissions(command_name: str) -> str:
    entry = _PERMISSIONS.get(command_name)
    if entry is None:
        return "*Non renseignée*"
    perm_type, detail = entry
    label = _PERMISSION_TYPE_LABELS.get(perm_type, perm_type)
    if detail:
        return f"{label} — {detail}"
    return label


# ============================================================
# 🔍 Orchestration
# ============================================================


@dataclass
class CommandDebugInfo:
    """Résultat du diagnostic."""

    command_name: str
    enabled: bool
    total: int
    today: int
    last_used_str: str
    cooldown_str: str
    permission_str: str


async def get_command_debug_info(command_name: str) -> CommandDebugInfo | None:
    """Rassemble le diagnostic complet d'une commande."""

    all_toggles = await get_all_commands()
    total = await get_command_total(command_name)
    known = (
        command_name in all_toggles
        or command_name in _COOLDOWNS
        or command_name in _PERMISSIONS
        or total > 0
    )
    if not known:
        return None

    enabled = all_toggles.get(command_name, True)
    today = await get_command_today_count(command_name)
    last_used = await get_command_last_used(command_name)
    last_used_str = last_used.strftime("%d/%m/%Y") if last_used else "*Jamais utilisée*"

    return CommandDebugInfo(
        command_name=command_name,
        enabled=enabled,
        total=total,
        today=today,
        last_used_str=last_used_str,
        cooldown_str=format_cooldown(command_name),
        permission_str=format_permissions(command_name),
    )