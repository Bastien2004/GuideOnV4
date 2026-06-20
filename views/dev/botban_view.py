"""
views/dev/botban_view.py — Dashboard de gestion des bans globaux du bot.

Flux :
  BotBanView (Bannir | Débannir | Liste)
    Bannir   → UserSelect → _BanModal (raison + durée) → ban_user → DB
    Débannir → UserSelect → confirmation implicite (unban direct si banni)
    Liste    → PaginatedView des bans actifs (triés par expiration)
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.container_universel import error_container, success_container, warning_container
from utils.managers.bot_ban_manager import ban_user, get_ban_info, list_active_bans, unban_user

from views._components.base_view import BaseLayoutView
from views._components.paginated_view import PaginatedView
from views._components.user_select import UserSelect

_MIN_DUREE = 1
_MAX_DUREE = 9999  # convention : ban "permanent"


# ── Helper retour main ───────────────────────────────────────

def _back_to_main(owner_id: int) -> BotBanView:
    return BotBanView(owner_id)


# ════════════════════════════════════════════════════════════
# 🏠 Vue principale
# ════════════════════════════════════════════════════════════

class BotBanView(BaseLayoutView):
    """Dashboard principal : 3 boutons d'action."""

    def __init__(self, owner_id: int) -> None:
        super().__init__(owner_id=owner_id, timeout=300)
        self._build()

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 🚫 Gestion des bans GuideOn"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Bannir un utilisateur l'empêche d'utiliser **toutes** les commandes du bot, "
            "sur **tous** les serveurs.\n\n"
            f"-# Tous les bans sont des tempbans ({_MIN_DUREE}-{_MAX_DUREE} jours). "
            f"Pour un ban de facto permanent, utilise {_MAX_DUREE} jours."
        ))
        c.add_item(Separator())

        btn_ban = Button(label="🚫 Bannir", style=ButtonStyle.danger, custom_id="botban_ban")
        btn_unban = Button(label="✅ Débannir", style=ButtonStyle.success, custom_id="botban_unban")
        btn_list = Button(label="📋 Liste des bannis", style=ButtonStyle.secondary, custom_id="botban_list")
        btn_ban.callback = self._on_ban
        btn_unban.callback = self._on_unban
        btn_list.callback = self._on_list

        c.add_item(ActionRow(btn_ban, btn_unban, btn_list))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_ban(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_UserSelectView(
            owner_id=self.owner_id,
            title="## 🚫 Bannir un utilisateur",
            desc="Sélectionne l'utilisateur Discord à bannir de GuideOn.",
            on_select=self._after_select_ban,
        ))

    async def _on_unban(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_UserSelectView(
            owner_id=self.owner_id,
            title="## ✅ Débannir un utilisateur",
            desc="Sélectionne l'utilisateur Discord à débannir de GuideOn.",
            on_select=self._after_select_unban,
        ))

    async def _on_list(self, interaction: Interaction) -> None:
        bans = await list_active_bans()
        await interaction.response.edit_message(view=_BanListView(bans, owner_id=self.owner_id))

    async def _after_select_ban(self, interaction: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        member = interaction.guild.get_member(uid) if interaction.guild else None
        label = str(member) if member else f"<@{uid}>"

        async def on_submit(inter: Interaction, raison: str, duree_jours: int) -> None:
            await ban_user(uid, raison, inter.user.id, duree_jours)
            await inter.response.edit_message(
                view=_ResultView(
                    owner_id=self.owner_id,
                    message=f"**{label}** a été **banni** de GuideOn pour `{duree_jours}` jour(s).\nRaison : {raison}",
                    success=True,
                )
            )

        modal = _BanModal(target_label=label, on_submit=on_submit)
        await interaction.response.send_modal(modal)

    async def _after_select_unban(self, interaction: Interaction, user_ids: list[int]) -> None:
        uid = user_ids[0]
        member = interaction.guild.get_member(uid) if interaction.guild else None
        label = str(member) if member else f"<@{uid}>"

        existing = await get_ban_info(uid)
        if existing is None:
            return await interaction.response.edit_message(
                view=_ResultView(
                    owner_id=self.owner_id,
                    message=f"**{label}** n'est pas banni de GuideOn.",
                    success=False,
                )
            )

        await unban_user(uid)
        await interaction.response.edit_message(
            view=_ResultView(
                owner_id=self.owner_id,
                message=f"**{label}** a été **débanni** de GuideOn.",
                success=True,
            )
        )


# ════════════════════════════════════════════════════════════
# 🔘 Sous-vue : UserSelect générique
# ════════════════════════════════════════════════════════════

class _UserSelectView(BaseLayoutView):
    def __init__(self, owner_id: int, title: str, desc: str, on_select) -> None:
        super().__init__(owner_id=owner_id, timeout=120)
        self._on_select_cb = on_select
        self._build(title, desc)

    def _build(self, title: str, desc: str) -> None:
        c = Container()
        c.add_item(TextDisplay(title))
        c.add_item(Separator())
        c.add_item(TextDisplay(desc))

        select = UserSelect(placeholder="Sélectionner un membre Discord", on_select=self._on_select_cb)
        c.add_item(ActionRow(select))
        c.add_item(Separator())

        btn_back = Button(label="↩️ Retour", style=ButtonStyle.secondary, custom_id="botban_usel_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        c.add_item(TextDisplay("-# GuideOn Studio"))
        self.add_item(c)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_back_to_main(self.owner_id))


# ════════════════════════════════════════════════════════════
# 📝 Modal de ban (raison + durée)
# ════════════════════════════════════════════════════════════

class _BanModal(discord.ui.Modal):
    def __init__(self, target_label: str, on_submit) -> None:
        super().__init__(title=f"Bannir — {target_label}"[:45])
        self._on_submit_cb = on_submit

        self.raison = discord.ui.TextInput(
            label="Raison du ban",
            placeholder="Ex: Spam de commandes, abus répétés...",
            style=discord.TextStyle.paragraph,
            min_length=3, max_length=512,
            required=True,
        )
        self.duree = discord.ui.TextInput(
            label=f"Durée en jours ({_MIN_DUREE}-{_MAX_DUREE})",
            placeholder=f"Ex: 7, 30, {_MAX_DUREE} pour un ban permanent",
            min_length=1, max_length=4,
            required=True,
        )
        self.add_item(self.raison)
        self.add_item(self.duree)

    async def on_submit(self, interaction: Interaction) -> None:
        raw = self.duree.value.strip()
        if not raw.isdigit():
            return await interaction.response.send_message(
                view=error_container("La durée doit être un **nombre entier** de jours."),
                ephemeral=True,
            )
        duree_jours = int(raw)
        if not (_MIN_DUREE <= duree_jours <= _MAX_DUREE):
            return await interaction.response.send_message(
                view=error_container(f"La durée doit être comprise entre `{_MIN_DUREE}` et `{_MAX_DUREE}` jours."),
                ephemeral=True,
            )
        await self._on_submit_cb(interaction, self.raison.value.strip(), duree_jours)


# ════════════════════════════════════════════════════════════
# ✅ Sous-vue : résultat d'une action
# ════════════════════════════════════════════════════════════

class _ResultView(BaseLayoutView):
    def __init__(self, owner_id: int, message: str, success: bool) -> None:
        super().__init__(owner_id=owner_id, timeout=120)
        c = success_container(message) if success else warning_container(message)
        # success_container/warning_container retournent déjà un LayoutView
        # complet — on récupère son unique Container pour l'intégrer ici
        # avec le bouton retour, plutôt que d'empiler deux LayoutView.
        for item in c.children:
            self.add_item(item)

        retour = Container()
        btn_back = Button(label="↩️ Retour au menu", style=ButtonStyle.secondary, custom_id="botban_result_back")
        btn_back.callback = self._on_back
        retour.add_item(ActionRow(btn_back))
        self.add_item(retour)

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_back_to_main(self.owner_id))


