"""
Génération d'IDs courts pour sanctions et giveaways.
"""
import secrets

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"


def short_id(length: int = 8) -> str:
    """Génère un ID."""
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def sanction_id() -> str:
    """ID de sanction : 6 caractères."""
    return short_id(6)


def giveaway_id() -> str:
    """ID de giveaway : 8 caractères."""
    return short_id(8)