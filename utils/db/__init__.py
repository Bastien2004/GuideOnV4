"""
Import central de tous les modèles.

Alembic autogenerate scanne ce fichier pour détecter les changements de schéma.
TOUT nouveau modèle DOIT être importé ici, sinon Alembic ne créera pas sa table.
"""
from utils.db.base import Base

from utils.db.models.control_admin import CommandControl
from utils.db.models.boutique import ShopEntry, ShopRole
from utils.db.models.bienvenue import BienvenueConfig

# TODO (au fur et à mesure que les systèmes sont portés en V4) :
# from utils.db.models.ticket import Ticket, TicketPanel, TicketBan
# from utils.db.models.giveaway import Giveaway, GiveawayEntry
# from utils.db.models.exp import ExpEntry, ExpConfig
# from utils.db.models.invite import ...
# from utils.db.models.moderation import ...
# etc.

__all__ = [
    "Base",
    "CommandControl",
    "ShopEntry",
    "ShopRole",
    "BienvenueConfig",
]