"""
utils/medialink/builders/container.py — rendu Components V2 pour les
VUES DU DASHBOARD MEDIALINK (pas les annonces envoyées aux membres, cf.
announcement.py pour celles-ci).

Pour les retours génériques (succès/erreur/info), ne pas dupliquer —
utils/container_universel.py fournit déjà error_container/
success_container/info_container/warning_container/send_ephemeral,
utilisés par tout le reste du bot (perm_admin, perm_staff...) : les vues
de views/medialink/ doivent les réutiliser tels quels plutôt que d'en
recréer des variantes locales.

Ce module ne contient donc que ce qui est SPÉCIFIQUE à MEDIALINK et pas
couvert par container_universel.py — pour l'instant, l'état vide du
dashboard (§6.2 : que montrer quand aucune connexion n'existe encore).
"""
from __future__ import annotations

from discord.ui import Container, LayoutView, Separator, TextDisplay


def empty_state_container() -> LayoutView:
    """Affiché sur /medialink config quand la guild n'a encore aucune
    connexion — invite explicitement à en ajouter une plutôt que de
    montrer un dashboard vide et silencieux (§6.2)."""
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 📡 MEDIALINK"))
    container.add_item(Separator())
    container.add_item(
        TextDisplay(
            "Aucun compte connecté pour le moment.\n"
            "Ajoute une première connexion (YouTube, Twitch, TikTok ou "
            "Reddit) pour commencer à recevoir des annonces automatiques."
        )
    )
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view
