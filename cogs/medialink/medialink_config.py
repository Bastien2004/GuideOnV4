"""
cogs/medialink/medialink_config.py — cogs/mod/mod_config.py exactement
(ban check → admin check → defer → maintenance check → tracker →
dashboard), appliqué à /medialink config.

Verrouillage : permission Discord `administrator` du serveur, via
utils.perm_admin.check_admin — PAS de permissions internes séparées
(MEDIALINK_VIEW/MANAGE/CONFIG/...), conformément à la correction de
Paul : "oublie la partie perm interne, il faut la perm admin du serveur
Discord."

NOTE — §14 du cahier ("commande principale" + "sous-commandes") : TOUTES
les commandes de ce bot sont regroupées sous un Group thématique
(utils/groupes.py — GroupeMOD→/mod, GroupeNGSTAFF→/ngstaff, etc.), il
n'y a AUCUNE commande racine isolée. MEDIALINK suit donc ce même moule :
un nouveau GroupeMEDIALINK (name="medialink"), et cette commande devient
`/medialink config` — exactement comme `/mod config` ou `/ngstaff
config` ouvrent le dashboard de leur domaine. Les futures actions plus
ponctuelles du cahier (ex: forcer un check de connexion) pourront
devenir d'autres sous-commandes du même groupe plutôt que des boutons,
si Paul préfère suivre le modèle mod_ban/mod_kick/... (actions séparées)
plutôt que le modèle mod_config (un dashboard unique) pour ces cas-là.

Câblage à ajouter dans utils/groupes.py (nouvelle entrée, à la suite des
autres) :

    class GroupeMEDIALINK(app_commands.Group):
        def __init__(self):
            super().__init__(name="medialink", description="Commandes MEDIALINK")

    def groupeMEDIALINK():
        return GroupeMEDIALINK()

Et dans bot.py (à la suite du bloc "🛡️ ── MOD ──", même endroit où les
autres groupes sont instanciés puis ajoutés à self.tree) :

    from cogs.medialink.medialink_config import medialink_config

    groupMEDIALINK = groupeMEDIALINK()
    for cmd in [medialink_config]:
        groupMEDIALINK.add_command(cmd)

    # ... puis ajouter groupMEDIALINK à la liste existante :
    for group in [groupCONFIG, groupNG, groupTICKET, groupINV, groupBIRTHDAY,
                  groupGIVE, groupEXP, groupMOD, groupQR, groupMEDIALINK]:
        self.tree.add_command(group)
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.perm_admin import check_admin
from utils.track_commande import tracker_commande

from views.medialink.medialink_dashboard_view import MediaLinkDashboardView

log = logging.getLogger(__name__)


# ============================================================
# 🧭 Commande : /medialink config
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="config", description="📡 Configure les annonces MEDIALINK du serveur")
async def medialink_config(interaction: discord.Interaction) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🔐 Verrouillage strict Admin Discord (pas de permission interne
    # séparée — cf. docstring de module).
    if not await check_admin(interaction, "configurer **MEDIALINK** du serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "medialink_config"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "medialink_config")

    # 💻 Envoi du dashboard.
    try:
        view = await MediaLinkDashboardView.build(
            guild=interaction.guild, owner_id=interaction.user.id,
        )
        await interaction.followup.send(view=view, ephemeral=True)
    except Exception:
        log.exception("[MEDIALINK CONFIG] Ouverture dashboard échouée guild=%s", interaction.guild.id)
        await interaction.followup.send(
            view=error_container("Impossible d'ouvrir le **dashboard MEDIALINK**."),
            ephemeral=True,
        )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@medialink_config.error
async def medialink_config_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
