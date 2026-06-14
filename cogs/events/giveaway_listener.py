"""
cogs/events/giveaway_listener.py — Gestion du système de giveaway.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container

from views.giveaway.panel_view import build_giveaway_panel
from utils.managers.giveaway_manager import (
    add_participant,
    count_participants,
    end_giveaway,
    get_all_expired_giveaways,
    get_giveaway,
    get_giveaway_by_message,
    get_participants,
    is_blacklisted,
    remove_participant,
)


log = logging.getLogger(__name__)

GIVEAWAY_EMOJI = "🎉"
CHECK_INTERVAL_SECONDS = 30


# ======================================================
# =================== HELPERS ==========================
# ======================================================

def _ensure_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalise un datetime à tz-aware UTC (compat SQLite)."""
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


async def _send_dm(member: discord.Member, view) -> None:
    """Envoie un DM en silence (Forbidden = DMs fermés)."""
    try:
        await member.send(view=view)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def _remove_reaction_safely(
    channel: discord.abc.Messageable, message_id: int, emoji: str, user: discord.abc.Snowflake
) -> None:
    """Retire la réaction d'un user en silence."""
    try:
        msg = await channel.fetch_message(message_id)
        await msg.remove_reaction(emoji, user)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


async def _refresh_panel(gid: str, guild: discord.Guild) -> None:
    """Recharge le giveaway depuis la DB et met à jour le message public."""
    data = await get_giveaway(gid)
    if data is None or data.get("message_id") is None:
        return
    channel = guild.get_channel(data["channel_id"])
    if channel is None:
        return
    try:
        msg = await channel.fetch_message(data["message_id"])
        nb = await count_participants(gid)
        data["participants_count"] = nb
        await msg.edit(view=build_giveaway_panel(data, guild))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass


async def _check_conditions(
    member: discord.Member, giveaway: dict, guild: discord.Guild
) -> Optional[str]:
    """
    Vérifie les 4 conditions de participation. Renvoie None si toutes sont OK,
    sinon une chaîne expliquant pourquoi le refus.
    """
    req = giveaway.get("requirements") or {}

    # 1. Rôle requis
    role_id = req.get("role_id")
    if role_id:
        role = guild.get_role(role_id)
        if role is None:
            return f"Le rôle requis (`ID {role_id}`) est introuvable sur le serveur."
        if role not in member.roles:
            return f"Tu dois avoir le rôle {role.mention} pour participer."

    # 2. Rôle interdit
    forbidden_id = req.get("forbidden_role_id")
    if forbidden_id:
        forbidden = guild.get_role(forbidden_id)
        if forbidden is not None and forbidden in member.roles:
            return f"Tu ne peux pas participer en ayant le rôle {forbidden.mention}."

    # 3. Min invitations
    min_invites = req.get("min_invites")
    if min_invites:
        try:
            from utils.managers.invite_manager import get_user_stats
            stats = await get_user_stats(guild.id, member.id)
            total = stats.get("total", 0)
        except Exception:
            log.exception("[Giveaway] Erreur lookup invitations")
            total = 0
        if total < min_invites:
            return (
                f"Il te faut au moins **{min_invites}** invitation(s) — "
                f"tu en as **{total}**."
            )

    # 4. Ancienneté serveur
    min_age = req.get("min_server_age_days")
    if min_age:
        joined = member.joined_at
        if joined is None:
            return "Impossible de vérifier ton ancienneté sur ce serveur."
        joined = _ensure_aware(joined)
        days_on_server = (datetime.now(timezone.utc) - joined).days
        if days_on_server < min_age:
            return (
                f"Tu dois être sur ce serveur depuis au moins **{min_age}** jour(s) — "
                f"tu y es depuis **{days_on_server}**."
            )

    return None


def _build_winner_dm(guild: discord.Guild, giveaway: dict) -> LayoutView:
    """Container V2 envoyé en DM à un gagnant."""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 🏆 Tu as gagné !"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"Félicitations ! Tu as remporté :\n"
        f"**{giveaway['prize']}**"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"-# 🏠 Serveur : {guild.name}\n"
        f"-# 🆔 ID : `{giveaway['id']}`\n"
        f"-# 🎤 Organisateur : <@{giveaway['host_id']}>"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# Contacte l'organisateur pour récupérer ton lot."))
    view.add_item(c)
    return view


