"""
views/alpha/derank_view.py — Confirmation du derank staff Alpha.

Extrait de cogs/alpha/derank.py : la logique métier (calcul de l'état cible,
persistance DB, rôles Discord, pseudo, annonces) vit dans utils/derank_logic.py,
appelé ici une fois l'utilisateur confirmé.

Branché sur BaseLayoutView (owner_id=l'auteur de la commande) : c'est une
confirmation strictement personnelle (envoyée en followup éphémère), donc le
cas d'usage exact pour lequel BaseLayoutView apporte tout (restriction au bon
utilisateur, on_error structuré, on_timeout qui désactive les boutons) sans
aucune contrepartie.
"""
from __future__ import annotations

import logging

import discord
from discord import ButtonStyle, Interaction
from discord.ui import ActionRow, Button, Container, Separator, TextDisplay

from utils.container_universel import success_container, warning_container
from utils.db.models.alpha_staff import GRADE_LABELS, SECONDARY_STATUSES, STATUTS_SECONDAIRES_ORDER
from utils.alpha_derank_logic import execute_derank, guard_message, secondary_dict
from views._components.base_view import BaseLayoutView

log = logging.getLogger(__name__)


class DerankConfirmView(BaseLayoutView):
    """Confirmation avant l'exécution d'un derank (complet, staff, ou un statut secondaire)."""

    def __init__(
        self, membre: discord.Member, member_data: dict, cfg: dict, guild_id: int, role: str,
        *, owner_id: int,
    ) -> None:
        """Création de l'interface de confirmation du derank."""
        super().__init__(owner_id=owner_id, timeout=120)
        self.membre = membre
        self.data = member_data
        self.cfg = cfg
        self.guild_id = guild_id
        self.role = role
        self._build()

    def _build(self) -> None:
        d = self.data
        role = self.role
        grade = d["grade"]
        label = GRADE_LABELS.get(grade, grade) if grade else None
        secondary = secondary_dict(d)
        active_statuses = [SECONDARY_STATUSES[k]["label"] for k in STATUTS_SECONDAIRES_ORDER if secondary[k]]

        if role == "complet":
            extras = f" + {' + '.join(active_statuses)}" if active_statuses else ""
            grade_part = label if label else (active_statuses[0] if active_statuses else "—")
            desc = (
                f"Confirmer le **derank complet** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n\n"
                f"Statut actuel : **{grade_part}**{extras if label else ''}\n"
                "-# Rôles retirés, pseudo réinitialisé, retiré du stafflist."
            )

        elif role == "staff":
            if not grade:
                desc = f"**{d['pseudo_jeu']}** n'a **aucun grade staff** à retirer."
            else:
                remaining = ", ".join(active_statuses) if active_statuses else None
                desc = (
                    f"Retirer le grade **{label}** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n"
                    + (f"(Conservera : {remaining}.)\n" if remaining else "")
                    + "-# Rôle Discord retiré, pseudo et stafflist mis à jour."
                )

        else:  # journaliste / affilie / builder
            meta = SECONDARY_STATUSES[role]
            if not secondary[role]:
                desc = f"**{d['pseudo_jeu']}** n'est pas **{meta['label']}**."
            else:
                remaining_parts = []
                if grade:
                    remaining_parts.append(label)
                remaining_parts += [SECONDARY_STATUSES[k]["label"] for k in STATUTS_SECONDAIRES_ORDER if k != role and secondary[k]]
                remaining = ", ".join(remaining_parts) if remaining_parts else None
                desc = (
                    f"Confirmer le retrait du statut **{meta['label']}** de **{d['pseudo_jeu']}** (<@{d['discord_id']}>) ?\n"
                    + (f"(Conservera : {remaining}.)\n" if remaining else "")
                    + "-# Rôle Discord retiré, pseudo et stafflist mis à jour."
                )

        c = Container()
        c.add_item(TextDisplay("# ⚠️ Confirmation de derank"))
        c.add_item(Separator())
        c.add_item(TextDisplay(desc))
        c.add_item(Separator())

        # Note : l'emoji va dans le paramètre `emoji=`, pas dans `label=`
        # (Discord n'interprète pas les shortcodes d'emoji personnalisé à
        # l'intérieur du texte d'un label de bouton — corrigé au passage).
        btn_confirm = Button(
            label="Confirmer",
            style=ButtonStyle.danger,
            emoji="<:valider:1495444292867723284>",
        )
        btn_cancel = Button(
            label="Annuler",
            style=ButtonStyle.secondary,
            emoji="<:annuler:1495444256754761979>",
        )
        btn_confirm.callback = self._on_confirm
        btn_cancel.callback = self._on_cancel
        c.add_item(ActionRow(btn_confirm, btn_cancel))
        self.add_item(c)

    async def _on_confirm(self, interaction: Interaction) -> None:
        """Exécute le derank confirmé."""
        await interaction.response.defer()

        d = self.data
        role = self.role
        secondary = secondary_dict(d)

        # ── Garde-fous : rien à faire ────────────────────────
        warning = guard_message(role, d["pseudo_jeu"], d["grade"], secondary)
        if warning:
            await interaction.edit_original_response(view=warning_container(warning))
            self.stop()
            return

        await execute_derank(interaction.client, self.membre, d, self.cfg, self.guild_id, role)

        await interaction.edit_original_response(view=success_container(f"**{d['pseudo_jeu']}** a été derank."))
        self.stop()

    async def _on_cancel(self, interaction: Interaction) -> None:
        await interaction.response.edit_message(view=warning_container("Le **processus** de derank a été __annulé__."))
        self.stop()