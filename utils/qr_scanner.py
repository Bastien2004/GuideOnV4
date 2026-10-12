"""
utils/qr_scanner.py — Décodage de QR codes à partir d'une image.
"""

from __future__ import annotations

import logging
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)


def decode_qr_image(image_bytes: bytes) -> Optional[str]:
    """Décode le premier QR code trouvé dans une image."""

    if not image_bytes:
        return None

    array = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(array, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None

    if len(img.shape) == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        bgr = img[:, :, :3]
        bg = np.ones_like(bgr, dtype=np.uint8) * 255
        alpha_factor = alpha[:, :, np.newaxis] / 255.0
        img = (bgr * alpha_factor + bg * (1 - alpha_factor)).astype(np.uint8)

    detector = cv2.QRCodeDetector()

    contenu, _, _ = detector.detectAndDecode(img)
    if contenu:
        return contenu

    height, width = img.shape[:2]
    if max(height, width) > 1024:
        scale = 1024 / max(height, width)
        resized = cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        contenu, _, _ = detector.detectAndDecode(resized)
        if contenu:
            return contenu

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    contenu, _, _ = detector.detectAndDecode(gray)
    if contenu:
        return contenu

    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10)
    contenu, _, _ = detector.detectAndDecode(thresh)

    return contenu if contenu else None