"""
utils/guild_info.py — Détection des systèmes configurés et dérivation des
informations bot (date d'ajout, permissions) pour un serveur, consommé par
views/dev/guild_info_view.py.

2026-10-06 (Paul, refonte /dev guild_info) : remplace l'ancien
`detect_modules()` (4 modules : Alpha / Tickets / Anniversaires /
Notations) par `gather_guild_systems()`, qui balaie TOUS les systèmes
configurables par serveur connus du bot (modération, automod, accueil,
engagement, boutique, Alpha/NG), regroupés par catégorie pour l'affichage
par onglets du nouveau panel.

Chaque manager appelé ici est un read-only DB/cache (TTL 60s selon le
manager, jamais de requête Discord) — aucun appel API supplémentaire n'est
ajouté par cette commande, qui reste un outil dev peu fréquent mais ne doit
pas pour autant déclencher une rafale de requêtes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import discord

from utils.boutique.gold_manager import is_gold
from utils.managers.autorole_manager import load_autorole_config
from utils.managers.bienvenue_manager import load_bienvenue_config
from utils.managers.birthday_manager import load_birthday_config
from utils.managers.exp_manager import load_exp_config
from utils.managers.giveaway_manager import get_active_giveaways
from utils.managers.invite_manager import load_invite_config
from utils.managers.join_to_create_manager import get_trigger_limit, list_triggers
from utils.managers.medialink_manager import get_hub_stats
from utils.managers.mod_automod_antiflood_manager import load_config as load_antiflood_config
from utils.managers.mod_automod_antifullcaps_manager import load_config as load_antifullcaps_config
from utils.managers.mod_automod_antilink_manager import list_extensions, load_config as load_antilink_config
from utils.managers.mod_automod_antispam_emoji_manager import load_config as load_antispam_emoji_config
from utils.managers.mod_automod_antispam_mention_manager import load_config as load_antispam_mention_config
from utils.managers.mod_automod_antispam_msg_manager import load_config as load_antispam_msg_config
from utils.managers.mod_automod_banword_manager import list_words, load_config as load_banword_config
from utils.managers.mod_automod_general_manager import load_general
from utils.managers.mod_automod_nolink_manager import list_whitelist, load_config as load_nolink_config
from utils.managers.mod_log_manager import load_log_config
from utils.managers.mod_permission_manager import PERMISSION_KEYS, get_all_for_guild
from utils.managers.ng_nota_manager import load_nota_config
from utils.managers.ng_onu_manager import load_onu_config
from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.ng_role_react_manager import get_rr_entry_count, load_rr_config
from utils.managers.ng_server_manager import get_server_by_guild
from utils.managers.ng_staff_manager import list_staff
from utils.managers.ng_statut_manager import list_statut_defs
from utils.managers.reaction_role_manager import obtenir_tous_messages
from utils.managers.ticket_manager import list_panels

EMOJI_ON = "<:valider:1495444292867723284>"
EMOJI_OFF = "<:annuler:1495444256754761979>"
EMOJI_INFO = "➖"


@dataclass
class SystemEntry:
    """Une ligne d'état dans la page 'Systèmes' du panel guild_info."""
    name: str
    enabled: bool | None  # None = ligne informative (pas un simple on/off)
    detail: str = ""

    @property
    def icon(self) -> str:
        if self.enabled is None:
            return EMOJI_INFO
        return EMOJI_ON if self.enabled else EMOJI_OFF

    def render(self) -> str:
        if self.detail:
            return f"{self.icon} **{self.name}** — {self.detail}"
        return f"{self.icon} **{self.name}**"


@dataclass
class SystemCategory:
    """Un onglet de la page 'Systèmes' (ex: Automod, Engagement...)."""
    key: str
    label: str
    emoji: str
    entries: list[SystemEntry] = field(default_factory=list)

    @property
    def active_count(self) -> int:
        return sum(1 for e in self.entries if e.enabled)

    @property
    def toggle_count(self) -> int:
        """Nombre d'entrées qui sont de vrais on/off (exclut les informatives)."""
        return sum(1 for e in self.entries if e.enabled is not None)


