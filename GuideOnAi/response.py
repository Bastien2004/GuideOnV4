"""
response.py — Réponses du chatbot GuideOn pour chaque intention.

⚠️ À VÉRIFIER TOI-MÊME :
- Les chemins de commande (/mod ban, /ticket close, etc.) sont déduits du
  nom du fichier + du nom de la commande trouvés dans le code. Vérifie
  qu'ils correspondent bien au group name réel déclaré dans chaque Cog
  (certains groupes peuvent avoir un nom différent du nom du dossier).
- Le ton est volontairement neutre/informatif, à toi de l'adapter.
"""

RESPONSES = {

    # ---- TICKET ----
    "ticket_create":       "Pour créer un ticket, clique sur le bouton du panel de tickets du serveur.",
    "ticket_add":          "Utilise `/ticket add` pour ajouter un membre à ce ticket (réservé au staff).",
    "ticket_remove":       "Utilise `/ticket remove` pour retirer un membre de ce ticket (réservé au staff).",
    "ticket_rename":       "Utilise `/ticket rename` pour renommer ce ticket (réservé au staff).",
    "ticket_ban":          "Utilise `/ticket ban` pour empêcher quelqu'un d'ouvrir des tickets (réservé au staff).",
    "ticket_unban":        "Utilise `/ticket unban` pour lever un ban ticket (réservé au staff).",
    "ticket_close":        "Utilise `/ticket close` pour fermer ce ticket (réservé au staff).",
    "ticket_delete":       "Utilise `/ticket delete` pour supprimer définitivement ce ticket (réservé au staff).",
    "ticket_wakeup":       "Utilise `/ticket wakeup` pour relancer le créateur du ticket (réservé au staff).",
    "ticket_panel_create": "Utilise `/ticket panel create` pour mettre en place un panel de tickets (admin).",
    "ticket_panel_delete": "Utilise `/ticket panel delete` pour supprimer un panel de tickets (admin).",
    "ticket_panel_edit":   "Utilise `/ticket panel edit` pour modifier un panel de tickets (admin).",
    "ticket_panel_list":   "Utilise `/ticket panel list` pour lister les panels de tickets (admin).",

    # ---- MOD ----
    "mod_ban":         "Utilise `/mod ban` pour bannir ce membre (soumis aux permissions /mod).",
    "mod_unban":       "Utilise `/mod unban` pour débannir ce membre (soumis aux permissions /mod).",
    "mod_kick":        "Utilise `/mod kick` pour expulser ce membre (soumis aux permissions /mod).",
    "mod_warn":        "Utilise `/mod warn` pour avertir ce membre (soumis aux permissions /mod).",
    "mod_mute":        "Utilise `/mod mute` pour rendre ce membre muet temporairement (soumis aux permissions /mod).",
    "mod_unmute":      "Utilise `/mod unmute` pour retirer le mute de ce membre (soumis aux permissions /mod).",
    "mod_tempban":     "Utilise `/mod tempban` pour bannir temporairement ce membre (soumis aux permissions /mod).",
    "mod_softban":     "Utilise `/mod softban` pour bannir puis débannir ce membre (efface ses messages, soumis aux permissions /mod).",
    "mod_historique":  "Utilise `/mod historique` pour voir les sanctions passées de ce membre (soumis aux permissions /mod).",
    "mod_rename":      "Utilise `/mod rename` pour changer le pseudo de ce membre (soumis aux permissions /mod).",
    "mod_clear":       "Utilise `/mod clear` pour supprimer des messages dans ce salon (soumis aux permissions /mod).",
    "mod_lock":        "Utilise `/mod lock` pour verrouiller l'écriture dans ce salon (soumis aux permissions /mod).",
    "mod_unlock":      "Utilise `/mod unlock` pour déverrouiller ce salon (soumis aux permissions /mod).",
    "mod_vocal":       "Utilise `/mod vocal` pour gérer les membres en vocal (mute/kick en masse, soumis aux permissions /mod).",
    "mod_config":      "Utilise `/mod config` pour configurer la modération automatique (administrateur uniquement).",
    "mod_permissions": "Utilise `/mod permissions` pour gérer qui a accès à quelles commandes de modération (administrateur uniquement).",
    "mod_piege":       "Utilise `/mod piege` pour configurer le salon piège anti-raid (administrateur uniquement).",
    "mod_logs":        "Utilise `/mod logs` pour configurer les logs de modération (soumis aux permissions /mod).",

    # ---- CONFIG (serveur) ----
    "config_autorole":       "Utilise `/config autorole` pour attribuer un rôle automatiquement aux nouveaux membres (administrateur).",
    "config_bienvenue":      "Utilise `/config bienvenue` pour configurer le message de bienvenue (administrateur).",
    "config_role_all":       "Utilise `/config role_all` pour gérer un rôle sur l'ensemble des membres (administrateur).",
    "config_role_reaction":  "Utilise `/config role_reaction` pour configurer un système de rôles par réaction (administrateur).",
    "config_join_to_create": "Utilise `/config join_to_create` pour configurer les salons vocaux automatiques (administrateur).",

    # ---- GIVEAWAY ----
    "giveaway_create":    "Utilise `/giveaway create` pour lancer un giveaway (administrateur).",
    "giveaway_manage":    "Utilise `/giveaway manage` pour gérer un giveaway existant (administrateur ou organisateur du giveaway).",
    "giveaway_blacklist": "Utilise `/giveaway blacklist` pour empêcher quelqu'un de participer aux giveaways (administrateur).",
    "giveaway_list":      "Utilise `/giveaway list` pour lister les giveaways du serveur (fonctionnalité Gold+).",
    "giveaway_participate": "Il n'y a pas de commande pour ça ! Réagis avec 🎉 sur le message du giveaway pour y participer.",

    # ---- BIRTHDAY ----
    "birthday_add":    "Utilise `/birthday add` pour enregistrer ta date d'anniversaire.",
    "birthday_list":   "Utilise `/birthday list` pour voir les prochains anniversaires (fonctionnalité VIP).",
    "birthday_next":   "Utilise `/birthday next` pour voir le prochain anniversaire à venir (fonctionnalité VIP).",
    "birthday_config": "Utilise `/birthday config` pour configurer le système d'anniversaires (administrateur).",

    # ---- EXP ----
    "exp_info":        "Utilise `/exp info` pour comprendre comment fonctionne le système d'expérience.",
    "exp_level":        "Utilise `/exp level` pour voir ton niveau et ton expérience actuelle.",
    "exp_leaderboard":  "Utilise `/exp leaderboard` pour voir le classement d'expérience du serveur.",
    "exp_config":       "Utilise `/exp config` pour configurer le système d'expérience (administrateur).",
    "exp_gestion":      "Utilise `/exp gestion` pour ajuster manuellement l'expérience d'un membre (administrateur).",

    # ---- INVITE ----
    "invite_classement": "Utilise `/invite classement` pour voir qui a invité le plus de membres.",
    "invite_user":       "Utilise `/invite user` pour voir le nombre d'invitations d'un membre.",
    "invite_config":     "Utilise `/invite config` pour configurer le système d'invitations (administrateur).",
    "invite_gestion":    "Utilise `/invite gestion` pour ajuster manuellement les invitations d'un membre (administrateur).",

    # ---- MEDIALINK ----
    "medialink_config": "Utilise `/medialink config` pour configurer les annonces de liens média (administrateur).",

    # ---- QR ----
    "qr_generate": "Utilise `/qr generate` pour générer un QR code.",
    "qr_scan":     "Utilise `/qr scan` pour décoder un QR code.",
    "qr_list":     "Utilise `/qr list` pour voir tes QR codes générés.",

    # ---- NG (NationsGlory, public) ----
    "ng_info":     "Utilise `/ng info` pour obtenir des informations sur NationsGlory.",
    "ng_version":  "Utilise `/ng version` pour connaître la version actuelle de NationsGlory Bedrock.",
    "ng_convert":  "Utilise `/ng convert` pour convertir des quantités d'items en coffres/stacks.",
    "ng_dynmaps":  "Utilise `/ng dynmaps` pour accéder à la carte dynamique du serveur.",
    "ng_rd":       "Utilise `/ng rd` pour obtenir des informations sur les paliers de recherche & développement.",
    "ng_autel":    "Utilise `/ng autel` pour obtenir des informations sur les autels.",
    "ng_onu":      "Utilise `/ng onu` pour obtenir des informations sur les ONU.",
    "ng_skin":     "Utilise `/ng skin` pour voir le skin d'un joueur.",
    "ng_sanction": "Utilise `/ng sanction` pour consulter le tableau des sanctions NationsGlory.",

    # ---- NGSTAFF ----
    "ngstaff_rank":            "Utilise `/ngstaff rank` pour promouvoir un membre du staff (réservé OP).",
    "ngstaff_derank":          "Utilise `/ngstaff derank` pour rétrograder un membre du staff (réservé OP).",
    "ngstaff_config":          "Utilise `/ngstaff config` pour configurer le système staff (réservé OP).",
    "ngstaff_stafflist":       "Utilise `/ngstaff stafflist` pour générer la liste du staff (réservé OP).",
    "ngstaff_edit_stafflist":  "Utilise `/ngstaff edit_stafflist` pour modifier la liste du staff (réservé OP).",
    "ngstaff_nota_debug":      "Utilise `/ngstaff nota_debug` pour diagnostiquer le système de notations (réservé dev).",

    # ---- ALPHA ----
    "alpha_event_start":     "Utilise `/alpha event_start` pour lancer un event (réservé Modérateur+).",
    "alpha_event_regle":     "Utilise `/alpha event_regle` pour afficher le règlement des events (réservé Modérateur+).",
    "alpha_event_list":      "Utilise `/alpha event_list` pour lister les events en cours (réservé Modérateur+).",
    "alpha_index":           "Utilise `/alpha index` pour gérer l'index du serveur Alpha (réservé OP).",
    "alpha_nous_rejoindre":  "Utilise `/alpha nous_rejoindre` pour afficher le tutoriel pour rejoindre Alpha (réservé OP).",
    "alpha_regle_interne":   "Utilise `/alpha regle_interne` pour afficher les règles internes de l'équipe (réservé OP).",
    "alpha_test":            "Commande de test Alpha, réservée à l'équipe dev.",

    # ---- IRIS ----
    "iris_reglement": "Utilise `/iris reglement` pour gérer le règlement du serveur Iris (réservé OP).",
    "iris_test":       "Commande de test Iris, réservée à l'équipe dev.",

    # ---- COMMANDES GÉNÉRALES (publiques) ----
    "wiki":              "Utilise `/wiki` pour accéder à la documentation.",
    "report":            "Utilise `/report` pour signaler un bug ou un problème avec le bot.",
    "id_command":        "Utilise `/id` pour rechercher un utilisateur par son identifiant Discord.",
    "user_command":      "Utilise `/user` pour voir le profil d'un membre.",
    "info":              "Utilise `/info` pour en savoir plus sur GuideOn.",
    "timestamp_command": "Utilise `/timestamp` pour générer un timestamp Discord à partir d'une date.",
    "ping_command":      "Utilise `/ping` pour voir la latence actuelle du bot.",

    # ---- DEV (réservé équipe dev) ----
    "dev_health":          "Commande `/dev health`, réservée à l'équipe dev — état de santé du bot.",
    "dev_guild_info":      "Commande `/dev guild_info`, réservée à l'équipe dev — informations sur un serveur.",
    "dev_stat_server":     "Commande `/dev stat_server`, réservée à l'équipe dev — statistiques globales du bot.",
    "dev_stat_cmd":        "Commande `/dev stat_cmd`, réservée à l'équipe dev — statistiques d'usage d'une commande.",
    "dev_debug_cmd":       "Commande `/dev debug_cmd`, réservée à l'équipe dev — diagnostic d'une commande.",
    "dev_database":        "Commande `/dev database`, réservée à l'équipe dev — exploration de la base de données.",
    "dev_maintenance":     "Commande `/dev maintenance`, réservée à l'équipe dev — active/désactive une commande.",
    "dev_permissions":     "Commande `/dev permissions`, réservée au créateur du bot — gestion des permissions internes.",
    "dev_botban":          "Commande `/dev botban`, réservée à l'équipe dev — bannit un serveur du bot.",
    "dev_kick":            "Commande `/dev kick`, réservée à l'équipe dev — fait quitter le bot d'un serveur.",
    "dev_join_serv":       "Commande `/dev join_serv`, réservée à l'équipe dev — génère une invitation vers un serveur.",
    "dev_delete_message":  "Commande `/dev delete_message`, réservée à l'équipe dev — supprime un message du bot.",
    "dev_setngversion":    "Commande `/dev setngversion`, réservée à l'équipe dev — change la version NG Bedrock affichée.",
    "dev_gold":            "Commande `/dev gold`, réservée à l'équipe dev — active/désactive le statut Gold+ d'un serveur.",
    "dev_vip":             "Commande `/dev vip`, réservée à l'équipe dev — attribue/retire le statut VIP à un membre.",
}