"""
views/wiki/wiki_view.py — Interface Components V2 du /wiki GuideON.

Architecture :
    WikiHomeView      : page d'accueil (stats bot + menu catégorie + nav)
    WikiCategoryView  : liste des commandes d'une catégorie (paginée, 4/page)
    WikiSupportView   : infos support (Discord, site, email)
    WikiLinksView     : liens utiles

Interactions : tous les callbacks sont assignés directement sur les boutons/
selects de chaque vue — pas de on_interaction global, conforme à la
convention V4. Sécurité owner-check sur toutes les vues interactives.
"""
from __future__ import annotations

import discord
from discord import ButtonStyle, SelectOption
from discord.ui import ActionRow, Button, Container, LayoutView, Select, Separator, TextDisplay

from utils.datetime_utils import format_duration, now_utc

# ═══════════════════════════════════════════════════════════════
# 📋  Données des catégories
# ═══════════════════════════════════════════════════════════════
# Chaque commande : (name, usage, description, example)
# available=False → catégorie "bientôt disponible" (commandes non implémentées)

CATEGORIES: dict[str, dict] = {
    "ng": {
        "name": "NationsGlory", "emoji": "🌍",
        "description": "Commandes autour de NationsGlory",
        "available": True,
        "commands": [
            ("autel",        "/ng autel <version>",                   "Informations sur les autels NationsGlory",      "/ng autel Java"),
            ("claim",        "/ng claim <serveur> <pays>",            "Nombre de claims d'un pays",                    "/ng claim Alpha France"),
            ("classement",   "/ng classement <serveur>",              "Classement d'un serveur NationsGlory",          "/ng classement Alpha"),
            ("convert",      "/ng convert <quantité> <type>",         "Convertir une quantité en stacks/coffres",      "/ng convert 10000 Stacks"),
            ("country",      "/ng country <serveur> <pays>",          "Informations détaillées d'un pays",             "/ng country Red Bolivie"),
            ("dynmaps",      "/ng dynmaps <serveur>",                 "Lien vers les dynmaps NationsGlory",            "/ng dynmaps White"),
            ("info",         "/ng info",                              "Infos pratiques autour de NationsGlory",        "/ng info"),
            ("lvl",          "/ng lvl <serveur> <pays>",              "Levels d'un pays",                              "/ng lvl Omega Bahamas"),
            ("mmr",          "/ng mmr <serveur> <pays>",              "MMR d'un pays",                                 "/ng mmr Blue Touva"),
            ("onu",          "/ng onu <serveur>",                     "Informations sur les ONUs NationsGlory",        "/ng onu Orange"),
            ("pillage",      "/ng pillage <serveur>",                 "Pays susceptibles d'être pillés",               "/ng pillage Black"),
            ("profil",       "/ng profil <pseudo> <serveur>",         "Infos d'un joueur NationsGlory",                "/ng profil Ruixi62 Alpha"),
            ("rd",           "/ng rd <version> <branche> <palier>",  "Infos d'un palier de R&D",                      "/ng rd Bedrock Militaire 6"),
            ("sanction",     "/ng sanction <serveur>",                "Tableau des sanctions d'un serveur",            "/ng sanction Lime"),
            ("serveur_stat", "/ng serveur_stat",                      "Statistiques des serveurs NationsGlory",        "/ng serveur_stat"),
            ("skin",         "/ng skin <pseudo>",                     "Skin d'un joueur NationsGlory",                 "/ng skin iBalix"),
            ("version",      "/ng version",                           "Version actuelle de NationsGlory Bedrock",      "/ng version"),
        ],
    },
    "ticket": {
        "name": "Tickets", "emoji": "🎫",
        "description": "Système de support par tickets",
        "available": True,
        "commands": [
            ("panel_create", "/ticket panel_create",                  "Créer un nouveau panel de tickets",             "/ticket panel_create"),
            ("panel_edit",   "/ticket panel_edit <lien>",             "Modifier un panel de tickets existant",         "/ticket panel_edit (lien)"),
            ("panel_delete", "/ticket panel_delete <lien>",           "Supprimer un panel de tickets",                 "/ticket panel_delete (lien)"),
            ("panel_list",   "/ticket panel_list",                    "Lister tous les panels de tickets",             "/ticket panel_list"),
            ("add",          "/ticket add <utilisateur>",             "Ajouter un utilisateur à ce ticket",            "/ticket add Comete"),
            ("remove",       "/ticket remove <utilisateur>",          "Retirer un utilisateur de ce ticket",           "/ticket remove Luka"),
            ("ban",          "/ticket ban <utilisateur>",             "Bannir un utilisateur des tickets",             "/ticket ban Tostam"),
            ("close",        "/ticket close",                         "Fermer ce ticket",                              "/ticket close"),
            ("delete",       "/ticket delete",                        "Supprimer définitivement ce ticket",            "/ticket delete"),
            ("rename",       "/ticket rename <nom>",                  "Renommer ce ticket",                            "/ticket rename Problème-0001"),
            ("wakeup",       "/ticket wakeup",                        "Relancer un ticket inactif",                    "/ticket wakeup"),
        ],
    },
    "giveaway": {
        "name": "Giveaways", "emoji": "🎁",
        "description": "Système de giveaways",
        "available": True,
        "commands": [
            ("create",    "/giveaway create",                         "Créer un nouveau giveaway",                     "/giveaway create"),
            ("manage",    "/giveaway manage <id>",                    "Gérer un giveaway existant",                    "/giveaway manage 4D554C16"),
            ("list",      "/giveaway list",                           "Lister les giveaways actifs",                   "/giveaway list"),
            ("blacklist", "/giveaway blacklist",                      "Gérer la blacklist des giveaways",              "/giveaway blacklist"),
        ],
    },
    "invite": {
        "name": "Invitations", "emoji": "✉️",
        "description": "Tracking et récompenses d'invitations",
        "available": True,
        "commands": [
            ("config",     "/invite config",                          "Configurer le système d'invitations",           "/invite config"),
            ("classement", "/invite classement",                      "Classement des invitations du serveur",         "/invite classement"),
            ("gestion",    "/invite gestion",                         "Gérer les invitations des membres",             "/invite gestion"),
            ("user",       "/invite user <pseudo>",                   "Invitations d'un membre spécifique",            "/invite user Ruixi62"),
        ],
    },
    "birthday": {
        "name": "Anniversaires", "emoji": "🎂",
        "description": "Rappels et annonces d'anniversaires",
        "available": True,
        "commands": [
            ("config", "/birthday config",                            "Configurer les annonces d'anniversaire",        "/birthday config"),
            ("add",    "/birthday add <date>",                        "Enregistrer ta date d'anniversaire",            "/birthday add 15/06"),
            ("list",   "/birthday list",                              "Liste des anniversaires à venir",               "/birthday list"),
            ("next",   "/birthday next",                              "Prochain anniversaire du serveur",              "/birthday next"),
        ],
    },
    "config": {
        "name": "Configuration", "emoji": "⚙️",
        "description": "Personnaliser GuideON sur ton serveur",
        "available": True,
        "commands": [
            ("autorole",      "/config autorole",                     "Attribution automatique de rôles à l'arrivée", "/config autorole"),
            ("bienvenue",     "/config bienvenue",                    "Messages de bienvenue et de départ",           "/config bienvenue"),
            ("role_all",      "/config role_all",                     "Attribuer/retirer un rôle à tous",            "/config role_all"),
            ("role_reaction", "/config role_reaction",                "Rôles attribués par réaction",                "/config role_reaction"),
        ],
    },
    "utility": {
        "name": "Utilitaire", "emoji": "🔧",
        "description": "Outils pratiques du quotidien",
        "available": True,
        "commands": [
            ("id",        "/id <user_id>",                            "Infos d'un utilisateur via son ID Discord",    "/id 1034564329061744640"),
            ("info",      "/info",                                    "Découvrir GuideON",                            "/info"),
            ("ping",      "/ping",                                    "Latence du bot",                               "/ping"),
            ("report",    "/report",                                  "Signaler un bug",                              "/report"),
            ("timestamp", "/timestamp",                               "Convertir une date en timestamp Discord",      "/timestamp"),
            ("wiki",      "/wiki",                                    "Ce wiki interactif",                           "/wiki"),
        ],
    },
    "moderation": {
        "name": "Modération", "emoji": "🛡️",
        "description": "Outils de modération (bientôt)",
        "available": False,
        "commands": [
            ("clear",     "/mod clear",                               "Suppression de messages en masse",             "/mod clear"),
            ("control",   "/mod control",                             "Panneau de contrôle de modération",           "/mod control"),
            ("inspect",   "/mod inspect <utilisateur>",               "Inspecter un utilisateur",                    "/mod inspect LeWyvernien"),
            ("registre",  "/mod registre <id_sanction>",              "Consulter une sanction via son ID",           "/mod registre 1U6Xoz"),
            ("règlement", "/mod règlement",                           "Envoyer un règlement de serveur Discord",     "/mod règlement"),
        ],
    },
    "exp": {
        "name": "EXP", "emoji": "🧩",
        "description": "Système d'expérience (bientôt)",
        "available": False,
        "commands": [
            ("level",       "/exp level (<pseudo>)",                  "Niveau et EXP d'un joueur",                   "/exp level"),
            ("leaderboard", "/exp leaderboard",                       "Classement EXP du serveur",                   "/exp leaderboard"),
            ("gestion",     "/exp gestion <pseudo>",                  "Gérer l'EXP d'un joueur",                     "/exp gestion Ruixi62"),
        ],
    },
}

