import json
import os

VERSION_FILE = "data/ng_json/ng_version.json"

def lire_version():
    if not os.path.exists(VERSION_FILE):
        return "Version inconnue"
    with open(VERSION_FILE, "r") as f:
        data = json.load(f)
    return data.get("version", "Version inconnue")

def ecrire_version(nouvelle_version: str):
    with open(VERSION_FILE, "w") as f:
        json.dump({"version": nouvelle_version}, f, indent=4)