"""
cogs/birthday/birthday_add.py — Commande /birthday add <date>.

Enregistre la date d'anniversaire de l'utilisateur courant.
Format accepté : `JJ/MM` ou `JJ/MM/AAAA`.

Règles (strict CdC) :
- Une seule date par utilisateur et par serveur
- Pas d'écrasement : si une date existe déjà, refus (l'admin doit la supprimer)
- Validation complète (jour/mois cohérent, année dans une plage raisonnable)

Pipeline :
    verifier_ban_utilisateur → defer → verifier_commande → tracker_commande
    → parse + validate → set_user_birthday
"""
from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import app_commands

from utils.botbancmd import verifier_ban_utilisateur
from utils.container_universel import error_container, success_container
from utils.control_admin import verifier_commande
from utils.error_handler import handle_app_command_error
from utils.managers.birthday_manager import (
    get_user_birthday,
    set_user_birthday,
    validate_date,
)
from utils.track_commande import tracker_commande

log = logging.getLogger(__name__)


def _parse_date_input(s: str) -> Optional[tuple[int, int, Optional[int]]]:
    """
    Parse "JJ/MM" ou "JJ/MM/AAAA". Retourne (day, month, year|None) ou None
    si le format est invalide. NE valide PAS la cohérence (utiliser validate_date).
    """
    s = s.strip()
    parts = s.split("/")
    if len(parts) not in (2, 3):
        return None
    try:
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2]) if len(parts) == 3 else None
    except ValueError:
        return None
    return day, month, year


@app_commands.guild_only()
@app_commands.checks.cooldown(1, 5)
@app_commands.command(
    name="add",
    description="🎂 Enregistre ta date d'anniversaire (format JJ/MM ou JJ/MM/AAAA)",
)
@app_commands.describe(date="Ta date d'anniversaire (JJ/MM ou JJ/MM/AAAA)")
async def birthday_add(interaction: discord.Interaction, date: str) -> None:

    # 🛡️ Vérification ban utilisateur.
    if not await verifier_ban_utilisateur(interaction):
        return

    # 🕒 Defer ephemeral (date de naissance = donnée personnelle).
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Vérification maintenance.
    if not await verifier_commande(interaction, "birthday_add"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "birthday_add")

    # 🚫 Refus des bots (sécurité).
    if interaction.user.bot:
        return

    # 📅 Parse du format.
    parsed = _parse_date_input(date)
    if parsed is None:
        await interaction.followup.send(
            view=error_container(
                "**Format invalide**. Utilise `JJ/MM` ou `JJ/MM/AAAA`.\n"
                "*Exemple :* `15/07` ou `15/07/2000`"
            ),
            ephemeral=True,
        )
        return

    day, month, year = parsed

    # ✅ Validation métier (jour/mois cohérent, année dans la plage).
    ok, error_msg = validate_date(day, month, year)
    if not ok:
        await interaction.followup.send(
            view=error_container(error_msg),
            ephemeral=True,
        )
        return

    # 🚧 Vérification "pas déjà enregistré" (strict CdC).
    existing = await get_user_birthday(interaction.guild.id, interaction.user.id)
    if existing is not None:
        year_txt = f"/{existing['year']}" if existing.get("year") else ""
        await interaction.followup.send(
            view=error_container(
                f"Tu as déjà une date enregistrée : "
                f"**{existing['day']:02d}/{existing['month']:02d}{year_txt}**.\n"
                f"-# Contacte un administrateur pour la modifier."
            ),
            ephemeral=True,
        )
        return

    # 💾 Enregistrement.
    try:
        created = await set_user_birthday(
            interaction.guild.id, interaction.user.id, day, month, year
        )
    except Exception:
        log.exception(
            "Échec set_user_birthday (guild=%s, user=%s)",
            interaction.guild.id, interaction.user.id,
        )
        await interaction.followup.send(
            view=error_container("Une erreur est survenue lors de l'**enregistrement**."),
            ephemeral=True,
        )
        return

    if not created:
        # Race condition : un autre call est passé entre get et set
        await interaction.followup.send(
            view=error_container(
                "Tu as déjà une date enregistrée. Contacte un administrateur pour la modifier."
            ),
            ephemeral=True,
        )
        return

    year_display = f"/{year}" if year else ""
    await interaction.followup.send(
        view=success_container(
            f"Date d'anniversaire enregistrée : **{day:02d}/{month:02d}{year_display}** 🎂"
        ),
        ephemeral=True,
    )


@birthday_add.error
async def birthday_add_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
) -> None:
    await handle_app_command_error(interaction, error)