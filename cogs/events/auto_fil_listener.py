"""
cogs/events/auto_fil_listener.py — Création automatique d'un fil sous
chaque message posté dans un salon configuré (/config auto_fil, Paul,
2026-10-15).

Logique volontairement minimale : à chaque on_message dans un salon
textuel, on vérifie via utils.managers.auto_fil_manager.is_auto_fil_channel
si CE salon précis est configuré, et si oui on crée un fil via
message.create_thread(). Rien d'autre (pas de compteur, pas de cache
spécifique ici — list_configs/is_auto_fil_channel a déjà son propre cache
côté manager).

Filtres appliqués, cohérents avec les autres listeners on_message du
dépôt (cf. cogs/events/exp_listener.py) :
  - message.author.bot -> ignoré (pas de fil sous les messages d'autres
    bots/webhooks — décision par défaut, à ajuster si Paul veut l'inverse).
  - message.guild absent (DM) -> ignoré, l'auto-fil n'a de sens qu'en serveur.
  - message.type non "default"/"reply" -> ignoré (messages système : arrivée
    de membre, boost, épinglage... ça n'a pas de sens de créer un fil
    dessous, et certains de ces types ne supportent même pas create_thread).

⚠️ Cooldown (slowmode) : PAS revérifié ici à chaque message — il est posé
UNE SEULE FOIS au moment où le salon est ajouté dans le panneau de config
(views/auto_fil/auto_fil_config_view.py::_on_select_channel). Ce listener
ne touche jamais aux réglages du salon.
"""
from __future__ import annotations

import logging

import discord
from discord.ext import commands

from utils.managers.auto_fil_manager import is_auto_fil_channel

log = logging.getLogger(__name__)

# Types de message sous lesquels créer un fil a du sens (cf. docstring).
_THREADABLE_TYPES = (discord.MessageType.default, discord.MessageType.reply)


class AutoFilListener(commands.Cog):
    """Cog de création automatique de fils."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        if message.type not in _THREADABLE_TYPES:
            return
        if not isinstance(message.channel, discord.TextChannel):
            # Déjà dans un fil, un forum, une voc textuelle, etc. — hors
            # périmètre : seuls les salons textuels classiques sont
            # proposés dans le panneau de config (ChannelSelect par
            # défaut text/news), donc rien d'autre ne peut être configuré,
            # mais on protège quand même is_auto_fil_channel() d'un
            # channel_id qui ne correspondrait à aucun salon valide.
            return

        try:
            if not await is_auto_fil_channel(message.channel.id):
                return
        except Exception:
            log.exception(
                "[AUTO_FIL] Échec vérification config guild=%s channel=%s",
                message.guild.id, message.channel.id,
            )
            return

        try:
            await message.create_thread(
                name=f"Fil de {message.author.display_name}"[:100],
                reason="Auto-fil",
            )
        except discord.Forbidden:
            log.warning(
                "[AUTO_FIL] Permissions insuffisantes pour créer un fil guild=%s channel=%s",
                message.guild.id, message.channel.id,
            )
        except discord.HTTPException:
            log.exception(
                "[AUTO_FIL] Erreur Discord lors de la création du fil guild=%s channel=%s",
                message.guild.id, message.channel.id,
            )


# ============================================================
# 🚀 Setup
# ============================================================

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoFilListener(bot))
