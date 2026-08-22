"""
cogs/events/ngstaff_notations.py — Listener du système de notations NGSTAFF.
"""

from __future__ import annotations

import discord
from discord.ext import commands, tasks

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from utils.managers.ng_nota_manager import (
    generate_notation_ranges,
    get_all_nota_operators,
    get_available_operators,
    is_past_deadline,
    is_time_now,
    list_all_nota_configs,
    load_nota_state,
    reset_nota_week,
    set_state_fields,
    toggle_availability,
)

from utils.managers.ng_nota_manager import load_nota_config as ng_load_nota_config
from utils.managers.ng_server_manager import get_server_by_guild, get_server_by_name
from views.ngstaff.nota_view import build_presence_view, build_public_nota_view

log = logging.getLogger(__name__)

PARIS_TZ = ZoneInfo("Europe/Paris")


# ============================================================
# 🧩 Class principale
# ============================================================

class NGSTAFF_NotationsListener(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._deadline_greyed: dict[str, bool] = {}
        self._nota_task.start()

    def cog_unload(self) -> None:
        self._nota_task.cancel()

    # ============================================================
    # 🔁 Boucle principale
    # ============================================================

    @tasks.loop(seconds=40)
    async def _nota_task(self) -> None:
        try:
            configs = await list_all_nota_configs()

        except Exception:
            log.exception("[NGSTAFF NOTATIONS] Erreur chargement des configs")
            return

        for cfg in configs:
            if not cfg.get("enabled"):
                continue

            server_name = cfg["server"]
            ng_server = get_server_by_name(server_name)
            if ng_server is None:
                log.warning("[NGSTAFF NOTATIONS] Serveur NG %r introuvable dans le cache", server_name)
                continue

            if not ng_server.active:
                continue

            try:
                await self._process_guild(cfg)
            except Exception:
                log.exception("[NGSTAFF NOTATIONS] Erreur server=%s", server_name)

    @_nota_task.before_loop
    async def _before_nota(self) -> None:
        await self.bot.wait_until_ready()

    @_nota_task.error
    async def _nota_error(self, error: Exception) -> None:
        log.exception("[NGSTAFF NOTATIONS] Erreur non gérée : %s", error)

    async def _process_guild(self, cfg: dict) -> None:
        server = cfg["server"]
        state = await load_nota_state(server)

        # ✉️ 1. Envoi message de présence
        if (
            is_time_now(cfg["send_presence_weekday"], cfg["send_presence_hour"], cfg["send_presence_minute"])
            and state["availability_message_id"] is None
            and cfg.get("channel_staff_id")
        ):
            await self._send_presence(cfg, state)
            state = await load_nota_state(server)

        # ⏳ 2. Gère la fin du temps de vote
        if (
            is_past_deadline(cfg["deadline_weekday"], cfg["deadline_hour"], cfg["deadline_minute"])
            and state.get("availability_message_id") is not None
            and state.get("public_message_id") is None
            and not self._deadline_greyed.get(server, False)
            and cfg.get("channel_staff_id")
        ):
            self._deadline_greyed[server] = True
            await self._update_presence_message(cfg, state, deadline_passed=True)

        # 📅 3. Envoi public + reset
        if (
            is_time_now(cfg["send_public_weekday"], cfg["send_public_hour"], cfg["send_public_minute"])
            and state["public_message_id"] is None
            and cfg.get("channel_public_id")
        ):
            await self._send_public_and_reset(cfg, state)

    # ============================================================
    # 📨 Helpers d'envoi
    # ============================================================

    async def _get_channel(self, channel_id: int | None) -> discord.TextChannel | None:
        """Récupère un channel par son ID."""

        if not channel_id:
            return None
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except (discord.NotFound, discord.HTTPException):
                log.warning("[NGSTAFF NOTATIONS] Salon %d introuvable", channel_id)
                return None
        return channel

    async def _send_log(self, cfg: dict, msg: str) -> None:
        """Envoie un message de log après envoi public des notations."""

        channel = await self._get_channel(cfg.get("channel_logs_id"))
        if channel:
            try:
                await channel.send(f"🛡️ **[LOG NOTATIONS NGSTAFF]** {msg}")

            except discord.HTTPException:
                pass

    async def _send_presence(self, cfg: dict, state: dict) -> None:
        """Envoie le message de présence."""

        server = cfg["server"]
        channel = await self._get_channel(cfg["channel_staff_id"])
        if channel is None:
            return

        operators = await get_all_nota_operators(server)
        available  = await get_available_operators(server)
        view = build_presence_view(operators, available, deadline_passed=False, role_id=cfg.get("role_id"))

        try:
            msg = await channel.send(view=view)

        except discord.HTTPException:
            log.exception("[NGSTAFF NOTATIONS] Erreur envoi présence | server=%s", server)
            return

        await set_state_fields(
            server,
            availability_message_id=msg.id,
            public_message_id=None,
        )
        self._deadline_greyed[server] = False
        log.info("[NGSTAFF NOTATIONS] Message de présence envoyé | server=%s", server)

    async def _send_public_and_reset(self, cfg: dict, state: dict) -> None:
        """Envoie le message public et réinitialise la semaine de notation."""

        server = cfg["server"]
        channel = await self._get_channel(cfg["channel_public_id"])
        if channel is None:
            return

        assignments = await generate_notation_ranges(server, cfg.get("countries_count", 238))

        if not assignments:
            await self._send_log(cfg, "⚠️ Aucun opérateur disponible — envoi annulé.")
            await set_state_fields(server, public_message_id=-1)
            await reset_nota_week(server, [])
            return

        operators = await get_all_nota_operators(server)
        ops_by_id = {op["discord_id"]: op for op in operators}
        date_str = datetime.now(PARIS_TZ).strftime("%d/%m/%Y")

        view = build_public_nota_view(
            date_str, assignments, ops_by_id,
            cfg.get("url_country_lookup"),
            cfg.get("role_id"),
        )

        try:
            msg = await channel.send(view=view)

        except discord.HTTPException:
            log.exception("[NGSTAFF NOTATIONS] Erreur envoi public | server=%s", server)

            await self._send_log(cfg, "**Erreur** lors de l'envoi du **message public**.")
            return

        await set_state_fields(server, public_message_id=msg.id, assigned_ranges=json.dumps(assignments))
        await self._send_log(cfg, f"✅ Notations publiées (semaine du {date_str}, {len(assignments)} opérateur(s)).")

        log.info("[NGSTAFF NOTATIONS] Envoi public OK | server=%s", server)

        await reset_nota_week(server, assignments)

    async def _update_presence_message(self, cfg: dict, state: dict, deadline_passed: bool = False) -> None:
        """Rafraîchit le message de présence. Grise le bouton si deadline_passed."""

        server = cfg["server"]
        msg_id = state.get("availability_message_id")
        if not msg_id:
            return
        channel = await self._get_channel(cfg.get("channel_staff_id"))
        if channel is None:
            return
        try:
            msg = await channel.fetch_message(msg_id)
        except (discord.NotFound, discord.HTTPException):
            return

        operators = await get_all_nota_operators(server)
        available  = await get_available_operators(server)
        view = build_presence_view(operators, available, deadline_passed=deadline_passed, role_id=cfg.get("role_id"))
        try:
            await msg.edit(view=view)
        except discord.HTTPException:
            log.warning("[NOTATIONS] Impossible de mettre à jour le message de présence | server=%s", server)

    # ============================================================
    # 🔘 Bouton de présence
    # ============================================================

    @commands.Cog.listener("on_interaction")
    async def on_presence_toggle(self, interaction: discord.Interaction) -> None:

        if interaction.type != discord.InteractionType.component:
            return
        
        if interaction.data.get("custom_id") != "notation_presence_toggle":
            return

        guild_id = interaction.guild_id
        if guild_id is None:
            return

        ng_server = get_server_by_guild(guild_id)
        if ng_server is None:
            return
        
        server = ng_server.name

        cfg = await ng_load_nota_config(server)

        if not cfg.get("enabled"):
            return await interaction.response.send_message("❌ Le système de notations est désactivé.", ephemeral=True)

        operators = await get_all_nota_operators(server)
        op_ids = {op["discord_id"] for op in operators}

        if interaction.user.id not in op_ids:
            return await interaction.response.send_message("❌ Vous n'êtes pas configuré comme opérateur.", ephemeral=True)

        if is_past_deadline(cfg["deadline_weekday"], cfg["deadline_hour"], cfg["deadline_minute"]):
            return await interaction.response.send_message("⛔ Les votes sont désormais terminés.", ephemeral=True)

        state = await load_nota_state(server)
        if state["availability_message_id"] is None:
            return await interaction.response.send_message("❌ Aucune session de notation active.", ephemeral=True)

        try:
            await interaction.response.defer(ephemeral=True)

        except (discord.NotFound, discord.HTTPException):
            return

        is_available, status = await toggle_availability(server, interaction.user.id)
        await self._update_presence_message(cfg, state)

        await interaction.followup.send(f"✔️ Votre statut a été mis à jour : **{status}**.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NGSTAFF_NotationsListener(bot))