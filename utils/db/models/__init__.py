"""
Import central de tous les modèles.
"""

from utils.db.base import Base

from utils.db.models.alpha import AlphaMessageConfig
from utils.db.models.alpha_event_config import AlphaEventConfig
from utils.db.models.autorole import AutoRoleConfig
from utils.db.models.bienvenue import BienvenueConfig
from utils.db.models.birthday import BirthdayConfig, BirthdayUser
from utils.db.models.bot_ban import BotBan
from utils.db.models.boutique import ShopEntry, ShopRole
from utils.db.models.bug_report import BugReport
from utils.db.models.command_stats import CommandStatDaily
from utils.db.models.control_admin import CommandControl
from utils.db.models.exp import ExpConfig, ExpUser
from utils.db.models.giveaway import Giveaway, GiveawayBlacklist, GiveawayParticipant
from utils.db.models.invite import InviteConfig, InviteLink, InviteStat
from utils.db.models.mod_log import LogConfig
from utils.db.models.mod_permission import ModPermissionRole
from utils.db.models.mod_sanction import ModSanctionConfig, Sanction, SanctionType
from utils.db.models.ng_nota_config import NGNotaAvailability, NGNotaConfig, NGNotaHistory, NGNotaWeekState
from utils.db.models.ng_onu_config import NGONUConfig, NGONUPingMember
from utils.db.models.ng_rank_config import NGRankConfig
from utils.db.models.ng_role_react import NGRoleReactCouple, NGRoleReaction
from utils.db.models.ng_server import NGServer
from utils.db.models.ng_staff import NGStaffMember
from utils.db.models.permission_rbac import PermissionCategory, PermissionGrade, PermissionGradeInclude, PermissionGradeMember
from utils.db.models.reaction_role import ReactionRoleCouple, ReactionRoleMessage
from utils.db.models.staff import StaffConfig
from utils.db.models.ticket import Ticket, TicketPanel, TicketPanelStaffRole
from utils.db.models.mod_automod_general import ModAutomodGeneral
from utils.db.models.mod_automod_infraction import ModAutomodInfraction
from utils.db.models.mod_automod_banword import ModAutomodBanwordConfig, ModAutomodBanwordWord
from utils.db.models.mod_automod_antifullcaps import ModAutomodAntifullcapsConfig
from utils.db.models.mod_automod_antispam_mention import ModAutomodAntispamMentionConfig
from utils.db.models.mod_automod_antispam_emoji import ModAutomodAntispamEmojiConfig
from utils.db.models.mod_automod_active_alert import ModAutomodActiveAlert

__all__ = [
    "AlphaEventConfig",
    "AlphaMessageConfig",
    "AutoRoleConfig",
    "Base",
    "BienvenueConfig",
    "BirthdayConfig",
    "BirthdayUser",
    "BotBan",
    "BugReport",
    "CommandControl",
    "CommandStatDaily",
    "ExpConfig",
    "ExpUser",
    "Giveaway",
    "GiveawayBlacklist",
    "GiveawayParticipant",
    "InviteConfig",
    "InviteLink",
    "InviteStat",
    "LogConfig",
    "ModPermissionRole",
    "ModSanctionConfig",
    "NGNotaAvailability",
    "NGNotaConfig",
    "NGNotaHistory",
    "NGNotaWeekState",
    "NGONUConfig",
    "NGONUPingMember",
    "NGRankConfig",
    "NGRoleReactCouple",
    "NGRoleReaction",
    "NGServer",
    "NGStaffMember",
    "PermissionCategory",
    "PermissionGrade",
    "PermissionGradeInclude",
    "PermissionGradeMember",
    "ReactionRoleCouple",
    "ReactionRoleMessage",
    "Sanction",
    "SanctionType",
    "ShopEntry",
    "ShopRole",
    "StaffConfig",
    "Ticket",
    "TicketPanel",
    "TicketPanelStaffRole",
    "ModAutomodGeneral",
    "ModAutomodInfraction",
    "ModAutomodBanwordConfig",
    "ModAutomodBanwordWord",
    "ModAutomodAntifullcapsConfig",
    "ModAutomodAntispamMentionConfig",
    "ModAutomodAntispamEmojiConfig",
    "ModAutomodActiveAlert",
]