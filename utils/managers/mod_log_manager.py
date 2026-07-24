"""
utils/managers/mod_log_manager.py — Systeme de logs /mod (3 packs cumulatifs).

Un seul pack actif a la fois par serveur : stagiaire < chercheur < espion,
chaque palier incluant tous les evenements du precedent (cf. PACK_EVENTS).
Espion necessite un serveur Gold+ (verifie a l'activation ET a l'envoi,
au cas ou le statut Gold+ serait perdu entre-temps).

Les logs sont envoyes en embed Discord (decision explicite de Paul pour
ce module precis — le reste du bot reste en Components V2), avec couleur
par categorie d'evenement, horodatage, miniature quand disponible (avatar
du membre, icone du serveur, rendu de l'emoji/sticker) et pied de page
GuideOn Studio.

bind_bot() permet de resoudre un guild_id en discord.Guild depuis les
managers (utils.managers.mod_sanction_manager, mod_rename_manager) sans
leur faire porter une dependance directe sur le client Discord — appele
une fois au demarrage du bot (cf. cogs/events/mod_log_guild.py).
"""
from __future__ import annotations

import logging

import discord

from utils.boutique.gold_manager import is_gold
from utils.db.models.mod_log import LogConfig
from utils.db.session import get_session

log = logging.getLogger(__name__)


