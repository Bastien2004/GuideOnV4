"""
views/role_all/config_view.py — Interface /config role_all.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, LayoutView, Section, Separator, TextDisplay

from utils.container_universel import error_container
from views._components.role_select import RoleSelect

log = logging.getLogger(__name__)

APPLY_DELAY = 0.4
PROGRESS_EVERY = 10
MAX_RETRY_PER_MEMBER = 3


# ============================================================
# ⚒️ Utilitaires
# ============================================================

def _bot_can_manage(guild: discord.Guild, role: discord.Role) -> bool:
    """Vérifie que le bot à les permissions pour gérer ce rôle."""

    return (
        guild.me.guild_permissions.manage_roles
        and role.position < guild.me.top_role.position
        and not role.is_default()
        and not role.is_bot_managed()
        and not role.is_integration()
    )


def _admin_can_manage(member: discord.Member, role: discord.Role) -> bool:
    """L'admin peut-il gérer ce rôle ? (hiérarchie)"""

    if member.id == member.guild.owner_id:
        return True
    return role.position < member.top_role.position


def get_role_stats(guild: discord.Guild, role: discord.Role) -> dict:
    """Gère la répartition d'un rôle : total / avec / sans / pourcentage."""

    total = guild.member_count or 0
    with_role = len(role.members)
    without_role = max(0, total - with_role)
    percentage = round(with_role / total * 100, 1) if total > 0 else 0.0
    return {
        "total": total,
        "with_role": with_role,
        "without_role": without_role,
        "percentage": percentage,
    }


async def apply_role_to_all(guild: discord.Guild, role: discord.Role, action: str, interaction: Interaction) -> dict:
    """Ajoute ou retire le rôle à tous les membres non-bots."""

    success = errors = skipped = 0
    members = [m for m in guild.members if not m.bot]
    total = len(members)
    action_label = "Ajout" if action == "add" else "Retrait"

    progress_msg = await interaction.followup.send(
        f"⏳ **{action_label} en cours…**\n"
        f"Rôle : {role.mention} · 0 / {total} membres traités",
        ephemeral=True,
    )

    for i, member in enumerate(members, start=1):
        has_role = role in member.roles

        if (action == "add" and has_role) or (action == "remove" and not has_role):
            skipped += 1
        else:
            done = False
            for attempt in range(MAX_RETRY_PER_MEMBER):
                try:
                    if action == "add":
                        await member.add_roles(role, reason="role_all : ajout en masse")
                    else:
                        await member.remove_roles(role, reason="role_all : retrait en masse")
                    success += 1
                    done = True
                    break
                except discord.Forbidden:
                    errors += 1
                    done = True
                    break
                except discord.HTTPException as e:
                    retry = getattr(e, "retry_after", None)
                    if retry:
                        await asyncio.sleep(float(retry) + 0.1)
                        continue
                    log.warning("role_all: HTTP %s sur %s (guild=%s)", e, member.id, guild.id)
                    errors += 1
                    done = True
                    break
                except Exception:
                    log.exception("role_all: erreur inattendue %s (guild=%s)", member.id, guild.id)
                    errors += 1
                    done = True
                    break
            if not done:
                errors += 1

        if i % PROGRESS_EVERY == 0 or i == total:
            try:
                await progress_msg.edit(content=(
                    f"⏳ **{action_label} en cours…**\n"
                    f"Rôle : {role.mention} · {i} / {total} membres traités"
                ))
            except (discord.NotFound, discord.HTTPException):
                pass

        await asyncio.sleep(APPLY_DELAY)

    try:
        await progress_msg.delete()
    except (discord.NotFound, discord.HTTPException):
        pass

    return {"success": success, "skipped": skipped, "errors": errors, "total": total}


