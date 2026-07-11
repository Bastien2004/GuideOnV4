"""
scripts/fix_ticket_open_counts.py — Recalcule open_tickets_count (réparation
one-shot, à lancer UNE FOIS après le déploiement du fix delete_ticket()).

Contexte :
    utils.managers.ticket_manager.delete_ticket() avait un garde `was_open`
    qui empêchait quasi-systématiquement la décrémentation d'open_tickets_count
    à la suppression d'un ticket (voir le fix apporté à cette fonction). Résultat :
    open_tickets_count n'a fait QUE croître depuis le lancement du système, sur
    tous les panels — d'où la limite temporairement montée à 1000/100.

    Le fix corrige le comportement pour les *futures* créations/suppressions,
    mais ne corrige PAS rétroactivement les valeurs déjà fausses en DB. Ce
    script recalcule open_tickets_count à partir de la source de vérité (le
    nombre de lignes dans `tickets` pour chaque panel — un ticket occupe un
    "slot" tant que sa ligne existe, qu'il soit closed=True ou False, exactement
    comme le fait maintenant delete_ticket()).

    Ne touche JAMAIS à la table `tickets` elle-même, ni à deleted_tickets_count
    ni à `counter` (numérotation) — uniquement à la colonne open_tickets_count
    de `ticket_panels`.

Sécurité :
    - DRY-RUN par défaut : affiche uniquement le diff (ancien → nouveau),
      n'écrit rien en DB.
    - Écriture réelle seulement avec le flag --apply.
    - Idempotent : relançable sans risque, un panel déjà correct n'est pas
      touché (pas de UPDATE si old == new).
    - Peut être lancé bot allumé, aucun downtime requis : ce script écrit
      uniquement en DB, il ne touche pas au cache mémoire du bot (TTL 60s,
      utils.managers.ticket_manager). Le bot peut donc mettre jusqu'à 60s à
      refléter la correction après le --apply, le temps que son cache expire
      et se recharge tout seul — aucune action manuelle nécessaire, aucun
      redémarrage requis.

Usage :
    python -m scripts.fix_ticket_open_counts            # dry-run (affichage seul)
    python -m scripts.fix_ticket_open_counts --apply     # applique réellement
"""
from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select, update

from utils.db.models.ticket import Ticket, TicketPanel
from utils.db.session import get_session
from utils.logging_config import setup_logging

log = logging.getLogger(__name__)


async def _compute_diffs() -> list[tuple[TicketPanel, int, int]]:
    """Renvoie [(panel, ancienne_valeur, vraie_valeur), ...] pour tous les panels."""
    async with get_session() as session:
        panels = (await session.execute(select(TicketPanel))).scalars().all()

        real_counts_rows = (
            await session.execute(
                select(Ticket.panel_fk, func.count())
                .group_by(Ticket.panel_fk)
            )
        ).all()
        real_counts = {panel_fk: count for panel_fk, count in real_counts_rows}

        diffs = []
        for panel in panels:
            real = real_counts.get(panel.id, 0)
            if real != panel.open_tickets_count:
                diffs.append((panel, panel.open_tickets_count, real))
        return diffs


async def _apply_fix(diffs: list[tuple[TicketPanel, int, int]]) -> None:
    async with get_session() as session:
        for panel, _old, new in diffs:
            await session.execute(
                update(TicketPanel)
                .where(TicketPanel.id == panel.id)
                .values(open_tickets_count=new)
            )


async def main(apply: bool) -> None:
    setup_logging()

    diffs = await _compute_diffs()

    if not diffs:
        log.info("Rien à corriger — open_tickets_count est déjà exact sur tous les panels.")
        return

    log.info("%d panel(s) avec un open_tickets_count incorrect :", len(diffs))
    for panel, old, new in diffs:
        log.info(
            "  guild=%s panel_id=%s (%r) : %d -> %d",
            panel.guild_id, panel.panel_id, panel.title, old, new,
        )

    if not apply:
        log.info(
            "Dry-run terminé (aucune écriture). Relance avec --apply pour appliquer ces %d correction(s).",
            len(diffs),
        )
        return

    await _apply_fix(diffs)
    log.info("%d panel(s) corrigé(s) en DB.", len(diffs))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recalcule open_tickets_count des panels de tickets.")
    parser.add_argument("--apply", action="store_true", help="Applique réellement les corrections (sinon dry-run).")
    args = parser.parse_args()

    asyncio.run(main(apply=args.apply))