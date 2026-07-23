"""
utils/managers/mod_log_manager.py — Systeme de logs /mod (3 packs cumulatifs).

Un seul pack actif a la fois par serveur : stagiaire < chercheur < espion,
chaque palier incluant tous les evenements du precedent (cf. PACK_EVENTS).
Espion necessite un serveur Gold+ (verifie a l'activation ET a l'envoi,
au cas ou le statut Gold+ serait perdu entre-temps).

Les logs sont envoyes en Components V2 (jamais d'embed, conformement aux
conventions du bot) dans le salon configure par /mod logs.

bind_bot() permet de resoudre un guild_id en discord.Guild depuis les
managers (utils.managers.mod_sanction_manager, mod_rename_manager) sans
leur faire porter une dependance directe sur le client Discord — appele
une fois au demarrage du bot (cf. cogs/events/mod_log_listener.py).
"""
from __future__ import annotations

import logging

import discord
from discord.ui import Container, LayoutView, Separator, TextDisplay

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
# 🔌 Liaison bot (résolution guild_id -> discord.Guild)
# ============================================================

_bot_ref: discord.Client | None = None


def bind_bot(bot: discord.Client) -> None:
    """À appeler une fois au démarrage (cf. cogs/events/mod_log_listener.py)."""
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


async def _resolve_log_channel(guild_id: int) -> discord.abc.Messageable | None:
    if _bot_ref is None:
        return None
    guild = _bot_ref.get_guild(guild_id)
    if guild is None:
        return None
    cfg = await load_log_config(guild_id)
    channel_id = cfg.get("log_channel_id")
    if channel_id is None:
        return None
    return guild.get_channel(channel_id)


async def send_log(guild_id: int, event_key: str, lines: list[str]) -> None:
    """Envoie un log Components V2 si l'évènement est activé pour ce serveur."""
    if not await is_event_enabled(guild_id, event_key):
        return

    channel = await _resolve_log_channel(guild_id)
    if channel is None:
        return

    emoji, label = EVENT_CATALOG[event_key]
    view = LayoutView(timeout=None)
    container = Container()
    container.add_item(TextDisplay(f"### {emoji} {label}"))
    container.add_item(Separator())
    container.add_item(TextDisplay("\n".join(lines)))
    view.add_item(container)

    try:
        await channel.send(view=view)
    except (discord.Forbidden, discord.HTTPException):
        log.warning("[MOD_LOG] Envoi impossible guild=%s event=%s", guild_id, event_key)


async def log_mod_action(
    guild_id: int, action_label: str, moderator_id: int, target_id: int, reason: str,
    *, extra: str | None = None,
) -> None:
    """Log générique pour toute action /mod (sanction ou renommage)."""
    lines = [
        f"**Modérateur :** <@{moderator_id}>",
        f"**Cible :** <@{target_id}>",
        f"**Action :** {action_label}",
        f"**Raison :** {reason}",
    ]
    if extra:
        lines.append(f"-# {extra}")
    await send_log(guild_id, "mod_action", lines)