def _make_result_view(action: str, role: discord.Role, results: dict) -> LayoutView:
    """Rapport final après l'opération."""

    action_label = "ajouté à" if action == "add" else "retiré de"
    view = LayoutView(timeout=None)
    container = Container()
    container.add_item(TextDisplay(
        f"# ✅ Opération terminée\n"
        f"-# Rôle {role.mention} {action_label} **{results['success']}** membre(s)"
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        f"**✅ Succès :** {results['success']}\n"
        f"**⏭️ Ignorés :** {results['skipped']}\n"
        f"**❌ Erreurs :** {results['errors']}"
    ))
    if results["errors"] > 0:
        container.add_item(Separator())
        container.add_item(TextDisplay(
            "-# Des erreurs sont survenues sur certains membres "
            "(permissions insuffisantes ou hiérarchie de rôle)."
        ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(container)
    return view


# ============================================================
# 🛡️ Garde
# ============================================================

def _guard(author_id: Optional[int]):
    async def check(interaction: Interaction) -> bool:
        if author_id is not None and interaction.user.id != author_id:
            await interaction.response.send_message(
                view=error_container("Seul l'auteur de la commande peut **utiliser** ce menu."),
                ephemeral=True,
            )
            return False
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            await interaction.response.send_message(
                view=error_container("Vous devez être **Administrateur**."),
                ephemeral=True,
            )
            return False
        return True
    return check


# ============================================================
# 🧩 Builder de la vue
# ============================================================

async def create_role_all_view(guild: discord.Guild, bot, author_id: Optional[int] = None, page: str = "main", selected_role: Optional[discord.Role] = None, action: Optional[str] = None,) -> LayoutView:
    view = LayoutView(timeout=600)
    container = Container()

    if page == "main":
        _build_main(container, guild, bot, author_id, selected_role)
    elif page == "confirm":
        _build_confirm(container, guild, bot, author_id, selected_role, action)
    else:
        log.error("create_role_all_view : page inconnue '%s' (guild=%s)", page, guild.id)

    view.add_item(container)
    return view


def _build_main(container, guild, bot, author_id, selected_role):
    container.add_item(TextDisplay(
        "# <:profil:1495444182137831515> Attribution de rôle en masse\n"
        "-# Ajouter ou retirer un rôle à tous les membres du serveur."
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        "### <:analyser:1495446292963528798> Serveur\n"
        f"**{guild.member_count}** membre(s) · **{len(guild.roles) - 1}** rôle(s) disponible(s)"
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        "### <:information:1495446355395612794> À savoir\n"
        "• Mon rôle doit être **au-dessus** du rôle à gérer dans la hiérarchie.\n"
        "• Les **bots** ne seront pas affectés.\n"
        "• L'opération peut prendre **plusieurs minutes** selon la taille du serveur.\n"
        "• Un **rapport détaillé** sera affiché à la fin."
    ))
    container.add_item(Separator())

    async def on_role_selected(interaction: Interaction, ids: list[int]):
        check = _guard(author_id)
        if not await check(interaction):
            return
        role = guild.get_role(ids[0]) if ids else None
        if role is None:
            return await interaction.response.send_message(
                view=error_container("Rôle introuvable."), ephemeral=True
            )


        if not _admin_can_manage(interaction.user, role):
            return await interaction.response.send_message(
                view=error_container(
                    "Ce rôle est au-dessus de votre plus haut rôle.\n"
                    "-# Vous ne pouvez pas l'attribuer."
                ),
                ephemeral=True,
            )
        new_view = await create_role_all_view(
            guild, bot, author_id, page="main", selected_role=role
        )
        await interaction.response.edit_message(view=new_view)

    container.add_item(ActionRow(RoleSelect(
        placeholder="🎭 Choisir un rôle à gérer",
        on_select=on_role_selected,
    )))

    if selected_role:
        stats = get_role_stats(guild, selected_role)
        can_manage = _bot_can_manage(guild, selected_role)
        warn = ("\n-# ⚠️ Je ne peux pas gérer ce rôle (hiérarchie insuffisante)"
                if not can_manage else "")
        container.add_item(Separator())
        container.add_item(TextDisplay(
            f"**🎭 Rôle sélectionné :** {selected_role.mention}{warn}\n\n"
            f"**Membres avec le rôle :** {stats['with_role']} ({stats['percentage']}%)\n"
            f"**Membres sans le rôle :** {stats['without_role']}"
        ))
        container.add_item(Separator())

        add_btn = Button(
            label="Ajouter à tous", style=ButtonStyle.success, emoji="<:plus:1495444111505752154>",
            disabled=not can_manage or stats["without_role"] == 0,
        )
        remove_btn = Button(
            label="Retirer à tous", style=ButtonStyle.danger, emoji="<:moins:1508532114465882285>",
            disabled=not can_manage or stats["with_role"] == 0,
        )

        def _go_confirm(act):
            async def cb(interaction: Interaction):
                check = _guard(author_id)
                if not await check(interaction):
                    return
                new_view = await create_role_all_view(
                    guild, bot, author_id, page="confirm",
                    selected_role=selected_role, action=act,
                )
                await interaction.response.edit_message(view=new_view)
            return cb

        add_btn.callback = _go_confirm("add")
        remove_btn.callback = _go_confirm("remove")

        container.add_item(Section(
            TextDisplay(f"**➕ Ajouter à tous**\n-# {stats['without_role']} membre(s) recevront le rôle"),
            accessory=add_btn,
        ))
        container.add_item(Section(
            TextDisplay(f"**➖ Retirer à tous**\n-# {stats['with_role']} membre(s) perdront le rôle"),
            accessory=remove_btn,
        ))

    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))


