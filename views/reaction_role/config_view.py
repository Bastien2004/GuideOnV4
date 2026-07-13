"""
views/reaction_role/config_view.py — Interface de configuration du système de rôle reaction.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Modal, Section, Separator, TextDisplay, TextInput

from utils.boutique.gold_manager import is_gold
from utils.container_universel import error_container, success_container
from views._components.base_view import BaseLayoutView
from views._components.select_page import SelectPageView
from utils.managers.reaction_role_manager import (
    creer_message_reaction,
    nettoyer_messages_supprimes,
    obtenir_limite_couples,
    obtenir_limite_messages,
    obtenir_tous_messages,
    peut_creer_message,
    supprimer_message_reaction,
)

from utils.settings import settings

log = logging.getLogger(__name__)


# ============================================================
# 🔩 Paramètres
# ============================================================

DEFAULT_TEXT = "Choisissez le rôle qui vous plaît selon les emojis ci-dessous."


# ============================================================
# 🛠️ Fonctions utilitaires (UI)
# ============================================================

def _progress_bar(current: int, maximum: int, length: int = 5) -> str:
    """Gère la barre de progression."""
    if maximum <= 0:
        return "▱" * length
    filled = round((current / maximum) * length)
    filled = max(0, min(filled, length))
    return "▰" * filled + "▱" * (length - filled)


def _preview(text: str, max_len: int = 40) -> str:
    """Raccourcit le texte pour affichage."""
    return (text[:max_len] + "…") if len(text) > max_len else text


# ============================================================
# 📑 Modals (texte + emoji)
# ============================================================

class MessageTextModal(Modal, title="✏️ Modifier le texte du message"):
    def __init__(self, current_text: str):
        super().__init__()
        self.value: Optional[str] = None
        self.text_input = TextInput(
            label="Texte affiché dans le message",
            style=discord.TextStyle.paragraph,
            default=current_text or DEFAULT_TEXT,
            max_length=1000,
            required=True,
            placeholder="Ex : Réagissez avec un emoji pour obtenir votre rôle !",
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: Interaction):
        value = (self.text_input.value or "").strip()
        if not value:
            return await interaction.response.send_message(
                view=error_container("Le message ne peut pas être **vide**."), ephemeral=True
            )
        self.value = value
        await interaction.response.defer()


class EmojiModal(Modal, title="😀 Choisir un emoji"):
    def __init__(self, default: str = "", *, on_valid: Callable[[Interaction, str], Awaitable[None]]):
        super().__init__()
        self._on_valid = on_valid
        self.input = TextInput(
            label="Emoji (standard ou personnalisé)",
            placeholder="🎮  ou  <:nom:123456789>  ou  <a:nom:123456789>",
            default=default,
            max_length=100,
            required=True,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: Interaction):
        raw = (self.input.value or "").strip()
        if not raw:
            return await interaction.response.send_message(
                view=error_container("Veuillez entrer un **emoji valide**."), ephemeral=True
            )
        if raw.startswith("<") and raw.endswith(">"):
            try:
                parsed = discord.PartialEmoji.from_str(raw)
                if parsed.id is None:
                    raise ValueError("Pas d'ID")
                emoji = raw
            except Exception:
                return await interaction.response.send_message(
                    view=error_container(
                        "Format d'emoji personnalisé invalide.\n"
                        "-# Utilisez `<:nom:123456789>` ou `<a:nom:123456789>`"
                    ),
                    ephemeral=True,
                )
        else:
            if len(raw) > 8:
                return await interaction.response.send_message(
                    view=error_container("Cet __emoji__ ne semble **pas valide**."), ephemeral=True
                )
            emoji = raw
        await self._on_valid(interaction, emoji)


# ============================================================
# 💻 View publique
# ============================================================

def build_sent_message_view(text: str, guild: discord.Guild, couples: list[dict[str, Any]]) -> LayoutView:
    """Interface publique envoyée dans le salon cible."""

    view = LayoutView(timeout=None)
    container = Container()

    container.add_item(TextDisplay("# 🎭 Rôles Réaction"))
    container.add_item(Separator())

    container.add_item(TextDisplay(text or DEFAULT_TEXT))
    container.add_item(Separator())
    lines = [
        f"{c['emoji']} → {role.mention}"
        for c in couples
        if (role := guild.get_role(c["role_id"]))
    ]

    couples_text = "\n".join(lines) if lines else "_Aucun rôle configuré._"

    container.add_item(TextDisplay(f"## Rôles disponibles\n{couples_text}"))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))
    
    view.add_item(container)
    return view


# ============================================================
# 🧩 View de configuration
# ============================================================

async def create_reaction_role_view(guild_id: int, bot, page: str = "main", data: Optional[dict[str, Any]] = None, author_id: Optional[int] = None) -> Optional[BaseLayoutView]:
    """Constrution de l'interface de création."""

    try:
        await nettoyer_messages_supprimes(guild_id, bot)
    except Exception:
        log.exception("[Rôle-Réaction] Nettoyage des messages non bloquant échoué (guild=%s)", guild_id)

    if data is None:
        data = {"text": DEFAULT_TEXT, "couples": [], "channel": None}
    else:
        data.setdefault("text", DEFAULT_TEXT)
        data.setdefault("couples", [])
        data.setdefault("channel", None)
        if not isinstance(data["couples"], list):
            data["couples"] = []
        data["couples"] = [
            c for c in data["couples"]
            if isinstance(c, dict) and "emoji" in c and "role_id" in c
        ]

    guild = bot.get_guild(guild_id)
    if not guild:
        log.error("[Rôle-Réaction] Guild %s introuvable", guild_id)
        return None
    if not guild.me.guild_permissions.manage_roles:
        log.warning("[Rôle-Réaction] Permission manage_roles manquante (guild=%s)", guild_id)
        return None

    is_gold_server = is_gold(guild_id)
    limite_couples = obtenir_limite_couples(guild_id)

    view = BaseLayoutView(owner_id=author_id, timeout=600)
    container = Container()

    if page == "main":
        await _build_main(container, guild_id, bot, is_gold_server, author_id)
    elif page == "create":
        await _build_create(
            container, guild, guild_id, bot, data, is_gold_server,
            limite_couples, author_id,
        )
    elif page == "list":
        await _build_list(container, guild_id, bot, author_id)
    else:
        log.error("[Rôle-Réaction] page inconnue '%s' (guild=%s)", page, guild_id)
        return None

    view.add_item(container)
    return view


