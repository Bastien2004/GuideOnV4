"""
cogs/events/mod_automod_listener.py — Écoute on_message pour l'auto-modération.

Flow (v3, refonte avec récidive temporelle) :

  1. Message reçu → skip bots/admins/DM
  2. Interroge chaque sous-système activé pour la guild
  3. Si un système détecte une infraction :
     a. Supprime le message (best-effort)
     b. Compte les récidives dans la fenêtre configurée (in-memory tracker)
     c. Enregistre l'infraction en DB (mod_automod_infractions)
     d. Envoie un container V2 dans le salon d'origine (option)
     e. Envoie un MP au user (container V2, best-effort)
     f. Si récidive (>=2 infractions même système dans la fenêtre) :
        - Applique un timeout Discord natif (max 28j)
        - Envoie une alerte staff DANS le salon d'alerte avec bouton
          "Je m'en occupe" (view persistante)
        - Ping le rôle staff configuré
        - Insère la ligne dans mod_automod_active_alerts
        - Reset le compteur récidive (évite mute en cascade sur les messages
          suivants du même user dans la fenêtre)
     g. Sinon (première infraction) : log staff léger dans le salon d'alerte
        (juste info, pas de bouton)
"""
from __future__ import annotations

import logging
from datetime import timedelta

import discord
from discord.ext import commands
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.automod import recidive_tracker
from utils.automod.detectors import (
    antifullcaps as antifullcaps_detector,
    antispam_emoji as antispam_emoji_detector,
    antispam_mention as antispam_mention_detector,
    banword as banword_detector,
)
from utils.managers import (
    mod_automod_alert_manager as alert_mgr,
    mod_automod_antifullcaps_manager as antifullcaps_mgr,
    mod_automod_antispam_emoji_manager as antispam_emoji_mgr,
    mod_automod_antispam_mention_manager as antispam_mention_mgr,
    mod_automod_banword_manager as banword_mgr,
    mod_automod_general_manager as general_mgr,
    mod_automod_infraction_manager as infr_mgr,
)
from views.mod.automod_alert_view import build_alert_container

log = logging.getLogger(__name__)

# Timeout Discord natif : max autorisé par l'API = 28 jours pile.
_MUTE_DURATION = timedelta(days=28)


# ============================================================
# 📚 Registre des systèmes
# ============================================================

_SYSTEM_META: dict[str, dict[str, str]] = {
    "banword": {
        "display_name": "Ban Word",
        "user_msg": "Ton message contenait un **mot interdit**.",
        "emoji": "🚫",
    },
    "antifullcaps": {
        "display_name": "Anti Full Maj",
        "user_msg": "Ton message était majoritairement en **MAJUSCULES**.",
        "emoji": "🔠",
    },
    "antispam_mention": {
        "display_name": "Anti Spam Mention",
        "user_msg": "Ton message contenait **trop de mentions**.",
        "emoji": "📣",
    },
    "antispam_emoji": {
        "display_name": "Anti Spam Emoji",
        "user_msg": "Ton message contenait **trop d'emojis**.",
        "emoji": "😀",
    },
}


def get_system_display(system_key: str) -> str:
    """Nom affichable pour un system_key. Utilisé par la view d'alerte."""
    return _SYSTEM_META.get(system_key, {}).get("display_name", system_key)


# ============================================================
# 🧩 Cog
# ============================================================

class ModAutomodListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is None:
            return
        if not isinstance(message.author, discord.Member):
            return
        if message.author.guild_permissions.administrator:
            return

        try:
            hit = await self._analyze_message(message)
        except Exception:
            log.exception("[AUTOMOD] Erreur analyse message %s", message.id)
            return

        if hit is None:
            return

        system_key, matched_term = hit
        try:
            await self._apply_action(message, system_key, matched_term)
        except Exception:
            log.exception(
                "[AUTOMOD] Erreur application action guild=%s system=%s",
                message.guild.id, system_key,
            )

    # ────────────────────────────────────────────────────────
    # 🔎 Analyse
    # ────────────────────────────────────────────────────────

    async def _analyze_message(
        self, message: discord.Message,
    ) -> tuple[str, str | None] | None:
        guild_id = message.guild.id
        content = message.content or ""

        # ── Ban word ──
        bw_cfg = await banword_mgr.load_config(guild_id)
        if bw_cfg.get("enabled"):
            words = await banword_mgr.list_words(guild_id)
            if words:
                match = banword_detector.detect(content, words)
                if match is not None:
                    return ("banword", match)

        # ── Anti Full Maj ──
        fc_cfg = await antifullcaps_mgr.load_config(guild_id)
        if fc_cfg.get("enabled"):
            match = antifullcaps_detector.detect(
                content,
                min_length=fc_cfg.get("min_length", 10),
                ratio_threshold=fc_cfg.get("ratio_threshold", 0.7),
            )
            if match is not None:
                return ("antifullcaps", match)

        # ── Anti Spam Mention ──
        m_cfg = await antispam_mention_mgr.load_config(guild_id)
        if m_cfg.get("enabled"):
            match = antispam_mention_detector.detect(
                message, max_mentions=m_cfg.get("max_mentions", 5),
            )
            if match is not None:
                return ("antispam_mention", match)

        # ── Anti Spam Emoji ──
        e_cfg = await antispam_emoji_mgr.load_config(guild_id)
        if e_cfg.get("enabled"):
            match = antispam_emoji_detector.detect(
                content, max_emoji=e_cfg.get("max_emoji", 10),
            )
            if match is not None:
                return ("antispam_emoji", match)

        return None

    # ────────────────────────────────────────────────────────
    # ⚡ Application (delete + tracking + notif + éventuel mute)
    # ────────────────────────────────────────────────────────

    async def _apply_action(
        self, message: discord.Message, system_key: str, matched_term: str | None,
    ) -> None:
        guild = message.guild
        author = message.author
        guild_id = guild.id
        user_id = author.id
        meta = _SYSTEM_META.get(system_key, {})
        display = meta.get("display_name", system_key)
        emoji = meta.get("emoji", "⚠️")

        # 1. Delete du message.
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "[AUTOMOD] Delete refusé guild=%s channel=%s message=%s",
                guild_id, message.channel.id, message.id,
            )

        # 2. Compte les récidives AVANT d'enregistrer la nouvelle (sinon
        # la nouvelle serait toujours >=1).
        general = await general_mgr.load_general(guild_id)
        window = general.get("notification_window_seconds", 60)
        recent = recidive_tracker.count_recent(
            guild_id, user_id, system_key, window_seconds=window,
        )
        is_recidive = recent >= 1  # >=1 précédente dans la fenêtre → celle-ci est la 2e

        # 3. Enregistre en DB + ajoute au tracker mémoire.
        try:
            await infr_mgr.register_infraction(
                guild_id=guild_id, user_id=user_id,
                channel_id=message.channel.id,
                system_key=system_key,
                matched_term=matched_term,
                message_content=message.content,
            )
        except Exception:
            log.exception("[AUTOMOD] Enregistrement DB échoué guild=%s", guild_id)
        recidive_tracker.record_infraction(guild_id, user_id, system_key)

        # 4. Notif dans le salon d'origine (container V2).
        if general.get("notify_in_channel"):
            await self._send_channel_notice(
                message.channel, author, system_display=display,
                emoji=emoji, is_recidive=is_recidive,
                user_msg=meta.get("user_msg", ""),
            )

        # 5. MP au user (container V2).
        await self._send_user_dm(
            author, guild, system_display=display, emoji=emoji,
            is_recidive=is_recidive, user_msg=meta.get("user_msg", ""),
        )

        # 6. Escalade selon récidive.
        alert_channel_id = general.get("alert_channel_id")
        alert_channel = guild.get_channel(alert_channel_id) if alert_channel_id else None

        if is_recidive:
            # Mute Discord natif + alerte staff avec bouton.
            muted = await self._apply_timeout(author, system_key)
            if alert_channel is not None:
                await self._send_full_alert(
                    alert_channel, guild=guild, user=author, message=message,
                    system_key=system_key, system_display=display,
                    matched_term=matched_term,
                    staff_role_id=general.get("staff_role_id"),
                )
            else:
                log.warning(
                    "[AUTOMOD] Récidive détectée mais aucun alert_channel configuré "
                    "guild=%s user=%s system=%s", guild_id, user_id, system_key,
                )
            # Reset le compteur : les prochains messages du user dans la fenêtre
            # ne redéclencheront pas de mute en cascade (le staff a la main).
            recidive_tracker.reset_key(guild_id, user_id, system_key)
        else:
            # 1re infraction : log staff léger dans le salon d'alerte, sans bouton.
            if alert_channel is not None:
                await self._send_light_alert(
                    alert_channel, user=author, message=message,
                    system_display=display, matched_term=matched_term,
                )

    # ────────────────────────────────────────────────────────
    # 📢 Notifications
    # ────────────────────────────────────────────────────────

    async def _send_channel_notice(
        self, channel, author: discord.Member, *,
        system_display: str, emoji: str, is_recidive: bool, user_msg: str,
    ) -> None:
        """Container V2 posté dans le salon d'origine, auto-delete 10s."""
        view = LayoutView(timeout=None)
        c = Container()
        title = f"# {emoji} {system_display}"
        c.add_item(TextDisplay(title))
        c.add_item(Separator())
        body = f"{author.mention}\n{user_msg}"
        if is_recidive:
            body += "\n\n🔒 **Récidive détectée** — un mute Discord a été appliqué."
        c.add_item(TextDisplay(body))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# Auto-modération · GuideOn Studio"))
        view.add_item(c)
        try:
            await channel.send(
                view=view,
                delete_after=10,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _send_user_dm(
        self, user: discord.User, guild: discord.Guild, *,
        system_display: str, emoji: str, is_recidive: bool, user_msg: str,
    ) -> None:
        """MP au user : container V2. Best-effort (DM peuvent être fermés)."""
        view = LayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(f"# {emoji} {system_display}"))
        c.add_item(Separator())
        body = (
            f"Ton message vient d'être supprimé sur **{guild.name}**.\n"
            f"{user_msg}"
        )
        if is_recidive:
            body += (
                "\n\n🔒 **Récidive détectée.** Un mute temporaire a été "
                "appliqué le temps qu'un modérateur examine la situation."
            )
        c.add_item(TextDisplay(body))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# Auto-modération · GuideOn Studio"))
        view.add_item(c)
        try:
            await user.send(view=view)
        except (discord.Forbidden, discord.HTTPException):
            # DM fermés ou bot bloqué : silencieux, c'est normal.
            pass

    async def _send_light_alert(
        self, alert_channel, *, user: discord.Member, message: discord.Message,
        system_display: str, matched_term: str | None,
    ) -> None:
        """Log staff léger sur 1re infraction (pas de bouton)."""
        view = LayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(f"# ⚠️ Auto-modération · {system_display}"))
        c.add_item(Separator())
        body = (
            f"**Membre** : {user.mention} (`{user.id}`)\n"
            f"**Salon** : {message.channel.mention}"
        )
        if matched_term:
            body += f"\n**Terme détecté** : `{matched_term}`"
        c.add_item(TextDisplay(body))
        c.add_item(Separator())
        excerpt = (message.content or "")[:500]
        if excerpt:
            c.add_item(TextDisplay(f"**Message** :\n> {excerpt}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "-# 1re infraction dans la fenêtre. Aucune sanction automatique."
        ))
        view.add_item(c)
        try:
            await alert_channel.send(view=view)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[AUTOMOD] Log léger refusé alert_channel=%s", alert_channel.id)

    async def _send_full_alert(
        self, alert_channel, *, guild: discord.Guild, user: discord.Member,
        message: discord.Message, system_key: str, system_display: str,
        matched_term: str | None, staff_role_id: int | None,
    ) -> None:
        """Alerte STAFF complète avec bouton 'Je m'en occupe' (persistante)."""
        excerpt = (message.content or "")[:500]

        # 1. Envoi initial avec un id temporaire (0) pour construire la vue.
        # On mettra à jour le message avec le vrai alert_id après INSERT DB.
        temp_view = build_alert_container(
            system_display=system_display,
            user_id=user.id,
            channel_id=message.channel.id,
            matched_term=matched_term,
            message_excerpt=excerpt,
            alert_id=0,
            staff_role_id=staff_role_id,
        )

        try:
            # Ping du rôle staff si configuré : allowed_mentions accepte le ping.
            allowed = discord.AllowedMentions(roles=True) if staff_role_id else discord.AllowedMentions.none()
            sent_msg = await alert_channel.send(view=temp_view, allowed_mentions=allowed)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[AUTOMOD] Envoi alerte staff refusé alert_channel=%s", alert_channel.id)
            return

        # 2. Enregistrement DB (récupère l'id).
        try:
            alert_id = await alert_mgr.create_alert(
                guild_id=guild.id,
                user_id=user.id,
                channel_id=message.channel.id,
                system_key=system_key,
                alert_channel_id=alert_channel.id,
                alert_message_id=sent_msg.id,
                matched_term=matched_term,
                message_excerpt=excerpt,
            )
        except Exception:
            log.exception("[AUTOMOD] Insertion alert DB échouée guild=%s", guild.id)
            return

        # 3. Édition du message avec le vrai alert_id (pour que le bouton
        # encode le bon id dans son custom_id).
        final_view = build_alert_container(
            system_display=system_display,
            user_id=user.id,
            channel_id=message.channel.id,
            matched_term=matched_term,
            message_excerpt=excerpt,
            alert_id=alert_id,
            staff_role_id=staff_role_id,
        )
        try:
            await sent_msg.edit(view=final_view)
        except (discord.Forbidden, discord.HTTPException):
            log.warning("[AUTOMOD] Edit final alerte échoué message=%s", sent_msg.id)

    async def _apply_timeout(self, user: discord.Member, system_key: str) -> bool:
        """Applique le timeout Discord natif (28j). Retourne True si appliqué."""
        try:
            await user.timeout(
                _MUTE_DURATION,
                reason=f"Auto-modération : récidive système {system_key}",
            )
            return True
        except (discord.Forbidden, discord.HTTPException):
            log.warning(
                "[AUTOMOD] Timeout refusé guild=%s user=%s",
                user.guild.id, user.id,
            )
            return False


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModAutomodListener(bot))