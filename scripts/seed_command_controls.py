"""
scripts/seed_command_controls.py — Mise à jour de la table de maintenance.
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from utils.db.session import get_session
from utils.db.models.control_admin import CommandControl

COMMANDS = {
    # ── ALPHA ──
    "alpha_event_list": False,
    "alpha_event_regle": False,
    "alpha_event_start": False,
    "alpha_index": True,
    "alpha_nous_rejoindre": True,
    "alpha_regle_interne": True,
    "alpha_test": True,

    # ── BIRTHDAY ──
    "birthday_add": True,
    "birthday_config": True,
    "birthday_list": True,
    "birthday_next": True,

    # ── UTILITAIRE ──
    "id_cmd": True,
    "info_cmd": True,
    "ping_cmd": True,
    "report_cmd": True,
    "timestamp": True,
    "user_cmd": True,
    "wiki_cmd": True,

    # ── CONFIG ──
    "config_autorole": True,
    "config_bienvenue": True,
    "config_role_all": True,
    "config_role_reaction": False,

    # ── DEV ──
    "dev_botban" : True,
    "dev_debug_cmd" : True,
    "dev_delete_message" : True,
    "dev_gold" : True,
    "dev_guild_info" : True,
    "dev_health" : True,
    "dev_join_serv": True,
    "dev_kick" : True,
    "dev_permissions" : True,
    "dev_stat_cmd" : True,
    "dev_stat_server" : True,
    "dev_vip" : True,

    # ── EXP ──
    "exp_config": True,
    "exp_gestion": True,
    "exp_leaderboard": True,
    "exp_level": True,

    # ── GIVEAWAY ──
    "giveaway_blacklist": True,
    "giveaway_create": True,
    "giveaway_list": True,
    "giveaway_manage": True,

    # ── INVITE ──
    "invite_classement": True,
    "invite_config": True,
    "invite_gestion": True,
    "invite_user": True,

    # ── MOD ──
    "mod_ban": True,
    "mod_clear": False,
    "mod_config": False,
    "mod_historique": True,
    "mod_kick": True,
    "mod_lock": True,
    "mod_logs": True,
    "mod_mute": True,
    "mod_permissions": True,
    "mod_rename": True,
    "mod_softban": True,
    "mod_tempban": True,
    "mod_unban": True,
    "mod_unlock": True,
    "mod_unmute": True,
    "mod_unwarn": True,
    "mod_voice_manage": False,
    "mod_warn": True,

    # ── NG ──
    "ng_autel": True,
    "ng_convert": True,
    "ng_dynmaps": True,
    "ng_info": True,
    "ng_version": True,
    "ng_onu": True,
    "ng_rd": True,
    "ng_sanction": True,
    "ng_skin": True,

    # ── NGSTAFF ──
    "ngstaff_config": True,
    "ngstaff_derank": True,
    "ngstaff_edit_stafflist": True,
    "ngstaff_nota_debug": True,
    "ngstaff_rank": True,
    "ngstaff_stafflist": True,

    # ── QRC ──
    "qr_generate": True,
    "qr_list": True,
    "qr_scan": True,
    
    # ── TICKET ──
    "ticket_add": True,
    "ticket_ban": True,
    "ticket_close": True,
    "ticket_delete": True,
    "ticket_panel_create": True,
    "ticket_panel_delete": True,
    "ticket_panel_edit": True,
    "ticket_panel_list": True,
    "ticket_remove": True,
    "ticket_rename": True,
    "ticket_unban": True,
    "ticket_wakeup": True,

}


async def seed() -> None:
    async with get_session() as session:
        stmt = pg_insert(CommandControl).values(
            [{"command_name": name, "enabled": enabled} for name, enabled in COMMANDS.items()]
        )
        stmt = stmt.on_conflict_do_nothing(index_elements=["command_name"])
        result = await session.execute(stmt)
    print(f"✅ Seed terminé — {result.rowcount} nouvelle(s) commande(s) insérée(s) "
          f"({len(COMMANDS)} référencées au total).")


if __name__ == "__main__":
    asyncio.run(seed())