COMMANDS_PER_PAGE = 4


# ═══════════════════════════════════════════════════════════════
# 🔧  Helpers internes
# ═══════════════════════════════════════════════════════════════

def _uptime(bot: discord.Client) -> str:
    start = getattr(bot, "start_time", None)
    return format_duration(now_utc() - start) if start else "Indisponible"


def _make_category_select(owner_id: int, callback) -> Select:
    """Construit le Select de choix de catégorie avec callback assigné."""
    options = [
        SelectOption(
            label=f"{cat['name']}{'  ⏳' if not cat['available'] else ''}",
            value=cat_id,
            emoji=cat["emoji"],
            description=cat["description"][:50],
        )
        for cat_id, cat in CATEGORIES.items()
    ]
    select = Select(
        placeholder="📚 Choisir une catégorie...",
        options=options,
        custom_id=f"wiki_cat:{owner_id}",
        min_values=1, max_values=1,
    )
    select.callback = callback
    return select


def _nav_buttons(owner_id: int, active: str, bot: discord.Client | None = None) -> list[Button]:
    """
    Retourne les 3 boutons de navigation avec callbacks assignés.
    active : 'home' | 'support' | 'links' — bouton correspondant désactivé.
    bot requis pour le bouton Accueil (reconstruit WikiHomeView avec la ref bot).
    """
    defs = [
        ("home",    "🏠", "Accueil", ButtonStyle.primary),
        ("support", "💬", "Support", ButtonStyle.secondary),
        ("links",   "🔗", "Liens",   ButtonStyle.secondary),
    ]
    buttons = []
    for key, emoji, label, style in defs:
        btn = Button(
            label=label, emoji=emoji, style=style,
            custom_id=f"wiki_{key}:{owner_id}",
            disabled=(key == active),
        )
        if key == "home":
            _b, _oid = bot, owner_id
            async def _cb_home(interaction: discord.Interaction, b=_b, oid=_oid):
                await interaction.response.edit_message(view=WikiHomeView(b, oid))
            btn.callback = _cb_home
        elif key == "support":
            _oid = owner_id
            async def _cb_support(interaction: discord.Interaction, oid=_oid):
                await interaction.response.edit_message(view=WikiSupportView(oid))
            btn.callback = _cb_support
        elif key == "links":
            _oid = owner_id
            async def _cb_links(interaction: discord.Interaction, oid=_oid):
                await interaction.response.edit_message(view=WikiLinksView(oid))
            btn.callback = _cb_links
        buttons.append(btn)
    return buttons


