"""
views/mod/automod_alert_view.py — Alerte staff avec bouton "Je m'en occupe".

Container V2 STYLISÉ posté dans le salon d'alerte quand un mute auto se
déclenche (récidive dans la fenêtre configurée). Contient un bouton
persistant qui :
  - vérifie que celui qui clique a la permission Discord native
    `moderate_members` (celui qui peut timeout un user)
  - lève le timeout Discord sur le user muté
  - marque l'alerte comme prise en charge dans la DB (mod_automod_active_alerts)
  - reconstruit le message pour afficher "Pris en charge par X à HH:MM"
  - désactive le bouton

VIEW PERSISTANTE : `timeout=None` + `custom_id` fixe → survit aux redémarrages
du bot. bot.py doit ajouter `bot.add_view(AutomodAlertView())` dans setup_hook.

Format custom_id : `automod_alert:{alert_id}` — l'alert_id est extrait par
un split côté callback (pas par regex : Discord n'accepte pas les patterns).
"""
from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import discord
from discord import ButtonStyle, Interaction
from discord.ui import Button, Container, LayoutView, Separator, TextDisplay

from utils.container_universel import error_container, warning_container
from utils.managers import mod_automod_alert_manager as alert_mgr

log = logging.getLogger(__name__)

DISPLAY_TZ = ZoneInfo("Europe/Paris")

# ============================================================
# 🎨 Construction du message d'alerte
# ============================================================

def build_alert_container(
    *,
    system_display: str,
    user_id: int,
    channel_id: int,
    matched_term: str | None,
    message_excerpt: str | None,
    alert_id: int,
    taken_by_user_id: int | None = None,
    taken_at: datetime | None = None,
    staff_role_id: int | None = None,
) -> LayoutView:
    """
    Construit la vue complète (container + bouton). Utilisée à la fois pour
    l'envoi initial et pour l'update après clic "Je m'en occupe" — le même
    template, avec taken_by/taken_at renseignés dans le second cas.
    """
    view = AutomodAlertView(alert_id=alert_id, is_taken=taken_by_user_id is not None)

    c = Container()
    c.add_item(TextDisplay(f"# 🚨 Mute automatique · {system_display}"))
    c.add_item(Separator())

    body = (
        f"**Membre** : <@{user_id}> (`{user_id}`)\n"
        f"**Salon** : <#{channel_id}>\n"
        f"**Motif** : récidive du système **{system_display}** dans la fenêtre configurée"
    )
    if matched_term:
        body += f"\n**Terme détecté** : `{matched_term}`"
    c.add_item(TextDisplay(body))
    c.add_item(Separator())

    if message_excerpt:
        c.add_item(TextDisplay(f"**Message d'origine** :\n> {message_excerpt[:500]}"))
        c.add_item(Separator())

    if taken_by_user_id is not None and taken_at is not None:
        taken_local = taken_at.astimezone(DISPLAY_TZ)
        c.add_item(TextDisplay(
            f"✅ **Pris en charge** par <@{taken_by_user_id}> "
            f"le {taken_local:%d/%m/%Y à %Hh%M}\n"
            "-# Le mute Discord a été levé."
        ))
    else:
        c.add_item(TextDisplay(
            "🔒 **Membre muté** (timeout Discord natif — max 28 jours).\n"
            "-# Un modérateur doit prendre en charge en cliquant ci-dessous."
        ))
        if staff_role_id is not None:
            c.add_item(TextDisplay(f"-# <@&{staff_role_id}>"))

    c.add_item(Separator())
    c.add_item(TextDisplay("-# GuideOn Studio · Auto-modération"))

    view.attach_container(c)
    return view


# ============================================================
# 🧩 View persistante
# ============================================================

class AutomodAlertView(LayoutView):
    """View persistante portant le bouton "Je m'en occupe"."""

    def __init__(self, *, alert_id: int | None = None, is_taken: bool = False) -> None:
        super().__init__(timeout=None)
        self._alert_id = alert_id
        self._is_taken = is_taken
        # Le container est ajouté par attach_container() après construction
        # du body (voir build_alert_container).

    def attach_container(self, container: Container) -> None:
        # On ajoute le bouton en dernier item du container.
        button = _make_button(self._alert_id, self._is_taken)
        button.callback = self._on_click_take
        container.add_item(button)
        self.add_item(container)

    async def _on_click_take(self, interaction: Interaction) -> None:
        await _handle_take_click(interaction)