async def _build_main(container, guild_id, bot, is_gold_server, author_id):
    """Construction de la page d'accueil."""

    messages = await obtenir_tous_messages(guild_id)
    limite = obtenir_limite_messages(guild_id)
    nb = len(messages)
    restant = max(0, limite - nb)
    progress = _progress_bar(nb, limite)

    container.add_item(TextDisplay("# 🎭 Rôles Réaction"))
    container.add_item(Separator())

    upgrade_hint = "" if is_gold_server else "\n-# 💡 Passez Gold pour débloquer plus de messages"
    
    container.add_item(TextDisplay(
        f"### 📊 Utilisation\n"
        f"`{progress}` **{nb} / {limite}** message(s) — {restant} slot(s) disponible(s)"
        f"{upgrade_hint}"
    ))
    container.add_item(Separator())

    peut_creer, raison = await peut_creer_message(guild_id)
    create_btn = Button(label="Créer un message", style=ButtonStyle.success,
                        emoji="📝", disabled=not peut_creer)

    async def create_cb(inter: Interaction):
        new_view = await create_reaction_role_view(
            guild_id, bot, "create",
            data={"text": DEFAULT_TEXT, "couples": [], "channel": None},
            author_id=author_id,
        )
        if new_view:
            await inter.response.edit_message(view=new_view)
        else:
            await inter.response.send_message(
                view=error_container("Impossible d'ouvrir l'**interface de création**."), ephemeral=True
            )

    create_btn.callback = create_cb
    create_sub = raison if not peut_creer else "Configurer un nouveau message de rôle-réaction"
    container.add_item(Section(
        TextDisplay(f"**📝 Nouveau message**\n-# {create_sub}"), accessory=create_btn
    ))
    container.add_item(Separator())

    list_btn = Button(label="Mes messages", style=ButtonStyle.primary,
                      emoji="📋", disabled=not messages)

    async def list_cb(inter: Interaction):
        new_view = await create_reaction_role_view(guild_id, bot, "list", author_id=author_id)
        if new_view:
            await inter.response.edit_message(view=new_view)

    list_btn.callback = list_cb
    list_sub = ("Aucun message configuré pour le moment" if not messages
                else f"{nb} message(s) actif(s) · cliquez pour gérer")
    container.add_item(Section(
        TextDisplay(f"**📋 Messages existants**\n-# {list_sub}"), accessory=list_btn
    ))
    container.add_item(Separator())

    container.add_item(ActionRow(Button(
        label="Documentation", style=ButtonStyle.link, url=settings.doc_url, emoji="📚"
    )))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideON Studio"))


