"""
cogs/events/mod_automod_listener.py — Gestion automod.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

import discord
from discord.ext import commands
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.automod import antispam_msg_buffer, recidive_tracker
from utils.automod.detectors import (
    antifullcaps as antifullcaps_detector,
    antiflood as antiflood_detector,
    antilink as antilink_detector,
    antispam_emoji as antispam_emoji_detector,
    antispam_mention as antispam_mention_detector,
    antispam_msg as antispam_msg_detector,
    banword as banword_detector,
    nolink as nolink_detector,
)

from utils.managers import (
    mod_automod_alert_manager as alert_mgr,
    mod_automod_antifullcaps_manager as antifullcaps_mgr,
    mod_automod_antiflood_manager as antiflood_mgr,
    mod_automod_antilink_manager as antilink_mgr,
    mod_automod_antispam_emoji_manager as antispam_emoji_mgr,
    mod_automod_antispam_mention_manager as antispam_mention_mgr,
    mod_automod_antispam_msg_manager as antispam_msg_mgr,
    mod_automod_banword_manager as banword_mgr,
    mod_automod_general_manager as general_mgr,
    mod_automod_infraction_manager as infr_mgr,
    mod_automod_nolink_manager as nolink_mgr,
)
from views.mod.automod_alert_view import build_alert_container

log = logging.getLogger(__name__)

_MUTE_DURATION = timedelta(days=28)

_REQUIRED_ALERT_PERMS: tuple[str, ...] = ("view_channel", "send_messages", "embed_links", "attach_files")

# 2026-10-03 (Paul) : fenêtre de déduplication par message pour _apply_action.
# Sur un serveur où un AUTRE bot (ou l'AutoMod natif Discord) a aussi un
# automod actif sur les mêmes règles, les deux systèmes peuvent détecter et
# réagir au même message en parallèle. Discord ne nous protège pas non plus
# contre un double-traitement interne : un même message peut nous arriver
# deux fois (on_message ET on_raw_message_edit s'il est édité juste après
# sa création, ou un replay d'évènement après une reconnexion Gateway).
# Sans garde-fou, ça double la sanction (2 DM, 2 lignes d'infraction en DB,
# 2 tentatives de timeout, 2 alertes staff) pour UNE seule vraie infraction.
_DEDUP_WINDOW_SECONDS = 30.0

# 2026-10-06 (Paul) : rate limit observé en prod le 06/10 — plusieurs salons
# ont déclenché des rafales de 429 sur GET /messages/{id}, toutes issues
# d'évènements d'édition de message (voir on_raw_message_edit ci-dessous).
# Filet de sécurité en plus du filtre payload/cache plus bas : borne le
# nombre de fetch_message() concurrents déclenchés par CE listener, pour
# qu'une rafale d'éditions simultanées (plusieurs messages édités dans la
# même seconde) ne parte pas en N requêtes simultanées avant même que le
# bucket Discord ait eu l'occasion de nous renvoyer un retry_after.
_EDIT_FETCH_SEMAPHORE = asyncio.Semaphore(2)


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
        "user_msg": "Ton message contenait trop de **MAJUSCULES**.",
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
    "nolink": {
        "display_name": "No Link",
        "user_msg": "Les **liens** ne sont pas autorisés dans ce salon.",
        "emoji": "🔗",
    },
    "antilink": {
        "display_name": "Anti Link",
        "user_msg": "L'**extension** de ton fichier/lien est **bloquée**.",
        "emoji": "🚫",
    },
    "antispam_msg": {
        "display_name": "Anti Spam Message",
        "user_msg": "Tu as envoyé **trop de fois le même message**.",
        "emoji": "🔁",
    },
    "antiflood": {
        "display_name": "Anti Flood",
        "user_msg": "Ton message ne veut rien dire.",
        "emoji": "🌊",
    },
}


def get_system_display(system_key: str) -> str:
    """Nom affichable pour un system_key. Utilisé par la view d'alerte."""
    return _SYSTEM_META.get(system_key, {}).get("display_name", system_key)


def _missing_send_permissions(channel, guild: discord.Guild) -> list[str]:
    """Vérification des permissions."""

    me = guild.me
    if me is None:
        return ["guild.me introuvable (bot pas dans le cache de la guild ?)"]
    perms = channel.permissions_for(me)
    return [name for name in _REQUIRED_ALERT_PERMS if not getattr(perms, name, True)]


