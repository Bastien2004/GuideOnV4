"""
utils/birthday.py — Logique métier du système d'anniversaire
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import discord

from utils.managers.birthday_manager import get_user_birthday, set_user_birthday, validate_date

log = logging.getLogger(__name__)


# ============================================================
# 🎉 Enregistrement d'une date d'anniversaire
# ============================================================

class BirthdayValidationError(Exception):
    """Problèmle de date (format date invalide, date déjà enregistrée ...)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass
class BirthdayResult:
    """Données pour créer le message d'enregistrement réussit."""

    day: int
    month: int
    year: Optional[int]

    @property
    def display(self) -> str:
        year_txt = f"/{self.year}" if self.year else ""
        return f"{self.day:02d}/{self.month:02d}{year_txt}"


# ============================================================
# 🔩 Fonctions utilitaires
# ============================================================

def parse_date_input(s: str) -> Optional[tuple[int, int, Optional[int]]]:
    """Vérifie le bon format de la date donnée par l'utilisateur."""
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


# ============================================================
# 🎂 Orchestration — extrait de cogs/birthday/birthday_add.py
# ============================================================

async def register_birthday(guild_id: int, user_id: int, date_str: str) -> BirthdayResult:
    """Parse, valide et enregistre une date d'anniversaire.

    Lève BirthdayValidationError si la demande doit être refusée (format
    invalide, date invalide, date déjà enregistrée) ou si l'enregistrement
    échoue techniquement en DB.
    """
    parsed = parse_date_input(date_str)
    if parsed is None:
        raise BirthdayValidationError(
            "**Format invalide**. Utilise `JJ/MM` ou `JJ/MM/AAAA`.\n"
            "*Exemple :* `15/07` ou `15/07/2000`"
        )

    day, month, year = parsed

    ok, error_msg = validate_date(day, month, year)
    if not ok:
        raise BirthdayValidationError(error_msg)

    existing = await get_user_birthday(guild_id, user_id)
    if existing is not None:
        year_txt = f"/{existing['year']}" if existing.get("year") else ""
        raise BirthdayValidationError(
            f"Tu as déjà une date enregistrée : "
            f"**{existing['day']:02d}/{existing['month']:02d}{year_txt}**.\n"
            f"-# Contacte un administrateur pour la modifier."
        )

    try:
        created = await set_user_birthday(guild_id, user_id, day, month, year)
    except Exception:
        log.exception("[BIRTHDAY] Échec set_user_birthday (guild=%s, user=%s)", guild_id, user_id)
        raise BirthdayValidationError("Une erreur est survenue lors de l'**enregistrement**.") from None

    if not created:
        raise BirthdayValidationError(
            "Tu as déjà une **date enregistrée**. Contacte un __administrateur__ pour la **modifier**."
        )

    return BirthdayResult(day=day, month=month, year=year)


# ============================================================
# 🎈 Rôle anniversaire — retrait partagé (scheduler + panneau config)
# ============================================================

async def strip_birthday_role(guild: discord.Guild, role_id: int) -> int:
    """Retire le rôle anniversaire de tous les membres qui le portent actuellement.

    Best-effort (Forbidden/HTTPException loggés et ignorés par membre). Partagé par :
    - cogs/events/birthday_scheduler.py (retrait de minuit, tous les jours) ;
    - views/birthday/config_view.py (dès qu'un admin retire le rôle de la config ou
      réinitialise le système) — sans ça, un membre fêté le matin puis "déconfiguré"
      en cours de journée garde le rôle pour toujours, puisque le scheduler de minuit
      ne peut plus retrouver quel rôle retirer une fois sa référence effacée de la
      configuration (bug identifié lors de l'audit du 2026-10-15).

    Renvoie le nombre de membres à qui le rôle a été retiré avec succès.
    """

    role = guild.get_role(role_id)
    if role is None:
        return 0

    me = guild.me
    if me is not None and role >= me.top_role:
        log.warning(
            "[BIRTHDAY] Rôle %s au-dessus du bot — retrait impossible guild=%s", role_id, guild.id
        )
        return 0

    removed = 0
    for member in list(role.members):
        try:
            await member.remove_roles(role, reason="Anniversaire : rôle retiré")
            removed += 1
        except discord.Forbidden:
            log.warning(
                "[BIRTHDAY] Forbidden retrait rôle %s → %s guild=%s", role.id, member.id, guild.id
            )
        except discord.HTTPException:
            log.exception(
                "[BIRTHDAY] Erreur HTTP retrait rôle %s → %s guild=%s", role.id, member.id, guild.id
            )

    return removed