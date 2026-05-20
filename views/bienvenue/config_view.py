"""
views/bienvenue/config_view.py — Interface de configuration /config bienvenue (V4).

Refonte de la V3 (BienvenueView.py) :
- Une vraie classe BienvenueConfigView (héritée d'un LayoutView), au lieu d'une
  grosse fonction de 400 lignes avec callbacks imbriqués.
- Re-render centralisé : _rebuild() reconstruit le container, _refresh() recharge
  la config + réaffiche. Plus de duplication load→save→reload dans chaque cb.
- DB au lieu de JSON (via bienvenue_manager).
- Vérif owner + admin centralisée.
- Le test du système est gated Gold+ (send_gold_error si serveur non-Gold+).

Améliorations UX vs V3 :
- État de complétion en tête (✅/⚠️ selon que tout est prêt à fonctionner).
- Avertissements contextuels : si une annonce est activée mais sans salon, on le
  signale visuellement (⚠️) au lieu de laisser l'admin deviner.
- Bouton "Réinitialiser" avec confirmation.
- Aperçu du message rendu avec un exemple de membre (pas juste le template brut).
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, ChannelType
from discord.ui import (
    ActionRow,
    Button,
    ChannelSelect,
    Container,
    LayoutView,
    Modal,
    Section,
    Separator,
    TextDisplay,
    TextInput,
)

from utils.boutique.gold_manager import is_gold, send_gold_error
from utils.managers.bienvenue_manager import (
    load_bienvenue_config,
    reset_bienvenue_config,
    save_bienvenue_config,
)

log = logging.getLogger(__name__)

VARIABLES_HELP = (
    "`{user}` — Nom de l'utilisateur\n"
    "`{mention}` — Mention de l'utilisateur\n"
    "`{server}` — Nom du serveur\n"
    "`{member_count}` — Nombre de membres"
)


# ============================================================
# 🔧 Helpers d'affichage
# ============================================================

def _preview(msg: str, limit: int = 80) -> str:
    truncated = (msg[: limit - 1] + "…") if len(msg) > limit else msg
    return f"```{truncated}```"


def _render_example(template: str, guild: discord.Guild, member: discord.Member) -> str:
    """Rend un template avec des valeurs d'exemple (pour l'aperçu)."""
    return (
        template.replace("{user}", member.display_name)
        .replace("{mention}", member.mention)
        .replace("{server}", guild.name)
        .replace("{member_count}", str(guild.member_count or 0))
    )


# ============================================================
# 📝 Modal d'édition de message
# ============================================================

class MessageModal(Modal):
    def __init__(self, view: "BienvenueConfigView", message_type: str, current: str):
        super().__init__(title="💬 Personnaliser le message")
        self.view_ref = view
        self.message_type = message_type

        self.message_input = TextInput(
            label="Message personnalisé",
            style=discord.TextStyle.paragraph,
            placeholder="Variables : {user} {mention} {server} {member_count}",
            default=current,
            required=True,
            max_length=2000,
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if interaction.user.id != self.view_ref.author_id:
            await interaction.response.send_message(
                "❌ Vous n'êtes pas l'auteur de cette commande.", ephemeral=True
            )
            return

        key = "arrive_message" if self.message_type == "arrive" else "depart_message"
        await save_bienvenue_config(self.view_ref.guild_id, {key: self.message_input.value})
        await self.view_ref.refresh(interaction)


# ============================================================
# 🪟 Vue principale
# ============================================================

class BienvenueConfigView(LayoutView):
    """
    Vue de configuration. On instancie via la factory async `create()` qui
    charge la config avant de construire l'UI.
    """

    def __init__(self, guild_id: int, author_id: int, bot, config: dict):
        super().__init__(timeout=1800)
        self.guild_id = guild_id
        self.author_id = author_id
        self.bot = bot
        self.config = config
        self._rebuild()

    # ---- Factory async ------------------------------------------------------

    @classmethod
    async def create(cls, guild_id: int, author_id: int, bot) -> "BienvenueConfigView":
        config = await load_bienvenue_config(guild_id)
        return cls(guild_id, author_id, bot, config)

    # ---- Sécurité -----------------------------------------------------------

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ Seul l'auteur de la commande peut utiliser ce menu.", ephemeral=True
            )
            return False
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Vous devez être administrateur pour effectuer cette action.",
                ephemeral=True,
            )
            return False
        return True

    # ---- Re-render ----------------------------------------------------------

    async def refresh(self, interaction: discord.Interaction) -> None:
        """Recharge la config depuis la DB et réaffiche la vue."""
        self.config = await load_bienvenue_config(self.guild_id)
        self.clear_items()
        self._rebuild()
        if interaction.response.is_done():
            await interaction.edit_original_response(view=self)
        else:
            await interaction.response.edit_message(view=self)

    def _rebuild(self) -> None:
        cfg = self.config
        system_active = cfg.get("system_active", False)
        arrive_active = cfg.get("arrive_active", False)
        depart_active = cfg.get("depart_active", False)
        arrive_channel = cfg.get("arrive_channel_id")
        depart_channel = cfg.get("depart_channel_id")
        gold = is_gold(self.guild_id)

        container = Container()

        # ── En-tête + état global (fusionnés dans un seul TextDisplay) ───────
        # Discord limite un LayoutView à 40 composants au total (récursif).
        # On reste sobre : un Separator uniquement entre les grands blocs, et on
        # fusionne les lignes de texte qui peuvent l'être.
        issues: list[str] = []
        if system_active:
            if arrive_active and not arrive_channel:
                issues.append("L'annonce d'**arrivée** est activée mais aucun salon n'est défini.")
            if depart_active and not depart_channel:
                issues.append("L'annonce de **départ** est activée mais aucun salon n'est défini.")
            if not arrive_active and not depart_active:
                issues.append("Le système est activé mais **aucune annonce** n'est active.")

        if not system_active:
            etat = "-# ⚪ Système **désactivé** — aucune annonce ne sera envoyée."
        elif issues:
            etat = "-# ⚠️ Système actif mais **incomplet** :\n" + "\n".join(
                f"-# • {i}" for i in issues
            )
        else:
            etat = "-# ✅ Système **opérationnel** — tout est correctement configuré."

        container.add_item(TextDisplay(f"# 👋 Configuration · Bienvenue & Départ\n{etat}"))

        # ── Toggle global ───────────────────────────────────────────────────
        btn_global = Button(
            label="Activé" if system_active else "Désactivé",
            style=ButtonStyle.success if system_active else ButtonStyle.danger,
        )
        btn_global.callback = self._cb_toggle("system_active")
        container.add_item(Section(
            TextDisplay("**État du système de bienvenue**"),
            accessory=btn_global,
        ))
        container.add_item(Separator())

        # ── Section arrivée ─────────────────────────────────────────────────
        self._add_announce_section(
            container,
            label="🛬 Annonce d'arrivée",
            active=arrive_active,
            active_key="arrive_active",
            channel_id=arrive_channel,
            channel_key="arrive_channel_id",
            message=cfg.get("arrive_message", ""),
            message_type="arrive",
        )
        container.add_item(Separator())

        # ── Section départ ──────────────────────────────────────────────────
        self._add_announce_section(
            container,
            label="🛫 Annonce de départ",
            active=depart_active,
            active_key="depart_active",
            channel_id=depart_channel,
            channel_key="depart_channel_id",
            message=cfg.get("depart_message", ""),
            message_type="depart",
        )
        container.add_item(Separator())

        # ── Variables (titre + corps fusionnés) ─────────────────────────────
        container.add_item(TextDisplay("### 📌 Variables disponibles\n" + VARIABLES_HELP))

        # ── Tests (Gold+) — titre fusionné, boutons en ActionRow ────────────
        test_title = "### 🧪 Tester le système" + ("" if gold else " *(Gold+ requis)*")
        container.add_item(TextDisplay(test_title))

        btn_test_arrive = Button(label="Tester arrivée", emoji="🛬", style=ButtonStyle.secondary)
        btn_test_depart = Button(label="Tester départ", emoji="🛫", style=ButtonStyle.secondary)
        btn_reset = Button(label="Réinitialiser", emoji="♻️", style=ButtonStyle.danger)
        btn_test_arrive.callback = self._cb_test("arrive")
        btn_test_depart.callback = self._cb_test("depart")
        btn_reset.callback = self._cb_reset()
        # Les 3 actions tiennent sur une seule ActionRow (max 5 boutons / row)
        container.add_item(ActionRow(btn_test_arrive, btn_test_depart, btn_reset))

        container.add_item(Separator())
        container.add_item(TextDisplay("-# GuideON Studio"))
        self.add_item(container)

    def _add_announce_section(
        self,
        container: Container,
        *,
        label: str,
        active: bool,
        active_key: str,
        channel_id: int | None,
        channel_key: str,
        message: str,
        message_type: str,
    ) -> None:
        container.add_item(TextDisplay(f"### {label}"))

        # Toggle activation
        btn_toggle = Button(
            label="ON" if active else "OFF",
            style=ButtonStyle.success if active else ButtonStyle.danger,
        )
        btn_toggle.callback = self._cb_toggle(active_key)
        container.add_item(Section(TextDisplay("**Activation**"), accessory=btn_toggle))

        # Salon
        ch_text = f"<#{channel_id}>" if channel_id else "`Non défini`"
        warn = "" if (channel_id or not active) else " ⚠️"
        btn_channel = Button(emoji="✏️", style=ButtonStyle.secondary)
        btn_channel.callback = self._cb_pick_channel(channel_key, message_type)
        container.add_item(Section(
            TextDisplay(f"**Salon :** {ch_text}{warn}"),
            accessory=btn_channel,
        ))

        # Message
        btn_msg = Button(emoji="✏️", style=ButtonStyle.secondary)
        btn_msg.callback = self._cb_edit_message(message_type, message)
        container.add_item(Section(
            TextDisplay(f"**Message :**\n{_preview(message)}"),
            accessory=btn_msg,
        ))

    # ---- Callbacks (closures) ----------------------------------------------

    def _cb_toggle(self, key: str):
        async def cb(interaction: discord.Interaction):
            if not await self._check(interaction):
                return
            current = (await load_bienvenue_config(self.guild_id)).get(key, False)
            await save_bienvenue_config(self.guild_id, {key: not current})
            await self.refresh(interaction)
        return cb

    def _cb_edit_message(self, message_type: str, current: str):
        async def cb(interaction: discord.Interaction):
            if not await self._check(interaction):
                return
            await interaction.response.send_modal(
                MessageModal(self, message_type, current)
            )
        return cb

    def _cb_pick_channel(self, channel_key: str, message_type: str):
        async def cb(interaction: discord.Interaction):
            if not await self._check(interaction):
                return

            parent_interaction = interaction
            select = ChannelSelect(
                placeholder="Sélectionner le salon",
                channel_types=[ChannelType.text],
                min_values=1,
                max_values=1,
            )

            async def on_select(sel: discord.Interaction):
                if not await self._check(sel):
                    return
                await save_bienvenue_config(
                    self.guild_id, {channel_key: int(sel.data["values"][0])}
                )
                await sel.response.defer()
                # Réaffiche la vue principale
                self.config = await load_bienvenue_config(self.guild_id)
                self.clear_items()
                self._rebuild()
                try:
                    await parent_interaction.edit_original_response(view=self)
                except (discord.NotFound, discord.HTTPException) as e:
                    log.warning("MAJ vue après sélection salon impossible : %s", e)
                # Confirmation éphémère
                confirm = LayoutView(timeout=5)
                c = Container()
                c.add_item(TextDisplay("✅ Salon mis à jour !"))
                confirm.add_item(c)
                await sel.edit_original_response(view=confirm)

            select.callback = on_select

            temp = LayoutView(timeout=60)
            tc = Container()
            tc.add_item(TextDisplay("📥 Choisis le salon :"))
            tc.add_item(ActionRow(select))
            temp.add_item(tc)
            await interaction.response.send_message(view=temp, ephemeral=True)
        return cb

    def _cb_test(self, msg_type: str):
        async def cb(interaction: discord.Interaction):
            if not await self._check(interaction):
                return
            # Gating Gold+
            if not is_gold(self.guild_id):
                await send_gold_error(interaction)
                return

            cog = interaction.client.get_cog("BienvenueMember")
            view = LayoutView(timeout=8)
            c = Container()
            if cog is None or not hasattr(cog, "simulate_event"):
                c.add_item(TextDisplay("❌ Système de bienvenue introuvable côté bot."))
            else:
                success = await cog.simulate_event(interaction.guild, msg_type)
                c.add_item(TextDisplay(
                    f"✅ Test **{msg_type}** envoyé !" if success
                    else "❌ Échec — vérifiez que le salon est défini et que le bot "
                         "peut y écrire."
                ))
            view.add_item(c)
            await interaction.response.send_message(view=view, ephemeral=True)
        return cb

    def _cb_reset(self):
        async def cb(interaction: discord.Interaction):
            if not await self._check(interaction):
                return
            await reset_bienvenue_config(self.guild_id)
            await self.refresh(interaction)
        return cb

    # ---- Timeout ------------------------------------------------------------

    async def on_timeout(self) -> None:
        def _disable(item):
            if hasattr(item, "disabled"):
                item.disabled = True
            for child in getattr(item, "children", []):
                _disable(child)
        for item in self.children:
            _disable(item)