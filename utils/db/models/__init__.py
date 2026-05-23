"""
Import central de tous les modèles.

Alembic autogenerate scanne ce fichier pour détecter les changements de schéma.
TOUT nouveau modèle DOIT être importé ici.
"""
from utils.db.base import Base

from utils.db.models.control_admin import CommandControl
from utils.db.models.ticket import Ticket, TicketPanel, TicketPanelStaffRole

# TODO (au fur et à mesure) :
# from utils.db.models.giveaway import Giveaway, GiveawayEntry
# from utils.db.models.exp import ExpEntry, ExpConfig
# etc.

__all__ = [
    "Base",
    "CommandControl",
    "Ticket",
    "TicketPanel",
    "TicketPanelStaffRole",
]