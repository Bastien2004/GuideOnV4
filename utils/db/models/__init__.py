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
from utils.db.models.join_to_create import JoinToCreateChannel, JoinToCreateConfig
from utils.db.models.mod_logs import LogConfig
from utils.db.models.mod_permission import ModPermissionRole
from utils.db.models.mod_sanction import ModSanctionConfig, Sanction, SanctionType
from utils.db.models.ng_nota_config import NGNotaAvailability, NGNotaConfig, NGNotaHistory, NGNotaWeekState
from utils.db.models.ng_onu_config import NGONUConfig, NGONUPingMember
from utils.db.models.ng_rank_config import NGRankConfig
from utils.db.models.ng_role_react import NGRoleReactCouple, NGRoleReaction
from utils.db.models.ng_server import NGServer
from utils.db.models.ng_staff import NGStaffMember
from utils.db.models.ng_statut import NGStaffStatut, NGStatutDef
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
from utils.db.models.mod_automod_nolink import ModAutomodNolinkConfig, ModAutomodNolinkWhitelist
from utils.db.models.mod_automod_antilink import ModAutomodAntilinkConfig, ModAutomodAntilinkExtension
from utils.db.models.mod_automod_antispam_msg import ModAutomodAntispamMsgConfig
from utils.db.models.mod_automod_antiflood import ModAutomodAntifloodConfig
from utils.db.models.mod_channel_lock_exemption import ModChannelLockExemption

# --- MEDIALINK (nouveau module, cf. cahier des charges) ---------------------
from utils.db.models.medialink_connection import MediaConnection, MediaPlatform, ConnectionStatus
from utils.db.models.medialink_rule import MediaRule
from utils.db.models.medialink_event import MediaEventRecord, MediaEventStatus
from utils.db.models.medialink_template import MediaTemplate
from utils.db.models.medialink_log import MediaLog, MediaLogLevel
# medialink_statistics : pas de modèle pour l'instant, cf. docstring du fichier.

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
    "JoinToCreateChannel",
    "JoinToCreateConfig",
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
    "NGStaffStatut",
    "NGStatutDef",
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
    "ModAutomodNolinkConfig",
    "ModAutomodNolinkWhitelist",
    "ModAutomodAntilinkConfig",
    "ModAutomodAntilinkExtension",
    "ModAutomodAntispamMsgConfig",
    "ModAutomodAntifloodConfig",
    "ModChannelLockExemption",
    # MEDIALINK
    "MediaConnection",
    "MediaPlatform",
    "ConnectionStatus",
    "MediaRule",
    "MediaEventRecord",
    "MediaEventStatus",
    "MediaTemplate",
    "MediaLog",
    "MediaLogLevel",
]
