"""
cogs/events/mod_automod_listener.py — Écoute on_message pour l'auto-modération.

Point d'entrée unique pour tous les sous-systèmes d'automod. Chaque système
activé pour la guild est interrogé dans l'ordre. Dès qu'un système détecte
une infraction :
  1. Le message est supprimé (best-effort — Discord peut refuser)
  2. Un message court est posté dans le salon d'origine (si notify_in_channel)
  3. Un log détaillé est envoyé au salon d'alerte du staff (si alert_channel_id)
  4. L'infraction est enregistrée en DB (pour historique + stats)

Aucun mute automatique, aucune escalade auto : le staff décide manuellement
en consultant /mod historique.

Exemptions : les admins Discord (permission `administrator`) et les bots
sont skippés systématiquement.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.automod.detectors import (
    antifullcaps as antifullcaps_detector,
    antispam_emoji as antispam_emoji_detector,
    antispam_mention as antispam_mention_detector,
    banword as banword_detector,
)
from utils.managers import (
    mod_automod_antifullcaps_manager as antifullcaps_mgr,
    mod_automod_antispam_emoji_manager as antispam_emoji_mgr,
    mod_automod_antispam_mention_manager as antispam_mention_mgr,
    mod_automod_banword_manager as banword_mgr,
    mod_automod_general_manager as general_mgr,
    mod_automod_infraction_manager as infr_mgr,
)

log = logging.getLogger(__name__)


# ============================================================
# 📚 Registre des systèmes
# ============================================================
#
# Chaque système est décrit par un dict :
#   - key           : identifiant technique stocké en DB (system_key)
#   - display_name  : nom affiché dans les logs staff
#   - notify_msg    : message court affiché dans le salon d'origine
#
# Ajouter un nouveau système : nouvelle entrée + un `_detect_<key>` async
# qui retourne (matched_term|None, ...) et branchage dans _analyze_message.

_SYSTEM_META: dict[str, dict[str, str]] = {
    "banword": {
        "display_name": "Ban Word",
        "notify_msg": "🚫 Ton message contenait un **mot interdit**. Il a été supprimé.",
    },
    "antifullcaps": {
        "display_name": "Anti Full Maj",
        "notify_msg": "🔠 Ton message était majoritairement en **MAJUSCULES**. Il a été supprimé.",
    },
    "antispam_mention": {
        "display_name": "Anti Spam Mention",
        "notify_msg": "📣 Ton message contenait **trop de mentions**. Il a été supprimé.",
    },
    "antispam_emoji": {
        "display_name": "Anti Spam Emoji",
        "notify_msg": "😀 Ton message contenait **trop d'emojis**. Il a été supprimé.",
    },
    # Futures entrées : nolink, antilink, antispam_msg, antiflood.
}


# ============================================================
# 🧩 Cog
# ============================================================

class ModAutomodListener(commands.Cog):
    """Écoute les messages et applique les règles d'auto-modération."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        # Ignorer bots, DM, systèmes.
        if message.author.bot:
            return
        if message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return

        # Exemption : administrateurs Discord.
        if message.author.guild_permissions.administrator:
            return

        # Analyse.
        try:
            hit = await self._analyze_message(message)
        except Exception:
            log.exception("[AUTOMOD] Erreur analyse message %s", message.id)
            return

        if hit is None:
            return

        system_key, matched_term = hit
        await self._apply_action(message, system_key, matched_term)

    # ────────────────────────────────────────────────────────
    # 🔎 Analyse par sous-système
    # ────────────────────────────────────────────────────────

    async def _analyze_message(
        self, message: discord.Message,
    ) -> tuple[str, str | None] | None:
        """
        Interroge chaque sous-système activé pour cette guild. Retourne
        (system_key, matched_term) au premier hit, ou None.
        """
        guild_id = message.guild.id
        content = message.content or ""

        # ── Ban word ──────────────────────────────────────
        bw_cfg = await banword_mgr.load_config(guild_id)
        if bw_cfg.get("enabled"):
            words = await banword_mgr.list_words(guild_id)
            if words:
                match = banword_detector.detect(content, words)
                if match is not None:
                    return ("banword", match)

        # ── Anti Full Maj ─────────────────────────────────
        fc_cfg = await antifullcaps_mgr.load_config(guild_id)
        if fc_cfg.get("enabled"):
            match = antifullcaps_detector.detect(
                content,
                min_length=fc_cfg.get("min_length", 10),
                ratio_threshold=fc_cfg.get("ratio_threshold", 0.7),
            )
            if match is not None:
                return ("antifullcaps", match)

        # ── Anti Spam Mention ─────────────────────────────
        # Passe le Message directement au détecteur : Discord fait la
        # résolution des mentions de manière fiable (ignore les mentions
        # dans les blocs de code, etc.).
        m_cfg = await antispam_mention_mgr.load_config(guild_id)
        if m_cfg.get("enabled"):
            match = antispam_mention_detector.detect(
                message, max_mentions=m_cfg.get("max_mentions", 5),
            )
            if match is not None:
                return ("antispam_mention", match)

        # ── Anti Spam Emoji ───────────────────────────────
        e_cfg = await antispam_emoji_mgr.load_config(guild_id)
        if e_cfg.get("enabled"):
            match = antispam_emoji_detector.detect(
                content, max_emoji=e_cfg.get("max_emoji", 10),
            )
            if match is not None:
                return ("antispam_emoji", match)

        # (Futurs systèmes ici : nolink, antilink, antispam_msg, antiflood.)

        return None

    # ────────────────────────────────────────────────────────
    # ⚡ Application de la sanction (delete + notify + log + DB)
    # ────────────────────────────────────────────────────────

    async def _apply_action(
        self, message: discord.Message, system_key: str, matched_term: str | None,
    ) -> None:
        guild = message.guild
        author = message.author
        meta = _SYSTEM_META.get(system_key, {})
        display = meta.get("display_name", system_key)

        # 1. Delete du message (best-effort — perms manquantes = on skip).
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "[AUTOMOD] Delete refusé guild=%s channel=%s message=%s",
                guild.id, message.channel.id, message.id,
            )

        # 2. Message dans le salon d'origine (si activé).
        general_cfg = await general_mgr.load_general(guild.id)
        if general_cfg.get("notify_in_channel") and meta.get("notify_msg"):
            try:
                await message.channel.send(
                    f"{author.mention} {meta['notify_msg']}",
                    delete_after=8,
                    allowed_mentions=discord.AllowedMentions(users=True),
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        # 3. Log staff (si un salon d'alerte est configuré).
        alert_channel_id = general_cfg.get("alert_channel_id")
        if alert_channel_id:
            alert_channel = guild.get_channel(alert_channel_id)
            if alert_channel is not None:
                try:
                    await alert_channel.send(view=_build_alert_view(
                        message, display, matched_term,
                    ))
                except (discord.Forbidden, discord.HTTPException):
                    log.warning(
                        "[AUTOMOD] Log staff refusé guild=%s alert_channel=%s",
                        guild.id, alert_channel_id,
                    )

        # 4. Enregistrement DB (toujours, même si les envois Discord ont
        # partiellement échoué — l'historique est la source de vérité).
        try:
            await infr_mgr.register_infraction(
                guild_id=guild.id,
                user_id=author.id,
                channel_id=message.channel.id,
                system_key=system_key,
                matched_term=matched_term,
                message_content=message.content,
            )
        except Exception:
            log.exception("[AUTOMOD] Enregistrement DB échoué guild=%s", guild.id)


# ============================================================
# 🎨 Vue d'alerte staff (Container V2)
# ============================================================

def _build_alert_view(
    message: discord.Message, display_name: str, matched_term: str | None,
) -> LayoutView:
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay(f"# ⚠️ Auto-modération · {display_name}"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"**Membre** : {message.author.mention} (`{message.author.id}`)\n"
        f"**Salon** : {message.channel.mention}"
    ))
    if matched_term is not None:
        c.add_item(TextDisplay(f"**Terme détecté** : `{matched_term}`"))
    c.add_item(Separator())
    excerpt = (message.content or "")[:500]
    if excerpt:
        c.add_item(TextDisplay(f"**Message** :\n> {excerpt}"))
    else:
        c.add_item(TextDisplay("_(Message vide ou sans contenu texte.)_"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        "-# Aucune sanction automatique appliquée. Consulte "
        f"`/mod historique {message.author.id}` pour décider."
    ))
    view.add_item(c)
    return view


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModAutomodListener(bot))