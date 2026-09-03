"""
utils/db/models/medialink_statistics.py — MEDIALINK : statistiques
(écran "Statistiques" du dashboard, §16).

VOLONTAIREMENT NON IMPLÉMENTÉ pour l'instant.

Le cahier des charges ne fige pas le besoin exact : il liste
"Statistiques" comme écran attendu (§16) mais renvoie la structure de
stockage à une décision de stratégie d'agrégation ("selon stratégie
d'agrégation" — comptage à la volée sur media_events vs. table
d'agrégats pré-calculés par jour/connexion). Les deux ont un coût
différent :

  - Comptage à la volée (SELECT ... GROUP BY sur media_events) : zéro
    nouvelle table, mais potentiellement lent une fois l'historique
    volumineux, et impossible si on veut purger/archiver media_events
    au bout d'un moment.
  - Table d'agrégats (ex: media_statistics_daily(guild_id, connection_id,
    day, event_type, count)) : rapide à lire, mais demande un job qui
    l'alimente (candidat naturel pour utils/medialink/scheduler.py ou
    processor.py) et une politique de rétention à elle.

Je n'ai pas tranché à la place de Paul — ce fichier sert de marqueur
explicite de la décision en attente plutôt que d'une hypothèse
silencieuse. Une fois le choix fait, ce module portera soit un modèle
d'agrégats, soit rien du tout (si comptage à la volée retenu, auquel cas
il peut être supprimé).
"""
from __future__ import annotations

# Aucun modèle défini ici pour l'instant — voir docstring de module.
