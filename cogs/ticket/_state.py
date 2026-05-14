"""
État éphémère du wizard de création/édition d'un panel ticket.

Cet objet vit pendant la durée d'une interaction et n'est PAS persisté en DB.
Au moment du "Publier", on l'utilise pour appeler ticket_manager.create_panel().

Préfixe `_` pour qu'il ne soit pas chargé par bot.py (load_cogs_from_directory).
"""
from dataclasses import dataclass, field


@dataclass
class TicketPanelDraft:
    """Brouillon d'un panel en cours d'édition."""

    guild_id: int

    # Obligatoires
    title: str | None = None
    description: str | None = None
    category_open_id: int | None = None
    transcript_channel_id: int | None = None
    staff_role_ids: list[int] = field(default_factory=list)

    # Optionnels
    category_closed_id: int | None = None
    ping_role_id: int | None = None
    ban_role_id: int | None = None

    def is_valid(self) -> bool:
        return all([
            self.title,
            self.description,
            self.category_open_id is not None,
            self.transcript_channel_id is not None,
            self.staff_role_ids,
        ])

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.title:
            missing.append("Titre")
        if not self.description:
            missing.append("Description")
        if self.category_open_id is None:
            missing.append("Catégorie d'ouverture")
        if self.transcript_channel_id is None:
            missing.append("Salon transcript")
        if not self.staff_role_ids:
            missing.append("Rôles staff")
        return missing
