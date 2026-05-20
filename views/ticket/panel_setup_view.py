"""
Wizard de création/édition d'un panel ticket.

PATRON À SUIVRE pour les autres wizards :
La View ne fait QUE l'assemblage. Chaque bouton/select est dans son propre fichier.
L'état est dans une dataclass (cogs/ticket/_state.py).
"""
from __future__ import annotations

import discord

from cogs.ticket._state import TicketPanelDraft
from views._components.wizard_view import WizardView
from views.ticket.category_select import CategorySelect
from views.ticket.description_button import DescriptionButton
from views.ticket.publish_button import PublishButton
from views.ticket.staff_roles_select import StaffRolesSelect
from views.ticket.title_button import TitleButton
from views.ticket.transcript_select import TranscriptSelect
from views.ticket.embeds import build_setup_embed


class PanelSetupView(WizardView):
    def __init__(self, draft: TicketPanelDraft, *, owner_id: int):
        super().__init__(draft, owner_id=owner_id, timeout=900)
        self.draft: TicketPanelDraft = draft

        # Row 0 : catégorie d'ouverture
        self.add_item(CategorySelect(draft, parent=self, row=0))
        # Row 1 : salon de transcript
        self.add_item(TranscriptSelect(draft, parent=self, row=1))
        # Row 2 : rôles staff
        self.add_item(StaffRolesSelect(draft, parent=self, row=2))
        # Row 3 : modals titre + description
        self.add_item(TitleButton(draft, parent=self, row=3))
        self.add_item(DescriptionButton(draft, parent=self, row=3))
        # Row 4 : action finale
        self.add_item(PublishButton(draft, parent=self, row=4))

    def build_embed(self) -> discord.Embed:
        return build_setup_embed(self.draft)
