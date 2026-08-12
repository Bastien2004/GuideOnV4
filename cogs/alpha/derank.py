"""
cogs/alpha/derank.py — Gestion du derank staff Alpha.
"""

from __future__ import annotations

import discord
from discord import app_commands, Interaction

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.container_universel import warning_container
from utils.error_handler import handle_app_command_error
from utils.perm_alpha import check_op_alpha

from utils.managers.ng_staff_manager import get_staff_member
from utils.managers.ng_rank_config_manager import load_rank_config
from views.alpha.derank_view import DerankConfirmView

# Refonte multi-serveurs (§7 du prompt) : câblé en dur sur "alpha" en
# permanence. Un équivalent générique /ngstaff existe (phase 12, voir
# PHASE_12.md) mais ce fichier — /alpha — reste volontairement inchangé :
# la logique partagée (utils/alpha_rank_logic.py, alpha_derank_logic.py,
# refresh_staff_message) accepte `server` en kwarg-only avec défaut
# "alpha", donc cette commande continue de se comporter à l'identique
# sans jamais passer `server=`.
SERVER = "alpha"


# ============================================================
# 📦 Constantes
# ============================================================

ROLE_CHOICES = [
    app_commands.Choice(name="Complet (staff + autres)"       , value="complet"),
    app_commands.Choice(name="Staff uniquement"               , value="staff"),
    app_commands.Choice(name="Journaliste uniquement"         , value="journaliste"),
    app_commands.Choice(name="Affilié uniquement"             , value="affilie"),
    app_commands.Choice(name="Builder uniquement"             , value="builder"),
]


# ============================================================
# 🧭 Commande : /alpha derank
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="derank", description="⬇️ [OP] Derank un membre du staff Alpha")
@app_commands.describe(membre="Membre Discord à derank", role="Ce qui est retiré (défaut : complet)")
@app_commands.choices(role=ROLE_CHOICES)
async def alpha_derank(interaction: Interaction, membre: discord.Member, role: app_commands.Choice[str] = None) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Vérification des permissions.
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
    member_data = await get_staff_member(SERVER, membre.id)
    if member_data is None:
        return await interaction.followup.send(
            view=warning_container(f"**{membre.display_name}** n'est pas dans la **liste du staff** Alpha."),
            ephemeral=True,
        )

    # 🧩 Ouverture de la confirmation de derank.
    role_val = role.value if role else "complet"
    cfg = await load_rank_config(SERVER)
    confirm_view = DerankConfirmView(
        membre, member_data, cfg, interaction.guild_id, role_val,
        owner_id=interaction.user.id,
    )
    await interaction.followup.send(view=confirm_view, ephemeral=True)


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@alpha_derank.error
async def alpha_derank_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