def _forwarded_snapshots(message: discord.Message) -> list[discord.MessageSnapshot]:
    """Snapshots d'un message transféré ("Forward" Discord), ou [] sinon.

    Un message transféré a son VRAI contenu dans message.message_snapshots
    (une liste, en pratique toujours 0 ou 1 élément), pas dans
    message.content qui est souvent vide (sauf commentaire ajouté par
    l'expéditeur en plus du forward) — Paul, 2026-09-28."""
    return list(getattr(message, "message_snapshots", None) or [])


def _analyzable_contents(message: discord.Message, snapshots: list[discord.MessageSnapshot]) -> list[str]:
    """Tous les textes à faire passer dans les détecteurs basés sur le
    contenu (banword, antifullcaps, nolink, antilink, antiflood, antispam
    emoji) : le texte du message lui-même PLUS celui de chaque snapshot
    transféré. Ne renvoie jamais une liste vide (au moins "")."""
    contents = [message.content] if message.content else []
    contents.extend(snap.content for snap in snapshots if snap.content)
    return contents or [""]


# ============================================================
# 🧩 Cog
# ============================================================

class ModAutomodListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # message_id -> horodatage (time.monotonic()) de la dernière action
        # appliquée pour ce message. Voir _DEDUP_WINDOW_SECONDS ci-dessus et
        # _already_handled_recently() plus bas.
        self._recent_actions: dict[int, float] = {}

    def _already_handled_recently(self, message_id: int) -> bool:
        """True si _apply_action a déjà traité ce message il y a moins de
        _DEDUP_WINDOW_SECONDS — dans ce cas l'appelant doit s'abstenir pour
        éviter de sanctionner deux fois la même infraction (cf. note sur
        _DEDUP_WINDOW_SECONDS : double évènement interne OU conflit avec un
        autre bot/système de modération qui aurait, lui, déjà fait réagir
        notre propre pipeline une première fois sur ce message)."""
        now = time.monotonic()

        # Purge opportuniste des entrées expirées pour ne pas laisser le
        # dict grossir indéfiniment (le bot tourne sur beaucoup de serveurs
        # avec un volume de messages conséquent).
        expired = [
            mid for mid, ts in self._recent_actions.items()
            if now - ts > _DEDUP_WINDOW_SECONDS
        ]
        for mid in expired:
            self._recent_actions.pop(mid, None)

        if message_id in self._recent_actions:
            return True

        self._recent_actions[message_id] = now
        return False

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

        await self._analyze_and_act(message)

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent) -> None:
        """Re-passe un message ÉDITÉ dans l'analyse automod.

        2026-10-06 (Paul) : AVANT, le filtre "auteur = bot/admin → on ignore"
        n'arrivait qu'APRÈS un fetch_message() complet — donc CHAQUE édition
        de contenu dans TOUS les salons déclenchait un appel Discord, même
        pour un message de bot (le nôtre qui rafraîchit un panel, ou un
        autre bot du serveur) ou d'un admin, qu'on jetait juste après coup.
        Sur un salon où ça arrive souvent (bot qui édite ses propres
        messages, salon très actif où les membres corrigent des fautes...),
        ça part en rafale de GET /messages non cadencée → 429 (c'est
        exactement ce qu'on a vu dans les logs du 06/10 sur plusieurs
        salons, avec des dizaines de messages différents fetchés en
        quelques secondes).

        Le correctif filtre maintenant sur l'auteur SANS appel réseau :
        pour une vraie édition de contenu (pas une mise à jour embed-only,
        déjà exclue par le "content in payload.data" ci-dessous), Discord
        envoie l'auteur complet dans le payload brut du gateway — gratuit.
        On ne fetch (et seulement via le cache interne discord.py en
        premier, lui aussi gratuit) que pour les messages qui ont encore
        une chance d'être analysés par l'automod après ce filtre.
        """

        if payload.guild_id is None:
            return

        if "content" not in payload.data:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return
        channel = guild.get_channel_or_thread(payload.channel_id)
        if channel is None:
            return

        # 🔎 Filtre auteur gratuit (payload brut du gateway) — évite le
        # fetch_message() pour tout message de bot/admin, sans requête.
        raw_author = payload.data.get("author") or {}
        try:
            raw_author_id = int(raw_author["id"]) if "id" in raw_author else None
        except (TypeError, ValueError):
            raw_author_id = None

        if raw_author_id is not None:
            if raw_author.get("bot"):
                return
            member = guild.get_member(raw_author_id)
            if member is not None and member.guild_permissions.administrator:
                return

        # 🗄️ Cache interne discord.py (gratuit) avant fetch_message().
        message = payload.cached_message
        if message is None:
            async with _EDIT_FETCH_SEMAPHORE:
                try:
                    message = await channel.fetch_message(payload.message_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                    log.debug(
                        "[AUTOMOD] Message édité introuvable/inaccessible channel=%s message=%s erreur=%s",
                        payload.channel_id, payload.message_id, exc,
                    )
                    return

        if message.author.bot:
            return
        if not isinstance(message.author, discord.Member):
            return
        if message.author.guild_permissions.administrator:
            return

        await self._analyze_and_act(message)

    async def _analyze_and_act(self, message: discord.Message) -> None:
        """Factorise le pipeline analyse -> action, partagé par on_message
        (nouveaux messages) et on_raw_message_edit (messages édités)."""
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
            log.exception("[AUTOMOD] Erreur application action guild=%s system=%s", message.guild.id, system_key)

    # ────────────────────────────────────────────────────────
    # 🔎 Analyse
    # ────────────────────────────────────────────────────────

    async def _analyze_message(self, message: discord.Message) -> tuple[str, str | None] | None:
        guild_id = message.guild.id
        content = message.content or ""

        # 📨 Message transféré ("Forward") : message.content est en général
        # VIDE (le vrai texte est dans message.message_snapshots), donc tous
        # les détecteurs basés sur le texte doivent aussi scanner le(s)
        # snapshot(s), pas seulement message.content (Paul, 2026-09-28).
        snapshots = _forwarded_snapshots(message)
        contents = _analyzable_contents(message, snapshots)
        attachment_filenames = [a.filename for a in message.attachments]
        attachment_filenames.extend(
            a.filename for snap in snapshots for a in snap.attachments
        )

        # ── Ban word ──
        bw_cfg = await banword_mgr.load_config(guild_id)
        if bw_cfg.get("enabled"):
            words = await banword_mgr.list_words(guild_id)
            if words:
                for text in contents:
                    match = banword_detector.detect(text, words)
                    if match is not None:
                        return ("banword", match)

        # ── Anti Full Maj ──
        fc_cfg = await antifullcaps_mgr.load_config(guild_id)
        if fc_cfg.get("enabled"):
            for text in contents:
                match = antifullcaps_detector.detect(
                    text,
                    min_length=fc_cfg.get("min_length", 10),
                    ratio_threshold=fc_cfg.get("ratio_threshold", 0.7),
                )
                if match is not None:
                    return ("antifullcaps", match)

        # ── Anti Spam Mention ──
        m_cfg = await antispam_mention_mgr.load_config(guild_id)
        if m_cfg.get("enabled"):
            max_mentions = m_cfg.get("max_mentions", 5)
            match = antispam_mention_detector.detect(
                message, max_mentions=max_mentions,
            )
            if match is None:
                # Un snapshot transféré n'a pas de .mentions résolus (pas de
                # Member) — on retombe sur un comptage brut (raw_mentions /
                # raw_role_mentions + @everyone/@here textuel) pour ne pas
                # laisser passer un forward qui abuse des mentions.
                for snap in snapshots:
                    count = (
                        len(snap.raw_mentions)
                        + len(snap.raw_role_mentions)
                        + (1 if ("@everyone" in snap.content or "@here" in snap.content) else 0)
                    )
                    if count > max_mentions:
                        match = f"{count} mentions"
                        break
            if match is not None:
                return ("antispam_mention", match)

        # ── Anti Spam Emoji ──
        e_cfg = await antispam_emoji_mgr.load_config(guild_id)
        if e_cfg.get("enabled"):
            for text in contents:
                match = antispam_emoji_detector.detect(
                    text, max_emoji=e_cfg.get("max_emoji", 10),
                )
                if match is not None:
                    return ("antispam_emoji", match)

        # ── No Link ──
        nl_cfg = await nolink_mgr.load_config(guild_id)
        if nl_cfg.get("enabled"):

            channel_id = message.channel.id

            if isinstance(message.channel, discord.Thread):
                channel_id = message.channel.parent_id

            if not await nolink_mgr.is_whitelisted(guild_id, channel_id):
                for text in contents:
                    match = nolink_detector.detect(
                        text, bypass_gif=nl_cfg.get("bypass_gif", False),
                    )
                    if match is not None:
                        return ("nolink", match)

        # ── Anti Link ──
        al_cfg = await antilink_mgr.load_config(guild_id)
        if al_cfg.get("enabled"):
            extensions = await antilink_mgr.list_extensions(guild_id)
            if extensions:
                for text in contents:
                    match = antilink_detector.detect(text, attachment_filenames, extensions)
                    if match is not None:
                        return ("antilink", match)

        # ── Anti Spam Message ──
        # Volontairement limité à message.content (pas aux snapshots) : ce
        # détecteur traque la répétition d'un texte TAPÉ par le membre, pas
        # le contenu d'un message transféré — élargir son périmètre créerait
        # des faux positifs si plusieurs forwards différents partagent un
        # même passage cité (Paul, 2026-09-28, décision de scope).
        sm_cfg = await antispam_msg_mgr.load_config(guild_id)
        if sm_cfg.get("enabled"):
            occurrences = antispam_msg_buffer.register_and_count(
                guild_id, message.author.id, content,
                window_seconds=sm_cfg.get("window_seconds", 10),
            )
            match = antispam_msg_detector.detect(
                occurrences, max_messages=sm_cfg.get("max_messages", 3),
            )
            if match is not None:
                return ("antispam_msg", match)

        # ── Anti Flood ──
        af_cfg = await antiflood_mgr.load_config(guild_id)
        if af_cfg.get("enabled"):
            for text in contents:
                match = antiflood_detector.detect(
                    text,
                    min_length=af_cfg.get("min_length", 20),
                    min_vowel_ratio=af_cfg.get("min_vowel_ratio", 0.2),
                )
                if match is not None:
                    return ("antiflood", match)

        return None

    # ────────────────────────────────────────────────────────
    # ⚡ Application (delete + tracking + notif + éventuel mute)
    # ────────────────────────────────────────────────────────

    async def _apply_action(self, message: discord.Message, system_key: str, matched_term: str | None) -> None:
        guild = message.guild
        author = message.author
        guild_id = guild.id
        user_id = author.id
        meta = _SYSTEM_META.get(system_key, {})
        display = meta.get("display_name", system_key)
        emoji = meta.get("emoji", "⚠️")

        if self._already_handled_recently(message.id):
            log.info(
                "[AUTOMOD] Message %s déjà traité très récemment (guild=%s, system=%s) — "
                "action ignorée pour éviter un double traitement.",
                message.id, guild_id, system_key,
            )
            return

        log.info("[AUTOMOD] Infraction détectée | guild=%s user=%s system=%s terme=%r", guild_id, user_id, system_key, matched_term)

        try:
            await message.delete()

        except discord.NotFound:
            log.info(
                "[AUTOMOD] Message déjà supprimé avant nous (probablement un autre bot/l'AutoMod natif "
                "Discord/un modérateur) | guild=%s channel=%s message=%s",
                guild_id, message.channel.id, message.id,
            )

        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("[AUTOMOD] Suppression de l'infraction échouée | guild=%s channel=%s message=%s erreur=%s", guild_id, message.channel.id, message.id, exc)


        general = await general_mgr.load_general(guild_id)
        window = general.get("notification_window_seconds", 60)
        recent = recidive_tracker.count_recent(
            guild_id, user_id, system_key, window_seconds=window,
        )
        is_recidive = recent >= 1

        snapshots = _forwarded_snapshots(message)
        record_content = message.content or "\n".join(
            snap.content for snap in snapshots if snap.content
        ) or None

        try:
            await infr_mgr.register_infraction(
                guild_id=guild_id, user_id=user_id,
                channel_id=message.channel.id,
                system_key=system_key,
                matched_term=matched_term,
                message_content=record_content,
            )

        except Exception:
            log.exception("[AUTOMOD] Enregistrement de l'infraction en DB échoué guild=%s", guild_id)
        recidive_tracker.record_infraction(guild_id, user_id, system_key)

        if general.get("notify_in_channel"):
            await self._send_channel_notice(
                message.channel, author, system_display=display,
                emoji=emoji, is_recidive=is_recidive,
                user_msg=meta.get("user_msg", ""),
            )

        await self._send_user_dm(author, guild, system_display=display, emoji=emoji, is_recidive=is_recidive, user_msg=meta.get("user_msg", ""))

        alert_channel_id = general.get("alert_channel_id")
        alert_channel = guild.get_channel(alert_channel_id) if alert_channel_id else None

        if alert_channel_id and alert_channel is None:
            log.warning("[AUTOMOD] alert_channel_id=%s configuré mais introuvable | guild=%s", alert_channel_id, guild_id)

        if is_recidive:
            muted = await self._apply_timeout(author, system_key)
            if alert_channel is not None:
                await self._send_full_alert(
                    alert_channel, guild=guild, user=author, message=message,
                    system_key=system_key, system_display=display,
                    matched_term=matched_term,
                    staff_role_id=general.get("staff_role_id"),
                )
            else:
                log.warning("[AUTOMOD] Récidive détectée mais aucun alert_channel configuré guild=%s user=%s system=%s", guild_id, user_id, system_key)
            recidive_tracker.reset_key(guild_id, user_id, system_key)

        else:
            if alert_channel is not None:
                await self._send_light_alert(
                    alert_channel, user=author, message=message,
                    system_display=display, matched_term=matched_term,
                )

    # ────────────────────────────────────────────────────────
    # 📢 Notifications
    # ────────────────────────────────────────────────────────

    async def _send_channel_notice(self, channel, author: discord.Member, *, system_display: str, emoji: str, is_recidive: bool, user_msg: str) -> None:
        """Container V2 posté dans le salon d'origine, auto-delete 8s."""

        view = LayoutView(timeout=None)
        c = Container()
        body = f"{author.mention}\n{user_msg}"

        if is_recidive:
            body += "\n\n🔒 **Récidive détectée** — un mute Discord a été appliqué."
        c.add_item(TextDisplay(body))

        c.add_item(Separator())
        c.add_item(TextDisplay("GuideOn Studio"))
        view.add_item(c)
        try:
            await channel.send(
                view=view,
                delete_after=8,
                allowed_mentions=discord.AllowedMentions(users=True),
            )

        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "[AUTOMOD] Notif salon refusée channel=%s erreur=%s",
                channel.id, exc,
            )

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
        c.add_item(TextDisplay("GuideOn Studio"))
        view.add_item(c)
        try:
            await user.send(view=view)
        except (discord.Forbidden, discord.HTTPException):
            # DM fermés ou bot bloqué : silencieux, c'est normal, pas un bug.
            pass

    async def _send_light_alert(
        self, alert_channel, *, user: discord.Member, message: discord.Message,
        system_display: str, matched_term: str | None,
    ) -> None:
        """Log staff léger sur 1re infraction (pas de bouton)."""
        view = LayoutView(timeout=None)
        c = Container()
        c.add_item(TextDisplay(f"# <:sanctionner:1495444382587949086> Alerte automod · {system_display}\n"))
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
            "-# 1re infraction. Aucune sanction automatique."
        ))
        view.add_item(c)
        try:
            await alert_channel.send(view=view)
        except (discord.Forbidden, discord.HTTPException) as exc:
            missing = _missing_send_permissions(alert_channel, message.guild)
            log.warning(
                "[AUTOMOD] Log léger refusé alert_channel=%s erreur=%s permissions_manquantes=%s",
                alert_channel.id, exc, missing or "aucune détectée",
            )

    async def _send_full_alert(
        self, alert_channel, *, guild: discord.Guild, user: discord.Member,
        message: discord.Message, system_key: str, system_display: str,
        matched_term: str | None, staff_role_id: int | None,
    ) -> None:
        """Alerte STAFF complète avec bouton 'Je m'en occupe' (persistante)."""
        excerpt = (message.content or "")[:500]

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
        except (discord.Forbidden, discord.HTTPException) as exc:
            missing = _missing_send_permissions(alert_channel, guild)
            log.warning(
                "[AUTOMOD] Envoi alerte staff refusé alert_channel=%s erreur=%s permissions_manquantes=%s",
                alert_channel.id, exc, missing or "aucune détectée (vérifier Embed Links / rôle @everyone)",
            )
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
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "[AUTOMOD] Edit final alerte échoué message=%s erreur=%s",
                sent_msg.id, exc,
            )

    async def _apply_timeout(self, user: discord.Member, system_key: str) -> bool:
        """Applique le timeout Discord natif (28j). Retourne True si appliqué."""
        try:
            await user.timeout(
                _MUTE_DURATION,
                reason=f"Auto-modération : récidive système {system_key}",
            )
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "[AUTOMOD] Timeout refusé guild=%s user=%s erreur=%s",
                user.guild.id, user.id, exc,
            )
            return False


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModAutomodListener(bot))