async def _build_create(container, guild, guild_id, bot, data, is_gold_server, limite_couples, author_id):
    """Création d'un nouveau message rôle réaction."""

    couples = data["couples"]
    channel_id = data["channel"]
    nb_couples = len(couples)

    has_text = bool(data["text"].strip())
    has_couples = nb_couples > 0
    has_channel = bool(channel_id)
    can_send = has_text and has_couples and has_channel
    steps_done = sum([has_text, has_couples, has_channel])
    steps_bar = _progress_bar(steps_done, 3, length=3)

    if can_send:
        status_line = "✅ Prêt à être envoyé"
    else:
        missing = []
        if not has_couples:
            missing.append("au moins 1 couple emoji/rôle")
        if not has_channel:
            missing.append("un salon de destination")
        status_line = f"<:erreur:1495443907281031359> Manquant : {', '.join(missing)}"

    container.add_item(TextDisplay(f"# 📝 Créer un message\n-# `{steps_bar}` {status_line}"))
    container.add_item(Separator())

    container.add_item(TextDisplay("### 💬 Texte affiché"))
    edit_text_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")

    async def edit_text(inter: Interaction):
        modal = MessageTextModal(data["text"])
        await inter.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            data["text"] = modal.value
            new_view = await create_reaction_role_view(guild_id, bot, "create", data, author_id)
            if new_view:
                await inter.edit_original_response(view=new_view)

    edit_text_btn.callback = edit_text
    container.add_item(Section(
        TextDisplay(f"> {_preview(data['text'])}"), accessory=edit_text_btn
    ))
    container.add_item(Separator())


    async def _validate_role_for_couple(role_inter: Interaction, role_id: int) -> Optional[str]:
        """Vérifie que le rôle du couple est valide."""

        role = guild.get_role(role_id)
        if role is None:
            return "Rôle introuvable."
        if role.is_default() or role.is_bot_managed() or role.is_integration():
            return "Ce type de rôle ne peut pas être utilisé."
        if role.position >= guild.me.top_role.position:
            return (
                "Ce rôle est au-dessus ou au même niveau que mon rôle.\n"
                "-# Placez mon rôle plus haut dans la hiérarchie."
            )
        actor = role_inter.user
        if (
            isinstance(actor, discord.Member)
            and actor.top_role.position <= role.position
            and not actor.guild_permissions.administrator
            and actor.id != guild.owner_id
        ):
            return "Vous ne pouvez pas attribuer un rôle plus haut que le vôtre."
        return None

    def _make_emoji_modal(index: int) -> EmojiModal:
        """Construit le modal emoji."""

        current = couples[index] if index < len(couples) else None
        emoji_default = current["emoji"] if current else ""
        current_role_id = current["role_id"] if current else None

        async def _on_emoji_valid(modal_inter: Interaction, emoji: str) -> None:
            """Vérifie que l'emoji n'appartient pas à un autre couple."""
            for idx, c in enumerate(couples):
                if idx != index and c["emoji"] == emoji:
                    await modal_inter.response.send_message(
                        view=error_container("Cet emoji est déjà utilisé dans un autre couple."),
                        ephemeral=True,
                    )
                    return

            async def _on_role_save(role_id: int) -> None:
                """Sauvegarde le couple emoji/rôle."""
                new_couple = {"emoji": emoji, "role_id": role_id}
                if index < len(couples):
                    couples[index] = new_couple
                else:
                    couples.append(new_couple)

            async def _build_return_view():
                return await create_reaction_role_view(guild_id, bot, "create", data, author_id)

            await modal_inter.response.edit_message(
                view=SelectPageView(
                    kind="role",
                    title=f"Rôle — {emoji}",
                    current_value=current_role_id,
                    owner_id=author_id,
                    on_save=_on_role_save,
                    build_return_view=_build_return_view,
                    validate=_validate_role_for_couple,
                )
            )

        return EmojiModal(default=emoji_default, on_valid=_on_emoji_valid)

    gold_suffix = " ✨" if is_gold_server else ""
    container.add_item(TextDisplay(
        f"### 🎨 Couples emoji / rôle{gold_suffix}\n"
        f"-# `{_progress_bar(nb_couples, limite_couples)}` {nb_couples} / {limite_couples} configuré(s)"
    ))

    for i, couple in enumerate(couples):
        role = guild.get_role(couple["role_id"])
        role_str = role.mention if role else "`Rôle supprimé`"
        edit_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")
        remove_btn = Button(label="Retirer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")

        async def edit_cb(inter: Interaction, index=i):
            """Modifie un couple."""
            await inter.response.send_modal(_make_emoji_modal(index))

        async def remove_cb(inter: Interaction, index=i):
            """Supprime un couple."""
            if index < len(couples):
                removed = couples.pop(index)
                new_view = await create_reaction_role_view(guild_id, bot, "create", data, author_id)
                if new_view:
                    await inter.response.edit_message(view=new_view)
                await inter.followup.send(
                    view=success_container(f"Couple {removed['emoji']} retiré."), ephemeral=True
                )
            else:
                await inter.response.defer()

        edit_btn.callback = edit_cb
        remove_btn.callback = remove_cb
        container.add_item(Section(
            TextDisplay(f"**Couple {i + 1}** — {couple['emoji']}  →  {role_str}"),
            accessory=edit_btn,
        ))
        rr = ActionRow()
        rr.add_item(remove_btn)
        container.add_item(rr)

    add_btn = Button(label="Ajouter un couple", style=ButtonStyle.success,
                     emoji="<:plus:1495444111505752154>", disabled=nb_couples >= limite_couples)

    async def add_couple_cb(inter: Interaction):
        """Ajoute un couple."""
        await inter.response.send_modal(_make_emoji_modal(len(couples)))

    add_btn.callback = add_couple_cb
    ar = ActionRow()
    ar.add_item(add_btn)
    container.add_item(ar)
    container.add_item(Separator())

    container.add_item(TextDisplay("### #️⃣ Salon de destination"))
    channel_text = f"<#{channel_id}>" if channel_id else "`Non défini`"
    channel_btn = Button(label="Modifier", style=ButtonStyle.secondary, emoji="<:modifier:1495444144712192003>")

    async def _validate_channel_for_create(chan_inter: Interaction, new_channel_id: int) -> Optional[str]:
        """Vérifie que le salon est valide pour l'envoi du message."""

        channel = chan_inter.guild.get_channel(new_channel_id) if chan_inter.guild else None
        if not isinstance(channel, discord.TextChannel):
            return "Salon texte introuvable."
        perms = channel.permissions_for(chan_inter.guild.me)
        required = {
            "Envoyer des messages": perms.send_messages,
            "Lire les messages": perms.read_messages,
            "Lire l'historique": perms.read_message_history,
            "Ajouter des réactions": perms.add_reactions,
        }
        missing = [name for name, ok in required.items() if not ok]
        if missing:
            return (
                f"Permissions manquantes dans {channel.mention} :\n"
                + "\n".join(f"• {m}" for m in missing)
            )
        return None

    async def _on_channel_save(new_channel_id: int) -> None:
        data["channel"] = new_channel_id

    async def _build_channel_return_view():
        return await create_reaction_role_view(guild_id, bot, "create", data, author_id)

    async def choose_channel_cb(inter: Interaction):
        await inter.response.edit_message(
            view=SelectPageView(
                kind="channel",
                title="Salon de destination",
                current_value=channel_id,
                owner_id=author_id,
                on_save=_on_channel_save,
                build_return_view=_build_channel_return_view,
                validate=_validate_channel_for_create,
            )
        )

    channel_btn.callback = choose_channel_cb
    container.add_item(Section(
        TextDisplay(f"**Destination :** {channel_text}\n-# Le message de réaction sera posté dans ce salon."),
        accessory=channel_btn,
    ))
    container.add_item(Separator())
    
    
    back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")

    async def back_cb(inter: Interaction):
        new_view = await create_reaction_role_view(guild_id, bot, "main", author_id=author_id)
        if new_view:
            await inter.response.edit_message(view=new_view)

    back_btn.callback = back_cb

    send_btn = Button(
        label="Envoyer le message" if can_send else "Compléter la configuration",
        style=ButtonStyle.success if can_send else ButtonStyle.secondary,
        emoji="📨", disabled=not can_send,
    )

    async def send_cb(inter: Interaction):
        ch = bot.get_channel(data["channel"])
        if not ch:
            return await inter.response.send_message(
                view=error_container("Salon introuvable — sélectionnez-en un autre."), ephemeral=True
            )
        if not ch.permissions_for(inter.guild.me).manage_roles:
            return await inter.response.send_message(
                view=error_container("Je n'ai pas la permission **Gérer les rôles**."), ephemeral=True
            )

        sent_view = build_sent_message_view(data["text"], inter.guild, couples)
        try:
            msg = await ch.send(view=sent_view)
        except discord.HTTPException as e:
            return await inter.response.send_message(
                view=error_container(f"Envoi impossible : `{e}`"), ephemeral=True
            )

        for c in couples:
            try:
                await msg.add_reaction(c["emoji"])
            except discord.HTTPException:
                log.warning("[Rôle-Réaction] réaction impossible %s sur msg %s", c["emoji"], msg.id)

        reactions_data = [{**c, "created_at": datetime.now().isoformat()} for c in couples]
        await creer_message_reaction(guild_id, ch.id, msg.id, data["text"], reactions_data)

        new_view = await create_reaction_role_view(guild_id, bot, "main", author_id=author_id)
        if new_view:
            await inter.response.edit_message(view=new_view)
        await inter.followup.send(
            view=success_container(f"Message envoyé dans {ch.mention} !"), ephemeral=True
        )

    send_btn.callback = send_cb

    container.add_item(ActionRow(back_btn, send_btn))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideON Studio"))