# ════════════════════════════════════════════════════════════
# 📋 Sous-vue : liste paginée des bannis
# ════════════════════════════════════════════════════════════

class _BanListView(PaginatedView):
    def __init__(self, bans: list[dict], *, owner_id: int) -> None:
        super().__init__(bans, per_page=8, owner_id=owner_id, timeout=180)

    def build_page_container(self, page_items: list[dict]) -> Container:
        c = Container()
        c.add_item(TextDisplay("# 📋 Bannis GuideOn"))
        c.add_item(Separator())

        if not page_items:
            c.add_item(TextDisplay("*Aucun utilisateur banni actuellement.*"))
        else:
            lines = []
            for ban in page_items:
                lines.append(
                    f"**<@{ban['discord_id']}>** (`{ban['discord_id']}`)\n"
                    f"⇝ Raison : {ban['raison']}\n"
                    f"⇝ Expire : <t:{int(ban['expiration'].timestamp())}:R>\n"
                    f"⇝ Par : <@{ban['moderator_id']}>"
                )
            c.add_item(TextDisplay("\n\n".join(lines)))

        c.add_item(Separator())
        btn_back = Button(label="↩️ Retour au menu", style=ButtonStyle.secondary, custom_id="botban_list_back")
        btn_back.callback = self._on_back
        c.add_item(ActionRow(btn_back))
        return c

    async def _on_back(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=_back_to_main(self.owner_id))