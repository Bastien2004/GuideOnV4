"""
utils/managers/mod_purge_manager.py — Supprime et recrée un salon (vide son historique).

Technique standard ("clone puis delete") : on clone le salon (même nom,
catégorie, permissions, topic, nsfw, slowmode), on replace le clone à la
position d'origine, PUIS on supprime l'ancien salon. L'ordre clone → delete
(plutôt que delete → create) garantit qu'on ne perd jamais le salon si la
création du clone échoue en cours de route.
"""
from __future__ import annotations

import discord


class PurgeError(Exception):
    """Erreur lors du /mod purge. `warning=True` => avertissement (texte
    neutre), sinon erreur franche."""

    def __init__(self, message: str, *, warning: bool = False):
        super().__init__(message)
        self.message = message
        self.warning = warning


async def purge_channel(
    channel: discord.TextChannel, moderator: discord.Member, *, reason: str | None = None,
) -> discord.TextChannel:
    """
    Clone `channel` (nom, catégorie, permissions, topic, nsfw, slowmode
    conservés), replace le clone à la position d'origine, puis supprime
    l'ancien salon. Retourne le nouveau salon.

    Lève PurgeError en cas d'échec Discord (permissions insuffisantes ou
    erreur HTTP), avant ou après la création du clone.
    """
    full_reason = f"Purge par {moderator} ({moderator.id})"
    if reason:
        full_reason += f" — {reason}"

    try:
        new_channel = await channel.clone(reason=full_reason)
    except discord.Forbidden as e:
        raise PurgeError(
            "Permissions insuffisantes pour créer le salon de remplacement.", warning=True,
        ) from e
    except discord.HTTPException as e:
        raise PurgeError(
            "Une erreur Discord est survenue lors de la création du salon.", warning=False,
        ) from e

    # Le clone est créé en fin de catégorie/serveur : on le replace à la
    # position d'origine. Non bloquant si ça échoue (le salon reste
    # utilisable, juste mal positionné).
    try:
        await new_channel.edit(position=channel.position)
    except discord.HTTPException:
        pass

    try:
        await channel.delete(reason=full_reason)
    except discord.Forbidden as e:
        raise PurgeError(
            "Le nouveau salon a été créé mais l'ancien n'a pas pu être supprimé "
            "(permissions insuffisantes).",
            warning=True,
        ) from e
    except discord.HTTPException as e:
        raise PurgeError(
            "Le nouveau salon a été créé mais la suppression de l'ancien a échoué.",
            warning=False,
        ) from e

    return new_channel