# ============================================================
# 📋 Interface liste message
# ============================================================

async def _build_list(container, guild_id, bot, author_id):
    container.add_item(TextDisplay(
        "# 📋 Messages actifs\n-# Tous les messages rôle-réaction de ce serveur"
    ))
    container.add_item(Separator())

    messages = await obtenir_tous_messages(guild_id)
    if not messages:
        container.add_item(TextDisplay(
            "### 📭 Aucun message configuré\n-# Retournez sur l'accueil pour en créer un."
        ))
    else:
        for msg_id, data_msg in messages.items():
            channel = bot.get_channel(data_msg["channel_id"])
            if not channel:
                continue
            try:
                message = await channel.fetch_message(int(msg_id))
            except discord.HTTPException:
                continue

            created_at = message.created_at.strftime("%d/%m/%Y à %H:%M")
            reactions = data_msg.get("reactions", [])
            couples_count = len(reactions)

            utilisations = 0
            try:
                for reaction in message.reactions:
                    utilisations += max(reaction.count - 1, 0)
            except Exception:
                pass

            preview = "  ·  ".join(r["emoji"] for r in reactions[:3])
            if len(reactions) > 3:
                preview += " …"

            delete_btn = Button(label="Supprimer", style=ButtonStyle.danger, emoji="<:supprimer:1495444051623809075>")

            async def delete_cb(inter: Interaction, mid=msg_id, ch_id=data_msg["channel_id"]):
                await supprimer_message_reaction(guild_id, int(mid))
                try:
                    ch = bot.get_channel(ch_id)
                    if ch:
                        m = await ch.fetch_message(int(mid))
                        await m.delete()
                except discord.HTTPException:
                    pass
                new_view = await create_reaction_role_view(guild_id, bot, "list", author_id=author_id)
                if new_view:
                    await inter.response.edit_message(view=new_view)
                await inter.followup.send(
                    view=success_container("Message supprimé avec succès."), ephemeral=True
                )

            delete_btn.callback = delete_cb
            url = f"https://discord.com/channels/{guild_id}/{data_msg['channel_id']}/{msg_id}"
            container.add_item(Section(
                TextDisplay(
                    f"**#{channel.name}** — créé le {created_at}\n"
                    f"-# {couples_count} couple(s)  ·  {utilisations} utilisation(s)"
                    + (f"  ·  {preview}" if preview else "")
                    + f"  ·  [Voir le message]({url})"
                ),
                accessory=delete_btn,
            ))
            container.add_item(Separator())

    back_btn = Button(label="Retour", style=ButtonStyle.secondary, emoji="<:retour:1515658955190308995>")

    async def back_main_cb(inter: Interaction):
        new_view = await create_reaction_role_view(guild_id, bot, "main", author_id=author_id)
        if new_view:
            await inter.response.edit_message(view=new_view)

    back_btn.callback = back_main_cb
    br = ActionRow()
    br.add_item(back_btn)
    container.add_item(br)
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))