def _build_participation_dm(guild: discord.Guild, giveaway: dict, joined: bool) -> LayoutView:
    """Container V2 — DM de confirmation (joined=True) ou de retrait (joined=False)."""
    view = LayoutView(timeout=None)
    c = Container()
    if joined:
        c.add_item(TextDisplay("# 🎉 Participation confirmée !"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Tu participes maintenant au giveaway :\n**{giveaway['prize']}**"
        ))
    else:
        c.add_item(TextDisplay("# ↩️ Participation retirée"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Tu ne participes plus à :\n**{giveaway['prize']}**\n\n"
            f"-# Réagis à nouveau avec 🎉 pour re-participer."
        ))
    end_time = _ensure_aware(giveaway["end_time"])
    c.add_item(TextDisplay(
        f"-# 🏠 Serveur : {guild.name}\n"
        f"-# 🆔 ID : `{giveaway['id']}`\n"
        f"-# 📅 Fin : <t:{int(end_time.timestamp())}:R>"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio · Bonne chance ! 🍀" if joined
                           else "-# GuideOn Studio"))
    view.add_item(c)
    return view


def _build_end_announcement(giveaway: dict, winners: list[int]) -> LayoutView:
    """Container V2 — annonce publique de fin avec mentions."""
    view = LayoutView(timeout=None)
    c = Container()
    if winners:
        mentions = " ".join(f"<@{w}>" for w in winners)
        c.add_item(TextDisplay(f"# 🎊 Giveaway terminé !"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Félicitations à {mentions} qui remporte(nt) :\n"
            f"**{giveaway['prize']}**"
        ))
    else:
        c.add_item(TextDisplay(f"# 😔 Giveaway terminé"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Aucun participant — pas de gagnant pour **{giveaway['prize']}**."
        ))
    c.add_item(Separator())
    c.add_item(TextDisplay(f"-# ID `{giveaway['id']}` · GuideOn Studio"))
    view.add_item(c)
    return view


# ======================================================
# =============== COG : GiveawayListener ===============
# ======================================================

