"""
cogs/events/notations_alpha.py — Listener du système de notations Alpha.

Boucle toutes les 40 s. Pour chaque guild configuré et activé :
  1. send_presence_* → envoie le message de présence staff + DM rappels
  2. deadline_*      → (vérifié côté interaction, pas dans la boucle)
  3. send_public_*   → génère les assignments, envoie le message public, reset la semaine

Gestion du bouton "Je suis présent" (custom_id="notation_presence_toggle")
via un listener on_interaction dans le Cog.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

import discord
from discord.ext import commands, tasks
from zoneinfo import ZoneInfo

from utils.managers.alpha_nota_manager import (
    generate_notation_ranges,
    get_all_nota_operators,
    get_available_operators,
    get_operator_history,
    is_past_deadline,
    is_time_now,
    list_all_nota_configs,
    load_nota_config,
    load_nota_state,
    reset_nota_week,
    set_state_fields,
    toggle_availability,
)
from views.alpha.nota_view import build_presence_view, build_public_nota_view

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")


class NotationsAlphaListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._deadline_greyed: dict[int, bool] = {}  # mémoire : déjà grisé cette semaine ?
        self._nota_task.start()

    def cog_unload(self) -> None:
        self._nota_task.cancel()

    # ════════════════════════════════════════════════════════
    # 🔁 Boucle principale
    # ════════════════════════════════════════════════════════

    @tasks.loop(seconds=40)
    async def _nota_task(self) -> None:
        try:
            configs = await list_all_nota_configs()
        except Exception:
            log.exception("[NOTATIONS] Erreur chargement configs")
            return

        for cfg in configs:
            if not cfg.get("enabled"):
                continue
            try:
                await self._process_guild(cfg)
            except Exception:
                log.exception("[NOTATIONS] Erreur guild=%d", cfg["guild_id"])

    @_nota_task.before_loop
    async def _before_nota(self) -> None:
        await self.bot.wait_until_ready()

    @_nota_task.error
    async def _nota_error(self, error: Exception) -> None:
        log.exception("[NOTATIONS] Erreur non gérée dans la boucle : %s", error)

    async def _process_guild(self, cfg: dict) -> None:
        gid = cfg["guild_id"]
        state = await load_nota_state(gid)

        # 1. Envoi message de présence
        if (
            is_time_now(cfg["send_presence_weekday"], cfg["send_presence_hour"], cfg["send_presence_minute"])
            and state["availability_message_id"] is None
            and cfg.get("channel_staff_id")
        ):
            await self._send_presence(cfg, state)
            state = await load_nota_state(gid)  # recharger après écriture

        # 2. Rappels DM (même déclencheur que présence, flag reminder_sent)
        if (
            is_time_now(cfg["send_presence_weekday"], cfg["send_presence_hour"], cfg["send_presence_minute"])
            and not state["reminder_sent"]
        ):
            await self._send_reminders(cfg)

        # 2b. Griser le bouton à la deadline (une seule fois, en mémoire)
        if (
            is_past_deadline(cfg["deadline_weekday"], cfg["deadline_hour"], cfg["deadline_minute"])
            and state.get("availability_message_id") is not None
            and state.get("public_message_id") is None
            and not self._deadline_greyed.get(gid, False)
            and cfg.get("channel_staff_id")
        ):
            self._deadline_greyed[gid] = True
            await self._update_presence_message(cfg, state, deadline_passed=True)

        # 3. Envoi public + reset
        if (
            is_time_now(cfg["send_public_weekday"], cfg["send_public_hour"], cfg["send_public_minute"])
            and state["public_message_id"] is None
            and cfg.get("channel_public_id")
        ):
            await self._send_public_and_reset(cfg, state)

    # ════════════════════════════════════════════════════════
    # 📨 Helpers d'envoi
    # ════════════════════════════════════════════════════════

    async def _get_channel(self, guild_id: int, channel_id: int | None) -> discord.TextChannel | None:
        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.HTTPException):
                log.warning("[NOTATIONS] Salon %d introuvable", channel_id)
                return None
        return channel

    async def _send_log(self, cfg: dict, msg: str) -> None:
        channel = await self._get_channel(cfg["guild_id"], cfg.get("channel_logs_id"))
        if channel:
            try:
                await channel.send(f"🛡️ **[LOG NOTATIONS]** {msg}")
            except discord.HTTPException:
                pass

    async def _send_presence(self, cfg: dict, state: dict) -> None:
        channel = await self._get_channel(cfg["guild_id"], cfg["channel_staff_id"])
        if channel is None:
            return

        operators = await get_all_nota_operators(cfg["guild_id"])
        available  = await get_available_operators(cfg["guild_id"])
        view = build_presence_view(operators, available, deadline_passed=False)

        try:
            msg = await channel.send(view=view)
        except discord.HTTPException:
            log.exception("[NOTATIONS] Erreur envoi présence | guild=%d", cfg["guild_id"])
            return

        await set_state_fields(
            cfg["guild_id"],
            availability_message_id=msg.id,
            public_message_id=None,   # reset du sentinel pour le nouveau cycle
        )
        self._deadline_greyed[cfg["guild_id"]] = False  # nouvelle semaine → reset
        log.info("[NOTATIONS] Message de présence envoyé | guild=%d", cfg["guild_id"])

    async def _send_reminders(self, cfg: dict) -> None:
        available_ids = set(await get_available_operators(cfg["guild_id"]))
        operators = await get_all_nota_operators(cfg["guild_id"])
        count = 0

        guild = self.bot.get_guild(cfg["guild_id"])
        if guild is None:
            return

        for op in operators:
            if op["discord_id"] in available_ids:
                continue
            member = guild.get_member(op["discord_id"])
            if member is None:
                try:
                    member = await guild.fetch_member(op["discord_id"])
                except (discord.NotFound, discord.HTTPException):
                    continue
            try:
                await member.send(
                    f"⚠️ **Rappel — Notations Alpha**\n"
                    f"Salut {op['pseudo_jeu']}, tu n'as pas encore confirmé ta **disponibilité** "
                    f"pour les notations de cette semaine.\nMerci de le faire dès que possible ! ✍️"
                )
                count += 1
            except (discord.Forbidden, discord.HTTPException):
                pass

        await set_state_fields(cfg["guild_id"], reminder_sent=True)
        await self._send_log(cfg, f"Rappels envoyés à {count} opérateur(s).")
        log.info("[NOTATIONS] Rappels envoyés (%d) | guild=%d", count, cfg["guild_id"])

    async def _send_public_and_reset(self, cfg: dict, state: dict) -> None:
        channel = await self._get_channel(cfg["guild_id"], cfg["channel_public_id"])
        if channel is None:
            return

        assignments = await generate_notation_ranges(cfg["guild_id"], cfg.get("countries_count", 238))

        if not assignments:
            await self._send_log(cfg, "⚠️ Aucun opérateur disponible — envoi annulé.")
            # Sentinel -1 : semaine tentée sans résultat → empêche les re-déclenchements
            await set_state_fields(cfg["guild_id"], public_message_id=-1)
            await reset_nota_week(cfg["guild_id"], [])
            return

        operators = await get_all_nota_operators(cfg["guild_id"])
        ops_by_id = {op["discord_id"]: op for op in operators}
        date_str = datetime.now(PARIS_TZ).strftime("%d/%m/%Y")

        view = build_public_nota_view(
            date_str, assignments, ops_by_id,
            cfg.get("url_country_lookup"),
        )

        try:
            msg = await channel.send(view=view)
        except discord.HTTPException:
            log.exception("[NOTATIONS] Erreur envoi public | guild=%d", cfg["guild_id"])
            await self._send_log(cfg, "❌ Erreur envoi message public.")
            return

        await set_state_fields(
            cfg["guild_id"],
            public_message_id=msg.id,
            assigned_ranges=json.dumps(assignments),
        )
        await self._send_log(cfg, f"✅ Notations publiées (semaine du {date_str}, {len(assignments)} opérateur(s)).")
        log.info("[NOTATIONS] Envoi public OK | guild=%d", cfg["guild_id"])

        await reset_nota_week(cfg["guild_id"], assignments)

    async def _update_presence_message(self, cfg: dict, state: dict, deadline_passed: bool = False) -> None:
        """Rafraîchit le message de présence. Grise le bouton si deadline_passed."""
        msg_id = state.get("availability_message_id")
        if not msg_id:
            return
        channel = await self._get_channel(cfg["guild_id"], cfg.get("channel_staff_id"))
        if channel is None:
            return
        try:
            msg = await channel.fetch_message(msg_id)
        except (discord.NotFound, discord.HTTPException):
            return

        operators = await get_all_nota_operators(cfg["guild_id"])
        available  = await get_available_operators(cfg["guild_id"])
        view = build_presence_view(operators, available, deadline_passed=deadline_passed)
        try:
            await msg.edit(view=view)
        except discord.HTTPException:
            log.warning("[NOTATIONS] Impossible de mettre à jour le message de présence | guild=%d", cfg["guild_id"])

    # ════════════════════════════════════════════════════════
    # 🔘 Bouton présence — on_interaction
    # ════════════════════════════════════════════════════════

    @commands.Cog.listener("on_interaction")
    async def on_presence_toggle(self, interaction: discord.Interaction) -> None:
        if interaction.type != discord.InteractionType.component:
            return
        if interaction.data.get("custom_id") != "notation_presence_toggle":
            return

        guild_id = interaction.guild_id
        if guild_id is None:
            return

        cfg = await load_nota_config(guild_id)

        # Vérifier que le système est activé
        if not cfg.get("enabled"):
            return await interaction.response.send_message(
                "❌ Le système de notations est désactivé.", ephemeral=True
            )

        # Vérifier que l'utilisateur est un opérateur (SM ou Admin)
        operators = await get_all_nota_operators(guild_id)
        op_ids = {op["discord_id"] for op in operators}

        if interaction.user.id not in op_ids:
            return await interaction.response.send_message(
                "❌ Vous n'êtes pas opérateur de notation.", ephemeral=True
            )

        # Vérifier la deadline
        if is_past_deadline(cfg["deadline_weekday"], cfg["deadline_hour"], cfg["deadline_minute"]):
            return await interaction.response.send_message(
                "⛔ La fenêtre de vote est terminée.", ephemeral=True
            )

        # Vérifier que le message de présence est actif
        state = await load_nota_state(guild_id)
        if state["availability_message_id"] is None:
            return await interaction.response.send_message(
                "❌ Aucune session de notation active.", ephemeral=True
            )

        # 🕒 Defer éphémère pour avoir le temps de faire les opérations DB + Discord
        try:
            await interaction.response.defer(ephemeral=True)
        except (discord.NotFound, discord.HTTPException):
            return

        # Toggle
        is_available, status = await toggle_availability(guild_id, interaction.user.id)

        # Mettre à jour le message de présence
        await self._update_presence_message(cfg, state)

        # Réponse éphémère
        await interaction.followup.send(
            f"✔️ Votre statut a été mis à jour : **{status}**.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NotationsAlphaListener(bot))