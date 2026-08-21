"""
cogs/events/join_to_create_listener.py — Système "Join to Create" (salons
vocaux à la volée), configuré via /config join_to_create.

Écoute on_voice_state_update :
  - Un membre rejoint le salon déclencheur configuré → crée un salon vocal
    personnel dans la catégorie destination et l'y déplace, SAUF si la
    catégorie a atteint la limite Discord de 50 salons (tous types
    confondus) : dans ce cas le membre est expulsé du salon déclencheur et
    prévenu en MP qu'il y a déjà trop de vocaux actifs.
  - Un salon devient vide (0 membre) → suppression automatique, UNIQUEMENT
    s'il est tracé en DB comme salon généré par ce système
    (utils.managers.join_to_create_manager) — jamais un salon posé
    manuellement par un admin dans la même catégorie (le salon déclencheur
    lui-même n'est jamais tracé, donc jamais supprimé par cette logique).
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.container_universel import warning_container
from utils.managers import join_to_create_manager as jtc_mgr

log = logging.getLogger(__name__)

# Limite Discord : 50 salons maximum par catégorie (tous types confondus).
_CATEGORY_CHANNEL_LIMIT = 50


# ============================================================
# 🧩 Cog
# ============================================================

class JoinToCreateListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        guild = member.guild
        if guild is None or member.bot:
            return

        try:
            cfg = await jtc_mgr.load_config(guild.id)
            trigger_id = cfg.get("trigger_channel_id")

            # 🎙️ Arrivée dans le salon déclencheur → création + déplacement.
            if trigger_id and after.channel is not None and after.channel.id == trigger_id:
                await self._handle_join_trigger(guild, member, cfg)

            # 🧹 Départ d'un salon devenu vide → suppression si généré par nous.
            if before.channel is not None and (after.channel is None or after.channel.id != before.channel.id):
                if len(before.channel.members) == 0:
                    await self._maybe_delete_empty(before.channel)
        except Exception:
            log.exception(
                "[JOIN_TO_CREATE] Erreur traitement voice_state_update guild=%s membre=%s",
                guild.id, member.id,
            )

    # ────────────────────────────────────────────────────────
    # 🎙️ Création à l'arrivée dans le salon déclencheur
    # ────────────────────────────────────────────────────────

    async def _handle_join_trigger(self, guild: discord.Guild, member: discord.Member, cfg: dict) -> None:
        category_id = cfg.get("category_id")
        category = guild.get_channel(category_id) if category_id else None
        if not isinstance(category, discord.CategoryChannel):
            log.warning(
                "[JOIN_TO_CREATE] Catégorie configurée introuvable guild=%s category_id=%s",
                guild.id, category_id,
            )
            return

        # 🚧 Limite Discord : 50 salons max par catégorie (tous types confondus).
        if len(category.channels) >= _CATEGORY_CHANNEL_LIMIT:
            await self._reject_full_category(guild, member)
            return

        channel_name = f"🔊 Salon de {member.display_name}"[:100]
        try:
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=category,
                reason=f"Join to Create — {member}",
            )
        except discord.Forbidden:
            log.warning("[JOIN_TO_CREATE] Permissions manquantes (Manage Channels) guild=%s", guild.id)
            return
        except discord.HTTPException as exc:
            log.warning("[JOIN_TO_CREATE] Création salon échouée guild=%s erreur=%s", guild.id, exc)
            return

        try:
            await jtc_mgr.register_channel(guild.id, new_channel.id, member.id)
        except Exception:
            log.exception(
                "[JOIN_TO_CREATE] Enregistrement DB échoué guild=%s channel=%s", guild.id, new_channel.id,
            )

        try:
            await member.move_to(new_channel, reason="Join to Create")
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "[JOIN_TO_CREATE] Déplacement membre échoué guild=%s membre=%s erreur=%s",
                guild.id, member.id, exc,
            )
            # Personne dans le salon flambant neuf : on ne laisse pas un
            # salon vide orphelin (jamais réutilisé, jamais nettoyé sinon).
            try:
                await new_channel.delete(reason="Join to Create — déplacement échoué")
            except (discord.Forbidden, discord.HTTPException):
                pass
            try:
                await jtc_mgr.unregister_channel(new_channel.id)
            except Exception:
                pass

    async def _reject_full_category(self, guild: discord.Guild, member: discord.Member) -> None:
        try:
            await member.move_to(None, reason="Join to Create — catégorie pleine")
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "[JOIN_TO_CREATE] Expulsion échouée (catégorie pleine) guild=%s membre=%s erreur=%s",
                guild.id, member.id, exc,
            )

        try:
            await member.send(view=warning_container(
                f"Il y a déjà **trop de vocaux actifs** sur **{guild.name}** "
                "pour t'en créer un nouveau. Réessaie un peu plus tard."
            ))
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ────────────────────────────────────────────────────────
    # 🧹 Suppression à la vacance
    # ────────────────────────────────────────────────────────

    async def _maybe_delete_empty(self, channel: discord.VoiceChannel) -> None:
        if not await jtc_mgr.is_generated_channel(channel.id):
            return

        try:
            await channel.delete(reason="Join to Create — salon vide")
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning(
                "[JOIN_TO_CREATE] Suppression salon vide échouée channel=%s erreur=%s",
                channel.id, exc,
            )

        try:
            await jtc_mgr.unregister_channel(channel.id)
        except Exception:
            log.exception("[JOIN_TO_CREATE] Désenregistrement DB échoué channel=%s", channel.id)


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JoinToCreateListener(bot))