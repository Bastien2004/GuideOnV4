"""
scripts/seed_command_controls.py — Seed/maj de la table command_controls.

Idempotent : utilise ON CONFLICT DO NOTHING, donc relançable sans erreur
pour ajouter les nouvelles commandes (ex: système Alpha) sans toucher
aux togglings déjà faits via /dev maintenance.
"""

import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from utils.db.session import get_session
from utils.db.models.control_admin import CommandControl

COMMANDS = {
    # ── ALPHA ──
    "alpha_derank": True,
    "alpha_event_list": False,
    "alpha_event_regle": False,
    "alpha_event_start": False,
    "alpha_index": True,
    "alpha_nous_rejoindre": True,
    "alpha_rank": True,
    "alpha_regle_interne": True,
    "alpha_stafflist": True,
    "alpha_config_alpha": True,
    "alpha_test": True,

    # ── BIRTHDAY ──
    "birthday_add": True,
    "birthday_config": True,
    "birthday_list": True,
    "birthday_next": True,

    # ── CONFIG ──
    "config_autorole": True,
    "config_bienvenue": True,
    "config_role_all": True,
    "config_role_reaction": False,

    # ── DEV ──
    "dev_delete_message": True,
    "dev_edit_stafflist_alpha" : True,
    "dev_kick" : True,
    "dev_maintenance" : True,
    "dev_permissions" : True,
    "dev_stat_server" : True,

    # ── NG ──
    "ng_autel": True,
    "ng_convert": True,
    "ng_rd": True,
    "ng_serveur_stat": True,
    "ng_skin": True,
    "ng_info": True,
    "ng_claim": False,
    "ng_classement": False,
    "ng_sanction": True,
    "ng_note_archi": True,
    "ng_country": True,
    "ng_mmr": True,
    "ng_profil": True,
    "ng_lvl": True,
    "ng_pillage": True,
    "ng_version": True,
    "ng_onu": True,
    "ng_dynmaps": True,
    # ── MOD ──
    "mod_control": True,
    "mod_reglement": True,
    "mod_inspect": True,
    "mod_registre": True,
    "mod_clear": True,

    # ── EXP ──
    "exp_gestion": True,
    "exp_level": True,
    "exp_leaderboard": True,
    # ── TICKET ──
    "ticket_panel_create": True,
    "ticket_panel_edit": True,
    "ticket_panel_delete": True,
    "ticket_panel_list": True,
    "ticket_close": True,
    "ticket_delete": True,
    "ticket_add": True,
    "ticket_ban": True,
    "ticket_rename": True,
    "ticket_remove": True,
    # ── INVITE ──
    "invite_config": True,
    "invite_gestion": True,
    "invite_classement": True,
    "invite_user": True,
    # ── GIVEAWAY ──
    "giveaway_create": True,
    "giveaway_manage": True,
    "giveaway_list": True,

    # ── ANNIV ──
    "anniv_anniversaire": True,
    "anniv_kit": True,
    "anniv_classement": True,
    "anniv_inventaire": True,
    "anniv_fouiller": True,
    "anniv_admin_give": True,
    "anniv_admin_event": True,
    "anniv_admin_stats": True,
    "anniv_admin_points": True,
    "anniv_admin_dollars": True,
    "anniv_admin_logs": True,
    "anniv_admin_reset": True,
    "anniv_admin_reset_all": True,
    "anniv_admin_setup": True,
    # ── GLOBAL ──
    "boutique": True,
    "wiki": True,
    "id_command": True,
    "ping": True,
    "info": True,
    "timestamp": True,
    "flex": True,
    "troll": True,
    "myserver": True,
    "rappel": True,
    "report": True,
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