@dataclass
class GuildInfoData:
    """Informations dérivées (hors champs bruts de discord.Guild), prêtes
    pour views/dev/guild_info_view.py."""
    bot_joined_at: str
    bot_perms_label: str
    bot_is_admin: bool
    categories: list[SystemCategory]

    @property
    def active_count(self) -> int:
        return sum(c.active_count for c in self.categories)

    @property
    def total_count(self) -> int:
        return sum(c.toggle_count for c in self.categories)


def _channel_detail(channel_id: int | None, guild: discord.Guild) -> str:
    if not channel_id:
        return "non configuré"
    channel = guild.get_channel(channel_id)
    return channel.mention if channel is not None else f"<#{channel_id}> (salon introuvable)"


def _role_count(cfg: dict, keys: list[str]) -> int:
    return sum(1 for k in keys if cfg.get(k))


# ============================================================
# 🛡️ Modération
# ============================================================

async def _category_moderation(guild: discord.Guild) -> SystemCategory:
    log_cfg = await load_log_config(guild.id)
    perms = await get_all_for_guild(guild.id)
    configured_perms = sum(1 for roles in perms.values() if roles)

    entries = [
        SystemEntry(
            "Logs d'évènements",
            enabled=log_cfg.get("log_channel_id") is not None,
            detail=(
                f"{_channel_detail(log_cfg.get('log_channel_id'), guild)}"
                + (f" • pack **{log_cfg['selected_pack']}**" if log_cfg.get("selected_pack") else "")
            ),
        ),
        SystemEntry(
            "Actions de modération",
            enabled=log_cfg.get("mod_action_channel_id") is not None,
            detail=_channel_detail(log_cfg.get("mod_action_channel_id"), guild),
        ),
        SystemEntry(
            "Permissions déléguées",
            enabled=None,
            detail=f"{configured_perms}/{len(PERMISSION_KEYS)} clé(s) configurée(s)",
        ),
    ]
    return SystemCategory(key="mod", label="Modération", emoji="🛡️", entries=entries)


# ============================================================
# 🤖 Automod
# ============================================================

async def _category_automod(guild: discord.Guild) -> SystemCategory:
    guild_id = guild.id
    (
        flood, caps, spam_msg, spam_emoji, spam_mention,
        antilink, extensions, banword, words, nolink, whitelist, general,
    ) = [
        r for r in await _gather_automod(guild_id)
    ]

    entries = [
        SystemEntry("Anti-flood", enabled=flood.get("enabled", False),
                     detail=f"min {flood.get('min_length', 0)} lettres"),
        SystemEntry("Anti-full-caps", enabled=caps.get("enabled", False),
                     detail=f"seuil {round((caps.get('ratio_threshold') or 0) * 100)}%"),
        SystemEntry("Anti-spam (messages)", enabled=spam_msg.get("enabled", False),
                     detail=f"{spam_msg.get('max_messages', 0)} msg / {spam_msg.get('window_seconds', 0)}s"),
        SystemEntry("Anti-spam (emojis)", enabled=spam_emoji.get("enabled", False),
                     detail=f"max {spam_emoji.get('max_emoji', 0)}"),
        SystemEntry("Anti-spam (mentions)", enabled=spam_mention.get("enabled", False),
                     detail=f"max {spam_mention.get('max_mentions', 0)}"),
        SystemEntry("Anti-liens (extensions)", enabled=antilink.get("enabled", False),
                     detail=f"{len(extensions)} extension(s) bloquée(s)"),
        SystemEntry("Mots bannis", enabled=banword.get("enabled", False),
                     detail=f"{len(words)} mot(s)"),
        SystemEntry("Anti-liens externes", enabled=nolink.get("enabled", False),
                     detail=f"{len(whitelist)} salon(s) exempté(s)"),
        SystemEntry("Alertes automod", enabled=None,
                     detail=_channel_detail(general.get("alert_channel_id"), guild)),
    ]
    return SystemCategory(key="automod", label="Automod", emoji="<:bouclier:1539013183577133106>", entries=entries)


