"""
cogs/dev/setng.py — /dev setng, /dev unsetng : simulation de serveur NG en
environnement dev (refonte multi-serveurs, phase 5, §9 du prompt).

RÉSERVÉ à settings.env == 'dev' — refuse systématiquement en prod, même
pour un créateur/dev. Permet de tester /ngstaff, /alpha, etc. sur un
Discord de dev en le faisant passer pour n'importe quel serveur NG, sans
jamais toucher la base `guideon` (prod) — la DB dev (`guideon_dev`) est
entièrement séparée (provisioning Bastien, cf §9 du prompt de refonte).
"""
from __future__ import annotations

import logging
from typing import Literal

import discord
from discord import Interaction, app_commands

from utils.container_universel import error_container, send_ephemeral, success_container
from utils.control_admin import verifier_commande
from utils.createur import is_creator
from utils.error_handler import handle_app_command_error
from utils.managers.ng_server_manager import (
    NGServerGuildConflictError,
    NGServerNameConflictError,
    dev_create_server,
    dev_delete_server_by_guild,
)
from utils.managers.permission_rbac_manager import has_grade
from utils.settings import settings
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)

DEV_GRADE_SLUG = "equipe_guideon.dev"


async def _is_authorized(interaction: Interaction) -> bool:
    if is_creator(interaction.user.id):
        return True
    return await has_grade(interaction.user.id, DEV_GRADE_SLUG)


async def _guard(interaction: Interaction) -> bool:
    """Garde commune à /dev setng et /dev unsetng : env=dev + grade dev."""
    if settings.env != "dev":
        await send_ephemeral(
            interaction,
            error_container(
                "Cette commande n'est disponible qu'en environnement **dev** "
                "(`settings.env == 'dev'`)."
            ),
        )
        return False
    if not await _is_authorized(interaction):
        await send_ephemeral(
            interaction, error_container(f"Permission insuffisante ({DEV_GRADE_SLUG}).")
        )
        return False
    return True


# ============================================================
# 🧭 /dev setng
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="setng", description="🧪 [DEV] Simuler ce Discord comme un serveur NG (dev uniquement)")
@app_commands.describe(
    server_name="Nom court du serveur NG à simuler (ex: alpha, delta, sigma)",
    display_name="Nom affiché (défaut : server_name capitalisé)",
    edition="Édition Minecraft du serveur simulé",
)
async def setng(
    interaction: Interaction,
    server_name: str,
    display_name: str | None = None,
    edition: Literal["bedrock", "java"] = "bedrock",
) -> None:
    if not await _guard(interaction):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "dev_setng"):
        return
    await tracker_commande(interaction, "dev_setng")

    name = server_name.strip().lower()
    if not name or not name.replace("_", "").isalnum():
        await interaction.followup.send(
            view=error_container(
                "Le nom doit être alphanumérique (underscores autorisés), ex: `alpha`, `delta`."
            ),
            ephemeral=True,
        )
        return

    try:
        server = await dev_create_server(
            name=name,
            display_name=(display_name or name.capitalize()).strip(),
            edition=edition,
            discord_guild_id=interaction.guild_id,
            active=True,
        )
    except (NGServerNameConflictError, NGServerGuildConflictError) as exc:
        await interaction.followup.send(view=error_container(str(exc)), ephemeral=True)
        return
    except Exception:
        log.exception("[DEV SETNG] Erreur création serveur simulé")
        await interaction.followup.send(
            view=error_container("Erreur lors de la création du serveur simulé."), ephemeral=True
        )
        return

    await interaction.followup.send(
        view=success_container(
            f"Ce Discord simule désormais **{server.display_name}** (`{server.name}`, {server.edition})."
        ),
        ephemeral=True,
    )


# ============================================================
# 🧭 /dev unsetng
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(name="unsetng", description="🧪 [DEV] Retirer la simulation de serveur NG sur ce Discord (dev uniquement)")
async def unsetng(interaction: Interaction) -> None:
    if not await _guard(interaction):
        return

    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    if not await verifier_commande(interaction, "dev_unsetng"):
        return
    await tracker_commande(interaction, "dev_unsetng")

    try:
        removed = await dev_delete_server_by_guild(interaction.guild_id)
    except Exception:
        log.exception("[DEV UNSETNG] Erreur suppression serveur simulé")
        await interaction.followup.send(
            view=error_container("Erreur lors de la suppression du serveur simulé."), ephemeral=True
        )
        return

    if removed is None:
        await interaction.followup.send(
            view=error_container("Ce Discord ne simule aucun serveur NG actuellement."), ephemeral=True
        )
        return

    await interaction.followup.send(
        view=success_container(f"Ce Discord ne simule plus **{removed.display_name}** (`{removed.name}`)."),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion erreurs
# ============================================================

@setng.error
async def setng_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)


@unsetng.error
async def unsetng_error(interaction: Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
