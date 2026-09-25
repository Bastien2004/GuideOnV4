"""
test.py — Teste le modèle entraîné (model.pth) sur un grand nombre de
phrases, et affiche un rapport de réussite/échec par intention.

⚠️ Important : les phrases ci-dessous sont volontairement DIFFÉRENTES
(ou légèrement différentes) de celles utilisées dans dataset.py. Le but
n'est pas de vérifier que le modèle "récite" ce qu'il a appris par
cœur, mais qu'il GÉNÉRALISE sur des formulations nouvelles.

Lance simplement :
    python test.py

Assure-toi d'avoir lancé train.py au moins une fois avant (il faut un
model.pth à jour).
"""

import torch
from tokenizer import tokenize
from vectorizer import vectorize
from model import Model


# ============================================================
# Chargement du modèle (identique à predict.py, mais sans les
# seuils de confiance / RESPONSES / PERMISSIONS : ici on veut la
# prédiction brute pour pouvoir la comparer à la bonne réponse).
# ============================================================

checkpoint = torch.load("model.pth")

vocabulary = checkpoint["vocabulary"]
intents = checkpoint["intents"]

model = Model(
    checkpoint["input_size"],
    checkpoint["hidden_size"],
    checkpoint["output_size"]
)
model.load_state_dict(checkpoint["model_state"])
model.eval()


def raw_predict(phrase):
    """Renvoie (intention_predite, confiance) sans aucun seuil appliqué."""
    tokens = tokenize(phrase)
    vector = vectorize(tokens, vocabulary)
    x = torch.tensor(vector).float().unsqueeze(0)

    with torch.no_grad():
        output = model(x)
        probabilities = torch.softmax(output, dim=1)
        predicted_class = probabilities.argmax(dim=1).item()

    confiance = probabilities[0][predicted_class].item()
    return intents[predicted_class], confiance


# ============================================================
# Cas de test : (phrase, intention_attendue)
#
# Volontairement reformulés par rapport à dataset.py pour tester la
# généralisation, pas la mémorisation.
# ============================================================

