"""
cogs/dev/avatar_bot.py — Applique/retire l'avatar de bot personnalisé d'un
serveur
Usage :
    /dev avatar_bot id_serveur:<id> image:<fichier>   → applique l'avatar
    /dev avatar_bot id_serveur:<id>                   → retire l'avatar
                                                          (retour au global)
"""

from __future__ import annotations

import logging
from typing import Optional

import discord
from discord import MediaGalleryItem, app_commands, Interaction
from discord.ui import Container, LayoutView, MediaGallery, Separator, TextDisplay

from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande
from utils.perm_check import has_grade_check

from utils.container_universel import error_container
from utils.error_handler import handle_app_command_error
from utils.db.models.boutique import ShopRole
from utils.managers.boutique_manager import add_entry, remove_entry
from utils.managers.bot_avatar_manager import (
    GuildNotFoundError,
    apply_guild_avatar,
    get_current_avatar_url,
    reset_guild_avatar,
    validate_avatar_attachment,
)

log = logging.getLogger(__name__)


# ============================================================
# 🧩 Confirmation visuelle (avec aperçu de l'avatar appliqué)
# ============================================================

def _build_confirmation_view(title: str, body: str, image_url: Optional[str] = None) -> LayoutView:
    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay(title))
    container.add_item(Separator())
    container.add_item(TextDisplay(body))

    if image_url:
        container.add_item(Separator())
        container.add_item(MediaGallery(MediaGalleryItem(media=image_url)))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))

    view.add_item(container)
    return view


# ============================================================
# 🧭 Commande : /dev avatar_bot
# ============================================================

@app_commands.guild_only()
@app_commands.checks.cooldown(1, 10)
@app_commands.command(
    name="avatar_bot",
    description="🖼️ [DEV] Applique/retire l'avatar de bot personnalisé d'un serveur (add-on boutique)",
)
@app_commands.describe(
    id_serveur="ID du serveur cible",
    image="Nouvel avatar à appliquer — laisser vide pour RETIRER l'avatar personnalisé (retour au global)",
)
async def avatar_bot(interaction: Interaction, id_serveur: str, image: Optional[discord.Attachment] = None) -> None:

    # 🔐 Vérification des permissions.
    if not await has_grade_check(interaction, "equipe_guideon.dev", "**gérer l'avatar personnalisé** d'un serveur"):
        return

    # 🕒 Defer.
    try:
        await interaction.response.defer(ephemeral=True)
    except (discord.NotFound, discord.HTTPException):
        return

    # ⚙️ Activation commande.
    if not await verifier_commande(interaction, "dev_avatar_bot"):
        return

    # 📊 Tracking.
    await tracker_commande(interaction, "dev_avatar_bot")

    # 🔎 Vérification de l'ID.
    try:
        guild_id = int(id_serveur)
    except ValueError:
        return await interaction.followup.send(
            view=error_container("`id_serveur` doit être un **identifiant numérique**."), ephemeral=True,
        )

    guild = interaction.client.get_guild(guild_id)
    if guild is None:
        return await interaction.followup.send(
            view=error_container("GuideOn n'est présent sur **aucun serveur** avec cet ID."), ephemeral=True,
        )

    reason = f"Avatar Perso géré par {interaction.user} ({interaction.user.id})"

    # ──────────────────────────────────────────────────────────
    # 🖼️ Avec image → on applique l'avatar personnalisé.
    # ──────────────────────────────────────────────────────────
    if image is not None:
        erreur = validate_avatar_attachment(image)
        if erreur:
            return await interaction.followup.send(view=error_container(erreur), ephemeral=True)

        try:
            image_bytes = await image.read()
        except discord.HTTPException:
            log.exception("[AVATAR_PERSO] Téléchargement de l'image échoué (guild=%s)", guild_id)
            return await interaction.followup.send(
                view=error_container("Impossible de **télécharger** ce fichier — réessayez."), ephemeral=True,
            )

        try:
            await apply_guild_avatar(interaction.client, guild_id, image_bytes, reason=reason)
        except GuildNotFoundError as e:
            return await interaction.followup.send(view=error_container(str(e)), ephemeral=True)
        except discord.Forbidden:
            return await interaction.followup.send(
                view=error_container("Permission **manquante** pour modifier le profil du bot sur ce serveur."),
                ephemeral=True,
            )
        except discord.HTTPException as e:
            log.warning("[AVATAR_PERSO] Discord a refusé l'avatar (guild=%s) : %s", guild_id, e)
            return await interaction.followup.send(
                view=error_container(f"Discord a **refusé** cette image : `{e}`"), ephemeral=True,
            )

        created = await add_entry(ShopRole.AVATAR_PERSO, guild_id)
        suffix = " (nouvel add-on enregistré en boutique)" if created else " (add-on déjà enregistré en boutique)"
        log.info(
            "[AVATAR_PERSO] Avatar appliqué pour %s (%d) | demandé par %d%s",
            guild.name, guild.id, interaction.user.id, suffix,
        )

        preview_url = get_current_avatar_url(interaction.client, guild_id)
        return await interaction.followup.send(
            view=_build_confirmation_view(
                "# 🖼️ Avatar personnalisé appliqué",
                f"**Serveur :** {guild.name} (`{guild.id}`)\n"
                f"**Add-on boutique :** ✅ Avatar Perso{suffix}",
                image_url=preview_url,
            ),
            ephemeral=True,
        )

    # ──────────────────────────────────────────────────────────
    # 🚫 Sans image → on retire l'avatar personnalisé.
    # ──────────────────────────────────────────────────────────
    try:
        await reset_guild_avatar(interaction.client, guild_id, reason=reason)
    except GuildNotFoundError as e:
        return await interaction.followup.send(view=error_container(str(e)), ephemeral=True)
    except discord.Forbidden:
        return await interaction.followup.send(
            view=error_container("Permission **manquante** pour modifier le profil du bot sur ce serveur."),
            ephemeral=True,
        )
    except discord.HTTPException as e:
        log.warning("[AVATAR_PERSO] Discord a refusé le retrait (guild=%s) : %s", guild_id, e)
        return await interaction.followup.send(
            view=error_container(f"Discord a **refusé** cette opération : `{e}`"), ephemeral=True,
        )

    removed = await remove_entry(ShopRole.AVATAR_PERSO, guild_id)
    suffix = " (add-on retiré de la boutique)" if removed else " (le serveur n'avait pas l'add-on enregistré)"
    log.info(
        "[AVATAR_PERSO] Avatar retiré pour %s (%d) | demandé par %d%s",
        guild.name, guild.id, interaction.user.id, suffix,
    )

    await interaction.followup.send(
        view=_build_confirmation_view(
            "# 🖼️ Avatar personnalisé retiré",
            f"**Serveur :** {guild.name} (`{guild.id}`)\n"
            f"Le bot utilise à nouveau son **avatar global** sur ce serveur.{suffix}",
        ),
        ephemeral=True,
    )


# ============================================================
# ❌ Gestion des erreurs
# ============================================================

@avatar_bot.error
async def avatar_bot_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    await handle_app_command_error(interaction, error)
