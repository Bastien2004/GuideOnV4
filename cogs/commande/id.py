"""
Commande /id — Affiche les informations d'un utilisateur à partir de son identifiant ou de sa mention.
"""

import re
import discord

from discord import app_commands
from discord.ext import commands
from discord.ui import LayoutView, Container, TextDisplay, Separator

from utils.botbancmd import verifier_ban_utilisateur
from utils.control_admin import verifier_commande
from utils.track_commande import tracker_commande

from utils.error_handler import handle_app_command_error
from utils.container_universel import error_container


# ============================================================
# 🔎 Extraction ID Discord
# ============================================================

def extract_id(value: str) -> int | None:
    """Extrait un ID Discord depuis une mention."""
    match = re.search(r"\d{15,20}", value)
    return int(match.group()) if match else None


# ============================================================
# 👤 Commande principale : /id
# ============================================================

class UserID(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guild_only()
    @app_commands.checks.cooldown(1, 10)
    @app_commands.command(name="id", description="👤 Récupère les informations d’un utilisateur via son ID")
    @app_commands.describe(user_id="L’ID ou la mention de l’utilisateur")
    async def id_command(self, interaction: discord.Interaction, user_id: str):

        # 🛡️ Vérification ban utilisateur
        if not await verifier_ban_utilisateur(interaction):
            return

        # ⚙️ Vérification activation commande
        if not await verifier_commande(interaction, "id_command"):
            return

        # 📊 Tracking commande
        await tracker_commande(interaction, "id_command")

        # 🔍 Extraction ID
        uid = extract_id(user_id)

        if uid is None:
            return await interaction.response.send_message(
                view=error_container(
                    "Format invalide.\nMerci de fournir un **ID Discord** ou une **mention valide**."
                ),
                ephemeral=True
            )

        # 🌐 Récupération utilisateur
        try:
            user = await self.bot.fetch_user(uid)

        except discord.NotFound:
            return await interaction.response.send_message(
                view=error_container(
                    "Aucun utilisateur trouvé avec cet ID."
                ),
                ephemeral=True
            )

        except discord.HTTPException as e:
            return await interaction.response.send_message(
                view=error_container(
                    f"Erreur réseau Discord :\n`{e}`"
                ),
                ephemeral=True
            )

        # ============================================================
        # 🧩 Construction CV2
        # ============================================================

        created_at = discord.utils.format_dt(user.created_at, style="F")

        view = LayoutView(timeout=None)
        c = Container()

        c.add_item(TextDisplay("# 👤 Informations utilisateur"))
        c.add_item(Separator())

        # Avatar
        c.add_item(
            TextDisplay(
                f"## 🖼️ Avatar\n"
                f"{user.display_avatar.url}"
            )
        )

        c.add_item(Separator())

        # Informations utilisateur
        c.add_item(
            TextDisplay(
                f"### 📌 Informations\n"
                f"**Pseudo :** `{user}`\n"
                f"**Nom affiché :** `{user.display_name}`\n"
                f"**ID :** `{user.id}`\n"
                f"**Bot :** `{'Oui' if user.bot else 'Non'}`\n"
                f"**Compte créé le :** {created_at}"
            )
        )

        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideON Studio"))

        view.add_item(c)

        await interaction.response.send_message(view=view)

# ============================================================
# ❌ Gestion des erreurs
# ============================================================

    @id_command.error
    async def id_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        await handle_app_command_error(interaction, error)

# ============================================================
# 🚀 Setup du Cog
# ============================================================

async def setup(bot: commands.Bot):
    await bot.add_cog(UserID(bot))