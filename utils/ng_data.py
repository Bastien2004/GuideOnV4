"""
Chargement des données statiques NationsGlory.

Ces données ne vont PAS en DB (référence statique mise à jour à la main) :
- data/ng/rd.json : table R&D complète
- data/ng/ng_coo_autel.json : coordonnées des autels
- data/ng/ng_version.json : version Bedrock courante
"""
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("data/ng")


def load_rd_data() -> dict[str, Any]:
    """Table R&D NationsGlory."""
    with (DATA_DIR / "rd.json").open(encoding="utf-8") as f:
        return json.load(f)


def load_autel_coords() -> dict[str, Any]:
    """Coordonnées des autels par serveur."""
    with (DATA_DIR / "ng_coo_autel.json").open(encoding="utf-8") as f:
        return json.load(f)


def load_ng_version() -> dict[str, Any]:
    """Version Bedrock courante (modifiable via /dev setngversion)."""
    with (DATA_DIR / "ng_version.json").open(encoding="utf-8") as f:
        return json.load(f)


def save_ng_version(data: dict[str, Any]) -> None:
    """Sauvegarde la version courante."""
    with (DATA_DIR / "ng_version.json").open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
