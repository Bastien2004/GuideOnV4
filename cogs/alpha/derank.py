"""
cogs/alpha/derank.py — Gestion du derank staff Alpha 
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

from utils.managers.alpha_staff_manager import get_staff_member, remove_staff_member, update_staff_member, upsert_staff_member
from utils.managers.alpha_rank_config_manager import load_rank_config
from utils.db.models.alpha_staff import GRADE_LABELS, GRADE_TO_ROLE_ATTR

log = logging.getLogger(__name__)

ROLE_CHOICES = [
    app_commands.Choice(name="Complet (staff + journaliste)", value="complet"),
    app_commands.Choice(name="Staff uniquement", value="staff"),
    app_commands.Choice(name="Journaliste uniquement", value="journaliste"),
]


# ============================================================
# 📁  Fonctions utilitaires
# ============================================================

def _build_derank_announcement(membre: discord.Member, old_grade: str, role: str,) -> LayoutView:
    """Création de l'annonce de derank."""

    label = GRADE_LABELS.get(old_grade, old_grade)
    view = LayoutView(timeout=None)
    c = Container()

    if role == "journaliste":
        c.add_item(TextDisplay(f"<:Alpha:1500414179650048070> **Merci** à <@{membre.id}> pour son travail chez les **journalistes** ! 📰"))

    elif role == "staff":
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> **Merci** à <@{membre.id}> pour son travail chez les **{label}** !"))
        
    else:
        c.add_item(TextDisplay(f"<:Alpha:1500414179650048070> Merci à <@{membre.id}> pour son travail en tant que **{label}** !"))

    view.add_item(c)
    return view


def _build_journaliste_derank_message(pseudo_jeu: str, old_grade: str, journaliste_ping_id: int | None, role: str) -> LayoutView:
    """Création du message pour les journalistes pour l'affiche de derank."""

    label = GRADE_LABELS.get(old_grade, old_grade)
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""
    view = LayoutView(timeout=None)

    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de derank"))
    c.add_item(Separator())

    if role == "staff":
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** quitte le **Staff** en tant que **{label}**.\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))

    elif role == "journaliste":
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** quitte l'équipe des **Journalistes**.\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))

    else:
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** ne fait plus parti du staff (**{label}**).\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))

    view.add_item(c)
    return view


async def _fetch_channel(bot: discord.Client, channel_id: int):
    """Récupère le salon d'envoi."""
    try:
        return await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.HTTPException):
        return None


