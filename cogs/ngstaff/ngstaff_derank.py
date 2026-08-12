"""
cogs/ngstaff/ngstaff_derank.py — /ngstaff derank : derank d'un membre du
staff, généralisé multi-serveurs (refonte multi-serveurs, phase 12, §13 du
prompt).

Réplique de cogs/alpha/derank.py — mêmes différences que ngstaff_rank.py
(flow require_ng_server + has_grade_check dynamique, server résolu et passé
explicitement à DerankConfirmView via son kwarg `server`, ajouté phase 12).
"""

from __future__ import annotations

import discord
from discord import Interaction, app_commands

from utils.container_universel import warning_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.ng_rank_config_manager import load_rank_config
from utils.managers.ng_staff_manager import get_staff_member
from utils.ng_server_check import require_ng_server
from utils.perm_check import has_grade_check
from utils.track_commande import tracker_commande
from views.alpha.derank_view import DerankConfirmView

# ============================================================
# 📦 Constantes
# ============================================================

ROLE_CHOICES = [
    app_commands.Choice(name="Complet (staff + autres)", value="complet"),
    app_commands.Choice(name="Staff uniquement", value="staff"),
    app_commands.Choice(name="Journaliste uniquement", value="journaliste"),
    app_commands.Choice(name="Affilié uniquement", value="affilie"),
    app_commands.Choice(name="Builder uniquement", value="builder"),
]


# ============================================================
# 🧭 Commande : /ngstaff derank
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="derank", description="⬇️ [OP] Derank un membre du staff")
@app_commands.describe(membre="Membre Discord à derank", role="Ce qui est retiré (défaut : complet)")
@app_commands.choices(role=ROLE_CHOICES)
async def ngstaff_derank(interaction: Interaction, membre: discord.Member, role: app_commands.Choice[str] = None) -> None:

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
    role_val = role.value if role else "complet"
    cfg = await load_rank_config(server.name)
    confirm_view = DerankConfirmView(
        membre, member_data, cfg, interaction.guild_id, role_val,
        owner_id=interaction.user.id, server=server.name,
    )
    await interaction.followup.send(view=confirm_view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@ngstaff_derank.error
async def ngstaff_derank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