async def _gather_automod(guild_id: int) -> list:
    """Regroupe tous les loads automod (pas de bénéfice à paralléliser : DB
    async SQLAlchemy sur une session partagée par requête, et le volume ici
    est trivial pour une commande dev peu fréquente)."""
    flood = await load_antiflood_config(guild_id)
    caps = await load_antifullcaps_config(guild_id)
    spam_msg = await load_antispam_msg_config(guild_id)
    spam_emoji = await load_antispam_emoji_config(guild_id)
    spam_mention = await load_antispam_mention_config(guild_id)
    antilink = await load_antilink_config(guild_id)
    extensions = await list_extensions(guild_id)
    banword = await load_banword_config(guild_id)
    words = await list_words(guild_id)
    nolink = await load_nolink_config(guild_id)
    whitelist = await list_whitelist(guild_id)
    general = await load_general(guild_id)
    return [flood, caps, spam_msg, spam_emoji, spam_mention, antilink, extensions, banword, words, nolink, whitelist, general]


# ============================================================
# 👋 Serveur (accueil, rôles)
# ============================================================

async def _category_serveur(guild: discord.Guild) -> SystemCategory:
    guild_id = guild.id
    bienvenue = await load_bienvenue_config(guild_id)
    autorole = await load_autorole_config(guild_id)
    rr_messages = await obtenir_tous_messages(guild_id)
    rr_couples = sum(len(m.get("reactions", [])) for m in rr_messages.values())
    j2c_triggers = await list_triggers(guild_id)
    j2c_limit = get_trigger_limit(guild_id)

    entries = [
        SystemEntry(
            "Bienvenue (arrivée)",
            enabled=bienvenue.get("arrive_active", False),
            detail=_channel_detail(bienvenue.get("arrive_channel_id"), guild),
        ),
        SystemEntry(
            "Bienvenue (départ)",
            enabled=bienvenue.get("depart_active", False),
            detail=_channel_detail(bienvenue.get("depart_channel_id"), guild),
        ),
        SystemEntry(
            "Auto-rôle",
            enabled=autorole.get("auto_role_active", False),
            detail=f"{_role_count(autorole, ['role_id_1', 'role_id_2', 'role_id_3'])} rôle(s)",
        ),
        SystemEntry(
            "Rôles réaction",
            enabled=len(rr_messages) > 0,
            detail=f"{len(rr_messages)} message(s), {rr_couples} lien(s) emoji→rôle",
        ),
        SystemEntry(
            "Salons vocaux à la demande",
            enabled=len(j2c_triggers) > 0,
            detail=f"{len(j2c_triggers)}/{j2c_limit} déclencheur(s)",
        ),
    ]
    return SystemCategory(key="serveur", label="Serveur", emoji="👋", entries=entries)


# ============================================================
# 🎉 Engagement
# ============================================================

async def _category_engagement(guild: discord.Guild) -> SystemCategory:
    guild_id = guild.id
    invite_cfg = await load_invite_config(guild_id)
    exp_cfg = await load_exp_config(guild_id)
    active_giveaways = await get_active_giveaways(guild_id)
    birthday_cfg = await load_birthday_config(guild_id)
    panels = await list_panels(guild_id)
    hub_stats = await get_hub_stats(guild_id)

    platforms = hub_stats.get("platforms", {}) if isinstance(hub_stats, dict) else {}
    connected_platforms = [p for p, n in platforms.items() if n]

    entries = [
        SystemEntry(
            "Invitations",
            enabled=invite_cfg.get("enabled", False),
            detail="annonce active" if invite_cfg.get("announce_active") else "annonce désactivée",
        ),
        SystemEntry(
            "Niveaux (EXP)",
            enabled=exp_cfg.get("enabled", False),
            detail=(
                f"montée de niveau → {_channel_detail(exp_cfg.get('levelup_channel_id'), guild)}"
                if exp_cfg.get("levelup_announce_enabled")
                else "annonce de montée désactivée"
            ),
        ),
        SystemEntry(
            "Giveaways",
            enabled=None,
            detail=f"{len(active_giveaways)} actif(s)",
        ),
        SystemEntry(
            "Anniversaires",
            enabled=birthday_cfg.get("enabled", False),
            detail=_channel_detail(birthday_cfg.get("channel_id"), guild),
        ),
        SystemEntry(
            "Tickets",
            enabled=len(panels) > 0,
            detail=f"{len(panels)} panel(s)",
        ),
        SystemEntry(
            "MediaLink",
            enabled=bool(connected_platforms),
            detail=(", ".join(connected_platforms) if connected_platforms else "aucune connexion"),
        ),
    ]
    return SystemCategory(key="engagement", label="Engagement", emoji="🎉", entries=entries)


