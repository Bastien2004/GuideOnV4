"""
cogs/alpha/derank.py — Gestion du derank staff Alpha (grades + statuts secondaires).

/alpha derank distingue 5 cibles via le paramètre `role` :
  - complet    : retire TOUT (grade + journaliste + affilié + builder),
                 supprime la ligne DB, réinitialise le pseudo Discord brut.
  - staff      : retire uniquement le grade (+ rôle équipe). Les statuts
                 secondaires restent intacts.
  - journaliste / affilie / builder : retire uniquement ce statut (+ son
                 rôle Discord, + pseudo_jeu_builder remis à None pour builder).
                 Le grade et les autres statuts restent.

Dans tous les cas (sauf complet), le pseudo Discord est recalculé via
compute_nick_prefix() sur l'état RESTANT après le retrait — ex: un
Modérateur+ Journaliste deranké côté staff devient automatiquement
"Journaliste | Pseudo".
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

from utils.alpha_rank_logic import apply_staff_roles, compute_nick_prefix

from utils.managers.alpha_staff_manager import get_staff_member, remove_staff_member, update_staff_member
from utils.managers.alpha_rank_config_manager import load_rank_config

from utils.db.models.alpha_staff import GRADE_LABELS, SECONDARY_STATUSES, STATUTS_SECONDAIRES_ORDER

log = logging.getLogger(__name__)

ROLE_CHOICES = [
    app_commands.Choice(name="Complet (grade + tous les statuts)", value="complet"),
    app_commands.Choice(name="Staff uniquement (grade)", value="staff"),
    app_commands.Choice(name="Journaliste uniquement", value="journaliste"),
    app_commands.Choice(name="Affilié uniquement", value="affilie"),
    app_commands.Choice(name="Builder uniquement", value="builder"),
]


def _secondary_dict(d: dict) -> dict[str, bool]:
    """Extrait l'état des 3 statuts secondaires depuis un dict membre."""
    return {key: d.get(f"is_{key}", False) for key in STATUTS_SECONDAIRES_ORDER}


# ============================================================
# 📁  Fonctions utilitaires — construction des annonces
# ============================================================

def _build_derank_announcement(membre: discord.Member, role: str, old_grade: str | None) -> LayoutView:
    """Annonce publique de derank."""
    view = LayoutView(timeout=None)
    c = Container()

    if role == "complet":
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "l'équipe"
        c.add_item(TextDisplay(f"<:Alpha:1500414179650048070> Merci à <@{membre.id}> pour son travail en tant que **{label}** !"))

    elif role == "staff":
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "Staff"
        c.add_item(TextDisplay(f"<:Alpha:1500414179650048070> **Merci** à <@{membre.id}> pour son travail chez les **{label}** !"))

    else:
        statut_label = SECONDARY_STATUSES[role]["label"]
        badge = SECONDARY_STATUSES[role]["badge"] or ""
        c.add_item(TextDisplay(
            f"<:Alpha:1500414179650048070> **Merci** à <@{membre.id}> pour son travail chez les **{statut_label}** ! {badge}".rstrip()
        ))

    view.add_item(c)
    return view


