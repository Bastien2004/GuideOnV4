"""
cogs/dev/join_serv.py — Crée une invitation Discord sur un serveur où le bot est présent.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import Container, LayoutView, Separator, TextDisplay

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

log = logging.getLogger(__name__)


# ============================================================
# 📁  Fonctions utilitaires
# ============================================================

def _find_invitable_channel(guild: discord.Guild) -> discord.TextChannel | None:
    """
    Cherche un salon textuel où le bot peut créer une invitation
    (permission create_instant_invite). Priorité au salon système
    (souvent le salon d'accueil), sinon le premier salon textuel valide
    par ordre de position.
    """
    me = guild.me
    if me is None:
        return None

    candidates: list[discord.TextChannel] = []
    if guild.system_channel is not None:
        candidates.append(guild.system_channel)
    candidates += [c for c in guild.text_channels if c not in candidates]

    for channel in candidates:
        perms = channel.permissions_for(me)
        if perms.create_instant_invite:
            return channel
    return None


def _build_invite_view(guild: discord.Guild, invite: discord.Invite, channel: discord.TextChannel) -> LayoutView:
    """Construit la réponse Components V2 avec le lien d'invitation."""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# <:valider:1495444292867723284> Invitation créée"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"⇝ **Serveur :** {guild.name}\n"
        f"⇝ **ID :** `{guild.id}`\n"
        f"⇝ **Salon :** {channel.mention}\n"
        f"⇝ **Expire dans :** 24h\n"
        f"⇝ **Usages :** Illimités\n\n"
        f"**Lien :** {invite.url}"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view


# ============================================================
# 🧭 Commande : /dev join_serv
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="join_serv", description="🔗 [DEV] Crée une invitation sur un serveur où GuideOn est présent")
@app_commands.describe(id_serveur="ID du serveur cible")
async def join_serv(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**créer une invitation** sur un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_join_serv"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_join_serv")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."),
            ephemeral=True,
        )

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."),
            ephemeral=True,
        )

    # 🔎 Recherche d'un salon où créer l'invitation.
    channel = _find_invitable_channel(guild)
    if channel is None:
        return await interaction.followup.send(
            view=error_container(
                f"Aucun salon de **{guild.name}** ne permet à GuideOn de créer une invitation "
                f"(permission `Créer une invitation` manquante partout)."
            ),
            ephemeral=True,
        )

    # 🔗 Création de l'invitation.
    try:
        invite = await channel.create_invite(
            max_age=86400,   # 24h
            max_uses=0,       # illimité
            temporary=False,
            unique=True,
            reason=f"Demandé par {interaction.user} ({interaction.user.id}) via /dev join_serv",
        )
    except discord.Forbidden:
        return await interaction.followup.send(
            view=error_container(f"GuideOn n'a pas la permission de créer une invitation sur **{guild.name}**."),
            ephemeral=True,
        )
    except discord.HTTPException:
        log.exception("[DEV_JOIN_SERV] Erreur create_invite guild=%d", guild_id)
        return await interaction.followup.send(
            view=error_container("Une **erreur Discord** est survenue lors de la création de l'invitation."),
            ephemeral=True,
        )

    log.info(
        "[DEV_JOIN_SERV] Invitation créée pour %s (%d) | salon=%d | demandé par %d",
        guild.name, guild.id, channel.id, interaction.user.id,
    )

    await interaction.followup.send(view=_build_invite_view(guild, invite, channel), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@join_serv.error
async def join_serv_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)