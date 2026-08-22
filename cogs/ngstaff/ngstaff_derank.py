"""
cogs/ngstaff/ngstaff_derank.py — /ngstaff derank : derank d'un membre du
staff, généralisé multi-serveurs (refonte multi-serveurs, phase 12, §13 du
prompt).

Réplique de cogs/alpha/derank.py — mêmes différences que ngstaff_rank.py
(flow require_ng_server + has_grade_check dynamique, server résolu et passé
explicitement à DerankConfirmView via son kwarg `server`, ajouté phase 12).

Statuts (Paul, 2026-08-22) : `role` était une liste FIGÉE de 5 valeurs
(complet/staff/journaliste/affilie/builder) — impossible à faire varier par
serveur. Converti en paramètre `str` avec `@app_commands.autocomplete`, qui
propose "Complet"/"Staff uniquement" plus chaque statut défini pour le
serveur NG détecté.
"""

from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.container_universel import error_container, warning_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.ng_server_manager import get_server_by_guild
from utils.managers.ng_staff_manager import get_staff_member
from utils.managers.ng_statut_manager import list_statut_defs
from utils.ng_server_check import require_ng_server
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande
from views.ngstaff.derank_view import DerankConfirmView

# ============================================================
# 📦 Constantes
# ============================================================

_BASE_ROLE_CHOICES = [
    ("complet", "Complet (staff + autres)"),
    ("staff", "Staff uniquement"),
]


async def role_autocomplete(interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Propose "Complet"/"Staff uniquement" plus chaque statut défini pour
    le serveur NG détecté."""
    current_lower = current.lower().strip()
    choices = [
        app_commands.Choice(name=label, value=key)
        for key, label in _BASE_ROLE_CHOICES
        if current_lower in label.lower()
    ]

    server = get_server_by_guild(interaction.guild_id)
    if server is not None:
        statut_defs = await list_statut_defs(server.name)
        choices += [
            app_commands.Choice(name=f"{d['label']} uniquement", value=d["key"])
            for d in statut_defs
            if current_lower in d["label"].lower()
        ]

    return choices[:25]


# ============================================================
# 🧭 Commande : /ngstaff derank
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="derank", description="⬇️ [OP] Derank un membre du staff")
@app_commands.describe(membre="Membre Discord à derank", role="Ce qui est retiré (défaut : complet)")
@app_commands.autocomplete(role=role_autocomplete)
async def ngstaff_derank(interaction: Interaction, membre: discord.Member, role: str | None = None) -> None:

    # 🌐 Vérification "Discord NG" (résout le serveur, sinon message + return).
    server = await require_ng_server(interaction)
    if server is None:
        return

    # 🔐 Vérification RBAC dynamique, propre au serveur détecté.
    if not await has_grade_check(interaction, f"staff_{server.name}.op"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "ngstaff_derank"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "ngstaff_derank")

    # 🔎 Vérification que le membre est dans le staff.
    member_data = await get_staff_member(server.name, membre.id)
    if member_data is None:
        return await interaction.followup.send(
            view=warning_container(f"**{membre.display_name}** n'est pas dans la **liste du staff** `{server.name}`."),
            ephemeral=True,
        )

    # 🧩 Ouverture de la confirmation de derank.
    role_val = (role or "complet").strip()
    statut_defs = await list_statut_defs(server.name)

    # 🔎 Vérification cohérence : "role" n'est plus contraint par Discord
    # (str + autocomplete, pas de app_commands.choices) — un utilisateur
    # peut saisir n'importe quoi sans passer par l'autocomplete.
    valid_keys = {"complet", "staff"} | {d["key"] for d in statut_defs}
    if role_val not in valid_keys:
        noms = ", ".join(["Complet", "Staff"] + [d["label"] for d in statut_defs])
        return await interaction.followup.send(
            view=error_container(f"**{role_val}** n'est pas une valeur valide pour `role`. Choisis parmi : {noms}."),
            ephemeral=True,
        )

    cfg = await load_rank_config(server.name)
    confirm_view = DerankConfirmView(
        membre, member_data, cfg, interaction.guild_id, role_val,
        owner_id=interaction.user.id, server=server.name, statut_defs=statut_defs,
    )
    await interaction.followup.send(view=confirm_view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@ngstaff_derank.error
async def ngstaff_derank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)