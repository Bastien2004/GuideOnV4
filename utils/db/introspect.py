"""
utils/db/introspect.py — Introspection et lecture générique des tables de la
base de données, pour un outil de diagnostic (/dev database).

STRICTEMENT LECTURE SEULE : ce module ne fait que des SELECT (via SQLAlchemy
Core, sur les Table déjà déclarées par les modèles de utils.db.models — pas
de SQL brut, pas d'écriture, aucune fonction ici ne doit jamais faire
d'INSERT/UPDATE/DELETE).

La liste des tables provient de Base.metadata (donc de utils.db.models, qui
importe centralement tous les modèles) : toujours synchronisée avec le
schéma réel du code, sans liste à maintenir à la main.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Table, func, select

import utils.db.models as _models  # noqa: F401  (déclenche l'import de tous les modèles)
from utils.db.base import Base
from utils.db.session import get_session

PREVIEW_LIMIT = 10
SEARCH_LIMIT = 10
VALUE_MAX_LEN = 150


class ColumnNotFoundError(Exception):
    """La colonne demandée n'existe pas dans la table."""


class InvalidSearchValueError(Exception):
    """La valeur fournie n'est pas compatible avec le type de la colonne."""


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    type_str: str
    primary_key: bool
    unique: bool
    nullable: bool
    foreign_key: bool


# ══════════════════════════════════════════════════════════════════════════
# 📖 Introspection (sync, depuis les métadonnées SQLAlchemy déjà chargées)
# ══════════════════════════════════════════════════════════════════════════

def list_table_names() -> list[str]:
    """Toutes les tables connues du code (via Base.metadata), triées."""
    return sorted(Base.metadata.tables.keys())


def get_table(name: str) -> Table | None:
    """Renvoie la Table SQLAlchemy correspondant à ce nom, ou None."""
    return Base.metadata.tables.get(name)


def describe_table(table: Table) -> list[ColumnInfo]:
    """Colonnes de la table, avec type et indicateurs clé primaire/unique."""
    return [
        ColumnInfo(
            name=col.name,
            type_str=str(col.type),
            primary_key=col.primary_key,
            unique=bool(col.unique) or col.primary_key,
            nullable=col.nullable,
            foreign_key=bool(col.foreign_keys),
        )
        for col in table.columns
    ]


def list_indexed_columns(table: Table) -> list[str]:
    """
    Colonnes utilisables comme "indice" pour retrouver une ligne rapidement :
    clé primaire, colonnes uniques, colonnes indexées, et clés étrangères
    (souvent le point d'entrée le plus utile, ex: guild_id).

    Purement indicatif — la recherche (fetch_by_column) accepte en réalité
    n'importe quelle colonne réelle de la table, pas seulement celles-ci.
    """
    cols: set[str] = set()
    for col in table.columns:
        if col.primary_key or col.unique or col.foreign_keys:
            cols.add(col.name)
    for index in table.indexes:
        for col in index.columns:
            cols.add(col.name)
    return sorted(cols)


# ══════════════════════════════════════════════════════════════════════════
# 🔎 Lecture (async, DB réelle — jamais de cache)
# ══════════════════════════════════════════════════════════════════════════

async def count_rows(table: Table) -> int:
    async with get_session() as session:
        return (await session.execute(select(func.count()).select_from(table))).scalar_one()


async def fetch_preview(table: Table, *, limit: int = PREVIEW_LIMIT) -> list[dict]:
    """Les `limit` premières lignes de la table, telles quelles."""
    async with get_session() as session:
        rows = (await session.execute(select(table).limit(limit))).mappings().all()
    return [dict(r) for r in rows]


def _cast_value(column, raw: str):
    """Convertit la valeur texte saisie vers le type Python de la colonne."""
    try:
        py_type = column.type.python_type
    except NotImplementedError:
        py_type = str

    raw = raw.strip()
    try:
        if py_type is bool:
            return raw.lower() in ("1", "true", "vrai", "oui", "yes")
        if py_type is int:
            return int(raw)
        if py_type is float:
            return float(raw)
        return raw
    except ValueError as e:
        raise InvalidSearchValueError(
            f"Valeur `{raw}` incompatible avec le type `{column.type}` de la colonne `{column.name}`."
        ) from e


async def fetch_by_column(
    table: Table, column_name: str, raw_value: str, *, limit: int = SEARCH_LIMIT
) -> list[dict]:
    """
    Recherche par égalité sur une colonne quelconque de la table.

    Lève ColumnNotFoundError si la colonne n'existe pas, ou
    InvalidSearchValueError si la valeur ne peut pas être convertie vers le
    type de la colonne. Requête paramétrée (aucune concaténation de SQL) —
    aucun risque d'injection malgré la saisie libre côté Discord.
    """
    if column_name not in table.c:
        raise ColumnNotFoundError(f"Colonne `{column_name}` introuvable dans `{table.name}`.")

    column = table.c[column_name]
    value = _cast_value(column, raw_value)

    async with get_session() as session:
        rows = (
            await session.execute(select(table).where(column == value).limit(limit))
        ).mappings().all()
    return [dict(r) for r in rows]


def format_value(value) -> str:
    """Rendu compact d'une valeur de colonne pour l'affichage Discord (hors tableau)."""
    if value is None:
        return "`NULL`"
    text = str(value)
    if len(text) > VALUE_MAX_LEN:
        text = text[:VALUE_MAX_LEN] + "…"
    return f"`{text}`"


def format_value_plain(value, *, max_len: int = VALUE_MAX_LEN) -> str:
    """
    Même rendu que format_value, mais SANS les backticks — pour une valeur
    déjà destinée à l'intérieur d'un bloc de code (```...```), où des
    backticks casseraient le rendu.
    """
    if value is None:
        return "NULL"
    text = str(value)
    if len(text) > max_len:
        text = text[:max_len] + "…"
    return text