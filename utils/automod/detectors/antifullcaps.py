"""
utils/automod/detectors/antifullcaps.py — Détection des messages en full maj.

Fonction pure, testable en isolation. Retourne le ratio détecté (utile
comme matched_term pour les stats) ou None si pas d'infraction.

Algorithme :
  1. Si le message fait moins de min_length caractères, on ne fait rien
     (protège "OK", "LOL", etc.).
  2. On extrait les LETTRES uniquement (isalpha). Si aucune lettre → None.
  3. On calcule le ratio (lettres MAJ) / (lettres totales).
  4. Si ratio >= ratio_threshold → détecté, on retourne la chaîne "X%".
"""
from __future__ import annotations


def detect(
    message_content: str,
    *,
    min_length: int = 10,
    ratio_threshold: float = 0.7,
) -> str | None:
    if not message_content:
        return None
    if len(message_content) < min_length:
        return None

    letters = [c for c in message_content if c.isalpha()]
    if not letters:
        return None

    upper_count = sum(1 for c in letters if c.isupper())
    ratio = upper_count / len(letters)

    if ratio >= ratio_threshold:
        return f"{int(ratio * 100)}% MAJ"
    return None