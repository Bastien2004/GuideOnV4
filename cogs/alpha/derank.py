"""
cogs/alpha/derank.py — Commande /alpha derank.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import success_container, warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha

from utils.managers.alpha_staff_manager import get_staff_member, remove_staff_member
from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.db.models.alpha_staff import GRADE_LABELS, GRADE_TO_ROLE_ATTR

log = logging.getLogger(__name__)


# ============================================================
#  📁 Fonctions utilitaires
# ============================================================

def _build_derank_announcement(membre: discord.Member, pseudo_jeu: str, old_grade: str) -> LayoutView:
    """Construit le message de derank envoyé dans le salon rank-derank."""

    view = LayoutView(timeout=None)
    c = Container()

    c.add_item(TextDisplay("# 👋 Départ du staff Alpha"))
    c.add_item(TextDisplay(f"Merci à <@{membre.id}>) qui quitte le staff Alpha."))
    
    return view


def _build_journaliste_derank_message(
    pseudo_jeu: str,
    old_grade: str,
    journaliste_ping_id: int | None,
) -> LayoutView:
    label = GRADE_LABELS.get(old_grade, old_grade)
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""

    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de derank"))
    c.add_item(Separator())
    c.add_item(TextDisplay(
        f"{ping}**{pseudo_jeu}** (**{label}**) vient d'être **deranké**.\n"
        f"Merci de préparer l'affiche de derank. 🎨"
    ))
    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c)
    return view


async def _fetch_channel(bot: discord.Client, channel_id: int):
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def _send_to_channel(bot: discord.Client, channel_id: int | None, view: LayoutView) -> None:
    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if channel is None:
        return
    try:
        await channel.send(view=view)
    except discord.HTTPException:
        log.warning("Impossible d'envoyer dans le salon %d", channel_id)


# ════════════════════════════════════════════════════════════
# ❓ Vue de confirmation derank
# ════════════════════════════════════════════════════════════

class _ConfirmDerank(LayoutView):
    def __init__(
        self,
        membre: discord.Member,
        member_data: dict,
        cfg: dict,
        guild_id: int,
    ) -> None:
        super().__init__(timeout=60)
        self.membre = membre
        self.data = member_data
        self.cfg = cfg
        self.guild_id = guild_id
        self._build()

    def _build(self) -> None:
        d = self.data
        label = GRADE_LABELS.get(d["grade"], d["grade"])
        c = Container()
        c.add_item(TextDisplay("# ⚠️ Confirmation de derank"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"Confirmer le **derank** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n\n"
            f"Grade actuel : **{label}**\n\n"
            f"Actions qui seront effectuées :\n"
            f"• Retrait du rôle Discord **{label}**\n"
            f"• Pseudo Discord remis à l'original\n"
            f"• Message d'au revoir dans le salon rank\n"
            f"• Message aux journalistes pour l'affiche\n"
            f"• Retrait de la liste staff"
        ))
        c.add_item(Separator())

        btn_confirm = Button(label="✅ Confirmer", style=discord.ButtonStyle.danger, custom_id="derank_confirm")
        btn_cancel  = Button(label="↩️ Annuler",  style=discord.ButtonStyle.secondary, custom_id="derank_cancel")
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback  = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        await interaction.response.defer()

        membre = self.membre
        d = self.data
        cfg = self.cfg

        # 1. Suppression DB
        await remove_staff_member(d["discord_id"])

        # 2. Retrait rôle Discord
        try:
            role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(d["grade"], ""))
            if role_id:
                role = interaction.guild.get_role(role_id)
                if role and role in membre.roles:
                    await membre.remove_roles(role, reason="Derank Alpha")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Impossible de retirer le rôle de %s", membre.id)

        # 3. Remise du username d'origine
        try:
            await membre.edit(nick=membre.name, reason="Derank Alpha — remise pseudo d'origine")
        except (discord.Forbidden, discord.HTTPException):
            log.warning("Impossible de remettre le pseudo de %s", membre.id)

        # 4. Messages
        await _send_to_channel(
            interaction.client,
            cfg.get("rank_channel_id"),
            _build_derank_announcement(membre, d["pseudo_jeu"], d["grade"]),
        )
        await _send_to_channel(
            interaction.client,
            cfg.get("journaliste_channel_id"),
            _build_journaliste_derank_message(
                d["pseudo_jeu"], d["grade"], cfg.get("journaliste_ping_id")
            ),
        )

        # 5. Rafraîchissement stafflist
        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, self.guild_id)

        label = GRADE_LABELS.get(d["grade"], d["grade"])
        await interaction.edit_original_response(
            view=success_container(
                f"**{d['pseudo_jeu']}** deranké avec succès.\n"
                f"• Ancien grade : **{label}**\n"
                f"• Rôle Discord retiré\n"
                f"• Pseudo remis : `{membre.name}`\n"
                f"• Messages envoyés\n"
                f"• Liste staff rafraîchie"
            )
        )
        self.stop()

    async def _on_cancel(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(
            view=warning_container("Derank annulé.")
        )
        self.stop()


# ════════════════════════════════════════════════════════════
# 🧭 Commande
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="derank", description="⬇️ Derank un membre du staff Alpha")
@app_commands.describe(membre="Membre Discord à deranker")
async def derank(interaction: Interaction, membre: discord.Member) -> None:

    # 🛡️ Ban bot
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Permission OP Alpha
    if not await check_op_alpha(interaction, "deranker un membre du staff"):
        return

    # 🕒 Defer
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande
    if not await verifier_commande(interaction, "alpha_derank"):
        return

    # 📊 Tracking
    await tracker_commande(interaction, "alpha_derank")

    # 🔍 Vérification existence
    member_data = await get_staff_member(membre.id)
    if member_data is None:
        return await interaction.followup.send(
            view=warning_container(
                f"**{membre.display_name}** n'est pas dans la liste du staff Alpha."
            ),
            ephemeral=True,
        )

    # 📋 Config rank
    cfg = await load_rank_config(interaction.guild_id)

    # ❓ Vue de confirmation
    confirm_view = _ConfirmDerank(membre, member_data, cfg, interaction.guild_id)
    await interaction.followup.send(view=confirm_view, ephemeral=True)


# ── Erreurs ────────────────────────────────────────────────

@derank.error
async def derank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)