def _build_confirm(container, guild, bot, author_id, selected_role, action):
    stats = get_role_stats(guild, selected_role)
    affected = stats["without_role"] if action == "add" else stats["with_role"]
    verb = "ajouter" if action == "add" else "retirer"

    container.add_item(TextDisplay("# ⚠️ Confirmation\n-# Cette action est irréversible !"))
    container.add_item(Separator())
    container.add_item(TextDisplay(
        f"Vous allez **{verb}** {selected_role.mention} "
        f"{'à' if action == 'add' else 'de'} **{affected} membre(s)**."
    ))
    container.add_item(Separator())

    confirm_label = "✅ Confirmer l'ajout" if action == "add" else "🗑️ Confirmer le retrait"
    confirm_btn = Button(
        label=f"Confirmer — {verb.capitalize()}",
        style=ButtonStyle.success if action == "add" else ButtonStyle.danger,
        emoji="✅",
    )
    cancel_btn = Button(label="Annuler", style=ButtonStyle.secondary, emoji="◀️")

    async def confirm_cb(interaction: Interaction):
        check = _guard(author_id)
        if not await check(interaction):
            return
        # Re-vérif hiérarchie au moment de l'exécution (le rôle a pu bouger)
        if not _bot_can_manage(guild, selected_role):
            return await interaction.response.edit_message(
                view=error_container("Je ne peux plus gérer ce rôle (hiérarchie modifiée).")
            )
        if not _admin_can_manage(interaction.user, selected_role):
            return await interaction.response.edit_message(
                view=error_container("Ce rôle est au-dessus de votre plus haut rôle.")
            )
        await interaction.response.defer()
        results = await apply_role_to_all(guild, selected_role, action, interaction)
        await interaction.edit_original_response(
            view=_make_result_view(action, selected_role, results)
        )

    async def cancel_cb(interaction: Interaction):
        check = _guard(author_id)
        if not await check(interaction):
            return
        new_view = await create_role_all_view(
            guild, bot, author_id, page="main", selected_role=selected_role
        )
        await interaction.response.edit_message(view=new_view)

    confirm_btn.callback = confirm_cb
    cancel_btn.callback = cancel_cb

    container.add_item(Section(
        TextDisplay(f"**{confirm_label}**\n-# {affected} membre(s) seront affectés"),
        accessory=confirm_btn,
    ))
    container.add_item(Section(
        TextDisplay("**◀️ Annuler**\n-# Revenir sans effectuer de modification"),
        accessory=cancel_btn,
    ))
    container.add_item(Separator())
    container.add_item(TextDisplay("-# GuideOn Studio"))