# ============================================================
# 💎 Extra (boutique, Alpha/NG)
# ============================================================

async def _category_extra(guild: discord.Guild) -> SystemCategory:
    guild_id = guild.id
    gold = is_gold(guild_id)
    entries = [
        SystemEntry("Boutique Gold+", enabled=gold, detail="serveur Gold+" if gold else "serveur standard"),
    ]

    ng_server = get_server_by_guild(guild_id)
    if ng_server is not None:
        rank_cfg = await load_rank_config(ng_server.name)
        rank_fields = [v for k, v in rank_cfg.items() if k not in ("server",)]
        rank_configured = sum(1 for v in rank_fields if v)
        nota_cfg = await load_nota_config(ng_server.name)
        onu_cfg = await load_onu_config(ng_server.name)
        staff = await list_staff(ng_server.name)
        statuts = await list_statut_defs(ng_server.name)
        rr_cfg = await load_rr_config(ng_server.name)
        rr_count = await get_rr_entry_count(ng_server.name)

        entries.extend([
            SystemEntry(
                f"Alpha — {ng_server.display_name}",
                enabled=rank_configured > 0,
                detail=f"{rank_configured} champ(s) configuré(s)",
            ),
            SystemEntry("Notations", enabled=bool(nota_cfg.get("enabled")), detail=""),
            SystemEntry(
                "ONU",
                enabled=bool(onu_cfg.get("enabled")),
                detail=_channel_detail(onu_cfg.get("channel_id"), guild),
            ),
            SystemEntry("Staff NG", enabled=len(staff) > 0, detail=f"{len(staff)} membre(s)"),
            SystemEntry("Statuts NG", enabled=len(statuts) > 0, detail=f"{len(statuts)} statut(s) défini(s)"),
            SystemEntry(
                "Rôles réaction NG",
                enabled=rr_cfg.get("channel_id") is not None,
                detail=f"{rr_count} lien(s)",
            ),
        ])

    return SystemCategory(key="extra", label="Extra", emoji="💎", entries=entries)


# ============================================================
# 🔍 Orchestration
# ============================================================

async def gather_guild_systems(guild: discord.Guild) -> list[SystemCategory]:
    """Balaie tous les systèmes configurables connus pour cette guild,
    regroupés par catégorie. Tout est lu en DB/cache, rien n'appelle
    l'API Discord au-delà des objets déjà en cache local (guild.get_channel,
    guild.get_role...)."""
    return [
        await _category_moderation(guild),
        await _category_automod(guild),
        await _category_serveur(guild),
        await _category_engagement(guild),
        await _category_extra(guild),
    ]


async def gather_guild_info(guild: discord.Guild) -> GuildInfoData:
    """Rassemble les informations dérivées (hors champs bruts de
    discord.Guild, lus directement par la view) pour /dev guild_info."""
    if guild.me is not None and guild.me.joined_at is not None:
        bot_joined_at = discord.utils.format_dt(guild.me.joined_at, style="D")
    else:
        bot_joined_at = "*Inconnue*"

    if guild.me is not None:
        perms = guild.me.guild_permissions
        bot_is_admin = perms.administrator
        bot_perms_label = "✓ Administrator" if bot_is_admin else f"`{perms.value}` (pas Administrator)"
    else:
        bot_is_admin = False
        bot_perms_label = "*Indisponible*"

    categories = await gather_guild_systems(guild)

    return GuildInfoData(
        bot_joined_at=bot_joined_at,
        bot_perms_label=bot_perms_label,
        bot_is_admin=bot_is_admin,
        categories=categories,
    )
