"""
permissions.py — Permissions requises par intention pour GuideOn.

Champ "verified" :
- True  → confirmé en lisant le code (import du bon check dans le fichier
          de la commande, ex: check_admin, check_mod_permission, is_staff...)
- False → déduit d'un tag dans la description de la commande (ex: [OP],
          [DEV], [M+], [VIP], Gold+) ou de la convention du module, mais
          pas confirmé ligne par ligne dans le code. À vérifier toi-même.

Types de permission (mêmes catégories que ton propre utils/command_debug.py) :
- "discord_admin" : permission Administrateur Discord native (check_admin)
- "interne"       : permission interne au bot (check_mod_permission,
                     has_grade_check, is_staff, check_dev...)
- "boutique"       : palier VIP / Gold+
- "aucune"        : commande publique, pas de restriction trouvée
"""

PERMISSIONS = {

    # ---- TICKET ----
    "ticket_create":       {"type": "aucune",  "detail": "Pas une slash command — bouton public sur un panel (views/ticket/panel_public_view.py)", "verified": True},
    "ticket_add":          {"type": "interne", "detail": "is_staff (staff ticket)",                "verified": True},
    "ticket_remove":       {"type": "interne", "detail": "is_staff (staff ticket)",                "verified": True},
    "ticket_rename":       {"type": "interne", "detail": "is_staff (staff ticket)",                "verified": True},
    "ticket_ban":          {"type": "interne", "detail": "is_staff (staff ticket)",                "verified": True},
    "ticket_unban":        {"type": "interne", "detail": "is_staff (staff ticket)",                "verified": True},
    "ticket_close":        {"type": "interne", "detail": "is_staff — délégué à handle_close(staff_only=True) dans views/ticket/lifecycle.py", "verified": True},
    "ticket_delete":       {"type": "interne", "detail": "is_staff (staff ticket)",                "verified": True},
    "ticket_wakeup":       {"type": "interne", "detail": "is_staff — délégué à handle_wakeup() dans views/ticket/lifecycle.py", "verified": True},
    "ticket_panel_create": {"type": "discord_admin", "detail": "check_admin",                      "verified": True},
    "ticket_panel_delete": {"type": "discord_admin", "detail": "check_admin",                      "verified": True},
    "ticket_panel_edit":   {"type": "discord_admin", "detail": "check_admin",                      "verified": True},
    "ticket_panel_list":   {"type": "discord_admin", "detail": "check_admin",                      "verified": True},

    # ---- MOD (permission interne dédiée, configurable via /mod permissions) ----
    "mod_ban":         {"type": "interne", "detail": "check_mod_permission('mod_ban')",       "verified": True},
    "mod_unban":       {"type": "interne", "detail": "check_mod_permission('mod_unban')",     "verified": True},
    "mod_kick":        {"type": "interne", "detail": "check_mod_permission('mod_kick')",      "verified": True},
    "mod_warn":        {"type": "interne", "detail": "check_mod_permission('mod_warn')",      "verified": True},
    "mod_mute":        {"type": "interne", "detail": "check_mod_permission('mod_mute')",      "verified": True},
    "mod_unmute":      {"type": "interne", "detail": "check_mod_permission('mod_unmute')",    "verified": True},
    "mod_tempban":     {"type": "interne", "detail": "check_mod_permission('mod_tempban')",   "verified": True},
    "mod_softban":     {"type": "interne", "detail": "check_mod_permission('mod_softban')",   "verified": True},
    "mod_historique":  {"type": "interne", "detail": "check_mod_permission('mod_historique')","verified": True},
    "mod_rename":      {"type": "interne", "detail": "check_mod_permission('mod_rename')",    "verified": True},
    "mod_clear":       {"type": "interne", "detail": "check_mod_permission('mod_clear')",     "verified": True},
    "mod_lock":        {"type": "interne", "detail": "check_mod_permission('mod_lock')",      "verified": True},
    "mod_unlock":      {"type": "interne", "detail": "check_mod_permission('mod_lock')",      "verified": True},
    "mod_vocal":       {"type": "interne", "detail": "check_mod_permission('mod_voice_manage')","verified": True},
    "mod_config":      {"type": "discord_admin", "detail": "check_admin — non délégable via /mod permissions", "verified": True},
    "mod_permissions": {"type": "discord_admin", "detail": "check_admin",                     "verified": True},
    "mod_piege":       {"type": "discord_admin", "detail": "check_admin",                     "verified": True},
    "mod_logs":        {"type": "interne", "detail": "check_mod_permission('config_logs')",   "verified": True},

    # ---- CONFIG (serveur) ----
    "config_autorole":       {"type": "discord_admin", "detail": "check_admin", "verified": True},
    "config_bienvenue":      {"type": "discord_admin", "detail": "check_admin", "verified": True},
    "config_role_all":       {"type": "discord_admin", "detail": "check_admin", "verified": True},
    "config_role_reaction":  {"type": "discord_admin", "detail": "check_admin", "verified": True},
    "config_join_to_create": {"type": "discord_admin", "detail": "check_admin", "verified": True},

    # ---- GIVEAWAY ----
    "giveaway_create":    {"type": "discord_admin", "detail": "check_admin",              "verified": True},
    "giveaway_manage":    {"type": "discord_admin", "detail": "Administrateur Discord OU organisateur du giveaway (is_admin or is_host) — pas Gold+, contrairement à ce que je disais avant", "verified": True},
    "giveaway_blacklist": {"type": "discord_admin", "detail": "check_admin",              "verified": True},
    "giveaway_list":      {"type": "boutique", "detail": "is_gold (Gold+)",                "verified": True},
    "giveaway_participate": {"type": "aucune", "detail": "Pas une commande — participation via réaction 🎉 sur le message (views/giveaway/panel_view.py)", "verified": True},

    # ---- BIRTHDAY ----
    "birthday_add":    {"type": "aucune",    "detail": "Publique (confirmé, aucun import de permission)", "verified": True},
    "birthday_list":   {"type": "boutique",  "detail": "is_vip (VIP)",          "verified": True},
    "birthday_next":   {"type": "boutique",  "detail": "is_vip (VIP)",          "verified": True},
    "birthday_config": {"type": "discord_admin", "detail": "check_admin",      "verified": True},

    # ---- EXP ----
    "exp_info":        {"type": "aucune",        "detail": "Publique (confirmé)",         "verified": True},
    "exp_level":        {"type": "aucune",       "detail": "Publique (confirmé)",         "verified": True},
    "exp_leaderboard":  {"type": "aucune",       "detail": "Publique (confirmé)",         "verified": True},
    "exp_config":       {"type": "discord_admin","detail": "check_admin",      "verified": True},
    "exp_gestion":      {"type": "discord_admin","detail": "check_admin",      "verified": True},

    # ---- INVITE ----
    "invite_classement": {"type": "aucune",        "detail": "Publique (confirmé)",       "verified": True},
    "invite_user":       {"type": "aucune",        "detail": "Publique (confirmé)",       "verified": True},
    "invite_config":     {"type": "discord_admin", "detail": "check_admin",    "verified": True},
    "invite_gestion":    {"type": "discord_admin", "detail": "check_admin",    "verified": True},

    # ---- MEDIALINK ----
    "medialink_config": {"type": "discord_admin", "detail": "check_admin",     "verified": True},

    # ---- QR ----
    "qr_generate": {"type": "aucune", "detail": "Publique (confirmé, aucun import de permission)", "verified": True},
    "qr_scan":     {"type": "aucune", "detail": "Publique (confirmé, aucun import de permission)", "verified": True},
    "qr_list":     {"type": "aucune", "detail": "Publique (confirmé, aucun import de permission)", "verified": True},

    # ---- NG (public, confirmé par ton propre registre) ----
    "ng_info":     {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_version":  {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_convert":  {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_dynmaps":  {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_rd":       {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_autel":    {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_onu":      {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_skin":     {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},
    "ng_sanction": {"type": "aucune", "detail": "Publique (confirmé registre)", "verified": True},

    # ---- NGSTAFF (grade interne, tag [OP]/[DEV] dans les descriptions) ----
    "ngstaff_rank":            {"type": "interne", "detail": "has_grade_check('staff_{server}.op') — [OP]",       "verified": True},
    "ngstaff_derank":          {"type": "interne", "detail": "has_grade_check('staff_{server}.op') — [OP]",       "verified": True},
    "ngstaff_config":          {"type": "interne", "detail": "has_grade_check('staff_{server}.op') — [OP]",       "verified": True},
    "ngstaff_stafflist":       {"type": "interne", "detail": "has_grade_check('staff_{server}.op') — [OP]",       "verified": True},
    "ngstaff_edit_stafflist":  {"type": "interne", "detail": "has_grade_check('staff_{server}.op') — [OP]",       "verified": True},
    "ngstaff_nota_debug":      {"type": "interne", "detail": "has_grade_check('equipe_guideon.dev') — [DEV]", "verified": True},

    # ---- ALPHA (grade interne, tags [M+]/[OP]/[DEV] dans les descriptions) ----
    "alpha_event_start":     {"type": "interne", "detail": "has_grade_check('staff_alpha.moderateur_plus') — [M+]",  "verified": True},
    "alpha_event_regle":     {"type": "interne", "detail": "has_grade_check('staff_alpha.moderateur_plus') — [M+]",  "verified": True},
    "alpha_event_list":      {"type": "interne", "detail": "has_grade_check('staff_alpha.moderateur_plus') — [M+]",  "verified": True},
    "alpha_index":           {"type": "interne", "detail": "has_grade_check('staff_alpha.op') — [OP]",  "verified": True},
    "alpha_nous_rejoindre":  {"type": "interne", "detail": "has_grade_check('staff_alpha.op') — [OP]",  "verified": True},
    "alpha_regle_interne":   {"type": "interne", "detail": "has_grade_check('staff_alpha.op') — [OP]",  "verified": True},
    "alpha_test":            {"type": "interne", "detail": "has_grade_check('equipe_guideon.dev') — [DEV]", "verified": True},

    # ---- IRIS ----
    "iris_reglement": {"type": "interne", "detail": "has_grade_check('staff_iris.op') — [OP]",  "verified": True},
    "iris_test":       {"type": "interne", "detail": "has_grade_check('equipe_guideon.dev') — [DEV]", "verified": True},

    # ---- COMMANDES GÉNÉRALES ----
    "wiki":              {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},
    "report":            {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},
    "id_command":        {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},
    "user_command":      {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},
    "info":              {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},
    "timestamp_command": {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},
    "ping_command":      {"type": "aucune", "detail": "Publique (confirmé)", "verified": True},

    # ---- DEV (équipe dev uniquement, confirmé registre + tag [DEV]) ----
    "dev_health":          {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_guild_info":      {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_stat_server":     {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_stat_cmd":        {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_debug_cmd":       {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_database":        {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_maintenance":     {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_permissions":     {"type": "interne", "detail": "is_creator + has_grade (RBAC) — plus restreint que le reste du groupe DEV", "verified": True},
    "dev_botban":          {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_kick":            {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_join_serv":       {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_delete_message":  {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_setngversion":    {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_gold":            {"type": "interne", "detail": "Interne — DEV", "verified": True},
    "dev_vip":             {"type": "interne", "detail": "Interne — DEV", "verified": True},
}