class GiveawayListener(commands.Cog):
    """Cog responsable des giveaways : clôture auto + réactions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Anti double-end pour les clôtures concurrentes
        self._ending: set[str] = set()
        self.check_giveaways.start()
        log.info("[Giveaway] Listener démarré (intervalle clôture: %ds)", CHECK_INTERVAL_SECONDS)

    async def cog_unload(self) -> None:
        self.check_giveaways.cancel()

    # ------------------------------------------------------------------
    # ⏰ Tâche de clôture
    # ------------------------------------------------------------------

    @tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
    async def check_giveaways(self) -> None:
        try:
            expired = await get_all_expired_giveaways()
        except Exception:
            log.exception("[Giveaway] check_giveaways : échec lecture")
            return

        for g in expired:
            gid = g["id"]
            if gid in self._ending:
                continue
            self._ending.add(gid)
            try:
                await self._close_giveaway(g)
            except Exception:
                log.exception("[Giveaway] Erreur clôture %s", gid)
            finally:
                self._ending.discard(gid)

    @check_giveaways.before_loop
    async def _before_check(self) -> None:
        await self.bot.wait_until_ready()

    async def _close_giveaway(self, giveaway: dict) -> None:
        """Clôture un giveaway expiré : tirage, refresh, annonce, DMs."""
        gid = giveaway["id"]
        guild_id = giveaway["guild_id"]

        # Re-fetch frais (l'état peut avoir changé entre lecture et traitement)
        fresh = await get_giveaway(gid)
        if fresh is None or fresh["ended"]:
            return

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            log.warning("[Giveaway] Guild %s introuvable — skip clôture %s", guild_id, gid)
            return

        # Tirage des gagnants
        participants = await get_participants(gid)
        winners_count = fresh["winners_count"]
        if not participants:
            winners = []
        elif len(participants) <= winners_count:
            winners = list(participants)
        else:
            winners = random.sample(participants, winners_count)

        # Marquer comme terminé
        await end_giveaway(gid, winners)
        log.info(
            "[Giveaway] Clôture %s (guild=%s) : %d participants → %d gagnant(s)",
            gid, guild_id, len(participants), len(winners),
        )

        # Refresh du panel public
        await _refresh_panel(gid, guild)

        # Annonce publique
        channel = guild.get_channel(fresh["channel_id"])
        if channel is not None:
            try:
                mentions_text = (
                    discord.AllowedMentions(users=True) if winners
                    else discord.AllowedMentions.none()
                )
                final = await get_giveaway(gid) or fresh
                await channel.send(
                    view=_build_end_announcement(final, winners),
                    allowed_mentions=mentions_text,
                )
            except (discord.Forbidden, discord.HTTPException):
                log.warning("[Giveaway] Échec annonce publique %s", gid)

        # DMs aux gagnants
        if winners and channel is not None:
            for wid in winners:
                member = guild.get_member(wid)
                if member is None or member.bot:
                    continue
                await _send_dm(member, _build_winner_dm(guild, fresh))

    # ------------------------------------------------------------------
    # 🎉 Réaction ajoutée → tentative de participation
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        # Filtres rapides
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != GIVEAWAY_EMOJI:
            return
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None or member.bot:
            return

        # Lookup giveaway via index (guild_id, message_id)
        giveaway = await get_giveaway_by_message(guild.id, payload.message_id)
        if giveaway is None:
            return

        # Giveaway encore actif ?
        end_time = _ensure_aware(giveaway["end_time"])
        if giveaway["ended"] or datetime.now(timezone.utc) >= end_time:
            # On retire la réaction pour signaler que ce n'est plus possible
            channel = guild.get_channel(payload.channel_id)
            if channel is not None:
                await _remove_reaction_safely(channel, payload.message_id, payload.emoji, member)
            return

        # Blacklist
        try:
            if await is_blacklisted(guild.id, member.id):
                channel = guild.get_channel(payload.channel_id)
                if channel is not None:
                    await _remove_reaction_safely(
                        channel, payload.message_id, payload.emoji, member
                    )
                await _send_dm(
                    member,
                    error_container(
                        f"Tu es **blacklist** du système de giveaway sur **{guild.name}**.\n"
                        f"-# Contacte un administrateur si tu penses que c'est une erreur."
                    ),
                )
                return
        except Exception:
            log.exception("[Giveaway] Erreur check blacklist")
            return

        # Conditions de participation
        try:
            reason = await _check_conditions(member, giveaway, guild)
        except Exception:
            log.exception("[Giveaway] Erreur _check_conditions")
            return

        if reason is not None:
            channel = guild.get_channel(payload.channel_id)
            if channel is not None:
                await _remove_reaction_safely(channel, payload.message_id, payload.emoji, member)
            await _send_dm(
                member,
                error_container(
                    f"Tu **ne peux pas** participer au giveaway **{giveaway['prize']}** :\n"
                    f"-# {reason}"
                ),
            )
            return

        # ✅ Ajout du participant
        try:
            added = await add_participant(giveaway["id"], member.id)
        except Exception:
            log.exception("[Giveaway] Erreur add_participant")
            return

        if added:
            await _refresh_panel(giveaway["id"], guild)
            # Re-fetch giveaway frais avant DM (compteur à jour)
            fresh = await get_giveaway(giveaway["id"])
            if fresh is not None:
                await _send_dm(member, _build_participation_dm(guild, fresh, joined=True))
            log.info(
                "[Giveaway] Participation %s ← user %s (guild=%s)",
                giveaway["id"], member.id, guild.id,
            )

    # ------------------------------------------------------------------
    # ❌ Réaction retirée → retrait de participation
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.bot.user.id:
            return
        if str(payload.emoji) != GIVEAWAY_EMOJI:
            return
        if not payload.guild_id:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        giveaway = await get_giveaway_by_message(guild.id, payload.message_id)
        if giveaway is None or giveaway["ended"]:
            return

        try:
            removed = await remove_participant(giveaway["id"], payload.user_id)
        except Exception:
            log.exception("[Giveaway] Erreur remove_participant")
            return

        if removed:
            await _refresh_panel(giveaway["id"], guild)
            member = guild.get_member(payload.user_id)
            if member is not None and not member.bot:
                fresh = await get_giveaway(giveaway["id"])
                if fresh is not None:
                    await _send_dm(member, _build_participation_dm(guild, fresh, joined=False))
            log.info(
                "[Giveaway] Retrait %s ← user %s (guild=%s)",
                giveaway["id"], payload.user_id, guild.id,
            )


# ----------------------------------------------------
# 🔧 Setup
# ----------------------------------------------------

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GiveawayListener(bot))