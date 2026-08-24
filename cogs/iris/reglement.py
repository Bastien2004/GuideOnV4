"""
cogs/iris/reglement.py — Gestion de l'interface reglement (règlement du
Discord Iris).

Même système "je crée ou je met à jour" que cogs/alpha/nous_rejoindre.py :
un seul message persistant par guilde (suivi via alpha_message_manager —
générique par guild_id/clé malgré son nom, déjà réutilisé tel quel par
/ngstaff stafflist), édité en place tant qu'il existe, recréé sinon.

Différence avec /alpha nous_rejoindre : pas de salon configurable en base
(NGRankConfig.content_nous_rejoindre_channel_id n'a pas d'équivalent pour
Iris, qui n'a pas de table de config dédiée) — la commande poste/édite
directement dans le salon où elle est exécutée. Si un salon dédié fixe est
préférable, on peut basculer sur channel_id figé en constante ici, ou sur
une vraie table de config le jour où Iris a besoin d'autres réglages.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container, send_ephemeral
from utils.error_handler import handle_app_command_error
from utils.managers.ng_server_manager import get_server_by_guild
from utils.perm_check import has_grade_check

from utils.managers.alpha_message_manager import get_alpha_message, upsert_alpha_message, clear_alpha_message

from views.iris.reglement_view import build_reglement_view, get_fresh_files

SERVER = "iris"

log = logging.getLogger(__name__)

MESSAGE_KEY = "iris_reglement"


# ============================================================
# 🌐 Vérification "Discord Iris"
# ============================================================

async def _require_iris_guild(interaction: Interaction) -> bool:
    """
    Protège la commande hors serveur Iris — même principe que
    require_alpha_guild/require_delta_guild (utils/ng_check_discord.py).
    Gardée ici en local plutôt que déplacée dans ce fichier partagé, pour
    rester un ajout isolé à ce seul fichier (à déplacer si Iris obtient
    d'autres commandes dédiées du même genre).
    """
    guild_id = interaction.guild_id
    server = get_server_by_guild(guild_id) if guild_id is not None else None

    if server is None or server.name != SERVER:
        await send_ephemeral(interaction, error_container("Cette commande est **réservée** au Discord Iris."))
        return False

    return True


# ============================================================
# 📜 Commande : /iris reglement
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 20)
@app_commands.command(name="reglement", description="📜 [OP] Envoie ou met à jour le règlement du serveur Iris")
async def reglement(interaction: Interaction) -> None:

    # 🌐 Vérification "Discord Iris".
    if not await _require_iris_guild(interaction):
        return

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "staff_iris.op", "gérer le règlement"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "iris_reglement"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "iris_reglement")

    # 🧩 Salon cible : celui où la commande est exécutée (pas de config dédiée
    # pour Iris — voir docstring module).
    channel = interaction.channel
    if channel is None:
        return await interaction.followup.send(
            view=error_container("Salon **introuvable**."),
            ephemeral=True,
        )
    channel_id = channel.id
    guild_id = interaction.guild_id

    fresh_files = get_fresh_files()
    view = build_reglement_view(fresh_files)
    kwargs: dict = {"view": view}
    if fresh_files:
        kwargs["files"] = fresh_files

    # 🔍 Vérification si le message existe.
    msg_cfg = await get_alpha_message(guild_id, MESSAGE_KEY)
    existing: discord.Message | None = None
    if msg_cfg and msg_cfg.message_id:
        try:
            existing = await channel.fetch_message(msg_cfg.message_id)
        except (discord.NotFound, discord.HTTPException):
            existing = None
            await clear_alpha_message(guild_id, MESSAGE_KEY)

    try:
        if existing:
            await existing.edit(view=view, attachments=fresh_files)
            return await interaction.followup.send(
                view=success_container(f"**Règlement** mis à jour dans {channel.mention} !"),
                ephemeral=True,
            )

        sent = await channel.send(**kwargs)
        await upsert_alpha_message(guild_id, MESSAGE_KEY, channel_id, sent.id)

        return await interaction.followup.send(
            view=success_container(f"Le **Règlement** a été envoyé dans {channel.mention} !"),
            ephemeral=True,
        )

    except discord.HTTPException:
        log.exception("[REGLEMENT IRIS] Erreur | guild=%s", guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur** Discord est survenue lors de l'envoi."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@reglement.error
async def reglement_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)