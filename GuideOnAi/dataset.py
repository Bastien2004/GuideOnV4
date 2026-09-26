"""
dataset.py — Dataset d'intentions pour GuideOn (version 4, ajout du
smalltalk : salutations, remerciements, petites conversations, pour que
le bot ait l'air d'une vraie IA conversationnelle et pas juste d'un
répertoire de commandes).

Nouveauté v4 :
- 16 intentions de conversation courante ajoutées (greeting, how_are_you,
  thanks, goodbye, who_are_you, bot_creator, what_can_you_do, joke,
  compliment_bot, insult_bot, bored, smalltalk_weather, smalltalk_time,
  yes_confirm, no_deny, are_you_there).
- yes_confirm / no_deny couvrent aussi un bug de flow observé en usage :
  quand predict() renvoie "Je pense que tu veux X, c'est bien ça ?"
  (confiance moyenne), la réponse "oui"/"non" de l'utilisateur au tour
  suivant était classifiée comme une intention à part entière (souvent
  "unknown", faute d'intention dédiée) puisque predict() ne garde pas de
  contexte entre deux appels. Ces deux intentions donnent au moins une
  réponse cohérente à "oui"/"non" isolé — mais ça ne résout pas le fond
  du problème (l'absence de mémoire de conversation dans predict()).

⚠️ Après avoir modifié ce fichier (et response.py / permissions.py), le
modèle doit être RÉENTRAÎNÉ (le script train.py qui génère model.pth) :
ajouter des intentions ici ne change rien tant que le checkpoint n'est
pas régénéré avec ce nouveau jeu d'intentions.

Nouveauté v3 : "giveaway_participate" ajoutée — il n'existe aucune commande
pour participer à un giveaway (ça se fait en réagissant avec 🎉 sur le
message), mais le modèle répondait quand même "giveaway_create" avec
70%+ de confiance sur ce genre de phrase. Sans intention dédiée, le
modèle n'a pas d'autre choix que de forcer vers l'intention la plus
proche — d'où l'ajout.

Paires volontairement renforcées avec du vocabulaire contrasté (pas
juste plus de phrases au hasard) car elles se confondaient dans les
tests :
- ngstaff_rank / ngstaff_derank (antonymes, vocabulaire trop proche)
- ticket_panel_create / _delete / _edit / _list (même racine "panel")
- ticket_ban (souvent confondu avec ticket_close)
- exp_level / exp_leaderboard
- ng_version / ng_rd
- ng_sanction / giveaway_list
- alpha_nous_rejoindre / alpha_index
- ping_command / dev_stat_server
- config_bienvenue / mod_rename (attracteur bizarre vers exp_leaderboard)
"""

INTENTS = [
    # ---- TICKET ----
    "ticket_create",
    "ticket_add",
    "ticket_remove",
    "ticket_rename",
    "ticket_ban",
    "ticket_unban",
    "ticket_close",
    "ticket_delete",
    "ticket_wakeup",
    "ticket_panel_create",
    "ticket_panel_delete",
    "ticket_panel_edit",
    "ticket_panel_list",

    # ---- MOD ----
    "mod_ban",
    "mod_unban",
    "mod_kick",
    "mod_warn",
    "mod_mute",
    "mod_unmute",
    "mod_tempban",
    "mod_softban",
    "mod_historique",
    "mod_rename",
    "mod_clear",
    "mod_lock",
    "mod_unlock",
    "mod_vocal",
    "mod_config",
    "mod_permissions",
    "mod_piege",
    "mod_logs",

    # ---- CONFIG (serveur) ----
    "config_autorole",
    "config_bienvenue",
    "config_role_all",
    "config_role_reaction",
    "config_join_to_create",

    # ---- GIVEAWAY ----
    "giveaway_create",
    "giveaway_manage",
    "giveaway_blacklist",
    "giveaway_list",
    "giveaway_participate",

    # ---- BIRTHDAY ----
    "birthday_add",
    "birthday_list",
    "birthday_next",
    "birthday_config",

    # ---- EXP ----
    "exp_info",
    "exp_level",
    "exp_leaderboard",
    "exp_config",
    "exp_gestion",

    # ---- INVITE ----
    "invite_classement",
    "invite_user",
    "invite_config",
    "invite_gestion",

    # ---- MEDIALINK ----
    "medialink_config",

    # ---- QR ----
    "qr_generate",
    "qr_scan",
    "qr_list",

    # ---- NG (NationsGlory, public) ----
    "ng_info",
    "ng_version",
    "ng_convert",
    "ng_dynmaps",
    "ng_rd",
    "ng_autel",
    "ng_onu",
    "ng_skin",
    "ng_sanction",

    # ---- NGSTAFF ----
    "ngstaff_rank",
    "ngstaff_derank",
    "ngstaff_config",
    "ngstaff_stafflist",
    "ngstaff_edit_stafflist",
    "ngstaff_nota_debug",

    # ---- ALPHA ----
    "alpha_event_start",
    "alpha_event_regle",
    "alpha_event_list",
    "alpha_index",
    "alpha_nous_rejoindre",
    "alpha_regle_interne",
    "alpha_test",

    # ---- IRIS ----
    "iris_reglement",
    "iris_test",

    # ---- COMMANDES GÉNÉRALES (publiques) ----
    "wiki",
    "report",
    "id_command",
    "user_command",
    "info",
    "timestamp_command",
    "ping_command",

    # ---- DEV (réservé équipe dev) ----
    "dev_health",
    "dev_guild_info",
    "dev_stat_server",
    "dev_stat_cmd",
    "dev_debug_cmd",
    "dev_database",
    "dev_maintenance",
    "dev_permissions",
    "dev_botban",
    "dev_kick",
    "dev_join_serv",
    "dev_delete_message",
    "dev_setngversion",
    "dev_gold",
    "dev_vip",

    # ---- CONVERSATION / SMALLTALK (nouveau v4) ----
    "greeting",
    "how_are_you",
    "thanks",
    "goodbye",
    "who_are_you",
    "bot_creator",
    "what_can_you_do",
    "joke",
    "compliment_bot",
    "insult_bot",
    "bored",
    "smalltalk_weather",
    "smalltalk_time",
    "yes_confirm",
    "no_deny",
    "are_you_there",
]


