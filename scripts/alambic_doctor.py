"""
scripts/alembic_doctor.py — diagnostic Alembic complet, 100% LECTURE SEULE.

Objectif : réunir en UNE commande tout ce qu'il a fallu vérifier à la
main lors de l'incident du 2026-09 (une révision `26ed1e229c53`
tamponnée en base sans fichier correspondant, ayant fait planter
`alembic upgrade head`/`current`) — et le généraliser à TOUTE la base
(pas seulement MEDIALINK), pour que la prochaine fois ça prenne 2
minutes au lieu d'une session de debug.

CE SCRIPT NE MODIFIE RIEN : aucun DDL, aucun INSERT/UPDATE/DELETE, aucun
alembic stamp/upgrade/downgrade n'est exécuté. Il ne fait que lire
(fichiers de migrations + base de données) et imprimer un rapport. Les
corrections éventuelles sont juste suggérées en texte, à lancer à la
main volontairement.

Contrôles effectués :
  1. Intégrité de la chaîne de migrations (fichiers migrations/versions/) :
     têtes multiples, doublons de revision id, fichiers illisibles.
  2. État réel de la base (table alembic_version) comparé aux fichiers :
     détecte une revision "fantôme" (le bug qu'on vient de corriger).
  3. Dérive schéma réel vs modèles SQLAlchemy (utils/db/models) : pour
     CHAQUE modèle enregistré (pas juste MEDIALINK) — tables manquantes,
     colonnes manquantes/en trop, contraintes et index absents.

Usage (depuis la racine du projet — là où se trouve alembic.ini) :
    python3 alembic_doctor.py
    docker exec -it guideon-v4-bot python3 alembic_doctor.py   # si copié dans le conteneur
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Connection

# ── Repérage d'alembic.ini (le script doit tourner depuis la racine du
# projet, comme la commande `alembic` elle-même) ──────────────────────
PROJECT_ROOT = Path.cwd()
ALEMBIC_INI = PROJECT_ROOT / "alembic.ini"

W = 78


def _title(txt: str) -> None:
    print()
    print("=" * W)
    print(txt)
    print("=" * W)


def _sub(txt: str) -> None:
    print()
    print(f"── {txt} " + "─" * max(0, W - 4 - len(txt)))


def _mask_url(url: str) -> str:
    """Masque le mot de passe dans une URL de connexion avant affichage."""
    return re.sub(r"(://[^:/@]+:)[^@]+(@)", r"\1***\2", url)


PROBLEMS: list[str] = []
WARNINGS: list[str] = []


def problem(msg: str) -> None:
    PROBLEMS.append(msg)
    print(f"❌ {msg}")


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"⚠️  {msg}")


def ok(msg: str) -> None:
    print(f"✅ {msg}")


# ════════════════════════════════════════════════════════════════════
# 1) Config Alembic
# ════════════════════════════════════════════════════════════════════

def check_config():
    _title("1) CONFIGURATION ALEMBIC")

    if not ALEMBIC_INI.exists():
        problem(
            f"alembic.ini introuvable dans {PROJECT_ROOT} — lance ce script "
            "depuis la racine du projet (là où tu lances `alembic ...` normalement)."
        )
        return None

    ok(f"alembic.ini trouvé : {ALEMBIC_INI}")

    from alembic.config import Config

    cfg = Config(str(ALEMBIC_INI))
    script_location = cfg.get_main_option("script_location")
    file_template = cfg.get_main_option("file_template")
    print(f"  script_location : {script_location}")
    print(f"  file_template   : {file_template}")

    try:
        from utils.settings import settings
        print(f"  database_url (settings) : {_mask_url(settings.database_url)}")
    except Exception as e:
        warn(f"Impossible de lire settings.database_url : {e}")

    return cfg


# ════════════════════════════════════════════════════════════════════
# 2) Intégrité de la chaîne de migrations (fichiers uniquement)
# ════════════════════════════════════════════════════════════════════

def check_migration_chain(cfg):
    _title("2) CHAÎNE DE MIGRATIONS (fichiers migrations/versions/)")

    versions_dir = PROJECT_ROOT / "migrations" / "versions"
    if not versions_dir.exists():
        problem(f"Dossier introuvable : {versions_dir}")
        return None, None

    py_files = sorted(versions_dir.glob("*.py"))
    print(f"  {len(py_files)} fichier(s) .py dans migrations/versions/")

    # ── Scan direct des fichiers (indépendant d'Alembic) : détecte les
    # doublons de revision id et les fichiers où revision/down_revision
    # ne sont pas des littéraux simples à repérer par regex — un
    # signal fort d'un fichier corrompu même si Alembic ne dit rien.
    _sub("Scan brut des fichiers (regex, indépendant du loader Alembic)")
    # Type annotation optionnelle (` : str` / `: Union[str, None]` / ...) —
    # certains fichiers plus anciens du repo écrivent juste
    # `revision = '...'` sans annotation, il ne faut pas la rendre obligatoire.
    rev_re = re.compile(r"^revision\s*(?::[^=\n]*)?=\s*['\"]([0-9a-fA-F_]+)['\"]", re.MULTILINE)
    down_re = re.compile(r"^down_revision\s*(?::[^=\n]*)?=\s*['\"]?([0-9a-fA-F_]+|None)['\"]?", re.MULTILINE)

    seen_revisions: dict[str, Path] = {}
    file_info: dict[str, dict] = {}
    for f in py_files:
        try:
            content = f.read_text(encoding="utf-8")
        except Exception as e:
            problem(f"{f.name} : illisible ({e})")
            continue

        m_rev = rev_re.search(content)
        m_down = down_re.search(content)
        if not m_rev:
            problem(f"{f.name} : pas de 'revision = ...' détectable (fichier corrompu/tronqué ?)")
            continue

        rev = m_rev.group(1)
        down = None if not m_down or m_down.group(1) == "None" else m_down.group(1)

        if rev in seen_revisions:
            problem(
                f"Revision id EN DOUBLE : '{rev}' apparaît dans {seen_revisions[rev].name} "
                f"ET {f.name} — Alembic ne peut pas distinguer les deux."
            )
        seen_revisions[rev] = f
        file_info[rev] = {"file": f, "down": down}

    if not PROBLEMS:
        ok(f"{len(seen_revisions)} revision id uniques, tous parsables.")

    # ── Chaîne logique : down_revision de chaque fichier doit exister
    # (sauf le tout premier, down_revision=None).
    _sub("Chaînage down_revision → revision")
    known = set(file_info.keys())
    roots = []
    referenced_as_down = set()
    for rev, info in file_info.items():
        down = info["down"]
        referenced_as_down.add(down)
        if down is None:
            roots.append(rev)
        elif down not in known:
            problem(
                f"{info['file'].name} : down_revision='{down}' ne correspond à AUCUN "
                "fichier présent — chaîne cassée à cet endroit."
            )

    if len(roots) == 0:
        problem("Aucune migration racine (down_revision=None) trouvée — chaîne incomplète.")
    elif len(roots) > 1:
        warn(f"{len(roots)} racines trouvées (down_revision=None) : {roots} — plusieurs chaînes indépendantes ?")
    else:
        ok(f"1 racine : {roots[0]} ({file_info[roots[0]]['file'].name})")

    # Têtes = revisions jamais référencées comme down_revision par une autre.
    heads_from_files = known - referenced_as_down
    if len(heads_from_files) == 0:
        problem("Aucune tête détectée (cycle dans la chaîne ?).")
    elif len(heads_from_files) > 1:
        warn(
            f"PLUSIEURS TÊTES détectées : {sorted(heads_from_files)} — Alembic refusera "
            "`upgrade head` tant que ce n'est pas résolu (une seule tête autorisée, sauf "
            "branches explicites). Fichiers concernés : "
            + ", ".join(file_info[h]["file"].name for h in heads_from_files)
        )
    else:
        head = next(iter(heads_from_files))
        ok(f"1 seule tête (attendu) : {head} ({file_info[head]['file'].name})")

    # ── Cross-check avec le ScriptDirectory officiel d'Alembic (le
    # même mécanisme que la vraie commande `alembic` utilise) — si ça
    # diverge du scan brut ci-dessus, ou si ça lève une exception,
    # c'est un signal très fort.
    _sub("Vérification via alembic.script.ScriptDirectory (le vrai loader)")
    script = None
    if cfg is not None:
        try:
            from alembic.script import ScriptDirectory

            script = ScriptDirectory.from_config(cfg)
            official_heads = script.get_heads()
            ok(f"ScriptDirectory chargé sans erreur. Tête(s) officielle(s) : {official_heads}")
            if set(official_heads) != heads_from_files:
                warn(
                    f"Le scan brut ({sorted(heads_from_files)}) et ScriptDirectory "
                    f"({sorted(official_heads)}) ne sont PAS d'accord — investiguer en priorité."
                )
        except Exception as e:
            problem(f"ScriptDirectory a levé une exception en chargeant les fichiers : {e!r}")

    return script, file_info


# ════════════════════════════════════════════════════════════════════
# 3) État réel de la base vs fichiers
# ════════════════════════════════════════════════════════════════════

async def check_db_vs_files(script, file_info):
    _title("3) ÉTAT DE LA BASE (alembic_version) vs FICHIERS")

    try:
        from utils.db.engine import engine
    except Exception as e:
        problem(f"Impossible d'importer utils.db.engine : {e}")
        return

    try:
        async with engine.connect() as conn:
            exists = (
                await conn.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_name='alembic_version')"
                    )
                )
            ).scalar()

            if not exists:
                warn("Table alembic_version absente — la base n'a jamais été migrée par Alembic.")
                return

            rows = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
            print(f"  Contenu brut de alembic_version : {rows}")

            if len(rows) == 0:
                warn("Table alembic_version vide (0 ligne).")
            elif len(rows) > 1:
                warn(f"{len(rows)} lignes dans alembic_version (multi-head stampé) : {rows}")

            for rev in rows:
                if file_info is not None and rev in file_info:
                    ok(f"'{rev}' → fichier trouvé : {file_info[rev]['file'].name}")
                else:
                    problem(
                        f"'{rev}' est tamponné en base mais NE CORRESPOND À AUCUN FICHIER "
                        "dans migrations/versions/ — revision fantôme (c'est exactement le bug "
                        "du 2026-09). Cause typique : quelqu'un a fait tourner une migration "
                        "jamais committée sur git, ou un `alembic stamp` avec un mauvais ID."
                    )

            if script is not None and file_info is not None:
                known_heads = {h for h in script.get_heads()}
                current = set(rows)
                if current and current.issubset(file_info.keys()):
                    if current == known_heads:
                        ok("La base est exactement à jour (head).")
                    else:
                        try:
                            pending = list(script.iterate_revisions(known_heads, current))
                            pending_files = [r.path.split("/")[-1] for r in reversed(pending)]
                            if pending_files:
                                warn(
                                    f"La base est EN RETARD de {len(pending_files)} migration(s) : "
                                    + ", ".join(pending_files)
                                )
                        except Exception as e:
                            warn(f"Impossible de calculer les migrations en attente : {e}")
    except Exception as e:
        problem(f"Connexion à la base impossible : {e!r}")


# ════════════════════════════════════════════════════════════════════
# 4) Dérive schéma réel vs modèles SQLAlchemy (TOUTE la base, pas
#    seulement MEDIALINK)
# ════════════════════════════════════════════════════════════════════

async def check_schema_drift():
    _title("4) DÉRIVE SCHÉMA RÉEL vs MODÈLES SQLALCHEMY (utils/db/models)")

    try:
        from utils.db.models import Base
        from utils.db.engine import engine
    except Exception as e:
        problem(f"Impossible d'importer utils.db.models.Base / utils.db.engine : {e}")
        return

    metadata = Base.metadata
    print(f"  {len(metadata.tables)} table(s) déclarée(s) dans les modèles SQLAlchemy.")

    def _sync_work(conn: Connection):
        from sqlalchemy import inspect

        inspector = inspect(conn)
        db_tables = set(inspector.get_table_names(schema="public"))

        report = {"missing_tables": [], "extra_tables": [], "table_reports": {}}
        report["extra_tables"] = sorted(db_tables - set(metadata.tables.keys()) - {"alembic_version"})

        for table_name, table in metadata.tables.items():
            if table_name not in db_tables:
                report["missing_tables"].append(table_name)
                continue

            db_cols = {c["name"]: c for c in inspector.get_columns(table_name, schema="public")}
            model_cols = {c.name: c for c in table.columns}

            missing_cols = sorted(set(model_cols) - set(db_cols))
            extra_cols = sorted(set(db_cols) - set(model_cols))
            nullable_mismatches = [
                name for name in (set(model_cols) & set(db_cols))
                if bool(model_cols[name].nullable) != bool(db_cols[name]["nullable"])
            ]

            db_index_names = {ix["name"] for ix in inspector.get_indexes(table_name, schema="public")}
            model_index_names = {ix.name for ix in table.indexes if ix.name}
            missing_indexes = sorted(model_index_names - db_index_names)

            db_fk_names = {
                fk["name"] for fk in inspector.get_foreign_keys(table_name, schema="public") if fk.get("name")
            }
            model_fk_names = {
                c.name for c in table.constraints
                if c.__class__.__name__ == "ForeignKeyConstraint" and c.name
            }
            missing_fks = sorted(model_fk_names - db_fk_names)

            db_unique_names = {
                uq["name"] for uq in inspector.get_unique_constraints(table_name, schema="public") if uq.get("name")
            }
            model_unique_names = {
                c.name for c in table.constraints
                if c.__class__.__name__ == "UniqueConstraint" and c.name
            }
            missing_uniques = sorted(model_unique_names - db_unique_names)

            report["table_reports"][table_name] = {
                "missing_cols": missing_cols,
                "extra_cols": extra_cols,
                "nullable_mismatches": nullable_mismatches,
                "missing_indexes": missing_indexes,
                "missing_fks": missing_fks,
                "missing_uniques": missing_uniques,
            }

        return report

    try:
        async with engine.connect() as conn:
            report = await conn.run_sync(_sync_work)
    except Exception as e:
        problem(f"Inspection du schéma impossible : {e!r}")
        return

    if report["missing_tables"]:
        for t in report["missing_tables"]:
            problem(f"Table '{t}' déclarée dans les modèles mais ABSENTE de la base (migration non appliquée ?).")
    else:
        ok("Toutes les tables des modèles existent en base.")

    if report["extra_tables"]:
        warn(
            f"{len(report['extra_tables'])} table(s) en base sans modèle correspondant "
            f"(informatif, pas forcément un problème) : {', '.join(report['extra_tables'])}"
        )

    any_table_issue = False
    for table_name, t in report["table_reports"].items():
        issues = []
        if t["missing_cols"]:
            issues.append(f"colonnes manquantes en base : {t['missing_cols']}")
        if t["nullable_mismatches"]:
            issues.append(f"nullable différent : {t['nullable_mismatches']}")
        if t["missing_indexes"]:
            issues.append(f"index manquants : {t['missing_indexes']}")
        if t["missing_fks"]:
            issues.append(f"clés étrangères manquantes : {t['missing_fks']}")
        if t["missing_uniques"]:
            issues.append(f"contraintes uniques manquantes : {t['missing_uniques']}")

        if issues:
            any_table_issue = True
            problem(f"{table_name} : " + " | ".join(issues))
        if t["extra_cols"]:
            warn(f"{table_name} : colonnes en base absentes du modèle (informatif) : {t['extra_cols']}")

    if not any_table_issue:
        ok("Aucune dérive colonnes/index/contraintes détectée sur les tables communes.")


# ════════════════════════════════════════════════════════════════════
# Résumé final
# ════════════════════════════════════════════════════════════════════

def print_summary():
    _title("RÉSUMÉ")
    if not PROBLEMS and not WARNINGS:
        print("✅ Rien à signaler — chaîne de migrations et schéma cohérents.")
        return

    if PROBLEMS:
        print(f"❌ {len(PROBLEMS)} problème(s) bloquant(s) :")
        for p in PROBLEMS:
            print(f"   - {p}")
    if WARNINGS:
        print(f"⚠️  {len(WARNINGS)} point(s) à surveiller (pas forcément bloquant) :")
        for w in WARNINGS:
            print(f"   - {w}")

    print()
    print("Rappel : ce script n'a RIEN modifié. Les corrections (alembic stamp,")
    print("suppression d'un doublon, ajout d'une colonne manquante...) sont à")
    print("faire à la main, une fois le diagnostic ci-dessus compris.")


async def main() -> None:
    cfg = check_config()
    script, file_info = check_migration_chain(cfg) if cfg is not None else (None, None)
    await check_db_vs_files(script, file_info)
    await check_schema_drift()
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())