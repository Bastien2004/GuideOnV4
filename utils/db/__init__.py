"""
utils/db/__init__.py — marqueur de package, intentionnellement minimal.

Le registre central des modèles — celui que lit réellement Alembic pour
l'autogenerate (voir migrations/env.py : `from utils.db.models import Base`)
— est utils/db/models/__init__.py. Tout nouveau modèle doit être importé
LÀ-BAS, pas ici.

Historique : ce fichier contenait auparavant sa propre liste partielle
d'imports (Bienvenue, Boutique, Permission...), jamais importée nulle
part dans le code (vérifié), qui avait divergé du vrai registre — ces
3 modèles étaient donc invisibles pour Alembic. Supprimé le 2026-07-03.
"""
from utils.db.models import Base  # noqa: F401 — reste dispo via `from utils.db import Base` par compat