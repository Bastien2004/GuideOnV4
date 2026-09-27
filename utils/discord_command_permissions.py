"""
utils/discord_command_permissions.py — Diagnostic de la visibilité d'une
commande Discord pour un membre donné, via les permissions d'intégration
(Server Settings → Intégrations → GuideOn), extrait pour
cogs/dev/command_visibility.py.

Contexte : les groupes de commandes ngstaff/iris/alpha/dev ne sont PAS des
commandes globales — elles sont enregistrées serveur par serveur (cf.
bot.py::_sync_commands — IRIS_GUILDS/ALPHA_GUILDS/DEV_GUILDS/
list_active_ng_servers()). Aucun default_member_permissions n'est fixé
dans le code sur ces commandes (vérifié par recherche sur tout le repo) :
la seule restriction possible de VISIBILITÉ (la commande n'apparaît même
plus dans le picker, avant toute exécution) vient donc d'un overwrite de
permission de commande configuré manuellement sur Discord (page
Intégrations), pas du code du bot. Ce module lit cette configuration
brute côté API Discord et la résout en un diagnostic lisible.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import discord
from discord import app_commands

__all__ = ["CommandVisibilityReport", "scan_command_permissions"]

# Types d'overwrite renvoyés par l'API Discord pour une permission de commande.
_TYPE_ROLE = 1
_TYPE_USER = 2
_TYPE_CHANNEL = 3


@dataclass
class ResolvedOverwrite:
    kind: str          # "role" | "user" | "channel" | "?"
    label: str          # nom résolu, prêt à afficher
    target_id: int
    allow: bool


@dataclass
class CommandPermissionEntry:
    entry_id: int
    command_label: str
    is_catch_all: bool
    overwrites: list[ResolvedOverwrite] = field(default_factory=list)


@dataclass
class CommandVerdict:
    command_label: str
    visible: bool | None   # True/False si déterminé, None si indéterminé (pas d'overwrite trouvé)
    reason: str


@dataclass
class CommandVisibilityReport:
    guild: discord.Guild
    member: discord.Member
    member_role_ids: set[int]
    member_is_admin_or_owner: bool
    guild_commands: dict[int, str]            # id -> nom, commandes guild-scoped réellement synchronisées
    entries: list[CommandPermissionEntry]      # overwrites bruts résolus (tous)
    verdicts: list[CommandVerdict]              # un verdict par commande concernée


def _resolve_target(guild: discord.Guild, perm_type: int, target_id: int) -> tuple[str, str]:
    """Retourne (kind, label) pour un item de permission {id, type, permission}."""
    if perm_type == _TYPE_ROLE:
        if target_id == guild.id:
            return "role", "@everyone (tous les membres du serveur)"
        role = guild.get_role(target_id)
        return "role", (f"@{role.name}" if role else f"Rôle inconnu/supprimé (`{target_id}`)")
    if perm_type == _TYPE_USER:
        member = guild.get_member(target_id)
        return "user", (member.mention if member else f"Utilisateur inconnu (`{target_id}`)")
    if perm_type == _TYPE_CHANNEL:
        channel = guild.get_channel(target_id)
        return "channel", (f"#{channel.name}" if channel else f"Salon inconnu (`{target_id}`)")
    return "?", f"Type de permission inconnu ({perm_type}) — `{target_id}`"


async def scan_command_permissions(
    client: discord.Client,
    guild: discord.Guild,
    member: discord.Member,
    *,
    command_filter: list[str] | None = None,
) -> CommandVisibilityReport:
    """
    Rassemble :
      - les commandes guild-scoped réellement synchronisées sur `guild`
        à l'instant présent (source de vérité Discord — pas les constantes
        IRIS_GUILDS/ALPHA_GUILDS/DEV_GUILDS de bot.py, qui ne disent que sur
        quels serveurs le bot *tente* de synchroniser, pas ce qui est
        effectivement actif côté Discord) ;
      - les overwrites de permission de commande configurés sur ce serveur
        (page Intégrations), bruts puis résolus (rôles/utilisateurs/salons
        nommés plutôt que des IDs) ;
    et calcule un verdict best-effort de visibilité pour `member`, commande
    par commande (filtrée sur les noms de `command_filter` si fourni, ex.
    ["ngstaff", "iris"] — sinon toutes les commandes guild-scoped trouvées).
    """
    app_id = client.application_id
    if app_id is None:
        app_info = await client.application_info()
        app_id = app_info.id

    # ── Commandes guild-scoped réellement synchronisées ────────────────
    tree: app_commands.CommandTree = client.tree
    try:
        guild_commands_list = await tree.fetch_commands(guild=guild)
    except discord.HTTPException:
        guild_commands_list = []
    guild_commands: dict[int, str] = {cmd.id: cmd.name for cmd in guild_commands_list}

    if command_filter:
        wanted = {name.lower() for name in command_filter}
        relevant_ids = {cid for cid, name in guild_commands.items() if name.lower() in wanted}
    else:
        relevant_ids = set(guild_commands.keys())

    # ── Overwrites bruts (page Intégrations) ───────────────────────────
    try:
        raw_entries = await client.http.get_guild_application_command_permissions(app_id, guild.id)
    except discord.HTTPException:
        raw_entries = []

    entries: list[CommandPermissionEntry] = []
    entries_by_command_id: dict[int, CommandPermissionEntry] = {}
    catch_all_entry: CommandPermissionEntry | None = None

    for raw in raw_entries:
        entry_id = int(raw["id"])
        is_catch_all = entry_id == app_id
        overwrites: list[ResolvedOverwrite] = []
        for p in raw.get("permissions", []):
            kind, label = _resolve_target(guild, p["type"], int(p["id"]))
            overwrites.append(ResolvedOverwrite(kind=kind, label=label, target_id=int(p["id"]), allow=bool(p["permission"])))

        if is_catch_all:
            command_label = "⚙️ Réglage par défaut (s'applique à toute commande sans overwrite explicite)"
        else:
            command_label = guild_commands.get(entry_id, f"Commande inconnue (`{entry_id}`)")

        entry = CommandPermissionEntry(entry_id=entry_id, command_label=command_label,
                                        is_catch_all=is_catch_all, overwrites=overwrites)
        entries.append(entry)
        if is_catch_all:
            catch_all_entry = entry
        else:
            entries_by_command_id[entry_id] = entry

    # ── Rôles/statut du membre ──────────────────────────────────────────
    member_role_ids = {r.id for r in member.roles}
    is_admin_or_owner = member.guild_permissions.administrator or member.id == guild.owner_id

    # ── Verdicts best-effort, commande par commande ──────────────────────
    target_ids = relevant_ids if relevant_ids else set(entries_by_command_id.keys())
    verdicts: list[CommandVerdict] = []
    for cid in sorted(target_ids, key=lambda i: guild_commands.get(i, str(i))):
        label = guild_commands.get(cid, f"Commande inconnue (`{cid}`)")
        verdicts.append(_build_verdict(
            label, entries_by_command_id.get(cid), catch_all_entry,
            member, member_role_ids, is_admin_or_owner,
        ))

    return CommandVisibilityReport(
        guild=guild,
        member=member,
        member_role_ids=member_role_ids,
        member_is_admin_or_owner=is_admin_or_owner,
        guild_commands=guild_commands,
        entries=entries,
        verdicts=verdicts,
    )


def _build_verdict(
    command_label: str,
    specific_entry: CommandPermissionEntry | None,
    catch_all_entry: CommandPermissionEntry | None,
    member: discord.Member,
    member_role_ids: set[int],
    is_admin_or_owner: bool,
) -> CommandVerdict:
    if is_admin_or_owner:
        return CommandVerdict(
            command_label, True,
            "Administrateur ou propriétaire du serveur — voit toujours toutes les commandes, "
            "quels que soient les overwrites configurés (règle Discord).",
        )

    chosen_entry = specific_entry if specific_entry is not None else catch_all_entry
    if chosen_entry is None:
        return CommandVerdict(
            command_label, None,
            "Aucun overwrite de permission configuré pour cette commande sur ce serveur : la "
            "visibilité ne dépend donc pas des Intégrations Discord — le blocage vient probablement "
            "d'ailleurs (rôle @everyone privé de la permission générale \"Utiliser les commandes "
            "d'application\", ou la commande n'est simplement pas synchronisée sur ce serveur).",
        )

    source = "la commande elle-même" if specific_entry is not None else "le réglage par défaut"

    # Priorité Discord : overwrite utilisateur explicite > overwrite par rôle
    # (pour chacun des rôles du membre) > @everyone.
    user_ow = next((o for o in chosen_entry.overwrites if o.kind == "user" and o.target_id == member.id), None)
    if user_ow is not None:
        verdict = "✅ autorisé" if user_ow.allow else "❌ refusé"
        return CommandVerdict(
            command_label, user_ow.allow,
            f"Overwrite **utilisateur** explicite trouvé sur {source} ({chosen_entry.command_label}) : "
            f"{verdict} pour vous personnellement.",
        )

    role_ows = [o for o in chosen_entry.overwrites if o.kind == "role" and o.target_id in member_role_ids
                and o.label != "@everyone (tous les membres du serveur)"]
    everyone_ow = next((o for o in chosen_entry.overwrites
                        if o.kind == "role" and o.label == "@everyone (tous les membres du serveur)"), None)

    if role_ows:
        allowed = [o for o in role_ows if o.allow]
        denied = [o for o in role_ows if not o.allow]
        if allowed:
            return CommandVerdict(
                command_label, True,
                f"Au moins un de vos rôles actuels est explicitement autorisé sur {source} "
                f"({chosen_entry.command_label}) : " + ", ".join(o.label for o in allowed) + ".",
            )
        return CommandVerdict(
            command_label, False,
            f"Un de vos rôles actuels est explicitement **refusé** sur {source} "
            f"({chosen_entry.command_label}), et aucun de vos rôles n'a d'autorisation explicite : "
            + ", ".join(o.label for o in denied) + ".",
        )

    if everyone_ow is not None:
        if everyone_ow.allow:
            return CommandVerdict(
                command_label, True,
                f"Aucun de vos rôles actuels n'a d'overwrite spécifique — c'est donc le réglage "
                f"@everyone de {source} ({chosen_entry.command_label}) qui s'applique : autorisé pour "
                "tout le monde par défaut.",
            )
        return CommandVerdict(
            command_label, False,
            f"Le réglage @everyone de {source} ({chosen_entry.command_label}) est **refusé** par "
            "défaut, et aucun de vos rôles actuels ne figure parmi les autorisations explicites "
            "listées ci-dessous — c'est très probablement ce qui bloque l'accès : le rôle qui était "
            "explicitement autorisé n'est plus parmi vos rôles.",
        )

    return CommandVerdict(
        command_label, True,
        f"Un overwrite existe sur {source} ({chosen_entry.command_label}) mais ne mentionne ni vous "
        "ni aucun de vos rôles actuels — par défaut Discord considère cela comme autorisé.",
    )