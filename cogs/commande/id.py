"""
Commande /id — Version 100% CV2 optimisée.
"""

import re
import discord

from discord import app_commands, MediaGalleryItem
from discord.ext import commands

from discord.ui import (
    LayoutView,
    Container,
    TextDisplay,
    Separator,
    MediaGallery,
    ActionRow,
    Button
)

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container


# ============================================================
# 🔎 Extraction ID Discord
# ============================================================

def extract_id(value: str) -> int | None:
    """Extrait un ID Discord depuis une mention ou un texte."""
    match = re.search(r"\d{15,20}", value)
    return int(match.group()) if match else None


# ============================================================
# 🖼️ Récupération URL avatar
# ============================================================

def get_avatar_url(user: discord.User) -> str:
    """Retourne l'URL de l'avatar utilisateur."""

    return user.display_avatar.replace(
        size=1024,
        format="gif" if user.display_avatar.is_animated() else "png"
    ).url


# ============================================================
# 📅 Formatage date création compte
# ============================================================

def get_creation_date(user: discord.User) -> str:
    """Retourne la date de création formatée."""

    return discord.utils.format_dt(
        user.created_at,
        style="F"
    )


# ============================================================
# 🖼️ Section avatar
# ============================================================

def build_avatar_section(container: Container, avatar_url: str) -> None:
    """Ajoute la section avatar."""

    container.add_item(TextDisplay("## 🖼️ Avatar"))

    container.add_item(
        MediaGallery(
            MediaGalleryItem(
                media=avatar_url
            )
        )
    )

    container.add_item(
        ActionRow(
            Button(
                label="Télécharger la PP",
                style=discord.ButtonStyle.link,
                url=avatar_url,
                emoji="📥"
            ),

            Button(
                label="Ouvrir dans le navigateur",
                style=discord.ButtonStyle.link,
                url=avatar_url,
                emoji="🌐"
            )
        )
    )

    container.add_item(Separator())


# ============================================================
# 📌 Section informations utilisateur
# ============================================================

def build_user_infos_section(
    container: Container,
    user: discord.User,
    created_at: str
) -> None:
    """Ajoute les informations utilisateur."""

    container.add_item(
        TextDisplay(
            "## 📌 Informations\n"
            f"**Pseudo :** `{user}`\n"
            f"**Nom affiché :** `{user.display_name}`\n"
            f"**ID :** `{user.id}`\n"
            f"**Bot :** `{'Oui' if user.bot else 'Non'}`\n"
            f"**Compte créé le :** {created_at}"
        )
    )

    container.add_item(Separator())


# ============================================================
# 🧩 Construction view CV2
# ============================================================

def build_user_view(user: discord.User) -> LayoutView:
    """Construit la view CV2 complète."""

    avatar_url = get_avatar_url(user)
    created_at = get_creation_date(user)

    view = LayoutView(timeout=None)

    container = Container()

    # Header
    container.add_item(
        TextDisplay("# 👤 Informations utilisateur")
    )

    container.add_item(Separator())

    # Avatar
    build_avatar_section(
        container,
        avatar_url
    )

    # Informations utilisateur
    build_user_infos_section(
        container,
        user,
        created_at
    )

    # Footer
    container.add_item(
        TextDisplay("-# GuideON Studio")
    )

    view.add_item(container)

    return view


# ============================================================
# 👤 Commande principale
# ============================================================

class UserID(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(
        name="id",
        description="👤 Récupère les informations d’un utilisateur via son ID ou sa mention."
    )
    @app_commands.describe(
        user_id="L’ID ou la mention de l’utilisateur"
    )
    async def id_command(
        self,
        interaction: discord.Interaction,
        user_id: str
    ):

        # 🛡️ Vérification ban utilisateur
        if not await verifier_ban_utilisateur(interaction):
            return

        # ⚙️ Vérification activation commande
        if not await verifier_commande(interaction, "id_command"):
            return

        # ⏳ Defer après maintenance check
        await interaction.response.defer()

        # 📊 Tracking commande
        await tracker_commande(interaction, "id_command")

        # 🔍 Extraction ID
        uid = extract_id(user_id)

        if uid is None:
            return await interaction.followup.send(
                view=error_container(
                    "Format invalide.\n"
                    "Merci de fournir un **ID Discord** ou une **mention valide**."
                ),
                ephemeral=True
            )

        # 🌐 Récupération utilisateur
        try:
            user = await self.bot.fetch_user(uid)

        except discord.NotFound:
            return await interaction.followup.send(
                view=error_container(
                    "Aucun utilisateur trouvé avec cet ID."
                ),
                ephemeral=True
            )

        except discord.HTTPException as e:
            return await interaction.followup.send(
                view=error_container(
                    f"Erreur réseau Discord :\n`{e}`"
                ),
                ephemeral=True
            )

        # 🧩 Construction view
        view = build_user_view(user)

        # 🚀 Envoi
        await interaction.followup.send(
            view=view
        )

    # ============================================================
    # ❌ Gestion des erreurs
    # ============================================================

    @id_command.error
    async def id_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        await handle_app_command_error(
            interaction,
            error
        )


# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(UserID(bot))