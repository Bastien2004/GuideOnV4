"""
cogs/api/api_dashboard.py — API Dashboard (configuration des serveurs depuis le site).

Permet de configurer depuis le site les mêmes systèmes que sur Discord :
Ticket · Automod · Bienvenue · Rôle réaction · Giveaway · Expérience ·
Media link · Join to create.

────────────────────────────────────────────────────────────
🔐 Modèle de sécurité
────────────────────────────────────────────────────────────
1. Le site (backend, jamais le navigateur) appelle cette API avec le token
   Bearer existant (`API_TOKEN`) — même protection que les autres routes.
2. Le site fait la connexion Discord (OAuth2) lui-même, puis envoie l'identité
   vérifiée de l'utilisateur dans le header `X-Discord-User-Id`.
3. Pour CHAQUE requête sur un serveur, le bot revérifie lui-même, avec ses
   propres données Discord, que l'utilisateur est Administrateur ou
   propriétaire du serveur (règle identique à `utils/perm_admin.is_admin`)
   et que le bot est bien présent sur ce serveur.
   → Même si le site se trompe, un non-admin n'obtient jamais l'accès.
4. Les mêmes garde-fous que sur Discord s'appliquent : ban du bot,
   commandes en maintenance, limites Gold+, hiérarchie des rôles,
   permissions du bot dans les salons.
5. Toute ressource ciblée par id (panel, giveaway, déclencheur, règle…)
   est vérifiée comme appartenant bien au serveur de l'URL (anti-IDOR).
6. Limitation de débit par utilisateur (pas par IP : le site partage la sienne).

────────────────────────────────────────────────────────────
🧵 Thread / event loop
────────────────────────────────────────────────────────────
L'API tourne dans un thread séparé (cf. `run_api_server`). Toute la logique
est donc réexécutée sur la boucle du bot (`_run`) : les appels Discord
(`channel.send`, `create_voice_channel`…) et les verrous des managers restent
sur la bonne boucle asyncio.

────────────────────────────────────────────────────────────
🔢 Identifiants Discord
────────────────────────────────────────────────────────────
Les snowflakes dépassent 2^53 : JavaScript les arrondirait. Toutes les
réponses renvoient donc les ids sous forme de chaînes ("123…"), et les
requêtes acceptent indifféremment chaîne ou entier.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated, Any, Awaitable, Callable, Literal, TypeVar

import discord
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from cogs.api.base import app, require_token
from utils.boutique.gold_manager import is_gold
from utils.managers import bot_ban_manager
from utils.managers import bienvenue_manager as bienvenue_mgr
from utils.managers import exp_manager as exp_mgr
from utils.managers import giveaway_manager as gw
from utils.managers import join_to_create_manager as jtc
from utils.managers import medialink_manager as ml
from utils.managers import mod_automod_antiflood_manager as am_flood
from utils.managers import mod_automod_antifullcaps_manager as am_caps
from utils.managers import mod_automod_antilink_manager as am_antilink
from utils.managers import mod_automod_antispam_emoji_manager as am_emoji
from utils.managers import mod_automod_antispam_mention_manager as am_mention
from utils.managers import mod_automod_antispam_msg_manager as am_spam
from utils.managers import mod_automod_banword_manager as am_banword
from utils.managers import mod_automod_general_manager as am_general
from utils.managers import mod_automod_nolink_manager as am_nolink
from utils.managers import reaction_role_manager as rr
from utils.managers import ticket_manager as tm
from utils.managers.command_toggle_manager import is_command_enabled
from utils.ticket_limits import (
    MAX_STAFF_ROLES_PER_PANEL,
    PANEL_MESSAGE_MAX_LENGTH,
    PANEL_TITLE_MAX_LENGTH,
)

log = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================
# 🔢 Snowflakes + réponse JSON sûre pour JavaScript
# ============================================================

_JS_MAX_SAFE_INT = 2**53 - 1


def _snowflake_in(v: Any) -> int:
    """Accepte "123" ou 123 → int. Refuse tout le reste."""
    if isinstance(v, bool):
        raise ValueError("Identifiant Discord invalide.")
    if isinstance(v, str):
        v = v.strip()
        if not v.isdigit():
            raise ValueError("Identifiant Discord invalide.")
        v = int(v)
    if not isinstance(v, int) or v <= 0 or v >= 2**63:
        raise ValueError("Identifiant Discord invalide.")
    return v


Snowflake = Annotated[int, BeforeValidator(_snowflake_in)]


def _js_safe(obj: Any) -> Any:
    """Convertit récursivement les entiers > 2^53 en chaînes."""
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, int):
        return str(obj) if abs(obj) > _JS_MAX_SAFE_INT else obj
    if isinstance(obj, dict):
        return {k: _js_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_js_safe(v) for v in obj]
    return obj


class _SafeJSONResponse(JSONResponse):
    def render(self, content: Any) -> bytes:
        return super().render(_js_safe(content))


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_token)],
    default_response_class=_SafeJSONResponse,
)


class _Body(BaseModel):
    """Base des corps de requête : champs inconnus refusés (pas d'erreur silencieuse)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _fail(status: int, message: str) -> "HTTPException":
    return HTTPException(status_code=status, detail=message)


def _changes(payload: BaseModel) -> dict:
    """Champs réellement envoyés (permet de distinguer « absent » de « null »)."""
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise _fail(422, "Aucun champ à modifier.")
    return data


# ============================================================
# 🧵 Exécution sur la boucle du bot
# ============================================================

def _bot() -> Any:
    bot = getattr(app.state, "bot", None)
    if bot is None or not bot.is_ready():
        raise _fail(503, "Le bot est en cours de démarrage, réessayez dans un instant.")
    return bot


async def _run(coro: Awaitable[T], *, timeout: float = 30.0) -> T:
    """Exécute `coro` sur la boucle du bot et attend le résultat."""
    loop = _bot().loop
    if asyncio.get_running_loop() is loop:
        return await asyncio.wait_for(coro, timeout)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    try:
        return await asyncio.wait_for(asyncio.wrap_future(future), timeout)
    except asyncio.TimeoutError:
        future.cancel()
        raise _fail(504, "Le bot a mis trop de temps à répondre.")


def _on_bot_loop(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Décorateur : le corps du handler s'exécute sur la boucle du bot."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        return await _run(fn(*args, **kwargs))

    return wrapper


# ============================================================
# 🚦 Limitation de débit (par utilisateur)
# ============================================================

_RATE_WINDOW = 60.0
_RATE_READ = 240
_RATE_WRITE = 60
_rate_hits: dict[tuple[int, bool], deque[float]] = defaultdict(deque)


def _rate_limit(user_id: int, write: bool) -> None:
    now = time.monotonic()
    hits = _rate_hits[(user_id, write)]
    while hits and now - hits[0] > _RATE_WINDOW:
        hits.popleft()
    if len(hits) >= (_RATE_WRITE if write else _RATE_READ):
        raise _fail(429, "Trop de requêtes, réessayez dans quelques instants.")
    hits.append(now)

    if len(_rate_hits) > 5000:  # ménage
        for key in [k for k, v in _rate_hits.items() if not v or now - v[-1] > _RATE_WINDOW]:
            _rate_hits.pop(key, None)


# ============================================================
# 🔐 Authentification + autorisation
# ============================================================

async def current_user_id(
    request: Request,
    x_discord_user_id: str | None = Header(default=None, alias="X-Discord-User-Id"),
) -> int:
    """Identité de l'utilisateur du site (id Discord vérifié par le site via OAuth2)."""
    raw = (x_discord_user_id or "").strip()
    if not raw.isdigit() or not 15 <= len(raw) <= 20:
        raise _fail(401, "Header X-Discord-User-Id manquant ou invalide.")
    user_id = int(raw)
    _rate_limit(user_id, write=request.method not in ("GET", "HEAD", "OPTIONS"))
    return user_id


def _is_admin(guild: discord.Guild, member: discord.Member) -> bool:
    """Même règle que utils/perm_admin.is_admin : Administrateur ou propriétaire."""
    return member.guild_permissions.administrator or member.id == guild.owner_id


@dataclass
class GuildCtx:
    bot: Any
    guild: discord.Guild
    member: discord.Member
    user_id: int

    @property
    def gid(self) -> int:
        return self.guild.id


async def _resolve_guild(guild_id: int, user_id: int, command: str | None) -> GuildCtx:
    bot = _bot()

    banned, _reason = await bot_ban_manager.is_banned(user_id)
    if banned:
        raise _fail(403, "Vous êtes banni du bot.")

    guild = bot.get_guild(guild_id)
    member = None
    if guild is not None:
        member = guild.get_member(user_id)
        if member is None:
            try:
                member = await guild.fetch_member(user_id)
            except (discord.NotFound, discord.HTTPException):
                member = None

    # Même message dans tous les cas : ne révèle pas si le bot est sur le serveur.
    if guild is None or member is None or not _is_admin(guild, member):
        raise _fail(403, "Accès refusé : il faut être Administrateur d'un serveur où le bot est présent.")

    if command and not await is_command_enabled(command):
        raise _fail(503, "Cette fonctionnalité est temporairement en maintenance.")

    return GuildCtx(bot=bot, guild=guild, member=member, user_id=user_id)


def guild_access(command: str | None = None):
    """Dépendance : l'utilisateur est admin du serveur `guild_id` de l'URL."""

    async def dependency(guild_id: int, user_id: int = Depends(current_user_id)) -> GuildCtx:
        return await _run(_resolve_guild(guild_id, user_id, command))

    return dependency


# ============================================================
# ✅ Validateurs Discord (salons / rôles)
# ============================================================

_PERM_LABELS = {
    "view_channel": "Voir le salon",
    "send_messages": "Envoyer des messages",
    "read_message_history": "Lire l'historique",
    "add_reactions": "Ajouter des réactions",
    "manage_channels": "Gérer les salons",
    "manage_roles": "Gérer les rôles",
    "embed_links": "Intégrer des liens",
}


def _check_perms(channel: discord.abc.GuildChannel, ctx: GuildCtx, perms: tuple[str, ...]) -> None:
    me = ctx.guild.me
    if me is None:
        raise _fail(503, "Le bot n'est pas prêt sur ce serveur.")
    granted = channel.permissions_for(me)
    missing = [_PERM_LABELS.get(p, p) for p in perms if not getattr(granted, p)]
    if missing:
        raise _fail(422, f"Le bot n'a pas les permissions requises dans #{channel.name} : {', '.join(missing)}.")


def _text_channel(
    ctx: GuildCtx,
    channel_id: int,
    *,
    label: str = "Salon",
    perms: tuple[str, ...] = ("view_channel", "send_messages"),
) -> discord.TextChannel:
    channel = ctx.guild.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        raise _fail(422, f"{label} : salon textuel introuvable sur ce serveur.")
    _check_perms(channel, ctx, perms)
    return channel


def _category(ctx: GuildCtx, category_id: int, *, label: str = "Catégorie") -> discord.CategoryChannel:
    category = ctx.guild.get_channel(category_id)
    if not isinstance(category, discord.CategoryChannel):
        raise _fail(422, f"{label} : catégorie introuvable sur ce serveur.")
    _check_perms(category, ctx, ("view_channel", "manage_channels"))
    return category


def _role(ctx: GuildCtx, role_id: int, *, label: str = "Rôle", assignable: bool = False) -> discord.Role:
    role = ctx.guild.get_role(role_id)
    if role is None:
        raise _fail(422, f"{label} : rôle introuvable sur ce serveur.")
    if role.is_default():
        raise _fail(422, f"{label} : le rôle @everyone ne peut pas être utilisé ici.")
    if assignable:
        if role.is_bot_managed() or role.is_integration() or role.managed:
            raise _fail(422, f"{label} : ce type de rôle (bot/intégration) ne peut pas être attribué.")
        me = ctx.guild.me
        if me is None or role.position >= me.top_role.position:
            raise _fail(422, f"{label} : ce rôle est au-dessus ou au niveau de celui du bot dans la hiérarchie.")
    return role


def _opt_text_channel(ctx: GuildCtx, value: int | None, label: str) -> int | None:
    return None if value is None else _text_channel(ctx, value, label=label).id


def _opt_role(ctx: GuildCtx, value: int | None, label: str) -> int | None:
    return None if value is None else _role(ctx, value, label=label).id


def _require_gold(ctx: GuildCtx, what: str) -> None:
    if not is_gold(ctx.gid):
        raise _fail(403, f"{what} est une fonctionnalité réservée aux serveurs Gold+.")


async def _best_effort_delete_message(guild: discord.Guild, channel_id: int | None, message_id: int | None) -> None:
    if not channel_id or not message_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    try:
        await channel.get_partial_message(message_id).delete()
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


# ============================================================
# 🏠 Serveurs / ressources / aperçu
# ============================================================

@router.get("/guilds")
async def list_my_guilds(user_id: int = Depends(current_user_id)):
    """Serveurs que l'utilisateur peut configurer (admin + bot présent). Liste de gauche du site."""

    async def work() -> dict:
        bot = _bot()
        banned, _ = await bot_ban_manager.is_banned(user_id)
        if banned:
            raise _fail(403, "Vous êtes banni du bot.")

        guilds = []
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member is None or not _is_admin(guild, member):
                continue
            guilds.append({
                "id": guild.id,
                "name": guild.name,
                "icon_url": guild.icon.url if guild.icon else None,
                "member_count": guild.member_count or 0,
                "is_owner": guild.owner_id == user_id,
                "is_gold": is_gold(guild.id),
            })
        guilds.sort(key=lambda g: g["name"].lower())
        return {"guilds": guilds}

    return await _run(work())


@router.get("/guilds/{guild_id}/resources")
@_on_bot_loop
async def guild_resources(ctx: GuildCtx = Depends(guild_access())):
    """Salons et rôles du serveur : alimente les menus déroulants du site."""
    guild = ctx.guild
    me = guild.me
    bot_top = me.top_role.position if me else 0

    def category_name(channel: discord.abc.GuildChannel) -> str | None:
        return channel.category.name if getattr(channel, "category", None) else None

    return {
        "text_channels": [
            {"id": c.id, "name": c.name, "category": category_name(c), "position": c.position}
            for c in guild.text_channels
        ],
        "voice_channels": [
            {"id": c.id, "name": c.name, "category": category_name(c), "position": c.position}
            for c in guild.voice_channels
        ],
        "categories": [{"id": c.id, "name": c.name, "position": c.position} for c in guild.categories],
        "roles": [
            {
                "id": r.id,
                "name": r.name,
                "color": r.color.value,
                "position": r.position,
                "managed": r.managed,
                "assignable": not (r.is_default() or r.managed or r.position >= bot_top),
            }
            for r in sorted(guild.roles, key=lambda r: -r.position)
            if not r.is_default()
        ],
    }


@router.get("/guilds/{guild_id}/overview")
@_on_bot_loop
async def guild_overview(ctx: GuildCtx = Depends(guild_access())):
    """Résumé de l'état des 8 systèmes (pastilles de la barre latérale)."""
    gid = ctx.gid

    panels = await tm.list_panels(gid)
    bienvenue = await bienvenue_mgr.load_bienvenue_config(gid)
    exp = await exp_mgr.load_exp_config(gid)
    rr_messages = await rr.obtenir_tous_messages(gid)
    giveaways = await gw.get_active_giveaways(gid)
    triggers = await jtc.list_triggers(gid)
    connections = await ml.list_connections(gid)
    automod_flags = {
        "banword": (await am_banword.load_config(gid)).get("enabled", False),
        "nolink": (await am_nolink.load_config(gid)).get("enabled", False),
        "antilink": (await am_antilink.load_config(gid)).get("enabled", False),
        "antifullcaps": (await am_caps.load_config(gid)).get("enabled", False),
        "antiflood": (await am_flood.load_config(gid)).get("enabled", False),
        "antispam_msg": (await am_spam.load_config(gid)).get("enabled", False),
        "antispam_emoji": (await am_emoji.load_config(gid)).get("enabled", False),
        "antispam_mention": (await am_mention.load_config(gid)).get("enabled", False),
    }

    return {
        "guild": {"id": gid, "name": ctx.guild.name, "is_gold": is_gold(gid)},
        "systems": {
            "ticket": {"configured": bool(panels), "panels": len(panels)},
            "automod": {"configured": any(automod_flags.values()), "enabled": automod_flags},
            "bienvenue": {"configured": bool(bienvenue.get("system_active"))},
            "role_reaction": {"configured": bool(rr_messages), "messages": len(rr_messages)},
            "giveaway": {"configured": bool(giveaways), "active": len(giveaways)},
            "exp": {"configured": bool(exp.get("enabled"))},
            "medialink": {"configured": bool(connections), "connections": len(connections)},
            "join_to_create": {"configured": bool(triggers), "triggers": len(triggers)},
        },
    }


# ============================================================
# 👋 BIENVENUE
# ============================================================

class BienvenueUpdate(_Body):
    system_active: bool | None = None
    arrive_active: bool | None = None
    depart_active: bool | None = None
    arrive_channel_id: Snowflake | None = None
    depart_channel_id: Snowflake | None = None
    arrive_message: str | None = Field(default=None, min_length=1, max_length=2000)
    depart_message: str | None = Field(default=None, min_length=1, max_length=2000)
    arrive_format: Literal["embed", "text"] | None = None
    depart_format: Literal["embed", "text"] | None = None
    arrive_image_url: str | None = Field(default=None, max_length=500)
    depart_image_url: str | None = Field(default=None, max_length=500)


@router.get("/guilds/{guild_id}/bienvenue")
@_on_bot_loop
async def bienvenue_get(ctx: GuildCtx = Depends(guild_access("config_bienvenue"))):
    from views.bienvenue.config_view import VARIABLES_FULL

    return {
        "config": await bienvenue_mgr.load_bienvenue_config(ctx.gid),
        "is_gold": is_gold(ctx.gid),
        "variables": [{"name": n, "description": d} for n, d in VARIABLES_FULL],
    }


@router.put("/guilds/{guild_id}/bienvenue")
@_on_bot_loop
async def bienvenue_update(payload: BienvenueUpdate, ctx: GuildCtx = Depends(guild_access("config_bienvenue"))):
    from utils.bienvenue_render import is_valid_image_url

    data = _changes(payload)

    for kind in ("arrive", "depart"):
        key = f"{kind}_channel_id"
        if key in data:
            data[key] = _opt_text_channel(ctx, data[key], f"Salon {kind}")

        key = f"{kind}_image_url"
        if key in data:
            url = (data[key] or "").strip()
            if url:
                _require_gold(ctx, "L'image personnalisée")
                if not is_valid_image_url(url):
                    raise _fail(422, "URL d'image invalide (formats .png .jpg .gif .webp, ou lien Discord/Imgur).")
            data[key] = url or None

        for key in (f"{kind}_message", f"{kind}_format"):
            if key in data and data[key] is None:
                raise _fail(422, f"{key} ne peut pas être vide.")

    return {"config": await bienvenue_mgr.save_bienvenue_config(ctx.gid, data)}


@router.post("/guilds/{guild_id}/bienvenue/reset")
@_on_bot_loop
async def bienvenue_reset(ctx: GuildCtx = Depends(guild_access("config_bienvenue"))):
    return {"config": await bienvenue_mgr.reset_bienvenue_config(ctx.gid)}


# ============================================================
# ⭐ EXPÉRIENCE
# ============================================================

class ExpUpdate(_Body):
    enabled: bool | None = None
    exp_per_message: int | None = Field(default=None, ge=0, le=1000)
    exp_per_voice_minute: int | None = Field(default=None, ge=0, le=1000)
    boost_role_id: Snowflake | None = None
    boost_percent: int | None = Field(default=None, ge=0, le=500)
    levelup_announce_enabled: bool | None = None
    levelup_channel_id: Snowflake | None = None


@router.get("/guilds/{guild_id}/exp")
@_on_bot_loop
async def exp_get(ctx: GuildCtx = Depends(guild_access("exp_config"))):
    return {"config": await exp_mgr.load_exp_config(ctx.gid)}


@router.put("/guilds/{guild_id}/exp")
@_on_bot_loop
async def exp_update(payload: ExpUpdate, ctx: GuildCtx = Depends(guild_access("exp_config"))):
    data = _changes(payload)

    for key in ("enabled", "exp_per_message", "exp_per_voice_minute", "boost_percent", "levelup_announce_enabled"):
        if key in data and data[key] is None:
            raise _fail(422, f"{key} ne peut pas être null.")

    if "boost_role_id" in data:
        data["boost_role_id"] = _opt_role(ctx, data["boost_role_id"], "Rôle boost")
    if "levelup_channel_id" in data:
        data["levelup_channel_id"] = _opt_text_channel(ctx, data["levelup_channel_id"], "Salon des level-up")

    return {"config": await exp_mgr.save_exp_config(ctx.gid, data)}


@router.post("/guilds/{guild_id}/exp/reset")
@_on_bot_loop
async def exp_reset(ctx: GuildCtx = Depends(guild_access("exp_config"))):
    return {"config": await exp_mgr.reset_exp_config(ctx.gid)}


# ============================================================
# 🛡️ AUTOMOD
# ============================================================

AUTOMOD = "mod_config"


class AutomodGeneralUpdate(_Body):
    alert_channel_id: Snowflake | None = None
    staff_role_id: Snowflake | None = None
    notify_in_channel: bool | None = None
    notification_window_seconds: int | None = Field(default=None, ge=am_general.WINDOW_MIN, le=am_general.WINDOW_MAX)


class AutomodToggle(_Body):
    enabled: bool


class AutomodFullcapsUpdate(_Body):
    enabled: bool | None = None
    min_length: int | None = Field(default=None, ge=1, le=500)
    ratio_pct: int | None = Field(default=None, ge=10, le=100)


class AutomodFloodUpdate(_Body):
    enabled: bool | None = None
    min_length: int | None = Field(default=None, ge=5, le=500)
    ratio_pct: int | None = Field(default=None, ge=5, le=60)


class AutomodSpamMsgUpdate(_Body):
    enabled: bool | None = None
    window_seconds: int | None = Field(default=None, ge=2, le=120)
    max_messages: int | None = Field(default=None, ge=2, le=20)


class AutomodEmojiUpdate(_Body):
    enabled: bool | None = None
    max_emoji: int | None = Field(default=None, ge=1, le=50)


class AutomodMentionUpdate(_Body):
    enabled: bool | None = None
    max_mentions: int | None = Field(default=None, ge=1, le=30)


class AutomodNolinkUpdate(_Body):
    enabled: bool | None = None
    bypass_gif: bool | None = None


class WordBody(_Body):
    word: str = Field(min_length=1, max_length=100)


class ExtensionBody(_Body):
    extension: str = Field(min_length=1, max_length=20)


class ChannelBody(_Body):
    channel_id: Snowflake


def _with_pct(cfg: dict, key: str) -> dict:
    out = dict(cfg)
    if key in out and out[key] is not None:
        out["ratio_pct"] = int(round(float(out[key]) * 100))
    return out


async def _automod_snapshot(gid: int) -> dict:
    return {
        "general": await am_general.load_general(gid),
        "banword": {**await am_banword.load_config(gid), "words": await am_banword.list_words(gid)},
        "nolink": {**await am_nolink.load_config(gid), "whitelist_channel_ids": await am_nolink.list_whitelist(gid)},
        "antilink": {**await am_antilink.load_config(gid), "extensions": await am_antilink.list_extensions(gid)},
        "antifullcaps": _with_pct(await am_caps.load_config(gid), "ratio_threshold"),
        "antiflood": _with_pct(await am_flood.load_config(gid), "min_vowel_ratio"),
        "antispam_msg": await am_spam.load_config(gid),
        "antispam_emoji": await am_emoji.load_config(gid),
        "antispam_mention": await am_mention.load_config(gid),
    }


@router.get("/guilds/{guild_id}/automod")
@_on_bot_loop
async def automod_get(ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    return await _automod_snapshot(ctx.gid)


@router.put("/guilds/{guild_id}/automod/general")
@_on_bot_loop
async def automod_general_update(payload: AutomodGeneralUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    if "alert_channel_id" in data:
        data["alert_channel_id"] = _opt_text_channel(ctx, data["alert_channel_id"], "Salon d'alertes")
    if "staff_role_id" in data:
        data["staff_role_id"] = _opt_role(ctx, data["staff_role_id"], "Rôle staff")
    for key in ("notify_in_channel", "notification_window_seconds"):
        if key in data and data[key] is None:
            raise _fail(422, f"{key} ne peut pas être null.")
    return await am_general.save_general(ctx.gid, **data)


@router.put("/guilds/{guild_id}/automod/banword")
@_on_bot_loop
async def automod_banword_toggle(payload: AutomodToggle, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    return await am_banword.set_enabled(ctx.gid, payload.enabled)


@router.post("/guilds/{guild_id}/automod/banword/words")
@_on_bot_loop
async def automod_banword_add(payload: WordBody, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    if not await am_banword.add_word(ctx.gid, payload.word):
        raise _fail(409, "Ce mot est déjà dans la liste.")
    return {"words": await am_banword.list_words(ctx.gid)}


@router.delete("/guilds/{guild_id}/automod/banword/words")
@_on_bot_loop
async def automod_banword_remove(word: str, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    if not await am_banword.remove_word(ctx.gid, word):
        raise _fail(404, "Ce mot n'est pas dans la liste.")
    return {"words": await am_banword.list_words(ctx.gid)}


@router.post("/guilds/{guild_id}/automod/banword/words/clear")
@_on_bot_loop
async def automod_banword_clear(ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    return {"removed": await am_banword.clear_words(ctx.gid), "words": []}


@router.put("/guilds/{guild_id}/automod/nolink")
@_on_bot_loop
async def automod_nolink_update(payload: AutomodNolinkUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    if data.get("enabled") is not None:
        await am_nolink.set_enabled(ctx.gid, data["enabled"])
    if data.get("bypass_gif") is not None:
        await am_nolink.set_bypass_gif(ctx.gid, data["bypass_gif"])
    return {**await am_nolink.load_config(ctx.gid), "whitelist_channel_ids": await am_nolink.list_whitelist(ctx.gid)}


@router.post("/guilds/{guild_id}/automod/nolink/whitelist")
@_on_bot_loop
async def automod_nolink_whitelist_add(payload: ChannelBody, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    channel = ctx.guild.get_channel(payload.channel_id)
    if channel is None or isinstance(channel, discord.CategoryChannel):
        raise _fail(422, "Salon introuvable sur ce serveur.")
    if not await am_nolink.add_channel(ctx.gid, channel.id):
        raise _fail(409, "Ce salon est déjà dans la liste blanche.")
    return {"whitelist_channel_ids": await am_nolink.list_whitelist(ctx.gid)}


@router.delete("/guilds/{guild_id}/automod/nolink/whitelist/{channel_id}")
@_on_bot_loop
async def automod_nolink_whitelist_remove(channel_id: int, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    if not await am_nolink.remove_channel(ctx.gid, channel_id):
        raise _fail(404, "Ce salon n'est pas dans la liste blanche.")
    return {"whitelist_channel_ids": await am_nolink.list_whitelist(ctx.gid)}


@router.put("/guilds/{guild_id}/automod/antilink")
@_on_bot_loop
async def automod_antilink_toggle(payload: AutomodToggle, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    await am_antilink.set_enabled(ctx.gid, payload.enabled)
    return {**await am_antilink.load_config(ctx.gid), "extensions": await am_antilink.list_extensions(ctx.gid)}


_EXTENSION_RE = re.compile(r"^\.?[a-z0-9]{1,19}$")


@router.post("/guilds/{guild_id}/automod/antilink/extensions")
@_on_bot_loop
async def automod_antilink_ext_add(payload: ExtensionBody, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    if not _EXTENSION_RE.match(payload.extension.lower()):
        raise _fail(422, "Extension invalide (lettres et chiffres uniquement, ex: exe).")
    if not await am_antilink.add_extension(ctx.gid, payload.extension):
        raise _fail(409, "Cette extension est déjà bloquée.")
    return {"extensions": await am_antilink.list_extensions(ctx.gid)}


@router.delete("/guilds/{guild_id}/automod/antilink/extensions")
@_on_bot_loop
async def automod_antilink_ext_remove(extension: str, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    if not await am_antilink.remove_extension(ctx.gid, extension):
        raise _fail(404, "Cette extension n'est pas dans la liste.")
    return {"extensions": await am_antilink.list_extensions(ctx.gid)}


@router.post("/guilds/{guild_id}/automod/antilink/extensions/clear")
@_on_bot_loop
async def automod_antilink_ext_clear(ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    return {"removed": await am_antilink.clear_extensions(ctx.gid), "extensions": await am_antilink.list_extensions(ctx.gid)}


def _reject_nulls(data: dict) -> None:
    for key, value in data.items():
        if value is None:
            raise _fail(422, f"{key} ne peut pas être null.")


@router.put("/guilds/{guild_id}/automod/antifullcaps")
@_on_bot_loop
async def automod_fullcaps_update(payload: AutomodFullcapsUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    _reject_nulls(data)
    if "ratio_pct" in data:
        data["ratio_threshold"] = data.pop("ratio_pct") / 100.0
    return _with_pct(await am_caps.save_config(ctx.gid, **data), "ratio_threshold")


@router.put("/guilds/{guild_id}/automod/antiflood")
@_on_bot_loop
async def automod_flood_update(payload: AutomodFloodUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    _reject_nulls(data)
    if "ratio_pct" in data:
        data["min_vowel_ratio"] = data.pop("ratio_pct") / 100.0
    return _with_pct(await am_flood.save_config(ctx.gid, **data), "min_vowel_ratio")


@router.put("/guilds/{guild_id}/automod/antispam_msg")
@_on_bot_loop
async def automod_spam_msg_update(payload: AutomodSpamMsgUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    _reject_nulls(data)
    return await am_spam.save_config(ctx.gid, **data)


@router.put("/guilds/{guild_id}/automod/antispam_emoji")
@_on_bot_loop
async def automod_spam_emoji_update(payload: AutomodEmojiUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    _reject_nulls(data)
    return await am_emoji.save_config(ctx.gid, **data)


@router.put("/guilds/{guild_id}/automod/antispam_mention")
@_on_bot_loop
async def automod_spam_mention_update(payload: AutomodMentionUpdate, ctx: GuildCtx = Depends(guild_access(AUTOMOD))):
    data = _changes(payload)
    _reject_nulls(data)
    return await am_mention.save_config(ctx.gid, **data)


# ============================================================
# 🎫 TICKET
# ============================================================

class TicketPanelCreate(_Body):
    title: str = Field(min_length=1, max_length=PANEL_TITLE_MAX_LENGTH)
    panel_message: str = Field(min_length=1, max_length=PANEL_MESSAGE_MAX_LENGTH)
    channel_id: Snowflake                      # salon où le panel est posté
    ticket_category_id: Snowflake
    transcript_channel_id: Snowflake
    staff_roles: list[Snowflake] = Field(min_length=1, max_length=MAX_STAFF_ROLES_PER_PANEL)
    closed_category_id: Snowflake | None = None
    backup_category_id: Snowflake | None = None
    panel_emoji: str | None = Field(default=None, max_length=64)
    panel_image_url: str | None = Field(default=None, max_length=512)
    ping_role_id: Snowflake | None = None
    role_ban_ticket_id: Snowflake | None = None


class TicketPanelUpdate(_Body):
    title: str | None = Field(default=None, min_length=1, max_length=PANEL_TITLE_MAX_LENGTH)
    panel_message: str | None = Field(default=None, min_length=1, max_length=PANEL_MESSAGE_MAX_LENGTH)
    channel_id: Snowflake | None = None
    ticket_category_id: Snowflake | None = None
    transcript_channel_id: Snowflake | None = None
    staff_roles: list[Snowflake] | None = Field(default=None, min_length=1, max_length=MAX_STAFF_ROLES_PER_PANEL)
    closed_category_id: Snowflake | None = None
    backup_category_id: Snowflake | None = None
    panel_emoji: str | None = Field(default=None, max_length=64)
    panel_image_url: str | None = Field(default=None, max_length=512)
    ping_role_id: Snowflake | None = None
    role_ban_ticket_id: Snowflake | None = None


_REQUIRED_PANEL_FIELDS = ("title", "panel_message", "channel_id", "ticket_category_id", "transcript_channel_id", "staff_roles")


def _validate_panel_fields(ctx: GuildCtx, data: dict, existing: dict | None) -> dict:
    """Valide les champs reçus (mêmes règles que views/ticket/panel_setup_view)."""
    from views.ticket.panel_setup_view import _parse_panel_emoji, _parse_panel_image_url

    out = dict(data)

    for key in _REQUIRED_PANEL_FIELDS:
        if key in out and out[key] is None:
            raise _fail(422, f"{key} ne peut pas être null.")

    if "channel_id" in out:
        out["channel_id"] = _text_channel(ctx, out["channel_id"], label="Salon du panel").id
    if "transcript_channel_id" in out:
        out["transcript_channel_id"] = _text_channel(ctx, out["transcript_channel_id"], label="Salon transcript").id
    if "ticket_category_id" in out:
        out["ticket_category_id"] = _category(ctx, out["ticket_category_id"], label="Catégorie des tickets").id
    for key, label in (("closed_category_id", "Catégorie des tickets fermés"), ("backup_category_id", "Catégorie de secours")):
        if key in out and out[key] is not None:
            out[key] = _category(ctx, out[key], label=label).id

    if "staff_roles" in out:
        roles = list(dict.fromkeys(out["staff_roles"]))
        out["staff_roles"] = [_role(ctx, rid, label="Rôle staff").id for rid in roles]
    for key, label in (("ping_role_id", "Rôle ping"), ("role_ban_ticket_id", "Rôle ban ticket")):
        if key in out and out[key] is not None:
            out[key] = _role(ctx, out[key], label=label).id

    if "panel_emoji" in out:
        value = (out["panel_emoji"] or "").strip()
        if value:
            parsed = _parse_panel_emoji(value, ctx.bot)
            if parsed is None:
                raise _fail(422, "Emoji invalide (un seul emoji, ou un emoji personnalisé accessible au bot).")
            value = parsed
        out["panel_emoji"] = value or None

    if "panel_image_url" in out:
        value = (out["panel_image_url"] or "").strip()
        if value:
            parsed = _parse_panel_image_url(value)
            if parsed is None:
                raise _fail(422, "URL d'image invalide (https:// uniquement, sans espace).")
            if parsed != (existing or {}).get("panel_image_url"):
                _require_gold(ctx, "L'image du panel")
            value = parsed
        out["panel_image_url"] = value or None

    return out


async def _post_or_edit_panel(ctx: GuildCtx, panel_id: str, merged: dict) -> discord.Message:
    from views.ticket.panel_public_view import PanelPublicView

    channel = ctx.guild.get_channel(merged["channel_id"])
    view = PanelPublicView(
        panel_id=panel_id,
        guild_id=ctx.gid,
        title=merged["title"],
        message=merged["panel_message"],
        emoji=merged.get("panel_emoji"),
        image_url=merged.get("panel_image_url"),
    )
    try:
        msg = None
        if merged.get("message_id"):
            try:
                msg = await channel.fetch_message(merged["message_id"])
                await msg.edit(view=view)
            except discord.HTTPException:
                msg = None
        if msg is None:
            msg = await channel.send(view=view)
    except discord.HTTPException as exc:
        raise _fail(502, f"Erreur Discord : {exc}")
    try:
        ctx.bot.add_view(view, message_id=msg.id)
    except Exception:
        log.debug("[DASHBOARD] add_view panel %s ignoré", panel_id, exc_info=True)
    return msg


@router.get("/guilds/{guild_id}/tickets/panels")
@_on_bot_loop
async def tickets_list(ctx: GuildCtx = Depends(guild_access("ticket_panel_list"))):
    return {"panels": await tm.list_panels(ctx.gid), "is_gold": is_gold(ctx.gid)}


@router.post("/guilds/{guild_id}/tickets/panels", status_code=201)
@_on_bot_loop
async def tickets_create(payload: TicketPanelCreate, ctx: GuildCtx = Depends(guild_access("ticket_panel_create"))):
    data = _validate_panel_fields(ctx, payload.model_dump(), existing=None)

    panel_id = f"panel_{int(time.time())}"
    while await tm.get_panel(ctx.gid, panel_id):
        panel_id += "x"

    msg = await _post_or_edit_panel(ctx, panel_id, data)
    try:
        panel = await tm.create_panel(
            guild_id=ctx.gid,
            panel_id=panel_id,
            message_id=msg.id,
            staff_role_ids=data.pop("staff_roles"),
            **data,
        )
    except Exception:
        log.exception("[DASHBOARD] Création panel échouée guild=%s", ctx.gid)
        await _best_effort_delete_message(ctx.guild, data["channel_id"], msg.id)
        raise _fail(500, "La sauvegarde du panel a échoué : le message a été retiré.")
    return {"panel": panel}


@router.patch("/guilds/{guild_id}/tickets/panels/{panel_id}")
@_on_bot_loop
async def tickets_update(panel_id: str, payload: TicketPanelUpdate, ctx: GuildCtx = Depends(guild_access("ticket_panel_edit"))):
    existing = await tm.get_panel(ctx.gid, panel_id)
    if existing is None:
        raise _fail(404, "Panel introuvable sur ce serveur.")

    changes = _validate_panel_fields(ctx, _changes(payload), existing=existing)
    merged = {**existing, **changes}

    old_channel, old_message = existing["channel_id"], existing.get("message_id")
    if merged["channel_id"] != old_channel:
        merged["message_id"] = None  # nouveau salon → nouveau message
    msg = await _post_or_edit_panel(ctx, panel_id, merged)
    if merged["channel_id"] != old_channel:
        await _best_effort_delete_message(ctx.guild, old_channel, old_message)

    panel = await tm.update_panel(
        ctx.gid,
        panel_id,
        staff_role_ids=merged["staff_roles"],
        channel_id=merged["channel_id"],
        message_id=msg.id,
        title=merged["title"],
        panel_message=merged["panel_message"],
        ticket_category_id=merged["ticket_category_id"],
        transcript_channel_id=merged["transcript_channel_id"],
        closed_category_id=merged.get("closed_category_id"),
        backup_category_id=merged.get("backup_category_id"),
        panel_emoji=merged.get("panel_emoji"),
        panel_image_url=merged.get("panel_image_url"),
        ping_role_id=merged.get("ping_role_id"),
        role_ban_ticket_id=merged.get("role_ban_ticket_id"),
    )
    return {"panel": panel}


@router.delete("/guilds/{guild_id}/tickets/panels/{panel_id}")
@_on_bot_loop
async def tickets_delete(panel_id: str, ctx: GuildCtx = Depends(guild_access("ticket_panel_delete"))):
    panel = await tm.get_panel(ctx.gid, panel_id)
    if panel is None:
        raise _fail(404, "Panel introuvable sur ce serveur.")
    await _best_effort_delete_message(ctx.guild, panel.get("channel_id"), panel.get("message_id"))
    await tm.delete_panel(ctx.gid, panel_id)
    return {"deleted": panel_id}


# ============================================================
# 🎭 RÔLE RÉACTION
# ============================================================

class ReactionCouple(_Body):
    emoji: str = Field(min_length=1, max_length=100)
    role_id: Snowflake


class ReactionRoleCreate(_Body):
    channel_id: Snowflake
    text: str | None = Field(default=None, max_length=1000)
    reactions: list[ReactionCouple] = Field(min_length=1)


def _validate_reaction_emoji(ctx: GuildCtx, raw: str) -> str:
    from views.reaction_role.config_view import _is_single_unicode_emoji

    raw = raw.strip()
    if raw.startswith("<"):
        partial = discord.PartialEmoji.from_str(raw)
        if partial.id is None:
            raise _fail(422, f"Emoji personnalisé invalide : {raw}")
        if ctx.bot.get_emoji(partial.id) is None:
            raise _fail(422, f"Le bot n'a pas accès à l'emoji personnalisé {raw}.")
        return raw
    if not _is_single_unicode_emoji(raw):
        raise _fail(422, f"« {raw} » n'est pas un emoji unique valide.")
    return raw


@router.get("/guilds/{guild_id}/role-reaction")
@_on_bot_loop
async def role_reaction_list(ctx: GuildCtx = Depends(guild_access("config_role_reaction"))):
    messages = await rr.obtenir_tous_messages(ctx.gid)
    return {
        "messages": sorted(messages.values(), key=lambda m: m.get("created_at") or ""),
        "limits": {
            "max_messages": rr.obtenir_limite_messages(ctx.gid),
            "max_couples_per_message": rr.obtenir_limite_couples(ctx.gid),
        },
        "is_gold": is_gold(ctx.gid),
    }


@router.post("/guilds/{guild_id}/role-reaction", status_code=201)
@_on_bot_loop
async def role_reaction_create(payload: ReactionRoleCreate, ctx: GuildCtx = Depends(guild_access("config_role_reaction"))):
    from views.reaction_role.config_view import DEFAULT_TEXT, build_sent_message_view

    ok, reason = await rr.peut_creer_message(ctx.gid)
    if not ok:
        raise _fail(403, reason)

    max_couples = rr.obtenir_limite_couples(ctx.gid)
    if len(payload.reactions) > max_couples:
        raise _fail(403, f"Limite atteinte : {max_couples} couples emoji/rôle par message maximum.")

    couples: list[dict] = []
    seen: set[str] = set()
    for item in payload.reactions:
        emoji = _validate_reaction_emoji(ctx, item.emoji)
        if emoji in seen:
            raise _fail(422, f"L'emoji {emoji} est utilisé plusieurs fois.")
        seen.add(emoji)
        role = _role(ctx, item.role_id, label=f"Rôle de {emoji}", assignable=True)
        couples.append({"emoji": emoji, "role_id": role.id})

    channel = _text_channel(
        ctx, payload.channel_id, label="Salon",
        perms=("view_channel", "send_messages", "read_message_history", "add_reactions", "manage_roles"),
    )
    text = (payload.text or "").strip() or DEFAULT_TEXT

    try:
        msg = await channel.send(view=build_sent_message_view(text, ctx.guild, couples))
    except discord.HTTPException as exc:
        raise _fail(502, f"Envoi impossible : {exc}")

    for couple in couples:
        try:
            await msg.add_reaction(couple["emoji"])
        except discord.HTTPException:
            log.warning("[DASHBOARD] Réaction impossible %s sur msg %s", couple["emoji"], msg.id)

    await rr.creer_message_reaction(ctx.gid, channel.id, msg.id, text, couples)
    return {"message": await rr.obtenir_message_reaction(ctx.gid, msg.id)}


@router.delete("/guilds/{guild_id}/role-reaction/{message_id}")
@_on_bot_loop
async def role_reaction_delete(message_id: int, ctx: GuildCtx = Depends(guild_access("config_role_reaction"))):
    data = await rr.obtenir_message_reaction(ctx.gid, message_id)
    if data is None:
        raise _fail(404, "Message rôle-réaction introuvable sur ce serveur.")
    await rr.supprimer_message_reaction(ctx.gid, message_id)
    await _best_effort_delete_message(ctx.guild, data.get("channel_id"), message_id)
    return {"deleted": message_id}


# ============================================================
# 🎉 GIVEAWAY
# ============================================================

class GiveawayRequirements(_Body):
    role_id: Snowflake | None = None
    forbidden_role_id: Snowflake | None = None
    min_invites: int | None = Field(default=None, ge=0, le=10_000)
    min_server_age_days: int | None = Field(default=None, ge=0, le=3650)


class GiveawayCreate(_Body):
    prize: str = Field(min_length=1, max_length=500)
    duration_seconds: int = Field(ge=1, le=365 * 86400)
    winners_count: int = Field(default=1, ge=1, le=100)
    channel_id: Snowflake
    requirements: GiveawayRequirements = Field(default_factory=GiveawayRequirements)


class BlacklistAdd(_Body):
    user_id: Snowflake
    reason: str | None = Field(default=None, max_length=200)
    expires_at: datetime | None = None


async def _owned_giveaway(ctx: GuildCtx, giveaway_id: str) -> dict:
    giveaway = await gw.get_giveaway(giveaway_id)
    if giveaway is None or giveaway.get("guild_id") != ctx.gid:
        raise _fail(404, "Giveaway introuvable sur ce serveur.")
    return giveaway


@router.get("/guilds/{guild_id}/giveaways")
@_on_bot_loop
async def giveaways_list(ctx: GuildCtx = Depends(guild_access("giveaway_list"))):
    active = await gw.get_active_giveaways(ctx.gid)
    for g in active:
        g["participants_count"] = await gw.count_participants(g["id"])
    return {"active": active, "ended": await gw.get_ended_giveaways(ctx.gid, limit=10)}


@router.post("/guilds/{guild_id}/giveaways", status_code=201)
@_on_bot_loop
async def giveaways_create(payload: GiveawayCreate, ctx: GuildCtx = Depends(guild_access("giveaway_create"))):
    from datetime import timedelta
    from views.giveaway.panel_view import build_giveaway_panel

    channel = _text_channel(ctx, payload.channel_id, label="Salon du giveaway")

    requirements = {k: v for k, v in payload.requirements.model_dump().items() if v}
    for key, label in (("role_id", "Rôle requis"), ("forbidden_role_id", "Rôle interdit")):
        if key in requirements:
            _role(ctx, requirements[key], label=label)

    try:
        giveaway_id = await gw.create_giveaway(
            guild_id=ctx.gid,
            channel_id=channel.id,
            host_id=ctx.user_id,
            prize=payload.prize,
            winners_count=payload.winners_count,
            duration_seconds=payload.duration_seconds,
            requirements=requirements,
        )
    except ValueError as exc:
        raise _fail(422, str(exc))

    panel_data = {
        "id": giveaway_id,
        "prize": payload.prize,
        "winners_count": payload.winners_count,
        "end_time": datetime.now(timezone.utc) + timedelta(seconds=payload.duration_seconds),
        "ended": False,
        "host_id": ctx.user_id,
        "winners": [],
        "participants_count": 0,
        "requirements": requirements,
    }
    try:
        msg = await channel.send(view=build_giveaway_panel(panel_data, ctx.guild))
        await msg.add_reaction("🎉")
    except discord.HTTPException as exc:
        await gw.delete_giveaway(giveaway_id)  # rollback, comme sur Discord
        raise _fail(502, f"Erreur Discord : {exc}")

    await gw.set_message_id(giveaway_id, msg.id)
    return {"giveaway": await gw.get_giveaway(giveaway_id)}


@router.post("/guilds/{guild_id}/giveaways/{giveaway_id}/end")
@_on_bot_loop
async def giveaways_end(giveaway_id: str, ctx: GuildCtx = Depends(guild_access("giveaway_manage"))):
    giveaway = await _owned_giveaway(ctx, giveaway_id)
    if giveaway["ended"]:
        raise _fail(409, "Ce giveaway est déjà terminé.")

    listener = ctx.bot.get_cog("GiveawayListener")
    if listener is None:
        raise _fail(503, "Le module giveaway n'est pas chargé.")
    if giveaway_id in listener._ending:
        raise _fail(409, "Ce giveaway est déjà en cours de clôture.")

    listener._ending.add(giveaway_id)
    try:
        await listener._close_giveaway(giveaway)
    finally:
        listener._ending.discard(giveaway_id)
    return {"giveaway": await gw.get_giveaway(giveaway_id)}


@router.delete("/guilds/{guild_id}/giveaways/{giveaway_id}")
@_on_bot_loop
async def giveaways_delete(giveaway_id: str, ctx: GuildCtx = Depends(guild_access("giveaway_manage"))):
    giveaway = await _owned_giveaway(ctx, giveaway_id)
    await _best_effort_delete_message(ctx.guild, giveaway.get("channel_id"), giveaway.get("message_id"))
    await gw.delete_giveaway(giveaway_id)
    return {"deleted": giveaway_id}


@router.get("/guilds/{guild_id}/giveaways/blacklist")
@_on_bot_loop
async def giveaways_blacklist_get(ctx: GuildCtx = Depends(guild_access("giveaway_blacklist"))):
    return {"blacklist": await gw.get_blacklist(ctx.gid)}


@router.post("/guilds/{guild_id}/giveaways/blacklist", status_code=201)
@_on_bot_loop
async def giveaways_blacklist_add(payload: BlacklistAdd, ctx: GuildCtx = Depends(guild_access("giveaway_blacklist"))):
    expires = payload.expires_at
    if expires is not None:
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            raise _fail(422, "La date d'expiration doit être dans le futur.")
    entry = await gw.add_to_blacklist(ctx.gid, payload.user_id, ctx.user_id, payload.reason, expires)
    return {"entry": entry}


@router.delete("/guilds/{guild_id}/giveaways/blacklist/{user_id}")
@_on_bot_loop
async def giveaways_blacklist_remove(user_id: int, ctx: GuildCtx = Depends(guild_access("giveaway_blacklist"))):
    if not await gw.remove_from_blacklist(ctx.gid, user_id):
        raise _fail(404, "Cet utilisateur n'est pas blacklisté.")
    return {"removed": user_id}


# ============================================================
# 🔊 JOIN TO CREATE
# ============================================================

class TriggerCreate(_Body):
    category_id: Snowflake
    name: str = Field(min_length=1, max_length=100)


class TriggerRename(_Body):
    name: str = Field(min_length=1, max_length=100)


async def _owned_trigger(ctx: GuildCtx, trigger_id: int) -> dict:
    trigger = await jtc.get_trigger(trigger_id)
    if trigger is None or trigger.get("guild_id") != ctx.gid:
        raise _fail(404, "Salon déclencheur introuvable sur ce serveur.")
    return trigger


@router.get("/guilds/{guild_id}/join-to-create")
@_on_bot_loop
async def jtc_list(ctx: GuildCtx = Depends(guild_access("config_join_to_create"))):
    return {
        "triggers": await jtc.list_triggers(ctx.gid),
        "limit": jtc.get_trigger_limit(ctx.gid),
        "is_gold": is_gold(ctx.gid),
    }


@router.post("/guilds/{guild_id}/join-to-create", status_code=201)
@_on_bot_loop
async def jtc_create(payload: TriggerCreate, ctx: GuildCtx = Depends(guild_access("config_join_to_create"))):
    can_add, count, limit = await jtc.can_add_trigger(ctx.gid)
    if not can_add:
        raise _fail(403, f"Limite de salons déclencheurs atteinte ({count}/{limit}).")
    if await jtc.category_already_used(ctx.gid, payload.category_id):
        raise _fail(409, "Cette catégorie est déjà utilisée par un autre salon déclencheur.")

    category = _category(ctx, payload.category_id)
    try:
        channel = await ctx.guild.create_voice_channel(
            name=payload.name, category=category, reason=f"Join to Create — nouveau déclencheur (site) par {ctx.member}",
        )
    except discord.Forbidden:
        raise _fail(403, "Permissions insuffisantes pour créer ce salon.")
    except discord.HTTPException:
        raise _fail(502, "Erreur Discord lors de la création du salon.")

    try:
        trigger = await jtc.create_trigger(
            ctx.gid, trigger_channel_id=channel.id, trigger_channel_name=payload.name, category_id=category.id,
        )
    except Exception:
        log.exception("[DASHBOARD] Enregistrement déclencheur échoué guild=%s", ctx.gid)
        try:
            await channel.delete(reason="Join to Create — enregistrement échoué")
        except (discord.Forbidden, discord.HTTPException):
            pass
        raise _fail(500, "Erreur interne : le salon n'a pas été créé.")
    return {"trigger": trigger}


@router.patch("/guilds/{guild_id}/join-to-create/{trigger_id}")
@_on_bot_loop
async def jtc_rename(trigger_id: int, payload: TriggerRename, ctx: GuildCtx = Depends(guild_access("config_join_to_create"))):
    trigger = await _owned_trigger(ctx, trigger_id)
    channel = ctx.guild.get_channel(trigger.get("trigger_channel_id"))
    if isinstance(channel, discord.VoiceChannel) and channel.name != payload.name:
        try:
            await channel.edit(name=payload.name, reason=f"Join to Create — renommage (site) par {ctx.member}")
        except discord.Forbidden:
            raise _fail(403, "Permissions insuffisantes pour renommer ce salon.")
        except discord.HTTPException:
            raise _fail(502, "Erreur Discord lors du renommage.")
    return {"trigger": await jtc.rename_trigger(trigger_id, payload.name)}


@router.delete("/guilds/{guild_id}/join-to-create/{trigger_id}")
@_on_bot_loop
async def jtc_delete(trigger_id: int, ctx: GuildCtx = Depends(guild_access("config_join_to_create"))):
    trigger = await _owned_trigger(ctx, trigger_id)
    channel = ctx.guild.get_channel(trigger.get("trigger_channel_id"))
    if isinstance(channel, discord.VoiceChannel):
        try:
            await channel.delete(reason=f"Join to Create — suppression déclencheur (site) par {ctx.member}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("[DASHBOARD] Suppression salon déclencheur échouée guild=%s : %s", ctx.gid, exc)
    await jtc.delete_trigger(trigger_id)
    return {"deleted": trigger_id}


# ============================================================
# 📡 MEDIA LINK
# ============================================================

class MediaConnectionCreate(_Body):
    platform: Literal["youtube", "twitch"]
    external_id: str = Field(min_length=1, max_length=128)


class MediaRuleCreate(_Body):
    connection_id: int
    event_type: str = Field(min_length=1, max_length=48)
    channel_id: Snowflake
    template_id: int | None = None
    mention_role_id: Snowflake | None = None


class MediaRuleUpdate(_Body):
    enabled: bool


def _event_catalog() -> dict[str, list[dict]]:
    """Types d'événements par plateforme (même catalogue que la vue Discord)."""
    from views.medialink.medialink_events_view import _PLATFORM_EVENT_CATALOGS

    return {
        platform: [{"event_type": et, "label": label} for _cap, et, label, _emoji in catalog]
        for platform, catalog in _PLATFORM_EVENT_CATALOGS.items()
    }


async def _owned_connection(ctx: GuildCtx, connection_id: int) -> dict:
    for connection in await ml.list_connections(ctx.gid):
        if connection["id"] == connection_id:
            return connection
    raise _fail(404, "Connexion introuvable sur ce serveur.")


async def _owned_rule(ctx: GuildCtx, rule_id: int) -> dict:
    for connection in await ml.list_connections(ctx.gid):
        for rule in await ml.list_rules(connection["id"]):
            if rule["id"] == rule_id:
                return rule
    raise _fail(404, "Règle introuvable sur ce serveur.")


@router.get("/guilds/{guild_id}/medialink")
@_on_bot_loop
async def medialink_get(ctx: GuildCtx = Depends(guild_access("medialink_config"))):
    connections = []
    for connection in await ml.list_connections(ctx.gid):
        connections.append({**connection, "rules": await ml.list_rules(connection["id"])})
    return {
        "connections": connections,
        "templates": await ml.list_templates(ctx.gid),
        "platforms": [p for p in ml.KNOWN_PLATFORMS if p not in ml.BLOCKED_PLATFORMS],
        "event_catalog": _event_catalog(),
    }


@router.post("/guilds/{guild_id}/medialink/connections", status_code=201)
@_on_bot_loop
async def medialink_connection_add(payload: MediaConnectionCreate, ctx: GuildCtx = Depends(guild_access("medialink_config"))):
    from utils.medialink import event_manager
    from utils.medialink.providers import twitch as twitch_mod
    from utils.medialink.providers import youtube as youtube_mod

    if payload.platform in ml.BLOCKED_PLATFORMS:
        raise _fail(422, "Cette plateforme n'est pas disponible.")

    provider_cls, not_found_exc, auth_exc = {
        "youtube": (youtube_mod.YouTubeProvider, youtube_mod.ProviderNotFoundError, youtube_mod.ProviderAuthError),
        "twitch": (twitch_mod.TwitchProvider, twitch_mod.ProviderNotFoundError, twitch_mod.ProviderAuthError),
    }[payload.platform]

    provider = provider_cls()
    try:
        account = await provider.get_account(payload.external_id)
    except not_found_exc:
        raise _fail(404, "Aucun compte trouvé pour cet identifiant.")
    except auth_exc:
        log.error("[DASHBOARD] Auth provider %s refusée (clé API invalide/quota) guild=%s", payload.platform, ctx.gid)
        raise _fail(502, "Impossible de vérifier le compte pour le moment, réessayez plus tard.")
    except httpx.HTTPError:
        log.exception("[DASHBOARD] Erreur réseau provider %s guild=%s", payload.platform, ctx.gid)
        raise _fail(502, "Impossible de contacter la plateforme, réessayez plus tard.")
    finally:
        await provider.disconnect()

    try:
        connection = await ml.add_connection(
            ctx.gid,
            payload.platform,
            account.external_id,
            external_username=account.username,
            external_url=account.url,
            avatar_url=account.avatar_url,
        )
    except IntegrityError:
        raise _fail(409, f"{account.username or payload.external_id} est déjà connecté sur ce serveur.")

    # Anti-rétroactif : on ignore les contenus déjà publiés (comme sur Discord).
    try:
        await provider.connect(account.external_id)
        baseline = await provider.fetch_events()
        await event_manager.seed_baseline_events(connection["id"], baseline)
    except Exception:
        log.warning("[DASHBOARD] Baseline anti-rétroactif échouée guild=%s connection=%s", ctx.gid, connection["id"], exc_info=True)
    finally:
        await provider.disconnect()

    return {"connection": connection}


@router.delete("/guilds/{guild_id}/medialink/connections/{connection_id}")
@_on_bot_loop
async def medialink_connection_delete(connection_id: int, ctx: GuildCtx = Depends(guild_access("medialink_config"))):
    await _owned_connection(ctx, connection_id)
    await ml.remove_connection(ctx.gid, connection_id)
    return {"deleted": connection_id}


@router.post("/guilds/{guild_id}/medialink/rules", status_code=201)
@_on_bot_loop
async def medialink_rule_add(payload: MediaRuleCreate, ctx: GuildCtx = Depends(guild_access("medialink_config"))):
    connection = await _owned_connection(ctx, payload.connection_id)

    allowed = {e["event_type"] for e in _event_catalog().get(connection["platform"], [])}
    if payload.event_type not in allowed:
        raise _fail(422, f"Type d'événement invalide pour {connection['platform']} : {', '.join(sorted(allowed))}.")

    channel = _text_channel(ctx, payload.channel_id, label="Salon d'annonce")

    if payload.template_id is not None:
        if not any(t["id"] == payload.template_id for t in await ml.list_templates(ctx.gid)):
            raise _fail(422, "Template introuvable sur ce serveur.")
    mention_role_id = _opt_role(ctx, payload.mention_role_id, "Rôle à mentionner")

    rule = await ml.add_rule(
        connection["id"], payload.event_type, channel.id,
        template_id=payload.template_id, mention_role_id=mention_role_id,
    )
    return {"rule": rule}


@router.patch("/guilds/{guild_id}/medialink/rules/{rule_id}")
@_on_bot_loop
async def medialink_rule_toggle(rule_id: int, payload: MediaRuleUpdate, ctx: GuildCtx = Depends(guild_access("medialink_config"))):
    await _owned_rule(ctx, rule_id)
    await ml.set_rule_enabled(rule_id, payload.enabled)
    return {"rule_id": rule_id, "enabled": payload.enabled}


@router.delete("/guilds/{guild_id}/medialink/rules/{rule_id}")
@_on_bot_loop
async def medialink_rule_delete(rule_id: int, ctx: GuildCtx = Depends(guild_access("medialink_config"))):
    await _owned_rule(ctx, rule_id)
    await ml.remove_rule(rule_id)
    return {"deleted": rule_id}


# ============================================================
# 🔌 Enregistrement
# ============================================================

app.include_router(router)