async def _send_with_reaction(bot, channel_id, view, emoji):
    """Envoie l'annonce de derank et ajoute la réaction."""

    if not channel_id:
        return
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    
    if not channel:
        return
    
    try:
        sent = await channel.send(view=view)
        if emoji:
            try:
                await sent.add_reaction(emoji)
            except discord.HTTPException:
                pass

    except discord.HTTPException:
        log.warning("[DERANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)


async def _send_to_channel(bot, channel_id, view):
    """Envoie le message de derank aux journalistes."""

    if not channel_id:
        return
    
    channel = bot.get_channel(channel_id) or await _fetch_channel(bot, channel_id)
    if not channel:
        return
    
    try:
        await channel.send(view=view)
    except discord.HTTPException:
        log.warning("[DERANK ALPHA] Impossible d'envoyer dans le salon %d", channel_id)


# ════════════════════════════════════════════════════════════
# 🛠️ Vue de confirmation
# ════════════════════════════════════════════════════════════

class _ConfirmDerank(LayoutView):

    def __init__(self, membre: discord.Member, member_data: dict, cfg: dict, guild_id: int, role: str) -> None:
        """Création de l'interface de confirmation du derank."""

        super().__init__(timeout=120)
        self.membre = membre
        self.data = member_data
        self.cfg = cfg
        self.guild_id = guild_id
        self.role = role
        self._build()

    def _build(self) -> None:

        d = self.data
        label = GRADE_LABELS.get(d["grade"], d["grade"])
        is_journ = d.get("is_journaliste", False)
        role = self.role

        if role == "complet":
            desc = (
                f"Confirmer le **derank complet** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n\n"
                f"Grade : **{label}**"
                + (" + 📰 Journaliste" if is_journ else "")
                + "\n-# Rôles retirés, pseudo réinitialisé, retiré du stafflist."
            )

        elif role == "staff":
            if d["staff"] == "journaliste":
                desc = (
                    f"**{d['pseudo_jeu']}** ne fait pas parti du __staff__ ! Il est juste **Journaliste**."
                    f"Confirmer son derank en tant que **journaliste** ?"
                )

            else:
                desc = (
                    f"Retirer le grade **{label}** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n"
                    + (f"(**{d['pseudo_jeu']}** restera **Journaliste**).\n" if is_journ else "")
                    + "-# Rôle Discord retiré, pseudo et stafflist mis à jour."
                )

        else:
            if not is_journ:
                desc = f"**{d['pseudo_jeu']}** n'est pas **Journaliste**."

            else:
                desc = (
                    f"Confirmer le retrait du statut **Journaliste** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n"
                    + (f"(**{d['pseudo_jeu']}** restera **{label}**).\n" if d["grade"] != "journaliste" else "")
                    + "-# Rôle Discord retiré, pseudo et stafflist mis à jour."
                )

        c = Container()
        c.add_item(TextDisplay("# ⚠️ Confirmation de derank"))
        c.add_item(Separator())

        c.add_item(TextDisplay(desc))
        c.add_item(Separator())

        btn_confirm = Button(
            label="<:valider:1495444292867723284> Confirmer",
            style=discord.ButtonStyle.danger,
            custom_id="derank_confirm",
        )

        btn_cancel = Button(
            label="<:annuler:1495444256754761979> Annuler",
            style=discord.ButtonStyle.secondary,
            custom_id="derank_cancel",
        )

        btn_confirm.callback = self._on_confirm
        btn_cancel.callback  = self._on_cancel

        c.add_item(ActionRow(btn_confirm, btn_cancel))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        """Tâche de derank si confirmation."""

        await interaction.response.defer()

        membre = self.membre
        d = self.data
        cfg = self.cfg
        role = self.role
        is_journ = d.get("is_journaliste", False)
        grade = d["grade"]

        if role == "journaliste" and not is_journ:
            await interaction.edit_original_response(
                view=warning_container(f"**{d['pseudo_jeu']}** n'est pas __Journaliste__.")
            )
            return

        if role == "complet" or (role == "grade" and grade == "journaliste"):
            await remove_staff_member(d["discord_id"])

            try:
                if grade != "journaliste":
                    role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(grade, ""))
                    if role_id:
                        role = interaction.guild.get_role(role_id)
                        if role and role in membre.roles:
                            await membre.remove_roles(role, reason="Derank Alpha complet")

                if is_journ or grade == "journaliste":
                    journ_id = cfg.get(GRADE_TO_ROLE_ATTR["journaliste"])
                    if journ_id:
                        journ_role = interaction.guild.get_role(journ_id)
                        if journ_role and journ_role in membre.roles:
                            await membre.remove_roles(journ_role, reason="Derank Alpha complet")

            except (discord.Forbidden, discord.HTTPException):
                log.warning("[DERANK ALPHA] Erreur rôles pour %s", membre.id)

            try:
                await membre.edit(nick=membre.name, reason="Derank Alpha complet")
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif role == "staff":
            if is_journ:
                await upsert_staff_member(
                    d["discord_id"], d["pseudo_jeu"], "journaliste", is_journaliste=True
                )
            else:
                await remove_staff_member(d["discord_id"])

            try:
                role_id = cfg.get(GRADE_TO_ROLE_ATTR.get(grade, ""))
                if role_id:
                    role = interaction.guild.get_role(role_id)
                    if role and role in membre.roles:
                        await membre.remove_roles(role, reason="Derank Alpha : grade retiré")

            except (discord.Forbidden, discord.HTTPException):
                pass

            try:
                new_nick = f"Journaliste | {d['pseudo_jeu']}" if is_journ else membre.name
                await membre.edit(nick=new_nick, reason="Derank Alpha : grade retiré")
            except (discord.Forbidden, discord.HTTPException):
                pass

        elif role == "journaliste":
            if grade == "journaliste":

                await remove_staff_member(d["discord_id"])
            else:
                await update_staff_member(d["discord_id"], is_journaliste=False)

            try:
                journ_id = cfg.get(GRADE_TO_ROLE_ATTR["journaliste"])
                if journ_id:
                    journ_role = interaction.guild.get_role(journ_id)
                    if journ_role and journ_role in membre.roles:
                        await membre.remove_roles(journ_role, reason="Derank Alpha : journaliste retiré")
            except (discord.Forbidden, discord.HTTPException):
                pass

        display_grade = grade if grade != "journaliste" else "journaliste"
        
        await _send_with_reaction(
            interaction.client,
            cfg.get("rank_channel_id"),
            _build_derank_announcement(membre, d["pseudo_jeu"], display_grade, role),
            cfg.get("rank_emoji"),
        )

        await _send_to_channel(
            interaction.client,
            cfg.get("journaliste_channel_id"),
            _build_journaliste_derank_message(
                d["pseudo_jeu"], display_grade, cfg.get("journaliste_ping_id"), role
            ),
        )

        from cogs.alpha.stafflist import refresh_staff_message
        await refresh_staff_message(interaction.client, self.guild_id)

        await interaction.edit_original_response(view=success_container(f"**{d['pseudo_jeu']}** a été derank."))

        self.stop()

    async def _on_cancel(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=warning_container("Le **processus** de derank a été __annulé__."))

        self.stop()


# ════════════════════════════════════════════════════════════
# 🧭 Commande : /alpha derank
# ════════════════════════════════════════════════════════════

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="derank", description="⬇️ [OP] Derank un membre du staff Alpha")
@app_commands.describe(membre="Membre Discord à derank", role="Ce qui est retiré (défaut : complet)")
@app_commands.choices(role=ROLE_CHOICES)
async def alpha_derank(interaction: Interaction, membre: discord.Member, role: app_commands.Choice[str] = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return
    
    # 🔐 Vérification Opérateur.
    if not await check_op_alpha(interaction, "**derank** un membre du staff"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "alpha_derank"):
        return
    
    # 📊 Tracking.
    await tracker_commande(interaction, "alpha_derank")

    # 🔎 Vérification que le membre est dans le staff Alpha.
    member_data = await get_staff_member(membre.id)
    if member_data is None:
        return await interaction.followup.send(
            view=warning_container(f"**{membre.display_name}** n'est pas dans la **liste du staff** Alpha."),
            ephemeral=True,
        )

    # 🧩 Exécution du processus de derank.
    role_val = role.value if role else "complet"
    cfg = await load_rank_config(interaction.guild_id)
    confirm_view = _ConfirmDerank(membre, member_data, cfg, interaction.guild_id, role_val)
    await interaction.followup.send(view=confirm_view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@alpha_derank.error
async def alpha_derank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)