# ═══════════════════════════════════════════════════════════════
# 🏠  Accueil
# ═══════════════════════════════════════════════════════════════

class WikiHomeView(LayoutView):
    def __init__(self, bot: discord.Client, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.bot = bot
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        bot = self.bot
        total_cmds = sum(len(c["commands"]) for c in CATEGORIES.values())

        c = Container()
        c.add_item(TextDisplay("# 📖 Wiki GuideON"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Bienvenue dans le **centre d'aide** de GuideON !\n"
            "Retrouve ici toutes les commandes organisées par catégorie."
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            f"**Serveurs :** `{len(bot.guilds)}`\n"
            f"**Utilisateurs :** `{sum(g.member_count or 0 for g in bot.guilds)}`\n"
            f"**Commandes :** `{total_cmds}`\n"
            f"**Uptime :** `{_uptime(bot)}`"
        ))
        c.add_item(Separator())
        c.add_item(TextDisplay("Sélectionne une catégorie pour explorer les commandes :"))

        _bot, _oid = self.bot, self.owner_id

        async def on_cat(interaction: discord.Interaction) -> None:
            cat_id = interaction.data["values"][0]
            await interaction.response.edit_message(
                view=WikiCategoryView(cat_id, 0, _oid, _bot)
            )

        c.add_item(ActionRow(_make_category_select(self.owner_id, on_cat)))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="home", bot=bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideON Studio — V4"))
        self.add_item(c)


# ═══════════════════════════════════════════════════════════════
# 📂  Catégorie (paginée)
# ═══════════════════════════════════════════════════════════════

class WikiCategoryView(LayoutView):
    def __init__(self, cat_id: str, page: int, owner_id: int, bot: discord.Client) -> None:
        super().__init__(timeout=300)
        self.cat_id = cat_id
        self.page = page
        self.owner_id = owner_id
        self.bot = bot
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        cat = CATEGORIES[self.cat_id]
        cmds = cat["commands"]
        total_pages = max(1, (len(cmds) + COMMANDS_PER_PAGE - 1) // COMMANDS_PER_PAGE)
        page = max(0, min(self.page, total_pages - 1))
        page_cmds = cmds[page * COMMANDS_PER_PAGE:(page + 1) * COMMANDS_PER_PAGE]

        c = Container()
        avail_tag = "" if cat["available"] else " *(Bientôt disponible)*"
        c.add_item(TextDisplay(f"# {cat['emoji']} {cat['name']}{avail_tag}"))
        c.add_item(Separator())
        c.add_item(TextDisplay(f"`{len(cmds)}` commande(s) · page `{page + 1}/{total_pages}`"))
        c.add_item(Separator())

        if not cat["available"]:
            c.add_item(TextDisplay(
                "⏳ Ces commandes sont en cours de développement.\n"
                "Elles seront disponibles dans une prochaine mise à jour !"
            ))
            c.add_item(Separator())
        else:
            for name, usage, description, example in page_cmds:
                c.add_item(TextDisplay(
                    f"### `/{name}`\n"
                    f"**Description :** {description}\n"
                    f"**Usage :** `{usage}`\n"
                    f"**Exemple :** `{example}`"
                ))
                c.add_item(Separator())

        # Pagination
        if total_pages > 1:
            _cat_id, _page, _oid, _bot = self.cat_id, page, self.owner_id, self.bot

            prev_btn = Button(
                emoji="⬅️", style=ButtonStyle.secondary,
                custom_id=f"wiki_prev:{_cat_id}:{page}:{_oid}",
                disabled=(page == 0),
            )
            indicator = Button(
                label=f"{page + 1} / {total_pages}",
                style=ButtonStyle.secondary,
                custom_id="wiki_indicator",
                disabled=True,
            )
            next_btn = Button(
                emoji="➡️", style=ButtonStyle.secondary,
                custom_id=f"wiki_next:{_cat_id}:{page}:{_oid}",
                disabled=(page == total_pages - 1),
            )

            async def _on_prev(interaction: discord.Interaction, cid=_cat_id, p=_page, oid=_oid, b=_bot):
                await interaction.response.edit_message(view=WikiCategoryView(cid, p - 1, oid, b))

            async def _on_next(interaction: discord.Interaction, cid=_cat_id, p=_page, oid=_oid, b=_bot):
                await interaction.response.edit_message(view=WikiCategoryView(cid, p + 1, oid, b))

            prev_btn.callback = _on_prev
            next_btn.callback = _on_next
            c.add_item(ActionRow(prev_btn, indicator, next_btn))
            c.add_item(Separator())

        # Select catégorie
        _oid, _bot = self.owner_id, self.bot

        async def on_cat(interaction: discord.Interaction, oid=_oid, b=_bot) -> None:
            cat_id = interaction.data["values"][0]
            await interaction.response.edit_message(view=WikiCategoryView(cat_id, 0, oid, b))

        c.add_item(ActionRow(_make_category_select(self.owner_id, on_cat)))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="", bot=self.bot)))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideON Studio — V4"))
        self.add_item(c)


