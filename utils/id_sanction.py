"""
Génération d'IDs courts pour sanctions et giveaways.

Alphabet sans ambiguïtés (pas de 0/O/1/l/I).
"""
import secrets

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"


def short_id(length: int = 8) -> str:
    """Génère un ID court alphanumérique."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def sanction_id() -> str:
    """ID de sanction : 6 caractères."""
    return short_id(6)


def giveaway_id() -> str:
    """ID de giveaway : 8 caractères."""
    return short_id(8)
