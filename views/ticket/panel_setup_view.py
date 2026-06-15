"""
views/ticket/panel_setup_view.py — Wizard de configuration d'un panel (CV2 pur).

Porté du V3 (views/TicketSetupView.py) — REMPLACE l'ancien WIP à embeds.

Principe : un `ctx` dict mutable accumule la config. Chaque section a un bouton
crayon qui ouvre un modal (saisie d'ID, fidèle V3) ; à la validation du modal on
rafraîchit la vue. Le bouton « Créer / Mettre à jour » poste le PanelPublicView
dans le salon et persiste via ticket_manager (create_panel / update_panel).

Utilisé par /ticket panel_create (ctx vide) et /ticket panel_edit (ctx pré-rempli).
"""
from __future__ import annotations

import logging
import time

import discord
from discord import ui
from discord.ui import Button, LayoutView, Modal, TextInput

from utils.container_universel import error_container, success_container
from utils.managers import ticket_manager as tm
from views.ticket.panel_public_view import PanelPublicView

log = logging.getLogger(__name__)

WIZARD_TIMEOUT = 600


# ============================================================
# 🔧 Helpers d'affichage
# ============================================================

def _fmt_role(guild: discord.Guild, role_id) -> str:
    if not role_id:
        return "`Non défini`"
    role = guild.get_role(int(role_id))
    return f"<@&{role.id}>" if role else "`Rôle introuvable`"


def _fmt_channel(guild: discord.Guild, channel_id) -> str:
    if not channel_id:
        return "`Non défini`"
    ch = guild.get_channel(int(channel_id))
    return f"<#{ch.id}>" if ch else "`Salon introuvable`"


def _fmt_roles_list(guild: discord.Guild, role_ids: list) -> str:
    if not role_ids:
        return "`Non défini`"
    parts = []
    for rid in role_ids:
        role = guild.get_role(int(rid))
        parts.append(f"<@&{role.id}>" if role else "`Introuvable`")
    return ", ".join(parts)


def _check_complete(ctx: dict) -> tuple[bool, list]:
    missing = []
    if not ctx.get("title"):                 missing.append("Titre")
    if not ctx.get("panel_message"):         missing.append("Message")
    if not ctx.get("ticket_category_id"):    missing.append("Catégorie")
    if not ctx.get("transcript_channel_id"): missing.append("Transcript")
    if not ctx.get("staff_roles"):           missing.append("Rôles staff")
    return (len(missing) == 0, missing)


async def _check_admin(interaction: discord.Interaction) -> bool:
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            view=error_container("Vous devez être administrateur pour cette action."),
            ephemeral=True,
        )
        return False
    return True


async def _refresh(interaction: discord.Interaction, guild: discord.Guild, ctx: dict):
    await interaction.edit_original_response(view=build_setup_view(guild, ctx))


# ============================================================
# 🪟 Vue principale du wizard
# ============================================================