TEST_CASES = [
    # ---- TICKET ----
    ("j'aimerais qu'on m'ouvre un ticket", "ticket_create"),
    ("comment je fais pour avoir un ticket support", "ticket_create"),
    ("peux-tu ajouter mon pote dans ce ticket", "ticket_add"),
    ("sors cette personne du ticket stp", "ticket_remove"),
    ("je voudrais changer le titre de ce ticket", "ticket_rename"),
    ("empêche ce mec d'ouvrir un ticket", "ticket_ban"),
    ("il peut de nouveau faire des tickets", "ticket_unban"),
    ("on peut clôturer ce ticket maintenant", "ticket_close"),
    ("supprime ce ticket pour de bon", "ticket_delete"),
    ("il n'a pas répondu depuis 2 jours dans son ticket", "ticket_wakeup"),
    ("installe le système de tickets ici", "ticket_panel_create"),
    ("enlève le panel de tickets du salon", "ticket_panel_delete"),
    ("change le texte du panel de tickets", "ticket_panel_edit"),
    ("combien de panels de tickets on a", "ticket_panel_list"),

    # ---- MOD ----
    ("bannis-moi ce trouble-fête", "mod_ban"),
    ("annule le ban de ce joueur", "mod_unban"),
    ("dégage-le du serveur", "mod_kick"),
    ("colle-lui un avertissement", "mod_warn"),
    ("empêche-le de parler pendant 10 minutes", "mod_mute"),
    ("il peut reparler maintenant", "mod_unmute"),
    ("bannis-le pour 48h", "mod_tempban"),
    ("softban ce type", "mod_softban"),
    ("montre-moi son casier de sanctions", "mod_historique"),
    ("change son surnom sur le serveur", "mod_rename"),
    ("nettoie les 100 derniers messages", "mod_clear"),
    ("bloque ce salon pour que personne écrive", "mod_lock"),
    ("réouvre l'écriture dans ce salon", "mod_unlock"),
    ("expulse tout le vocal", "mod_vocal"),
    ("je veux régler l'automod", "mod_config"),
    ("qui a accès aux commandes de modération", "mod_permissions"),
    ("mets en place le salon anti-raid", "mod_piege"),
    ("configure où vont les logs", "mod_logs"),

    # ---- CONFIG ----
    ("donne un rôle automatique aux arrivants", "config_autorole"),
    ("règle le message d'accueil du serveur", "config_bienvenue"),
    ("attribue ce rôle à tous les membres", "config_role_all"),
    ("crée un message avec des rôles à cliquer", "config_role_reaction"),
    ("configure les salons vocaux dynamiques", "config_join_to_create"),

    # ---- GIVEAWAY ----
    ("organise un concours avec un lot à gagner", "giveaway_create"),
    ("je veux modifier le giveaway actuel", "giveaway_manage"),
    ("empêche ce joueur de participer aux concours", "giveaway_blacklist"),
    ("quels concours sont ouverts en ce moment", "giveaway_list"),

    # ---- BIRTHDAY ----
    ("ajoute la date de mon anniversaire", "birthday_add"),
    ("montre les anniversaires du mois", "birthday_list"),
    ("qui fête bientôt son anniv", "birthday_next"),
    ("dans quel salon annoncer les anniversaires", "birthday_config"),

    # ---- EXP ----
    ("explique-moi comment marche le niveau", "exp_info"),
    ("c'est quoi mon niveau actuel", "exp_level"),
    ("qui est premier au classement d'exp", "exp_leaderboard"),
    ("modifie la vitesse pour monter de niveau", "exp_config"),
    ("enlève de l'expérience à ce joueur", "exp_gestion"),

    # ---- INVITE ----
    ("qui a ramené le plus de membres", "invite_classement"),
    ("combien de gens j'ai fait venir", "invite_user"),
    ("règle le système d'invitations", "invite_config"),
    ("corrige son nombre d'invitations", "invite_gestion"),

    # ---- MEDIALINK ----
    ("règle les liens medialink du serveur", "medialink_config"),

    # ---- QR ----
    ("fabrique-moi un qr code", "qr_generate"),
    ("lis ce qr code pour moi", "qr_scan"),
    ("montre mes qr codes créés", "qr_list"),

    # ---- NG ----
    ("dis m'en plus sur nationsglory", "ng_info"),
    ("c'est quelle version en ce moment", "ng_version"),
    ("transforme ces items en stacks", "ng_convert"),
    ("montre la carte en temps réel", "ng_dynmaps"),
    ("explique ce palier de r&d", "ng_rd"),
    ("comment marchent les autels", "ng_autel"),
    ("c'est quoi une onu ici", "ng_onu"),
    ("affiche le skin de ce pseudo", "ng_skin"),
    ("montre-moi les sanctions en cours", "ng_sanction"),

    # ---- NGSTAFF ----
    ("augmente son grade dans le staff", "ngstaff_rank"),
    ("fais-le redescendre en grade", "ngstaff_derank"),
    ("ouvre le dashboard staff", "ngstaff_config"),
    ("régénère la liste du staff", "ngstaff_stafflist"),
    ("corrige une erreur dans la stafflist", "ngstaff_edit_stafflist"),
    ("vérifie le système de notation du staff", "ngstaff_nota_debug"),

    # ---- ALPHA ----
    ("démarre l'event maintenant", "alpha_event_start"),
    ("quelles sont les règles de cet event", "alpha_event_regle"),
    ("montre tous les events prévus", "alpha_event_list"),
    ("mets à jour l'index alpha", "alpha_index"),
    ("comment on rejoint alpha", "alpha_nous_rejoindre"),
    ("affiche les règles internes de l'équipe", "alpha_regle_interne"),

    # ---- IRIS ----
    ("montre les règles du serveur iris", "iris_reglement"),

    # ---- COMMANDES GÉNÉRALES ----
    ("j'ai besoin d'aide, où est le wiki", "wiki"),
    ("je veux signaler un problème", "report"),
    ("cherche ce membre avec son id discord", "id_command"),
    ("montre le profil de ce membre", "user_command"),
    ("c'est quoi ce bot", "info"),
    ("donne-moi un timestamp discord", "timestamp_command"),
    ("le bot a combien de latence", "ping_command"),

    # ---- DEV ----
    ("le bot fonctionne normalement ?", "dev_health"),
    ("montre les infos de cette guild", "dev_guild_info"),
    ("combien de serveurs utilisent le bot", "dev_stat_server"),
    ("stats d'utilisation de cette commande", "dev_stat_cmd"),
    ("analyse le bug de cette commande", "dev_debug_cmd"),
    ("ouvre la base de données", "dev_database"),
    ("coupe temporairement cette commande", "dev_maintenance"),
    ("bannis ce serveur du bot", "dev_botban"),
    ("fais partir le bot de ce serveur", "dev_kick"),
    ("active le gold sur ce serveur", "dev_gold"),
    ("donne le vip à ce joueur", "dev_vip"),
]


# ============================================================
# Cas "pièges" : pas de bonne réponse fixe attendue, juste pour
# observer le comportement (confiance basse attendue).
# ============================================================

EDGE_CASES = [
    "bonjour",
    "merci beaucoup",
    "sdkfjqsdlkfj",
    "a",
    "je sais pas quoi faire",
]


def run_tests():
    print("=" * 60)
    print("TESTS DE GÉNÉRALISATION (phrases reformulées)")
    print("=" * 60)

    reussites = 0
    echecs = []

    for phrase, attendu in TEST_CASES:
        intent, confiance = raw_predict(phrase)
        ok = intent == attendu

        if ok:
            reussites += 1
            statut = "OK  "
        else:
            echecs.append((phrase, attendu, intent, confiance))
            statut = "FAIL"

        print(f"[{statut}] {confiance:>6.1%}  {phrase!r:55s} -> {intent} (attendu: {attendu})")

    total = len(TEST_CASES)
    print()
    print("=" * 60)
    print(f"RÉSULTAT : {reussites}/{total} réussites ({reussites/total:.1%})")
    print("=" * 60)

    if echecs:
        print()
        print(f"--- {len(echecs)} ÉCHEC(S) DÉTAILLÉ(S) ---")
        for phrase, attendu, obtenu, confiance in echecs:
            print(f"  {phrase!r}")
            print(f"    attendu : {attendu}")
            print(f"    obtenu  : {obtenu} (confiance {confiance:.1%})")

    print()
    print("=" * 60)
    print("CAS PIÈGES (pas de bonne réponse attendue)")
    print("=" * 60)
    for phrase in EDGE_CASES:
        intent, confiance = raw_predict(phrase)
        alerte = "  <-- confiance élevée sur une phrase hors-sujet !" if confiance > 0.6 else ""
        print(f"  {confiance:>6.1%}  {phrase!r:30s} -> {intent}{alerte}")


if __name__ == "__main__":
    run_tests()