class LogConfigError(Exception):
    """Erreur métier à afficher à l'utilisateur (warning=True -> warning_container)."""

    def __init__(self, message: str, *, warning: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.warning = warning


# ============================================================
# 📦 Catalogue des évènements par pack (cumulatif)
# ============================================================

PACK_KEYS = ("stagiaire", "chercheur", "espion")

PACK_LABELS: dict[str, tuple[str, str]] = {
    "stagiaire": ("🔬", "Stagiaire"),
    "chercheur": ("📡", "Chercheur"),
    "espion": ("🕵️", "Espion"),
}

# Pack nécessitant un statut Gold+ du serveur pour être activé.
GOLD_REQUIRED_PACKS = ("espion",)

EVENT_CATALOG: dict[str, tuple[str, str]] = {
    # ---- Stagiaire ----
    "message_delete": ("🗑️", "Message supprimé"),
    "message_edit": ("✏️", "Message modifié"),
    "member_join": ("📥", "Arrivée"),
    "member_leave": ("📤", "Départ"),
    "role_add": ("➕", "Rôle donné"),
    "role_remove": ("➖", "Rôle retiré"),
    "mod_action": ("🛡️", "Action GuideON MOD"),
    # ---- Chercheur ----
    "channel_create": ("📂", "Salon créé"),
    "channel_delete": ("🗑️", "Salon supprimé"),
    "channel_update": ("✏️", "Salon modifié"),
    "role_create": ("🎭", "Rôle créé"),
    "role_delete": ("🎭", "Rôle supprimé"),
    "role_update": ("🎭", "Rôle modifié"),
    "voice_join": ("🔊", "Connexion vocal"),
    "voice_leave": ("🔇", "Déconnexion vocal"),
    "guild_update": ("⚙️", "Serveur modifié"),
    "member_rename": ("🖊️", "Pseudo modifié"),
    # ---- Espion (Gold+) ----
    "emoji_create": ("😀", "Emoji créé"),
    "emoji_delete": ("😀", "Emoji supprimé"),
    "emoji_update": ("😀", "Emoji modifié"),
    "sticker_create": ("🏷️", "Sticker créé"),
    "sticker_delete": ("🏷️", "Sticker supprimé"),
    "sticker_update": ("🏷️", "Sticker modifié"),
    "user_rename": ("👤", "Nom d'utilisateur modifié"),
    "avatar_update": ("🖼️", "Avatar modifié"),
    "message_pin": ("📌", "Message épinglé"),
    "boost": ("💎", "Boost serveur"),
}

_STAGIAIRE_EVENTS = (
    "message_delete", "message_edit", "member_join", "member_leave",
    "role_add", "role_remove", "mod_action",
)
_CHERCHEUR_EVENTS = _STAGIAIRE_EVENTS + (
    "channel_create", "channel_delete", "channel_update",
    "role_create", "role_delete", "role_update",
    "voice_join", "voice_leave", "guild_update", "member_rename",
)
_ESPION_EVENTS = _CHERCHEUR_EVENTS + (
    "emoji_create", "emoji_delete", "emoji_update",
    "sticker_create", "sticker_delete", "sticker_update",
    "user_rename", "avatar_update", "message_pin", "boost",
)

PACK_EVENTS: dict[str, frozenset[str]] = {
    "stagiaire": frozenset(_STAGIAIRE_EVENTS),
    "chercheur": frozenset(_CHERCHEUR_EVENTS),
    "espion": frozenset(_ESPION_EVENTS),
}

# ============================================================
# 🎨 Couleurs par catégorie d'évènement
# ============================================================

_COLOR_CREATE = discord.Color.green()
_COLOR_DELETE = discord.Color.red()
_COLOR_UPDATE = discord.Color.orange()
_COLOR_MOD_ACTION = discord.Color.dark_gold()
_COLOR_BOOST = discord.Color.from_rgb(255, 115, 250)
_COLOR_PIN = discord.Color.blurple()
_COLOR_VOICE = discord.Color.teal()

EVENT_COLORS: dict[str, discord.Color] = {
    "message_delete": _COLOR_DELETE,
    "message_edit": _COLOR_UPDATE,
    "member_join": _COLOR_CREATE,
    "member_leave": _COLOR_DELETE,
    "role_add": _COLOR_CREATE,
    "role_remove": _COLOR_DELETE,
    "mod_action": _COLOR_MOD_ACTION,
    "channel_create": _COLOR_CREATE,
    "channel_delete": _COLOR_DELETE,
    "channel_update": _COLOR_UPDATE,
    "role_create": _COLOR_CREATE,
    "role_delete": _COLOR_DELETE,
    "role_update": _COLOR_UPDATE,
    "voice_join": _COLOR_VOICE,
    "voice_leave": _COLOR_VOICE,
    "guild_update": _COLOR_UPDATE,
    "member_rename": _COLOR_UPDATE,
    "emoji_create": _COLOR_CREATE,
    "emoji_delete": _COLOR_DELETE,
    "emoji_update": _COLOR_UPDATE,
    "sticker_create": _COLOR_CREATE,
    "sticker_delete": _COLOR_DELETE,
    "sticker_update": _COLOR_UPDATE,
    "user_rename": _COLOR_UPDATE,
    "avatar_update": _COLOR_UPDATE,
    "message_pin": _COLOR_PIN,
    "boost": _COLOR_BOOST,
}


# ============================================================
# 🔌 Liaison bot (résolution guild_id -> discord.Guild)
# ============================================================

_bot_ref: discord.Client | None = None


def bind_bot(bot: discord.Client) -> None:
    """À appeler une fois au démarrage (cf. cogs/events/mod_log_guild.py)."""
    global _bot_ref
    _bot_ref = bot


# ============================================================
# ⚙️ Config (par serveur, cache simple invalidé à l'écriture)
# ============================================================

DEFAULT_LOG_CONFIG: dict = {"log_channel_id": None, "selected_pack": None}

_config_cache: dict[int, dict] = {}


async def load_log_config(guild_id: int) -> dict:
    if guild_id in _config_cache:
        return _config_cache[guild_id].copy()

    async with get_session() as session:
        row = await session.get(LogConfig, guild_id)
        cfg = row.to_dict() if row is not None else {**DEFAULT_LOG_CONFIG, "guild_id": guild_id}

    _config_cache[guild_id] = cfg
    return cfg.copy()


async def save_log_config(guild_id: int, partial: dict) -> dict:
    allowed = set(DEFAULT_LOG_CONFIG.keys())
    clean = {k: v for k, v in partial.items() if k in allowed}

    async with get_session() as session:
        row = await session.get(LogConfig, guild_id)
        if row is None:
            merged = {**DEFAULT_LOG_CONFIG, **clean}
            row = LogConfig(guild_id=guild_id, **merged)
            session.add(row)
        else:
            for key, value in clean.items():
                setattr(row, key, value)
        await session.flush()
        result = row.to_dict()

    _config_cache[guild_id] = result
    return result.copy()


async def set_channel(guild_id: int, channel_id: int) -> dict:
    return await save_log_config(guild_id, {"log_channel_id": channel_id})


async def set_pack(guild_id: int, pack_key: str | None) -> dict:
    """Active un pack (désactivation si pack_key is None). Un seul pack actif à la fois."""
    if pack_key is not None and pack_key not in PACK_KEYS:
        raise LogConfigError("Pack de logs inconnu.", warning=True)
    if pack_key in GOLD_REQUIRED_PACKS and not is_gold(guild_id):
        _, label = PACK_LABELS[pack_key]
        raise LogConfigError(f"Le pack **{label}** nécessite un serveur **Gold+**.", warning=True)
    return await save_log_config(guild_id, {"selected_pack": pack_key})


# ============================================================
# 🛡️ Vérification + envoi
# ============================================================

async def is_event_enabled(guild_id: int, event_key: str) -> bool:
    cfg = await load_log_config(guild_id)
    pack = cfg.get("selected_pack")
    if pack is None:
        return False
    if pack in GOLD_REQUIRED_PACKS and not is_gold(guild_id):
        # Le statut Gold+ a pu être perdu après activation : on coupe par sécurité.
        return False
    return event_key in PACK_EVENTS.get(pack, frozenset())


async def _resolve_log_channel(guild_id: int) -> tuple[discord.abc.Messageable | None, discord.Guild | None]:
    if _bot_ref is None:
        return None, None
    guild = _bot_ref.get_guild(guild_id)
    if guild is None:
        return None, None
    cfg = await load_log_config(guild_id)
    channel_id = cfg.get("log_channel_id")
    if channel_id is None:
        return None, guild
    return guild.get_channel(channel_id), guild


async def send_log(
    guild_id: int,
    event_key: str,
    fields: list[tuple[str, str, bool]],
    *,
    description: str | None = None,
    thumbnail_url: str | None = None,
    image_url: str | None = None,
) -> None:
    """
    Envoie un log en embed décoré si l'évènement est activé pour ce serveur.

    `fields` : liste de (nom, valeur, inline). `description` : texte libre
    affiché sous le titre (ex. contenu d'un message). `thumbnail_url` :
    avatar du membre concerné, icône du serveur, ou rendu de l'emoji/sticker.
    """
    if not await is_event_enabled(guild_id, event_key):
        return

    channel, guild = await _resolve_log_channel(guild_id)
    if channel is None:
        return

    emoji, label = EVENT_CATALOG[event_key]
    embed = discord.Embed(
        title=f"{emoji} {label}",
        description=description,
        color=EVENT_COLORS.get(event_key, discord.Color.blurple()),
    )
    for name, value, inline in fields:
        embed.add_field(name=name, value=value or "`Aucune`", inline=inline)

    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    if image_url:
        embed.set_image(url=image_url)

    now = discord.utils.utcnow()
    guild_name = guild.name if guild is not None else "Serveur"
    footer_text = f"{guild_name} • {now:%d/%m/%Y à %Hh%M}"
    footer_icon = guild.icon.url if guild is not None and guild.icon is not None else None
    embed.set_footer(text=footer_text, icon_url=footer_icon)

    try:
        await channel.send(embed=embed)
    except (discord.Forbidden, discord.HTTPException):
        log.warning("[MOD_LOG] Envoi impossible guild=%s event=%s", guild_id, event_key)


async def log_mod_action(
    guild_id: int, action_label: str, moderator_id: int, target_id: int, reason: str,
    *, extra: str | None = None,
) -> None:
    """Log générique pour toute action /mod ciblant un membre (sanction ou renommage)."""
    fields = [
        ("Modérateur", f"<@{moderator_id}>", True),
        ("Cible", f"<@{target_id}>", True),
        ("Action", action_label, True),
        ("Raison", reason, False),
    ]
    if extra:
        fields.append(("Détail", extra, False))
    await send_log(guild_id, "mod_action", fields)


async def log_channel_action(
    guild_id: int, action_label: str, moderator_id: int, channel: discord.abc.GuildChannel,
    *, reason: str | None = None, extra: str | None = None,
) -> None:
    """Log générique pour toute action /mod ciblant un salon (clear, lock/unlock, gestion vocale)."""
    fields = [
        ("Modérateur", f"<@{moderator_id}>", True),
        ("Salon", channel.mention, True),
        ("Action", action_label, True),
    ]
    if reason:
        fields.append(("Raison", reason, False))
    if extra:
        fields.append(("Détail", extra, False))
    await send_log(guild_id, "mod_action", fields)