def _build_journaliste_derank_message(pseudo_jeu: str, role: str, old_grade: str | None, journaliste_ping_id: int | None) -> LayoutView:
    """Message pour les journalistes (affiche de remerciement) — uniquement pour role=complet/staff/journaliste."""
    ping = f"<@&{journaliste_ping_id}> " if journaliste_ping_id else ""
    view = LayoutView(timeout=None)
    c = Container()
    c.add_item(TextDisplay("# 📸 Affiche de derank"))
    c.add_item(Separator())

    if role == "staff":
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "Staff"
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** quitte le **Staff** en tant que **{label}**.\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))
    elif role == "journaliste":
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** quitte l'équipe des **Journalistes**.\n"
            f"Merci de créer et poster l'affiche de remerciement. 🎨"
        ))
    else:  # complet
        label = GRADE_LABELS.get(old_grade, old_grade) if old_grade else "l'équipe"
        c.add_item(TextDisplay(
            f"Hey {ping} ! **{pseudo_jeu}** ne fait plus partie de l'équipe (**{label}**).\n"
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
        role = self.role
        grade = d["grade"]
        label = GRADE_LABELS.get(grade, grade) if grade else None
        secondary = _secondary_dict(d)
        active_statuses = [SECONDARY_STATUSES[k]["label"] for k in STATUTS_SECONDAIRES_ORDER if secondary[k]]

        if role == "complet":
            extras = f" + {' + '.join(active_statuses)}" if active_statuses else ""
            grade_part = label if label else (active_statuses[0] if active_statuses else "—")
            desc = (
                f"Confirmer le **derank complet** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n\n"
                f"Statut actuel : **{grade_part}**{extras if label else ''}\n"
                "-# Rôles retirés, pseudo réinitialisé, retiré du stafflist."
            )

        elif role == "staff":
            if not grade:
                desc = f"**{d['pseudo_jeu']}** n'a **aucun grade staff** à retirer."
            else:
                remaining = ", ".join(active_statuses) if active_statuses else None
                desc = (
                    f"Retirer le grade **{label}** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n"
                    + (f"(Conservera : {remaining}.)\n" if remaining else "")
                    + "-# Rôle Discord retiré, pseudo et stafflist mis à jour."
                )

        else:  # journaliste / affilie / builder
            meta = SECONDARY_STATUSES[role]
            if not secondary[role]:
                desc = f"**{d['pseudo_jeu']}** n'est pas **{meta['label']}**."
            else:
                remaining_parts = []
                if grade:
                    remaining_parts.append(label)
                remaining_parts += [SECONDARY_STATUSES[k]["label"] for k in STATUTS_SECONDAIRES_ORDER if k != role and secondary[k]]
                remaining = ", ".join(remaining_parts) if remaining_parts else None
                desc = (
                    f"Confirmer le retrait du statut **{meta['label']}** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n"
                    + (f"(Conservera : {remaining}.)\n" if remaining else "")
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
        btn_cancel.callback = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        """Exécute le derank confirmé."""
        await interaction.response.defer()

        membre = self.membre
        d = self.data
        cfg = self.cfg
        role = self.role
        grade = d["grade"]
        secondary = _secondary_dict(d)

        # ── Garde-fous : rien à faire ────────────────────────
        if role == "staff" and not grade:
            await interaction.edit_original_response(
                view=warning_container(f"**{d['pseudo_jeu']}** n'a aucun grade staff à retirer.")
            )
            self.stop()
            return

        if role in SECONDARY_STATUSES and not secondary[role]:
            await interaction.edit_original_response(
                view=warning_container(f"**{d['pseudo_jeu']}** n'est pas **{SECONDARY_STATUSES[role]['label']}**.")
            )
            self.stop()
            return

        # ── Calcul de l'état cible (grade + statuts) ─────────
        if role == "complet":
            target_grade: str | None = None
            target_secondary = {key: False for key in STATUTS_SECONDAIRES_ORDER}
        elif role == "staff":
            target_grade = None
            target_secondary = dict(secondary)
        else:  # journaliste / affilie / builder
            target_grade = grade
            target_secondary = dict(secondary)
            target_secondary[role] = False

        # ── Persistance DB ────────────────────────────────────
        has_remaining_state = target_grade is not None or any(target_secondary.values())

        if not has_remaining_state:
            # Plus rien à conserver -> ligne supprimée entièrement.
            await remove_staff_member(d["discord_id"])
        else:
            update_kwargs: dict = {
                "grade": target_grade,
                "is_journaliste": target_secondary["journaliste"],
                "is_affilie": target_secondary["affilie"],
                "is_builder": target_secondary["builder"],
            }
            if role == "builder" or (role == "complet"):
                update_kwargs["pseudo_jeu_builder"] = None
            await update_staff_member(d["discord_id"], **update_kwargs)

        # ── Rôles Discord ──────────────────────────────────────
        await apply_staff_roles(
            membre, cfg,
            grade=target_grade,
            secondary=target_secondary,
            reason=f"Derank Alpha : {role}",
        )

        # ── Pseudo Discord ──────────────────────────────────────
        if role == "complet":
            try:
                await membre.edit(nick=membre.name, reason="Derank Alpha complet")
            except (discord.Forbidden, discord.HTTPException):
                log.warning("[DERANK ALPHA] Impossible de renommer %s", membre.id)
        else:
            prefix = compute_nick_prefix(target_grade, target_secondary)
            new_nick = f"{prefix} | {d['pseudo_jeu']}" if prefix else d["pseudo_jeu"]
            try:
                await membre.edit(nick=new_nick, reason=f"Derank Alpha : {role}")
            except (discord.Forbidden, discord.HTTPException):
                log.warning("[DERANK ALPHA] Impossible de renommer %s", membre.id)

        # ── Annonces ──────────────────────────────────────────
        await _send_with_reaction(
            interaction.client,
            cfg.get("rank_channel_id"),
            _build_derank_announcement(membre, role, grade),
            cfg.get("rank_emoji"),
        )

        # Affiche journaliste : pertinente pour complet / staff / journaliste
        # (pas affilié/builder, qui n'ont jamais eu d'affiche dédiée).
        if role in ("complet", "staff", "journaliste"):
            await _send_to_channel(
                interaction.client,
                cfg.get("journaliste_channel_id"),
                _build_journaliste_derank_message(d["pseudo_jeu"], role, grade, cfg.get("journaliste_ping_id")),
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