DATASET = [
    # ============================================================
    # TICKET
    # ============================================================
    ("je veux créer un ticket", "ticket_create"),
    ("comment créer un ticket", "ticket_create"),
    ("je veux ouvrir un ticket", "ticket_create"),
    ("crée-moi un ticket", "ticket_create"),
    ("comment ouvrir un ticket de support", "ticket_create"),
    ("j'aimerais ouvrir un ticket", "ticket_create"),
    ("comment contacter le support avec un ticket", "ticket_create"),
    ("je veux parler au staff via un ticket", "ticket_create"),
    ("comment on ouvre un ticket ici", "ticket_create"),

    ("ajoute quelqu'un à mon ticket", "ticket_add"),
    ("comment ajouter une personne au ticket", "ticket_add"),
    ("je veux ajouter un membre à ce ticket", "ticket_add"),
    ("ajoute cet utilisateur dans le ticket", "ticket_add"),
    ("comment inviter quelqu'un dans un ticket", "ticket_add"),
    ("rajoute-le dans le ticket", "ticket_add"),
    ("intègre ce membre à mon ticket", "ticket_add"),

    ("retire cette personne du ticket", "ticket_remove"),
    ("comment enlever quelqu'un du ticket", "ticket_remove"),
    ("supprime cet utilisateur de mon ticket", "ticket_remove"),
    ("vire-le du ticket", "ticket_remove"),
    ("comment exclure un membre du ticket", "ticket_remove"),
    ("enlève cette personne de ce ticket", "ticket_remove"),
    ("sors-le de ce ticket", "ticket_remove"),

    ("renomme ce ticket", "ticket_rename"),
    ("comment changer le nom du ticket", "ticket_rename"),
    ("je veux renommer mon ticket", "ticket_rename"),
    ("change le titre du ticket", "ticket_rename"),
    ("comment modifier le nom de ce ticket", "ticket_rename"),
    ("donne un autre nom à ce ticket", "ticket_rename"),

    ("bannis-le des tickets", "ticket_ban"),
    ("comment bannir quelqu'un des tickets", "ticket_ban"),
    ("empêche cette personne d'ouvrir de nouveaux tickets à l'avenir", "ticket_ban"),
    ("interdis-lui définitivement l'accès au système de tickets", "ticket_ban"),
    ("bloque-le pour qu'il ne puisse plus jamais créer de ticket", "ticket_ban"),
    ("ce membre abuse des tickets, bannis-le du système de tickets", "ticket_ban"),
    ("je veux lui retirer le droit d'ouvrir des tickets", "ticket_ban"),
    ("mets un ban ticket permanent sur ce membre", "ticket_ban"),

    ("débannis-le des tickets", "ticket_unban"),
    ("comment retirer un ban ticket", "ticket_unban"),
    ("il peut réouvrir un ticket maintenant", "ticket_unban"),
    ("redonne-lui l'accès aux tickets", "ticket_unban"),
    ("lève le ban ticket de ce membre", "ticket_unban"),
    ("annule l'interdiction de ticket de ce joueur", "ticket_unban"),

    ("je veux fermer mon ticket", "ticket_close"),
    ("comment fermer un ticket", "ticket_close"),
    ("ferme mon ticket", "ticket_close"),
    ("clôture ce ticket", "ticket_close"),
    ("comment clore un ticket", "ticket_close"),
    ("je veux clôturer ce ticket", "ticket_close"),
    ("termine ce ticket", "ticket_close"),
    ("le problème est résolu, ferme le ticket", "ticket_close"),

    ("je veux supprimer mon ticket", "ticket_delete"),
    ("comment supprimer un ticket", "ticket_delete"),
    ("supprime définitivement ce ticket", "ticket_delete"),
    ("efface ce ticket", "ticket_delete"),
    ("comment effacer complètement un ticket", "ticket_delete"),
    ("détruis ce ticket", "ticket_delete"),

    ("relance le créateur du ticket", "ticket_wakeup"),
    ("il ne répond plus dans son ticket", "ticket_wakeup"),
    ("envoie-lui un rappel pour son ticket", "ticket_wakeup"),
    ("réveille l'auteur du ticket", "ticket_wakeup"),
    ("comment relancer quelqu'un qui ne répond plus dans son ticket", "ticket_wakeup"),
    ("ça fait deux jours qu'il n'a pas répondu dans son ticket", "ticket_wakeup"),

    ("crée un panel de tickets", "ticket_panel_create"),
    ("je veux mettre en place le système de tickets pour la première fois", "ticket_panel_create"),
    ("comment configurer un panel de tickets", "ticket_panel_create"),
    ("installe le panel de tickets sur ce serveur", "ticket_panel_create"),
    ("comment créer le message avec les boutons de tickets", "ticket_panel_create"),
    ("mets en place un nouveau panel de tickets ici", "ticket_panel_create"),
    ("mon serveur n'a pas encore de système de tickets, aide-moi à en créer un", "ticket_panel_create"),

    ("supprime ce panel de tickets", "ticket_panel_delete"),
    ("comment retirer le panel de tickets", "ticket_panel_delete"),
    ("efface le panel de tickets existant", "ticket_panel_delete"),
    ("désinstalle complètement le système de tickets", "ticket_panel_delete"),
    ("enlève ce panel de tickets du salon", "ticket_panel_delete"),
    ("je ne veux plus de ce panel de tickets, supprime-le", "ticket_panel_delete"),

    ("modifie ce panel de tickets", "ticket_panel_edit"),
    ("je veux changer le contenu du panel de tickets", "ticket_panel_edit"),
    ("édite le message du panel de tickets existant", "ticket_panel_edit"),
    ("comment mettre à jour le texte du panel de tickets", "ticket_panel_edit"),
    ("corrige une erreur dans le panel de tickets", "ticket_panel_edit"),

    ("liste les panels de tickets", "ticket_panel_list"),
    ("montre-moi tous les panels de tickets existants", "ticket_panel_list"),
    ("combien de panels de tickets sont actifs sur ce serveur", "ticket_panel_list"),
    ("affiche la liste des panels de tickets", "ticket_panel_list"),

    # ============================================================
    # MOD
    # ============================================================
    ("bannis ce joueur", "mod_ban"),
    ("je veux bannir un joueur", "mod_ban"),
    ("comment bannir quelqu'un", "mod_ban"),
    ("je veux bannir cette personne", "mod_ban"),
    ("exclus définitivement ce membre du serveur", "mod_ban"),
    ("vire-le du serveur pour toujours", "mod_ban"),
    ("ban ce mec", "mod_ban"),
    ("bannis-moi ce trouble-fête du serveur", "mod_ban"),

    ("débannis ce joueur", "mod_unban"),
    ("retire le ban de ce membre", "mod_unban"),
    ("comment débannir quelqu'un", "mod_unban"),
    ("annule le bannissement de ce joueur", "mod_unban"),
    ("je veux le débannir du serveur", "mod_unban"),

    ("kick ce membre", "mod_kick"),
    ("je veux expulser quelqu'un", "mod_kick"),
    ("comment kick un joueur", "mod_kick"),
    ("vire-le temporairement du serveur", "mod_kick"),
    ("exclus-le du serveur (il peut revenir)", "mod_kick"),

    ("avertis ce joueur", "mod_warn"),
    ("donne un warn à ce membre", "mod_warn"),
    ("je veux avertir quelqu'un", "mod_warn"),
    ("mets un avertissement à ce joueur", "mod_warn"),
    ("comment donner un avertissement", "mod_warn"),

    ("mute ce membre", "mod_mute"),
    ("rends-le muet", "mod_mute"),
    ("je veux mute quelqu'un temporairement", "mod_mute"),
    ("empêche-le d'écrire pendant une heure", "mod_mute"),
    ("coupe le micro et le chat de ce joueur", "mod_mute"),

    ("unmute ce membre", "mod_unmute"),
    ("retire le mute de ce joueur", "mod_unmute"),
    ("redonne-lui la parole dans le chat", "mod_unmute"),
    ("comment enlever un mute", "mod_unmute"),
    ("il peut de nouveau écrire des messages maintenant", "mod_unmute"),
    ("lève le mute de ce membre sur le serveur", "mod_unmute"),

    ("bannis-le pour une semaine", "mod_tempban"),
    ("je veux un ban temporaire", "mod_tempban"),
    ("comment faire un tempban", "mod_tempban"),
    ("bannis-le juste 3 jours", "mod_tempban"),

    ("softban ce membre", "mod_softban"),
    ("bannis-le et supprime ses messages", "mod_softban"),
    ("fais un softban sur ce joueur", "mod_softban"),
    ("bannis puis débannis-le direct pour effacer ses messages", "mod_softban"),

    ("montre l'historique de sanctions de ce joueur", "mod_historique"),
    ("il a déjà eu des sanctions ?", "mod_historique"),
    ("je veux voir son casier", "mod_historique"),
    ("quelles sanctions a reçu ce membre", "mod_historique"),

    ("renomme ce membre", "mod_rename"),
    ("change son pseudo sur le serveur", "mod_rename"),
    ("modifie le surnom de ce joueur", "mod_rename"),
    ("je veux forcer un nouveau pseudo à ce membre", "mod_rename"),
    ("son pseudo est inapproprié, change-le", "mod_rename"),

    ("supprime les 50 derniers messages", "mod_clear"),
    ("nettoie ce salon", "mod_clear"),
    ("clear le chat", "mod_clear"),
    ("efface les messages de ce salon", "mod_clear"),
    ("purge ce salon", "mod_clear"),

    ("verrouille ce salon", "mod_lock"),
    ("bloque l'écriture dans ce salon", "mod_lock"),
    ("ferme ce salon temporairement", "mod_lock"),

    ("déverrouille ce salon", "mod_unlock"),
    ("réactive l'écriture dans ce salon", "mod_unlock"),
    ("rouvre ce salon", "mod_unlock"),

    ("mute tout le monde dans le vocal", "mod_vocal"),
    ("expulse tout le monde du vocal", "mod_vocal"),
    ("gère le vocal en masse", "mod_vocal"),
    ("coupe le micro de tous les membres en vocal", "mod_vocal"),

    ("configure l'automod", "mod_config"),
    ("je veux régler la modération automatique", "mod_config"),
    ("configure le système de sanctions", "mod_config"),

    ("gère les permissions de modération", "mod_permissions"),
    ("qui peut utiliser les commandes mod", "mod_permissions"),
    ("configure les accès aux commandes de modération", "mod_permissions"),

    ("configure le salon piège", "mod_piege"),
    ("mets en place le honeypot anti-raid", "mod_piege"),
    ("configure la protection anti-raid", "mod_piege"),

    ("configure les logs du serveur", "mod_logs"),
    ("je veux activer les logs de modération", "mod_logs"),
    ("dans quel salon envoyer les logs de sanctions", "mod_logs"),

    # ============================================================
    # CONFIG (serveur)
    # ============================================================
    ("configure l'autorole", "config_autorole"),
    ("attribue un rôle automatiquement aux nouveaux membres", "config_autorole"),
    ("donne un rôle par défaut à l'arrivée", "config_autorole"),

    ("configure le message de bienvenue", "config_bienvenue"),
    ("je veux un message quand quelqu'un rejoint le serveur", "config_bienvenue"),
    ("règle l'annonce d'arrivée des nouveaux membres", "config_bienvenue"),
    ("choisis le salon où annoncer les arrivées", "config_bienvenue"),
    ("écris un message d'accueil personnalisé pour les nouveaux", "config_bienvenue"),

    ("donne ce rôle à tout le monde", "config_role_all"),
    ("retire ce rôle à tous les membres", "config_role_all"),
    ("applique ce rôle à l'ensemble du serveur", "config_role_all"),

    ("configure les rôles par réaction", "config_role_reaction"),
    ("je veux un système de rôle réaction", "config_role_reaction"),
    ("mets en place un message avec des rôles à choisir en réagissant", "config_role_reaction"),

    ("configure le join to create", "config_join_to_create"),
    ("je veux des salons vocaux automatiques", "config_join_to_create"),
    ("crée un salon vocal qui en génère d'autres", "config_join_to_create"),

    # ============================================================
    # GIVEAWAY
    # ============================================================
    ("crée un giveaway", "giveaway_create"),
    ("je veux lancer un concours", "giveaway_create"),
    ("organise un giveaway", "giveaway_create"),
    ("comment créer un giveaway", "giveaway_create"),
    ("je veux faire un giveaway sur le serveur", "giveaway_create"),
    ("lance un concours avec un lot à gagner", "giveaway_create"),
    ("comment organiser un tirage au sort", "giveaway_create"),

    ("gère ce giveaway", "giveaway_manage"),
    ("modifie le giveaway en cours", "giveaway_manage"),
    ("comment gérer un giveaway existant", "giveaway_manage"),
    ("relance le tirage de ce giveaway", "giveaway_manage"),

    ("blacklist ce joueur des giveaways", "giveaway_blacklist"),
    ("empêche-le de participer aux giveaways à l'avenir", "giveaway_blacklist"),
    ("interdis-lui définitivement les concours", "giveaway_blacklist"),

    ("liste les giveaways du serveur", "giveaway_list"),
    ("montre-moi tous les giveaways", "giveaway_list"),
    ("quels giveaways sont en cours en ce moment", "giveaway_list"),
    ("y a-t-il des concours actifs sur ce serveur", "giveaway_list"),
    ("affiche la liste des giveaways ouverts", "giveaway_list"),

    ("je veux participer à ce giveaway", "giveaway_participate"),
    ("comment participer au giveaway", "giveaway_participate"),
    ("participer à un giveaway", "giveaway_participate"),
    ("rejoindre ce giveaway", "giveaway_participate"),
    ("comment je m'inscris à ce concours", "giveaway_participate"),
    ("je veux tenter ma chance à ce giveaway", "giveaway_participate"),
    ("comment on entre dans le tirage au sort", "giveaway_participate"),
    ("comment je participe pour gagner le lot", "giveaway_participate"),

    # ============================================================
    # BIRTHDAY
    # ============================================================
    ("enregistre ma date d'anniversaire", "birthday_add"),
    ("je veux ajouter mon anniversaire", "birthday_add"),
    ("comment enregistrer mon anniversaire sur le bot", "birthday_add"),
    ("ajoute ma date de naissance", "birthday_add"),

    ("liste les anniversaires à venir", "birthday_list"),
    ("montre-moi les prochains anniversaires du serveur", "birthday_list"),
    ("quels sont les anniversaires ce mois-ci", "birthday_list"),
    ("affiche le calendrier des anniversaires", "birthday_list"),
    ("y a-t-il des anniversaires cette semaine", "birthday_list"),

    ("c'est quand le prochain anniversaire", "birthday_next"),
    ("qui fête son anniversaire bientôt", "birthday_next"),
    ("quel est le prochain anniversaire sur le serveur", "birthday_next"),

    ("configure le système d'anniversaires", "birthday_config"),
    ("je veux régler les annonces d'anniversaire", "birthday_config"),
    ("dans quel salon annoncer les anniversaires", "birthday_config"),

    # ============================================================
    # EXP
    # ============================================================
    ("comment fonctionne l'exp", "exp_info"),
    ("explique-moi le système de niveaux", "exp_info"),
    ("c'est quoi le système d'expérience", "exp_info"),

    ("quel est mon niveau", "exp_level"),
    ("combien d'exp j'ai personnellement", "exp_level"),
    ("montre mon niveau actuel à moi", "exp_level"),
    ("où j'en suis dans ma progression d'exp", "exp_level"),

    ("montre le classement exp du serveur", "exp_leaderboard"),
    ("qui a le plus d'exp sur le serveur", "exp_leaderboard"),
    ("top des niveaux du serveur", "exp_leaderboard"),
    ("qui est premier au classement d'expérience", "exp_leaderboard"),
    ("montre le tableau des meilleurs niveaux", "exp_leaderboard"),
    ("classement général de l'exp entre tous les membres", "exp_leaderboard"),

    ("configure le système d'exp", "exp_config"),
    ("règle les paliers d'exp", "exp_config"),
    ("modifie la vitesse de progression d'exp pour monter de niveau", "exp_config"),
    ("change les paramètres du système de niveaux", "exp_config"),

    ("ajoute de l'exp à ce membre", "exp_gestion"),
    ("modifie manuellement son exp", "exp_gestion"),
    ("retire de l'exp à ce joueur", "exp_gestion"),

    # ============================================================
    # INVITE
    # ============================================================
    ("montre le classement des invitations", "invite_classement"),
    ("qui a invité le plus de monde", "invite_classement"),
    ("top des invitations sur ce serveur", "invite_classement"),

    ("combien d'invitations j'ai", "invite_user"),
    ("montre mes invitations", "invite_user"),
    ("combien de personnes j'ai invitées", "invite_user"),

    ("configure le système d'invitations", "invite_config"),
    ("règle les invitations du serveur", "invite_config"),
    ("dans quel salon annoncer les invitations", "invite_config"),

    ("modifie son compteur d'invitations", "invite_gestion"),
    ("ajuste ses invitations manuellement", "invite_gestion"),
    ("retire des invitations à ce membre", "invite_gestion"),

    # ============================================================
    # MEDIALINK
    # ============================================================
    ("configure medialink", "medialink_config"),
    ("règle les annonces medialink du serveur", "medialink_config"),
    ("dans quel salon poster les liens medialink", "medialink_config"),

    # ============================================================
    # QR
    # ============================================================
    ("génère un qr code", "qr_generate"),
    ("crée un qr code pour ce lien", "qr_generate"),
    ("comment générer un qr code", "qr_generate"),
    ("fais-moi un qr code", "qr_generate"),

    ("scanne ce qr code", "qr_scan"),
    ("décode ce qr code", "qr_scan"),
    ("lis le contenu de ce qr code", "qr_scan"),

    ("liste mes qr codes", "qr_list"),
    ("montre les qr codes que j'ai générés", "qr_list"),
    ("quels qr codes j'ai créés", "qr_list"),

    # ============================================================
    # NG (NationsGlory, public)
    # ============================================================
    ("infos nationsglory", "ng_info"),
    ("montre-moi les infos ng", "ng_info"),
    ("donne-moi des informations sur nationsglory", "ng_info"),

    ("quelle est la version actuelle du jeu", "ng_version"),
    ("c'est quoi la dernière version de nationsglory bedrock", "ng_version"),
    ("on est à quelle version du jeu en ce moment", "ng_version"),
    ("le jeu a été mis à jour vers quelle version", "ng_version"),

    ("convertis 5000 items en coffres", "ng_convert"),
    ("combien de stacks pour 3000 blocs", "ng_convert"),
    ("convertis ces items en caisses", "ng_convert"),

    ("montre-moi la dynmap", "ng_dynmaps"),
    ("lien de la carte du serveur", "ng_dynmaps"),
    ("où trouver la carte dynamique", "ng_dynmaps"),

    ("infos sur ce palier de r&d", "ng_rd"),
    ("c'est quoi ce palier de recherche et développement", "ng_rd"),
    ("explique-moi ce palier r&d précis", "ng_rd"),
    ("combien coûte ce palier de recherche", "ng_rd"),

    ("infos sur les autels", "ng_autel"),
    ("comment fonctionnent les autels", "ng_autel"),
    ("c'est quoi un autel sur nationsglory", "ng_autel"),

    ("infos sur les onus", "ng_onu"),
    ("c'est quoi une onu sur nationsglory", "ng_onu"),
    ("explique-moi le système d'onu", "ng_onu"),

    ("montre le skin de ce joueur", "ng_skin"),
    ("quel skin il a", "ng_skin"),
    ("affiche le skin de ce pseudo", "ng_skin"),

    ("montre les sanctions de ce serveur nationsglory", "ng_sanction"),
    ("tableau des sanctions ng en cours", "ng_sanction"),
    ("liste des sanctions appliquées sur nationsglory", "ng_sanction"),
    ("ce joueur a-t-il été sanctionné sur ng", "ng_sanction"),

    # ============================================================
    # NGSTAFF
    # ============================================================
    ("rank ce membre du staff", "ngstaff_rank"),
    ("monte-le en grade dans le staff", "ngstaff_rank"),
    ("promeus ce membre du staff au grade supérieur", "ngstaff_rank"),
    ("augmente son grade, il mérite une promotion", "ngstaff_rank"),
    ("fais-le monter d'un niveau dans la hiérarchie staff", "ngstaff_rank"),
    ("donne-lui un grade plus élevé dans l'équipe", "ngstaff_rank"),
    ("il a bien travaillé, promeus-le", "ngstaff_rank"),

    ("derank ce membre du staff", "ngstaff_derank"),
    ("rétrograde-le d'un grade", "ngstaff_derank"),
    ("baisse son grade dans le staff", "ngstaff_derank"),
    ("descends-le dans la hiérarchie staff", "ngstaff_derank"),
    ("il a fait une erreur, rétrograde-le", "ngstaff_derank"),
    ("retire-lui son grade actuel, mets-le en dessous", "ngstaff_derank"),
    ("fais-le redescendre d'un niveau dans le staff", "ngstaff_derank"),

    ("configure le staff ng", "ngstaff_config"),
    ("dashboard de configuration staff", "ngstaff_config"),
    ("règle la configuration de l'équipe staff", "ngstaff_config"),

    ("crée la liste du staff", "ngstaff_stafflist"),
    ("met à jour la stafflist", "ngstaff_stafflist"),
    ("génère la liste des membres du staff", "ngstaff_stafflist"),

    ("modifie la liste du staff", "ngstaff_edit_stafflist"),
    ("édite la stafflist", "ngstaff_edit_stafflist"),
    ("corrige un nom dans la stafflist", "ngstaff_edit_stafflist"),

    ("debug le système de notations", "ngstaff_nota_debug"),
    ("affiche l'état des notations staff", "ngstaff_nota_debug"),
    ("diagnostique le système de notes du staff", "ngstaff_nota_debug"),

    # ============================================================
    # ALPHA
    # ============================================================
    ("lance l'event alpha", "alpha_event_start"),
    ("annonce le début de l'event", "alpha_event_start"),
    ("démarre l'event alpha maintenant", "alpha_event_start"),

    ("montre les règles de l'event", "alpha_event_regle"),
    ("règlement de l'event alpha", "alpha_event_regle"),
    ("quelles sont les règles pour cet event", "alpha_event_regle"),

    ("liste les events alpha", "alpha_event_list"),
    ("quels sont les events en cours", "alpha_event_list"),
    ("montre tous les events alpha à venir", "alpha_event_list"),

    ("montre l'index du serveur alpha", "alpha_index"),
    ("met à jour l'interface d'info alpha", "alpha_index"),
    ("gère la page d'index alpha", "alpha_index"),
    ("modifie la page d'accueil informative du serveur alpha", "alpha_index"),

    ("comment rejoindre le serveur alpha", "alpha_nous_rejoindre"),
    ("tuto pour rejoindre alpha", "alpha_nous_rejoindre"),
    ("montre le guide pour rejoindre le serveur alpha", "alpha_nous_rejoindre"),
    ("je suis nouveau, comment je fais pour entrer sur alpha", "alpha_nous_rejoindre"),
    ("quelles sont les étapes pour nous rejoindre sur alpha", "alpha_nous_rejoindre"),

    ("montre le règlement interne alpha", "alpha_regle_interne"),
    ("règles internes de l'équipe alpha", "alpha_regle_interne"),
    ("affiche les consignes internes de l'équipe", "alpha_regle_interne"),

    ("teste la commande alpha", "alpha_test"),
    ("lance le test de debug alpha", "alpha_test"),

    # ============================================================
    # IRIS
    # ============================================================
    ("montre le règlement du serveur iris", "iris_reglement"),
    ("règles du serveur iris", "iris_reglement"),
    ("affiche le règlement iris", "iris_reglement"),

    ("teste la commande iris", "iris_test"),
    ("lance le test de debug iris", "iris_test"),

    # ============================================================
    # COMMANDES GÉNÉRALES (publiques)
    # ============================================================
    ("montre le wiki", "wiki"),
    ("où est la documentation", "wiki"),
    ("je cherche de l'aide sur le wiki", "wiki"),

    ("je veux signaler un bug", "report"),
    ("il y a un problème avec le bot", "report"),
    ("comment signaler un souci technique", "report"),

    ("montre les infos de cet utilisateur via son id", "id_command"),
    ("cherche ce membre par id", "id_command"),
    ("trouve cet utilisateur avec son identifiant discord", "id_command"),

    ("montre le profil de ce membre", "user_command"),
    ("infos sur cet utilisateur", "user_command"),
    ("donne-moi les infos de ce membre", "user_command"),

    ("c'est quoi guideon", "info"),
    ("présente-moi le bot", "info"),
    ("parle-moi de ce bot", "info"),

    ("convertis cette date en timestamp discord", "timestamp_command"),
    ("donne-moi le timestamp de cette heure", "timestamp_command"),
    ("génère un timestamp discord", "timestamp_command"),

    ("quelle est la latence du bot", "ping_command"),
    ("ping", "ping_command"),
    ("le bot répond vite ?", "ping_command"),
    ("le bot a combien de latence en millisecondes", "ping_command"),
    ("quelle est la vitesse de réponse du bot", "ping_command"),

    # ============================================================
    # DEV (réservé équipe dev)
    # ============================================================
    ("montre l'état de santé du bot", "dev_health"),
    ("le bot va bien ?", "dev_health"),
    ("vérifie que le bot fonctionne correctement", "dev_health"),

    ("infos sur ce serveur discord", "dev_guild_info"),
    ("montre les détails de cette guild", "dev_guild_info"),
    ("donne-moi les informations techniques de ce serveur", "dev_guild_info"),

    ("statistiques globales de guideon", "dev_stat_server"),
    ("montre les stats globales du bot", "dev_stat_server"),
    ("sur combien de serveurs le bot tourne au total", "dev_stat_server"),
    ("montre les statistiques d'utilisation générale du bot", "dev_stat_server"),

    ("statistiques d'usage de cette commande", "dev_stat_cmd"),
    ("combien de fois cette commande a été utilisée", "dev_stat_cmd"),
    ("montre les stats d'une commande précise", "dev_stat_cmd"),

    ("debug cette commande", "dev_debug_cmd"),
    ("diagnostic de cette commande", "dev_debug_cmd"),
    ("analyse pourquoi cette commande plante", "dev_debug_cmd"),

    ("explore la base de données du bot", "dev_database"),
    ("montre-moi cette table de la base de données", "dev_database"),
    ("accède directement à la base de données du bot", "dev_database"),
    ("je veux consulter les données stockées en base", "dev_database"),

    ("active le mode maintenance", "dev_maintenance"),
    ("désactive cette commande temporairement", "dev_maintenance"),
    ("mets cette commande en maintenance", "dev_maintenance"),

    ("gère les permissions internes du bot", "dev_permissions"),
    ("configure les accès internes développeur", "dev_permissions"),
    ("modifie les droits d'accès aux commandes dev", "dev_permissions"),

    ("bannis ce serveur du bot", "dev_botban"),
    ("blackliste cette guild", "dev_botban"),
    ("empêche ce serveur d'utiliser le bot", "dev_botban"),

    ("fais quitter guideon de ce serveur", "dev_kick"),
    ("retire le bot de ce serveur", "dev_kick"),

    ("crée une invitation sur ce serveur", "dev_join_serv"),
    ("génère un lien d'invitation pour rejoindre ce serveur", "dev_join_serv"),

    ("supprime ce message envoyé par guideon", "dev_delete_message"),
    ("efface ce message du bot", "dev_delete_message"),

    ("change la version ng bedrock actuelle", "dev_setngversion"),
    ("mets à jour la version affichée du jeu", "dev_setngversion"),

    ("active le gold+ sur ce serveur", "dev_gold"),
    ("retire le statut gold de ce serveur", "dev_gold"),
    ("donne l'abonnement gold à ce serveur", "dev_gold"),

    ("donne le vip à cet utilisateur", "dev_vip"),
    ("retire le vip de ce membre", "dev_vip"),
    ("active le statut vip pour ce joueur", "dev_vip"),

    # ============================================================
    # CONVERSATION / SMALLTALK (nouveau v4)
    # ============================================================
    ("salut", "greeting"),
    ("coucou", "greeting"),
    ("bonjour", "greeting"),
    ("hey", "greeting"),
    ("yo", "greeting"),
    ("salut ça va ?", "greeting"),
    ("bonsoir", "greeting"),
    ("hello", "greeting"),
    ("wesh", "greeting"),
    ("cc", "greeting"),

    ("ça va ?", "how_are_you"),
    ("comment tu vas", "how_are_you"),
    ("comment vas-tu", "how_are_you"),
    ("tu vas bien ?", "how_are_you"),
    ("ça roule ?", "how_are_you"),
    ("comment ça va toi", "how_are_you"),
    ("et toi ça va ?", "how_are_you"),
    ("tu te portes bien ?", "how_are_you"),

    ("merci", "thanks"),
    ("merci beaucoup", "thanks"),
    ("je te remercie", "thanks"),
    ("top merci", "thanks"),
    ("merci pour ton aide", "thanks"),
    ("thanks", "thanks"),
    ("merci infiniment", "thanks"),
    ("c'est gentil merci", "thanks"),

    ("au revoir", "goodbye"),
    ("à plus", "goodbye"),
    ("à bientôt", "goodbye"),
    ("bye", "goodbye"),
    ("salut à plus tard", "goodbye"),
    ("je m'en vais", "goodbye"),
    ("bonne nuit", "goodbye"),
    ("à la prochaine", "goodbye"),

    ("qui es-tu", "who_are_you"),
    ("t'es qui toi", "who_are_you"),
    ("c'est quoi ton nom", "who_are_you"),
    ("comment tu t'appelles", "who_are_you"),
    ("qui êtes-vous", "who_are_you"),
    ("présente-toi", "who_are_you"),
    ("tu es qui exactement", "who_are_you"),

    ("qui t'a créé", "bot_creator"),
    ("qui t'a codé", "bot_creator"),
    ("qui t'a programmé", "bot_creator"),
    ("qui est ton développeur", "bot_creator"),
    ("c'est qui ton créateur", "bot_creator"),
    ("qui a fait ce bot", "bot_creator"),

    ("que sais-tu faire", "what_can_you_do"),
    ("qu'est-ce que tu peux faire", "what_can_you_do"),
    ("aide-moi", "what_can_you_do"),
    ("help", "what_can_you_do"),
    ("quelles sont tes fonctionnalités", "what_can_you_do"),
    ("montre-moi ce que tu sais faire", "what_can_you_do"),
    ("à quoi tu sers", "what_can_you_do"),

    ("raconte une blague", "joke"),
    ("dis-moi une blague", "joke"),
    ("fais-moi rire", "joke"),
    ("tu connais une blague ?", "joke"),
    ("raconte-moi quelque chose de drôle", "joke"),

    ("t'es cool", "compliment_bot"),
    ("bien joué", "compliment_bot"),
    ("t'es un bon bot", "compliment_bot"),
    ("je t'aime bien", "compliment_bot"),
    ("t'assures", "compliment_bot"),
    ("gg", "compliment_bot"),
    ("t'es vraiment utile", "compliment_bot"),

    ("t'es nul", "insult_bot"),
    ("t'es useless", "insult_bot"),
    ("ferme-la", "insult_bot"),
    ("tu sers à rien", "insult_bot"),
    ("t'es débile", "insult_bot"),
    ("t'es pas doué", "insult_bot"),

    ("je m'ennuie", "bored"),
    ("je m'ennuie grave", "bored"),
    ("y'a rien à faire ici", "bored"),
    ("je sais pas quoi faire", "bored"),
    ("je me fais chier", "bored"),

    ("quel temps fait-il", "smalltalk_weather"),
    ("il fait beau chez toi", "smalltalk_weather"),
    ("quelle est la météo", "smalltalk_weather"),
    ("il pleut chez toi ?", "smalltalk_weather"),

    ("quelle heure est-il", "smalltalk_time"),
    ("on est quel jour", "smalltalk_time"),
    ("quel jour on est aujourd'hui", "smalltalk_time"),
    ("c'est quelle date aujourd'hui", "smalltalk_time"),

    ("oui", "yes_confirm"),
    ("ouais", "yes_confirm"),
    ("oui c'est ça", "yes_confirm"),
    ("exact", "yes_confirm"),
    ("c'est ça", "yes_confirm"),
    ("yes", "yes_confirm"),
    ("affirmatif", "yes_confirm"),
    ("tout à fait", "yes_confirm"),

    ("non", "no_deny"),
    ("non pas ça", "no_deny"),
    ("pas vraiment", "no_deny"),
    ("non c'est pas ça", "no_deny"),
    ("nope", "no_deny"),
    ("absolument pas", "no_deny"),

    ("test", "are_you_there"),
    ("y'a quelqu'un ?", "are_you_there"),
    ("t'es là ?", "are_you_there"),
    ("es-tu là", "are_you_there"),
    ("allo", "are_you_there"),
    ("1234", "are_you_there"),
    ("tu m'entends ?", "are_you_there"),
]