# ═══════════════════════════════════════════════════════════════
# 💬  Support
# ═══════════════════════════════════════════════════════════════

class WikiSupportView(LayoutView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 💬 Support GuideON"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Notre équipe est disponible pour t'aider !\n\n"
            "**📬 Discord :** https://discord.gg/ZKX3YQdDFT\n"
            "**🌐 Site web :** https://guideonbot.fr/\n"
            "**📧 Email :** gestion.guideon@gmail.com"
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(
            Button(label="Rejoindre le Discord", emoji="💬",
                   style=ButtonStyle.link, url="https://discord.gg/ZKX3YQdDFT"),
            Button(label="Site web", emoji="🌐",
                   style=ButtonStyle.link, url="https://guideonbot.fr/"),
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="support")))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideON Studio — nous sommes là pour t'aider !"))
        self.add_item(c)


# ═══════════════════════════════════════════════════════════════
# 🔗  Liens
# ═══════════════════════════════════════════════════════════════

class WikiLinksView(LayoutView):
    def __init__(self, owner_id: int) -> None:
        super().__init__(timeout=300)
        self.owner_id = owner_id
        self._build()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Ce menu ne t'appartient pas.", ephemeral=True)
            return False
        return True

    def _build(self) -> None:
        c = Container()
        c.add_item(TextDisplay("# 🔗 Liens GuideON"))
        c.add_item(Separator())
        c.add_item(TextDisplay(
            "Retrouvez GuideON partout :\n\n"
            "**🌐 Site web :** https://guideonbot.fr/\n"
            "**💬 Discord :** https://discord.gg/ZKX3YQdDFT\n"
            "**📊 Top.gg :** https://top.gg/bot/1184180079069249666"
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(
            Button(label="Site web", emoji="🌐",
                   style=ButtonStyle.link, url="https://guideonbot.fr/"),
            Button(label="Discord",  emoji="💬",
                   style=ButtonStyle.link, url="https://discord.gg/ZKX3YQdDFT"),
            Button(label="Top.gg",   emoji="📊",
                   style=ButtonStyle.link, url="https://top.gg/bot/1184180079069249666"),
        ))
        c.add_item(Separator())
        c.add_item(ActionRow(*_nav_buttons(self.owner_id, active="links")))
        c.add_item(Separator())
        c.add_item(TextDisplay("-# GuideON Studio — suivez-nous pour rester informé !"))
        self.add_item(c)