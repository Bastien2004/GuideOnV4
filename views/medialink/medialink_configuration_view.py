"""
views/medialink/medialink_configuration_view.py — réglages transverses
du module MEDIALINK pour une guild (à distinguer des réglages PAR
connexion/règle, gérés dans medialink_platforms_view.py/
medialink_events_view.py).

STUB minimal : le cahier des charges ne liste pas explicitement de
réglage "global" au module au-delà de ce qui est déjà par connexion/
règle/template — ce fichier existe pour recevoir ce qui apparaîtra
au fil des retours de Paul ("il y a d'autres points sur lesquelles je
reviendrais"), plutôt que d'inventer des options non demandées.
"""
from __future__ import annotations

from discord.ui import Container, Separator, TextDisplay

from views._components.base_view import BaseLayoutView


class MediaLinkSettingsView(BaseLayoutView):
    """Placeholder — pas de réglage global identifié pour l'instant."""

    def __init__(self, *, guild_id: int, owner_id: int):
        super().__init__(owner_id=owner_id, timeout=300)
        self.guild_id = guild_id
        self._build()

    def _build(self) -> None:
        container = Container()
        container.add_item(TextDisplay("# ⚙️ Réglages MEDIALINK"))
        container.add_item(Separator())
        container.add_item(
            TextDisplay(
                "Aucun réglage global identifié pour l'instant — les "
                "réglages actuels sont tous rattachés à une connexion "
                "ou une règle précise (voir le dashboard)."
            )
        )
        self.add_item(container)
