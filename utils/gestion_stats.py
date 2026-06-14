"""
utils/gestion_stats.py — Gestion des statistiques de commandes.

🟡 STUB : À compléter par le collègue responsable de la base de données.
"""

def incrementer_commande(nom_commande: str, user_id: int, guild_id: int | None):
    """
    Fonction appelée à chaque utilisation d'une commande.

    PARAMÈTRES :
    - nom_commande : str → nom interne de la commande (ex: "ng_dynmaps")
    - user_id      : int → ID Discord de l'utilisateur
    - guild_id     : int | None → ID du serveur (toujours présent grâce à tracker_commande)

    À FAIRE :
    - Insérer ou mettre à jour une ligne dans la table des stats
    - Incrémenter un compteur d'utilisation
    - Enregistrer la date/heure
    - Optionnel : stocker par utilisateur, par serveur, etc.

    ⚠️ IMPORTANT :
    - Cette fonction NE DOIT PAS lever d'erreur.
    - Si la DB est indisponible, log + return.
    """

    # Exemple de squelette (à remplacer par la vraie DB) :
    try:
        # TODO: écrire ici la logique SQLAlchemy / asyncpg / autre
        pass

    except Exception as e:
        print(f"[GESTION_STATS] Erreur DB : {e}")