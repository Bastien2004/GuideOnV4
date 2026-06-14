"""
cogs/dev/kick.py — Kick le bot d'un serveur
"""

from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, app_commands, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import error_container, success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_dev import check_dev

log = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# ❓ Vue de confirmation
# ════════════════════════════════════════════════════════════

class _ConfirmKickView(LayoutView):
    def __init__(self, guild: discord.Guild, requester_id: int) -> None:
        super().__init__(timeout=60)
        self.guild = guild
        self.requester_id = requester_id
        self._build()

    async def interaction_check(self, interaction: Interaction) -> bool:
        return interaction.user.id == self.requester_id

    def _build(self) -> None:
        g = self.guild
        owner = f"<@{g.owner_id}>" if g.owner_id else "*Inconnu*"

        c = Container()
        c.add_item(TextDisplay("# <:erreur:1495443907281031359> Confirmation — Kick bot"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"GuideOn va **quitter** ce serveur :\n\n"
            f"⇝ **Nom :** {g.name}\n"
            f"⇝ **ID :** `{g.id}`\n"
            f"⇝ **Propriétaire :** {owner}\n"
            f"⇝ **Membres :** `{g.member_count}`\n\n"
            f"<:erreur:1495443907281031359> Confirmer ?"
        ))
        c.add_item(Separator())

        btn_confirm = Button(label="<:valider:1495444292867723284> Confirmer", style=ButtonStyle.danger, custom_id="kick_confirm")
        btn_cancel  = Button(label="<:annuler:1495444256754761979> Annuler",  style=ButtonStyle.secondary, custom_id="kick_cancel")
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback  = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        g = self.guild
        name, gid = g.name, g.id

        try:
            await g.leave()

        except discord.HTTPException:
            log.exception("[DEV_KICK] Erreur leave() guild=%d", gid)
            await interaction.edit_original_response(view=error_container("Une **erreur Discord** est survenue lors du __kick__."))
            return

        log.info("[DEV_KICK] Bot a quitté %s (%d) | demandé par %d", name, gid, self.requester_id)
        await interaction.edit_original_response(
            view=success_container(f"GuideOn a quitté **{name}** (`{gid}`)."))
        
        self.stop()

    async def _on_cancel(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(
            view=warning_container("Départ annulé.")
        )
        self.stop()


# ============================================================
# 🧭 Commande : /dev kick
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="kick", description="💨 [DEV] Kick GuideOn d'un serveur")
@app_commands.describe(id_serveur="ID du serveur à quitter")
async def kick(interaction: Interaction, id_serveur: str) -> None:

    # 🔐 Vérification des permissions.
    if not await check_dev(interaction, "**kick** le bot d'un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_kick"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "dev_kick")

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

    # ✉️ Envoi du message de confirmation
    await interaction.followup.send(
        view=_ConfirmKickView(guild, interaction.user.id),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@kick.error
async def kick_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)