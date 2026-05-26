"""
Import central de tous les modèles.
"""
from utils.db.base import Base

from utils.db.models.control_admin import CommandControl
from utils.db.models.ticket import Ticket, TicketPanel, TicketPanelStaffRole
from utils.db.models.autorole import AutoRoleConfig
from utils.db.models.reaction_role import ReactionRoleCouple, ReactionRoleMessage

__all__ = [
    "Base",
    "CommandControl",
    "Ticket",
    "TicketPanel",
    "TicketPanelStaffRole",
    "AutoRoleConfig",
    "ReactionRoleCouple",
    "ReactionRoleMessage",
]