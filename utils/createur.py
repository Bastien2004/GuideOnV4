"""
utils/createur.py — IDs des créateur (en dur).
"""
from __future__ import annotations

CREATOR_IDS: set[int] = {
    930821995787091988,
    434754329317081098,
}


def is_creator(user_id: int) -> bool:
    """True si user_id est un créateur."""
    return user_id in CREATOR_IDS