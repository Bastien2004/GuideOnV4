"""
views/qr/scan_view.py — Vue de résultat pour /qr scan.
"""

from __future__ import annotations

from typing import Optional

from discord.ui import Container, Separator, TextDisplay

from views._components.base_view import BaseLayoutView
from views.qr._shared import format_date, truncate


# ============================================================
# 🎨 View — /qr scan
# ============================================================

class QRScanResultView(BaseLayoutView):
    """Résultat compact d'un scan : contenu décodé + origine (sur ce serveur)."""

    def __init__(self, contenu: str, origine: Optional[object], *, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self.contenu = contenu
        self.origine = origine
        self._build()

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# <:lien:1552027533032034394> QR code scanné"))
        c.add_item(Separator())

        c.add_item(TextDisplay(f"**Contenu détecté**\n➥ `{truncate(self.contenu, 300)}`"))
        c.add_item(Separator())

        c.add_item(TextDisplay("-# GuideOn n'est pas responsable du contenu de ces liens."))

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)


def build_qr_scan_view(contenu: str, origine: Optional[object], *, owner_id: int) -> QRScanResultView:
    """Construit l'interface de résultat d'un scan QR code."""

    return QRScanResultView(contenu, origine, owner_id=owner_id)