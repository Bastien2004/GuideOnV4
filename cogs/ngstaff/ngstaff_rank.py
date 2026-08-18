"""
cogs/ngstaff/ngstaff_rank.py — /ngstaff rank : rank-up d'un membre du staff,
généralisé multi-serveurs (refonte multi-serveurs, phase 12, §13 du prompt).

Réplique de cogs/alpha/rank.py, avec deux différences :
  - la vérification de permission utilise le flow deux temps dynamique
    (require_ng_server + has_grade_check(f"staff_{server}.op")) au lieu de
    utils.perm_alpha.check_op_alpha (RBAC legacy, propre à Alpha) ;
  - server est résolu depuis l'interaction plutôt que câblé en dur, et
    passé explicitement à execute_grade_rank/execute_statut_rank (kwarg
    server, ajouté phase 12 — défaut "alpha" pour ne rien casser côté
    /alpha rank, qui ne le passe jamais).
"""

from __future__ import annotations

import logging

import discord
from discord import Interaction, app_commands

from utils.ng_rank_logic import RankValidationError, execute_grade_rank, execute_statut_rank
from utils.container_universel import error_container, success_container, warning_container
from utils.control_admin import verifier_commande
from utils.db.models.alpha_staff import (
    GRADE_LABELS,
    GRADES_ORDER,
    SECONDARY_STATUSES,
    STATUTS_SECONDAIRES_ORDER,
)
from utils.error_handler import handle_app_command_error
from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.ng_staff_manager import get_staff_member
from utils.ng_server_check import require_ng_server
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)


# ============================================================
# 🛠️ Paramètres
# ============================================================

TYPE_CHOICES = [
    app_commands.Choice(name="Grade (Staff)", value="grade"),
    app_commands.Choice(name="Statut (Journaliste / Affilié / Builder)", value="statut"),
]

GRADE_CHOICES = [
    app_commands.Choice(name=GRADE_LABELS[g], value=g)
    for g in GRADES_ORDER
]

STATUT_CHOICES = [
    app_commands.Choice(name=SECONDARY_STATUSES[s]["label"], value=s)
    for s in STATUTS_SECONDAIRES_ORDER
]

VALEUR_CHOICES = GRADE_CHOICES + STATUT_CHOICES


# ============================================================
# 🧭 Commande : /ngstaff rank
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="rank", description="⬆️ [OP] Rank-up un membre du staff")
@app_commands.describe(membre="utilisateur Discord", pseudo_jeu="Pseudo IG exact", type="Type de rank-up", valeur="Grade ou statut à attribuer", pseudo_jeu_builder="Pseudo IG du compte builder")
@app_commands.choices(type=TYPE_CHOICES, valeur=VALEUR_CHOICES)
async def ngstaff_rank(interaction: Interaction, membre: discord.Member, pseudo_jeu: str, type: app_commands.Choice[str], valeur: app_commands.Choice[str], pseudo_jeu_builder: str | None = None) -> None:

    # 🌐 Vérification "Discord NG".
    server = await require_ng_server(interaction)
    if server is None:
        return

    # 🔐 Vérification RBAC dynamique, propre au serveur détecté.
    if not await has_grade_check(interaction, (f"staff_{server.name}.op" or f"staff_{server.name}.operateur")):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ngstaff_rank"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ngstaff_rank")

    # 🔎 Vérification cohérence type/valeur.
    if type.value == "grade" and valeur.value not in GRADES_ORDER:
        return await interaction.followup.send(
            view=error_container(
                f"**{valeur.name}** n'est pas un grade valide. "
                f"Avec `type:Grade`, choisis parmi : {', '.join(GRADE_LABELS.values())}."
            ),
            ephemeral=True,
        )
    if type.value == "statut" and valeur.value not in STATUTS_SECONDAIRES_ORDER:
        return await interaction.followup.send(
            view=error_container(
                f"**{valeur.name}** n'est pas un statut valide. "
                f"Avec `type:Statut`, choisis parmi : Journaliste, Affilié ou Builder."
            ),
            ephemeral=True,
        )

    cfg = await load_rank_config(server.name)
    existing = await get_staff_member(server.name, membre.id)
    pseudo = pseudo_jeu.strip()

    # 🚀 Gestion du rank-up.
    try:
        if type.value == "grade":
            result = await execute_grade_rank(
                interaction.client, interaction.guild_id, membre, pseudo, valeur.value, cfg, existing,
                server=server.name,
            )
        else:
            result = await execute_statut_rank(
                interaction.client, interaction.guild_id, membre, pseudo, valeur.value, cfg, existing, pseudo_jeu_builder,
                server=server.name,
            )
    except RankValidationError as e:
        view = warning_container(e.message) if e.warning else error_container(e.message)
        return await interaction.followup.send(view=view, ephemeral=True)

    # ✅ Gestion message de confirmation.
    lines = ["• Rôle(s) Discord mis à jour"]
    if result.new_nick:
        lines.append(f"• Pseudo renommé : `{result.new_nick}`")
    if result.builder_pseudo:
        lines.append(f"• Pseudo builder : `{result.builder_pseudo}`")
    lines.append("• Liste staff mise à jour")

    text = f"**{pseudo}** (<@{membre.id}>) → **{result.label}** ✅\n" + "\n".join(lines)
    if result.extra_warning:
        text += f"\n{result.extra_warning}"

    await interaction.followup.send(view=success_container(text), ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@ngstaff_rank.error
async def ngstaff_rank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
