import json
import logging
import os

log = logging.getLogger(__name__)

VERSION_FILE = "data/ng_json/ng_version.json"


def lire_version():
    if not os.path.exists(VERSION_FILE):
        return "Version inconnue"
    try:
        with open(VERSION_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        log.warning("[ngversion_manager] %s vide ou corrompu, valeur par défaut utilisée", VERSION_FILE)
        return "Version inconnue"
    if not isinstance(data, dict):
        return "Version inconnue"
    return data.get("version", "Version inconnue")


def ecrire_version(nouvelle_version: str):
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    tmp_path = f"{VERSION_FILE}.tmp"
    with open(tmp_path, "w") as f:
        json.dump({"version": nouvelle_version}, f, indent=4)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, VERSION_FILE)