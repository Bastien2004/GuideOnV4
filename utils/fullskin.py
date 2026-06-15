"""
utils/fullskin.py - Renvoie les URLs des skins d'un joueur NationsGlory.
"""

BASE_URL = "https://skins.nationsglory.fr"


# ============================================================
# 🧠 Fonctions
# ============================================================

def get_skin_original(pseudo: str) -> str:
    """Skin complet original du joueur."""
    return f"{BASE_URL}/{pseudo}"


def get_tete_2d(pseudo: str, size: int = 16) -> str:
    """Tête 2D du joueur."""
    return f"{BASE_URL}/face/{pseudo}/{size}"


def get_tete_3d(pseudo: str, size: int = 16) -> str:
    """Tête 3D du joueur."""
    return f"{BASE_URL}/face/{pseudo}/3d/{size}"


def get_skin_2d(pseudo: str, size: int = 16) -> str:
    """Corps 2D du joueur."""
    return f"{BASE_URL}/body/{pseudo}/{size}"


def get_skin_3d(pseudo: str, size: int = 16) -> str:
    """Corps 3D du joueur."""
    return f"{BASE_URL}/body/{pseudo}/3d/{size}"

def get_all_skins(pseudo: str, size: int = 16) -> dict:
    """Renvoie toutes les URLs utiles dans un seul dictionnaire."""
    return {
        "original": get_skin_original(pseudo),
        "tete_2d": get_tete_2d(pseudo, size),
        "tete_3d": get_tete_3d(pseudo, size),
        "corps_2d": get_skin_2d(pseudo, size),
        "corps_3d": get_skin_3d(pseudo, size),
    }