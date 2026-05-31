"""
Import central de tous les modèles.
"""
from utils.db.base import Base

from utils.db.models.control_admin import CommandControl
from utils.db.models.ticket import Ticket, TicketPanel, TicketPanelStaffRole
from utils.db.models.autorole import AutoRoleConfig
from utils.db.models.reaction_role import ReactionRoleCouple, ReactionRoleMessage
from utils.db.models.bug_report import BugReport
from utils.db.models.invite import InviteConfig, InviteLink, InviteStat
from utils.db.models.birthday import BirthdayConfig, BirthdayUser

__all__ = [
    "Base",
    "CommandControl",
    "Ticket",
    "TicketPanel",
    "TicketPanelStaffRole",
    "AutoRoleConfig",
    "ReactionRoleCouple",
    "ReactionRoleMessage",
    "BugReport",
    "InviteConfig",
    "InviteLink",
    "InviteStat",
    "BirthdayConfig",
    "BirthdayUser",
]