def _make_button(alert_id: int | None, is_taken: bool) -> Button:
    """
    Bouton "Je m'en occupe". custom_id encode l'alert_id pour survivre au
    restart (le bot recharge la view via bot.add_view() qui la matche par
    custom_id — l'alert_id est ensuite extrait dans le handler).

    Pour l'enregistrement au démarrage (bot.add_view sans alert_id connu),
    on utilise un placeholder `pending`. Le vrai id est envoyé par les
    messages persistants et récupéré par split côté handler.
    """
    if alert_id is None:
        # Cas enregistrement au démarrage (bot.add_view(AutomodAlertView())).
        return Button(
            label="Je m'en occupe",
            style=ButtonStyle.primary,
            emoji="🛠️",
            custom_id="automod_alert:pending",
        )
    if is_taken:
        return Button(
            label="Pris en charge",
            style=ButtonStyle.secondary,
            emoji="✅",
            disabled=True,
            custom_id=f"automod_alert:{alert_id}",
        )
    return Button(
        label="Je m'en occupe",
        style=ButtonStyle.primary,
        emoji="🛠️",
        custom_id=f"automod_alert:{alert_id}",
    )


# ============================================================
# 🎯 Handler du clic (extrait pour testabilité)
# ============================================================

async def _handle_take_click(interaction: Interaction) -> None:
    # 1. Extraire l'alert_id du custom_id du bouton cliqué.
    custom_id = getattr(interaction.data, "custom_id", None) if interaction.data else None
    if not custom_id and isinstance(interaction.data, dict):
        custom_id = interaction.data.get("custom_id")
    if not custom_id:
        return

    parts = custom_id.split(":", 1)
    if len(parts) != 2 or parts[0] != "automod_alert":
        return

    # Placeholder = message trop vieux, retrouvé via alert_message_id.
    if parts[1] == "pending":
        alert = await alert_mgr.get_alert_by_message(interaction.message.id)
        if alert is None:
            await interaction.response.send_message(
                view=error_container("Cette alerte n'existe plus."),
                ephemeral=True,
            )
            return
        alert_id = alert["id"]
    else:
        try:
            alert_id = int(parts[1])
        except ValueError:
            return
        alert = await alert_mgr.get_alert_by_message(interaction.message.id)
        # Fallback si le message ne correspond plus (dev/prod switch, edit manuel).
        if alert is None:
            await interaction.response.send_message(
                view=error_container("Cette alerte n'existe plus en base."),
                ephemeral=True,
            )
            return

    # 2. Vérif permission Discord native (celui qui peut timeout un user).
    if not isinstance(interaction.user, discord.Member):
        return
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message(
            view=error_container(
                "Vous n'avez pas la permission de **prendre en charge** cette alerte.\n"
                "-# Requis : permission Discord **Modérer les membres**."
            ),
            ephemeral=True,
        )
        return

    # 3. Marquer comme prise (idempotent : si déjà prise, on affiche par qui).
    updated = await alert_mgr.mark_taken(alert_id, interaction.user.id)
    if updated is None:
        await interaction.response.send_message(
            view=error_container("Cette alerte n'existe plus."), ephemeral=True,
        )
        return

    if updated["taken_by_user_id"] != interaction.user.id:
        # Course : quelqu'un d'autre a cliqué juste avant.
        await interaction.response.send_message(
            view=warning_container(
                f"Alerte déjà prise en charge par <@{updated['taken_by_user_id']}>."
            ),
            ephemeral=True,
        )
        return

    # 4. Lever le timeout Discord sur le user (best-effort).
    guild = interaction.guild
    if guild is not None:
        member = guild.get_member(updated["user_id"])
        if member is None:
            try:
                member = await guild.fetch_member(updated["user_id"])
            except (discord.NotFound, discord.HTTPException):
                member = None
        if member is not None:
            try:
                await member.timeout(None, reason=f"Alerte automod prise en charge par {interaction.user}")
            except (discord.Forbidden, discord.HTTPException):
                log.warning(
                    "[AUTOMOD] Levée du timeout échouée guild=%s user=%s",
                    updated["guild_id"], updated["user_id"],
                )

    # 5. Reconstruire la vue pour afficher "Pris en charge".
    # On a besoin du display_name du système + du staff_role_id pour cohérence
    # visuelle. Ces infos sont chargées ici pour éviter les imports circulaires.
    from cogs.events.mod_automod_listener import get_system_display
    from utils.managers import mod_automod_general_manager as general_mgr

    general = await general_mgr.load_general(updated["guild_id"])

    new_view = build_alert_container(
        system_display=get_system_display(updated["system_key"]),
        user_id=updated["user_id"],
        channel_id=updated["channel_id"],
        matched_term=updated["matched_term"],
        message_excerpt=updated["message_excerpt"],
        alert_id=updated["id"],
        taken_by_user_id=updated["taken_by_user_id"],
        taken_at=updated["taken_at"],
        staff_role_id=general.get("staff_role_id"),
    )
    await interaction.response.edit_message(view=new_view)