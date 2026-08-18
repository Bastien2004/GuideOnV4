"""
utils/qr_scanner.py — Décodage de QR codes à partir d'une image (bytes).

Bibliothèque : opencv-python-headless → pip install opencv-python-headless numpy
Choisie plutôt que pyzbar car 100% pip, sans dépendance système (libzbar).
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


def decode_qr_image(image_bytes: bytes) -> Optional[str]:
    """Décode le premier QR code trouvé dans une image. Renvoie None si rien n'est détecté."""

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if img is None:
        return None

    detector = cv2.QRCodeDetector()
    contenu, points, _ = detector.detectAndDecode(img)

    return contenu if contenu else None