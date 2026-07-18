"""
views/user/user_picker_view.py — Page de sélection utilisateur pour /user.
"""

from __future__ import annotations

import discord
from discord.ui import ActionRow, Container, Separator, TextDisplay

from utils.container_universel import error_container
from views._components.base_view import BaseLayoutView
from views._components.user_select import UserSelect
from views.user.user_view import build_user_view


class UserLookupView(BaseLayoutView):
    """Menu déroulant : sélectionne un membre, affiche sa carte de profil sur place."""

    def __init__(self, *, owner_id: int, bot: discord.Client) -> None:
        super().__init__(owner_id=owner_id, timeout=120)
        self._bot = bot

        container = Container()
        container.add_item(TextDisplay("# <:profil:1495444182137831515> Rechercher un profil"))
        container.add_item(Separator())
        container.add_item(TextDisplay(
            "Sélectionne un membre dans le menu ci-dessous pour afficher son profil."
        ))
        container.add_item(ActionRow(
            UserSelect(placeholder="Choisir un utilisateur", on_select=self._on_select)
        ))
        container.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(container)

    async def _on_select(self, interaction: discord.Interaction, ids: list[int]) -> None:
        uid = ids[0]

        # 🌐 Récupération utilisateur — mêmes erreurs, mêmes messages que /id.
        try:
            user = await self._bot.fetch_user(uid)
        except discord.NotFound:
            await interaction.response.send_message(
                view=error_container("**Aucun utilisateur** trouvé avec cet __ID__."),
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                view=error_container(f"Erreur **réseau** Discord :\n`{e}`"),
                ephemeral=True,
            )
            return

        # 🧩 Même carte de profil que /id, affichée à la place du menu.
        view = build_user_view(user)
        await self.push_update(interaction, view=view)