def build_setup_view(guild: discord.Guild, ctx: dict, locked: bool = False) -> LayoutView:
    view = LayoutView(timeout=WIZARD_TIMEOUT)
    container = ui.Container()

    is_edit = bool(ctx.get("panel_id"))
    is_complete, missing = _check_complete(ctx)
    header = "✏️ Modifier le panel" if is_edit else "🎫 Créer un panel de tickets"

    if locked:
        status = "✅ Panel enregistré — cette fenêtre est terminée."
    elif is_complete:
        status = "✅ Prêt à être validé"
    else:
        status = f"⚠️ Manquant : {', '.join(missing)}"

    container.add_item(ui.TextDisplay(f"# {header}"))
    container.add_item(ui.TextDisplay(f"-# {status}"))
    container.add_item(ui.Separator())

    # ── Présentation ──
    container.add_item(ui.TextDisplay("### 📝 Présentation"))
    title = ctx.get("title") or "`Non défini`"
    panel_msg = ctx.get("panel_message") or "`Non défini`"
    raw_preview = (panel_msg[:55] + "…") if len(panel_msg) > 55 else panel_msg
    preview = f"```{raw_preview}```" if panel_msg != "`Non défini`" else raw_preview

    container.add_item(ui.Section(
        ui.TextDisplay(f"**Titre :** {title}\n**Message :**\n{preview}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(TitleMessageModal(guild, ctx))),
    ))
    container.add_item(ui.Separator())

    # ── Salons ──
    container.add_item(ui.TextDisplay("### 📁 Salons"))
    container.add_item(ui.Section(
        ui.TextDisplay(f"**Catégorie tickets :** {_fmt_channel(guild, ctx.get('ticket_category_id'))}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(CategoryModal(guild, ctx))),
    ))
    container.add_item(ui.Section(
        ui.TextDisplay(f"**Salon transcript :** {_fmt_channel(guild, ctx.get('transcript_channel_id'))}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(TranscriptModal(guild, ctx))),
    ))
    closed_disp = (_fmt_channel(guild, ctx.get("closed_category_id"))
                   if ctx.get("closed_category_id") else "`Non défini (optionnel)`")
    container.add_item(ui.Section(
        ui.TextDisplay(f"**Catégorie tickets fermés :** {closed_disp}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(ClosedCategoryModal(guild, ctx))),
    ))
    container.add_item(ui.Separator())

    # ── Rôles ──
    container.add_item(ui.TextDisplay("### 👥 Rôles"))
    container.add_item(ui.Section(
        ui.TextDisplay(f"**Staff :** {_fmt_roles_list(guild, ctx.get('staff_roles', []))}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(StaffRolesModal(guild, ctx))),
    ))
    container.add_item(ui.Section(
        ui.TextDisplay(f"**Ping à l'ouverture :** {_fmt_role(guild, ctx.get('ping_role_id'))}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(PingRoleModal(guild, ctx))),
    ))
    container.add_item(ui.Section(
        ui.TextDisplay(f"**Ban ticket :** {_fmt_role(guild, ctx.get('role_ban_ticket_id'))}"),
        accessory=_pencil(locked, lambda i: i.response.send_modal(BanRoleModal(guild, ctx))),
    ))
    container.add_item(ui.Separator())

    # ── Valider ──
    validate_label = "✅ Mettre à jour le panel" if is_edit else "✅ Créer le panel"
    btn_validate = Button(
        label=validate_label,
        style=discord.ButtonStyle.success if not locked else discord.ButtonStyle.secondary,
        disabled=not is_complete or locked,
    )

    async def cb_validate(interaction: discord.Interaction):
        if not await _check_admin(interaction):
            return
        await _finalize_panel(interaction, guild, ctx)

    btn_validate.callback = cb_validate
    container.add_item(ui.ActionRow(btn_validate))
    container.add_item(ui.Separator())
    container.add_item(ui.TextDisplay("-# GuideON — Système de tickets"))

    view.add_item(container)
    return view


def _pencil(locked: bool, opener):
    """Crée un bouton crayon ✏️ qui, au clic, vérifie admin puis exécute `opener(i)`."""
    btn = Button(emoji="✏️", style=discord.ButtonStyle.secondary, disabled=locked)

    async def cb(interaction: discord.Interaction):
        if not await _check_admin(interaction):
            return
        await opener(interaction)

    btn.callback = cb
    return btn


# ============================================================
# 📝 Modals
# ============================================================

class TitleMessageModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Titre & Message")
        self.guild, self.ctx = guild, ctx
        self.title_input = TextInput(
            label="Titre", default=ctx.get("title", ""), required=True, max_length=80
        )
        self.message_input = TextInput(
            label="Message", default=ctx.get("panel_message", ""),
            style=discord.TextStyle.paragraph, required=True, max_length=500,
        )
        self.add_item(self.title_input)
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        self.ctx["title"] = self.title_input.value
        self.ctx["panel_message"] = self.message_input.value
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class CategoryModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Catégorie des tickets")
        self.guild, self.ctx = guild, ctx
        self.input = TextInput(
            label="ID de la catégorie",
            default=str(ctx.get("ticket_category_id") or ""), required=True,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if not val.isdigit() or not isinstance(
            self.guild.get_channel(int(val)), discord.CategoryChannel
        ):
            return await interaction.response.send_message(
                view=error_container("Catégorie invalide ou introuvable."), ephemeral=True
            )
        self.ctx["ticket_category_id"] = int(val)
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class TranscriptModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Salon transcript")
        self.guild, self.ctx = guild, ctx
        self.input = TextInput(
            label="ID du salon transcript",
            default=str(ctx.get("transcript_channel_id") or ""), required=True,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if not val.isdigit() or not isinstance(
            self.guild.get_channel(int(val)), discord.TextChannel
        ):
            return await interaction.response.send_message(
                view=error_container("Salon textuel invalide ou introuvable."), ephemeral=True
            )
        self.ctx["transcript_channel_id"] = int(val)
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class ClosedCategoryModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Catégorie fermée")
        self.guild, self.ctx = guild, ctx
        self.input = TextInput(
            label="ID catégorie (optionnel)",
            default=str(ctx.get("closed_category_id") or ""), required=False,
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if not val:
            self.ctx["closed_category_id"] = None
        elif val.isdigit() and isinstance(
            self.guild.get_channel(int(val)), discord.CategoryChannel
        ):
            self.ctx["closed_category_id"] = int(val)
        else:
            return await interaction.response.send_message(
                view=error_container("ID catégorie invalide."), ephemeral=True
            )
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class StaffRolesModal(Modal):
    def __init__(self, guild, ctx):
        super().__init__(title="✏️ Rôles staff")
        self.guild, self.ctx = guild, ctx
        current = ctx.get("staff_roles", [])
        self.r1 = TextInput(label="Staff 1", default=str(current[0]) if len(current) > 0 else "", required=True)
        self.r2 = TextInput(label="Staff 2", default=str(current[1]) if len(current) > 1 else "", required=False)
        self.r3 = TextInput(label="Staff 3", default=str(current[2]) if len(current) > 2 else "", required=False)
        for r in (self.r1, self.r2, self.r3):
            self.add_item(r)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            all_roles = await self.guild.fetch_roles()
        except discord.HTTPException:
            all_roles = []

        def resolve(val: str) -> bool:
            if not val.isdigit():
                return False
            role = self.guild.get_role(int(val)) or discord.utils.get(all_roles, id=int(val))
            return role is not None

        roles, seen = [], set()
        for r in (self.r1.value, self.r2.value, self.r3.value):
            v = r.strip()
            if v and resolve(v) and v not in seen:
                roles.append(int(v))
                seen.add(v)

        if not roles:
            return await interaction.response.send_message(
                view=error_container("Au moins un rôle staff valide est requis."), ephemeral=True
            )
        self.ctx["staff_roles"] = roles
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class _OptionalRoleModal(Modal):
    """Base commune pour Ping et Ban (rôle optionnel)."""

    ctx_key = ""

    def __init__(self, guild, ctx, title, label):
        super().__init__(title=title)
        self.guild, self.ctx = guild, ctx
        self.input = TextInput(
            label=label, default=str(ctx.get(self.ctx_key) or ""), required=False
        )
        self.add_item(self.input)

    async def on_submit(self, interaction: discord.Interaction):
        val = self.input.value.strip()
        if not val:
            self.ctx[self.ctx_key] = None
        elif val.isdigit():
            role = self.guild.get_role(int(val))
            if role is None:
                try:
                    role = discord.utils.get(await self.guild.fetch_roles(), id=int(val))
                except discord.HTTPException:
                    role = None
            if role:
                self.ctx[self.ctx_key] = int(val)
            else:
                return await interaction.response.send_message(
                    view=error_container("Rôle introuvable sur ce serveur."), ephemeral=True
                )
        else:
            return await interaction.response.send_message(
                view=error_container("ID invalide — entrez uniquement des chiffres."), ephemeral=True
            )
        await interaction.response.defer()
        await _refresh(interaction, self.guild, self.ctx)


class PingRoleModal(_OptionalRoleModal):
    ctx_key = "ping_role_id"

    def __init__(self, guild, ctx):
        super().__init__(guild, ctx, "✏️ Rôle ping", "ID rôle (optionnel)")


class BanRoleModal(_OptionalRoleModal):
    ctx_key = "role_ban_ticket_id"

    def __init__(self, guild, ctx):
        super().__init__(guild, ctx, "✏️ Rôle ban", "ID rôle ban (optionnel)")


# ============================================================
# ✅ Finalisation
# ============================================================

async def _finalize_panel(interaction: discord.Interaction, guild: discord.Guild, ctx: dict):
    await interaction.response.defer(ephemeral=True)

    guild_id = guild.id
    is_edit = bool(ctx.get("panel_id"))
    panel_id = ctx.get("panel_id") or f"panel_{int(time.time())}"
    channel_id = ctx.get("channel_id") or interaction.channel_id
    channel = guild.get_channel(channel_id)

    if not isinstance(channel, discord.TextChannel):
        return await interaction.followup.send(
            view=error_container("Salon d'envoi invalide."), ephemeral=True
        )

    panel_view = PanelPublicView(
        panel_id=panel_id, guild_id=guild_id,
        title=ctx["title"], message=ctx["panel_message"],
    )

    # Poste ou édite le message public
    try:
        if ctx.get("message_id"):
            try:
                msg = await channel.fetch_message(ctx["message_id"])
                await msg.edit(view=panel_view)
            except discord.HTTPException:
                msg = await channel.send(view=panel_view)
        else:
            msg = await channel.send(view=panel_view)
    except discord.HTTPException as e:
        return await interaction.followup.send(
            view=error_container(f"Erreur Discord : {e}"), ephemeral=True
        )

    # Persiste en DB
    try:
        if is_edit:
            await tm.update_panel(
                guild_id, panel_id,
                staff_role_ids=ctx["staff_roles"],
                channel_id=channel.id,
                message_id=msg.id,
                title=ctx["title"],
                panel_message=ctx["panel_message"],
                ticket_category_id=ctx["ticket_category_id"],
                transcript_channel_id=ctx["transcript_channel_id"],
                closed_category_id=ctx.get("closed_category_id"),
                ping_role_id=ctx.get("ping_role_id"),
                role_ban_ticket_id=ctx.get("role_ban_ticket_id"),
            )
        else:
            await tm.create_panel(
                guild_id=guild_id, panel_id=panel_id,
                channel_id=channel.id, message_id=msg.id,
                title=ctx["title"], panel_message=ctx["panel_message"],
                ticket_category_id=ctx["ticket_category_id"],
                transcript_channel_id=ctx["transcript_channel_id"],
                staff_role_ids=ctx["staff_roles"],
                closed_category_id=ctx.get("closed_category_id"),
                ping_role_id=ctx.get("ping_role_id"),
                role_ban_ticket_id=ctx.get("role_ban_ticket_id"),
                counter=ctx.get("counter", 1),
            )
    except Exception:
        log.exception("Persistance du panel échouée (guild=%s, panel=%s)", guild_id, panel_id)
        return await interaction.followup.send(
            view=error_container("Le panel a été posté mais la sauvegarde a échoué."),
            ephemeral=True,
        )

    # Réenregistre la vue persistante pour le process courant
    try:
        interaction.client.add_view(panel_view, message_id=msg.id)
    except Exception:
        pass

    # Verrouille le wizard + confirme
    ctx["panel_id"] = panel_id
    ctx["message_id"] = msg.id
    await interaction.edit_original_response(view=build_setup_view(guild, ctx, locked=True))

    action = "mis à jour" if is_edit else "créé"
    await interaction.followup.send(
        view=success_container(
            f"Le panel **{ctx['title']}** a été {action} dans {channel.mention}."
        ),
        ephemeral=True,
    )