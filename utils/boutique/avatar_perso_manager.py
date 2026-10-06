"""
utils/boutique/avatar_perso_manager.py — Gestion de l'add-on boutique
"Avatar Perso" (avatar de bot personnalisé par serveur).

Même structure que utils/boutique/gold_manager.py : un simple wrapper de
lecture autour du cache boutique partagé (utils.managers.boutique_manager).
L'écriture (achat/retrait) ne passe PAS par un flux self-service — elle est
appliquée manuellement par le staff via /dev avatar_bot (voir
cogs/dev/avatar_bot.py et utils/managers/bot_avatar_manager.py), qui
appelle directement boutique_manager.add_entry/remove_entry.
"""

from __future__ import annotations

from utils.managers.boutique_manager import is_avatar_perso_id


# ============================================================
# 🔩  Fonctions utilitaires
# ============================================================

def is_avatar_perso(guild_id: int) -> bool:
    """True si le serveur a payé l'add-on boutique "Avatar Perso"."""
    return is_avatar_perso_id(guild_id)
