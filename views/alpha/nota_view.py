"""
views/alpha/nota_views.py — Views Components V2 du système de notations Alpha.

build_presence_view    : message staff pour le vote de disponibilité
build_public_nota_view : message public avec la répartition des pays
"""
from __future__ import annotations

from discord import ButtonStyle
from discord.ui import ActionRow, Button, Container, LayoutView, Separator, TextDisplay


def build_presence_view(
    operators: list[dict],
    available_ids: list[int],
    deadline_passed: bool = False,
) -> LayoutView:
    """
    operators : liste de dicts {discord_id, label, skin_head_emoji}
    available_ids : liste des discord_id qui ont confirmé leur présence
    """
    view = LayoutView(timeout=None)
    available_set = set(available_ids)

    present = [op for op in operators if op["discord_id"] in available_set]
    waiting = [op for op in operators if op["discord_id"] not in available_set]

    # ── Header ──────────────────────────────────────────────
    c_header = Container()
    c_header.add_item(TextDisplay("## <:Alpha:1500414179650048070> Système de Notations"))
    c_header.add_item(TextDisplay("-# Confirmez votre disponibilité au plus vite !"))
    c_header.add_item(Separator())
    view.add_item(c_header)

    # ── Listes ──────────────────────────────────────────────
    c_ops = Container()
    lines = ["### ✅ __Opérateurs Disponibles__"]
    if present:
        lines += [
            f"{op.get('skin_head_emoji', '👤')} **{op['label']}**"
            for op in present
        ]
    else:
        lines.append("*Aucun pour le moment.*")

    lines += ["", "### ⏳ __En attente / Absents__"]
    if waiting:
        lines += [f"❌ {op['label']}" for op in waiting]
    else:
        lines.append("*Tout le monde est prêt !*")

    c_ops.add_item(TextDisplay("\n".join(lines)))
    c_ops.add_item(Separator())
    c_ops.add_item(TextDisplay(f"-# {len(present)}/{len(operators)} opérateur(s) disponible(s)"))
    view.add_item(c_ops)

    # ── Bouton toggle ────────────────────────────────────────
    c_btn = Container()
    c_btn.add_item(ActionRow(Button(
        label="Vote fermé" if deadline_passed else "Je suis présent",
        style=ButtonStyle.secondary if deadline_passed else ButtonStyle.success,
        custom_id="notation_presence_toggle",
        emoji="🔒" if deadline_passed else "✍️",
        disabled=deadline_passed,
    )))
    view.add_item(c_btn)

    return view


def build_public_nota_view(
    week_date: str,
    assignments: list[tuple[int, int, int]],
    operators_by_id: dict[int, dict],
    url_country_lookup: str | None = None,
) -> LayoutView:
    """
    assignments      : [(start, end, discord_id), ...]
    operators_by_id  : {discord_id: {label, skin_head_emoji, ...}}
    """
    view = LayoutView(timeout=None)

    # ── Header ──────────────────────────────────────────────
    c_header = Container()
    c_header.add_item(TextDisplay(f"# 🗺️ Semaine de Notation — {week_date}"))
    c_header.add_item(Separator())
    view.add_item(c_header)

    # ── Répartition ──────────────────────────────────────────
    c_ranges = Container()
    if assignments:
        lines = []
        for start, end, discord_id in assignments:
            op = operators_by_id.get(discord_id, {})
            emoji = op.get("skin_head_emoji", "👤")
            label = op.get("label", f"<@{discord_id}>")
            lines.append(f"{emoji} **Pays {start} → {end}** · {label}")
        c_ranges.add_item(TextDisplay("\n".join(lines)))
    else:
        c_ranges.add_item(TextDisplay("⚠️ Aucune donnée de répartition disponible."))
    c_ranges.add_item(Separator())
    view.add_item(c_ranges)

    # ── Instructions ─────────────────────────────────────────
    c_info = Container()
    c_info.add_item(TextDisplay(
        "📌 Consultez les messages épinglés pour connaître le numéro de votre pays.\n"
        "-# Pour toute réclamation, contactez le staff qui vous a noté."
    ))
    c_info.add_item(Separator())
    c_info.add_item(TextDisplay("-# GuideOn Studio"))
    view.add_item(c_info)

    # ── Bouton lien (optionnel) ──────────────────────────────
    if url_country_lookup:
        c_btn = Container()
        c_btn.add_item(ActionRow(Button(
            label="Voir le numéro de mon pays",
            style=ButtonStyle.link,
            url=url_country_lookup,
        )))
        view.add_item(c_btn)

    return view