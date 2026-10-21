"""
search.py — Recherche dans le wiki NationsGlory (léger, sans torch, pour le VPS).

Charge wiki_index.json (produit par build_index.py) et classe les paragraphes avec BM25.
Réutilise ton tokenize() : accents, abréviations Discord (stp, cmt...) et racinisation
française marchent donc comme pour le classifieur.

Utilisation dans le bot :
    from search import WikiSearch, format_hits
    wiki = WikiSearch()                       # ne plante pas si l'index est absent
    hits = wiki.search("comment crafter une machine")
    if hits:
        message = format_hits(hits)

Test rapide en ligne de commande (affiche aussi les scores pour régler les seuils) :
    python search.py "comment fonctionne le générateur"
"""

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

try:                                    # lancé depuis le bot : « from GuideOnAi.search import ... »
    from .tokenizer import tokenize
except ImportError:                     # lancé comme script : « python search.py »
    from tokenizer import tokenize

INDEX_PATH = Path(__file__).parent / "wiki_index.json"

# ── Réglages (à ajuster avec `python search.py "ta question"`) ────────────────
K1 = 1.4
B = 0.75
MIN_COVERAGE = 0.55     # part (pondérée par la rareté) des mots de la question retrouvés dans le paragraphe
MIN_SCORE = 2.0         # score minimum
TITLE_BOOST = 2.0       # bonus quand un mot de la question est dans le TITRE de la page
TITLE_ACCEPT = 0.4      # si les mots du titre pèsent au moins ça dans la question, la page est crédible
MAX_SNIPPET = 350       # taille max de l'extrait renvoyé (caractères)

# Mots sans valeur pour la recherche (formes de base, racinisées plus bas).
_STOP_WORDS = """
le la les l un une des de du d et en à au aux ce cet cette ces se sa son ses mon ma mes ton ta tes
je tu il elle on nous vous ils elles me te y qui que quoi quel quelle quels quelles dont ou où
est sont suis es etre ete a ai as avons avez ont avoir pour par sur sous dans avec sans vers chez
comment pourquoi quand combien faut peut peux peuvent veux veut voudrais voudrait puis pouvez
dis donne donner montre montrer explique expliquer cherche trouve trouver stp svp merci bonjour salut
moi toi lui ca cela ceci ne pas plus tres bien aussi mais donc or ni car si sinon fait faire fais
quelqu quelque tout tous toute toutes mon notre votre leur leurs ici la là
beaucoup salut coucou hello hey ok oui non sert servent aller vais va vas obtenir avoir
sais sil plait desole aujourdhui toujours quelquun parce pourquoi
fonctionne fonctionnent fonctionner fonctionnement marche marchent marcher
heure jour moment date temps
""".split()
STOP_TOKENS = {t for w in _STOP_WORDS for t in tokenize(w)}


def _useful_tokens(text):
    # on ignore aussi les lettres seules (« c'est » -> « c », « n'a » -> « n »...)
    return [t for t in tokenize(text) if t not in STOP_TOKENS and len(t) > 1]


# Titres construits à partir des URL : on remet les élisions et les accents les plus courants
# (« larrivee » -> « l'arrivée »). Sert à l'affichage ET à la recherche dans les titres.
_TITLE_FIXES = {
    "larrivee": "l'arrivée", "lelectricite": "l'électricité", "lenergie": "l'énergie",
    "largent": "l'argent", "lhotel": "l'hôtel", "lelevage": "l'élevage", "daventure": "d'aventure",
    "dasteroides": "d'astéroïdes", "dalliance": "d'alliance", "lincubateurs": "les incubateurs",
    "reglement": "règlement", "electricite": "électricité", "nucleaire": "nucléaire",
    "petrole": "pétrole", "fusee": "fusée", "oxygene": "oxygène", "cereales": "céréales",
    "cosmetiques": "cosmétiques", "developpement": "développement", "creer": "créer",
    "boite": "boîte", "evenement": "événement", "evenements": "événements",
    "ameliorations": "améliorations", "amelioration": "amélioration", "competences": "compétences",
    "succes": "succès", "toxicite": "toxicité", "gerer": "gérer", "epees": "épées",
    "durabilite": "durabilité", "reparation": "réparation", "aerienne": "aérienne",
    "recherches": "recherches", "diplomatiques": "diplomatiques", "vendes": "ventes",
    "boitte": "boîte", "arrivee": "arrivée", "energie": "énergie", "fabrication": "fabrication",
    "megalodon": "mégalodon", "merveilles": "merveilles", "catastrophes": "catastrophes",
}


def pretty_title(title):
    words = [_TITLE_FIXES.get(w.lower(), w) for w in title.split()]
    out = " ".join(words)
    return out[:1].upper() + out[1:]


def _in_title(token, title_tokens):
    """Le mot de la question est dans le titre (tolère les variantes : arriv / arrive)."""
    if token in title_tokens:
        return True
    return len(token) >= 4 and any(len(t) >= 4 and (t.startswith(token) or token.startswith(t)) for t in title_tokens)


class WikiSearch:
    def __init__(self, path=INDEX_PATH):
        self.docs = []
        self.available = False
        path = Path(path)
        if not path.exists():
            print(f"[search] {path.name} introuvable : recherche wiki désactivée")
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self.docs = data["docs"]
        self.tf, self.lengths, self.title_tokens = [], [], []
        df = Counter()
        for d in self.docs:
            d["title"] = pretty_title(d["title"])
            self.title_tokens.append(set(_useful_tokens(d["title"])))
            toks = [t for t in d["tokens"].split() if t not in STOP_TOKENS and len(t) > 1]
            counts = Counter(toks)
            self.tf.append(counts)
            self.lengths.append(len(toks))
            df.update(counts.keys())
        n = len(self.docs)
        self.avg_len = (sum(self.lengths) / n) if n else 1.0
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.max_idf = max(self.idf.values()) if self.idf else 1.0
        self.available = n > 0

    # ── recherche ────────────────────────────────────────────────────────────
    def search(self, query, k=3, min_coverage=MIN_COVERAGE, min_score=MIN_SCORE):
        """Renvoie jusqu'à k articles [{title, url, snippet, score, coverage}], meilleur d'abord."""
        if not self.available:
            return []
        q = list(dict.fromkeys(_useful_tokens(query)))
        if not q:
            return []
        known = [t for t in q if t in self.idf]
        if not known:
            return []
        # Un mot de la question absent de tout le wiki pèse lourd : c'est le signe d'une question
        # hors-sujet (« capitale de la France »).
        total_mass = sum(self.idf[t] for t in known) + self.max_idf * (len(q) - len(known))

        scored = []
        for i, counts in enumerate(self.tf):
            bm25, matched_mass = 0.0, 0.0
            norm_len = 1 - B + B * self.lengths[i] / self.avg_len
            for t in known:
                f = counts.get(t, 0)
                if f:
                    matched_mass += self.idf[t]
                    bm25 += self.idf[t] * f * (K1 + 1) / (f + K1 * norm_len)
            if not matched_mass:
                continue
            title_mass = sum(self.idf[t] for t in known if _in_title(t, self.title_tokens[i]))
            score = bm25 + TITLE_BOOST * title_mass
            scored.append((score, matched_mass / total_mass, title_mass / total_mass, i))
        scored.sort(reverse=True)

        hits, seen_urls = [], set()
        for score, coverage, title_ratio, i in scored:
            # Une page dont le titre contient l'essentiel de la question est crédible
            # même si le reste de la question n'a pas de mot en commun avec elle.
            if score < min_score or (coverage < min_coverage and title_ratio < TITLE_ACCEPT):
                continue
            doc = self.docs[i]
            if doc["url"] in seen_urls:          # un seul paragraphe par article
                continue
            seen_urls.add(doc["url"])
            hits.append({
                "title": doc["title"],
                "url": doc["url"],
                "snippet": best_snippet(doc["text"], q),
                "score": round(score, 2),
                "coverage": round(coverage, 2),
                "in_title": title_ratio >= TITLE_ACCEPT,
                "n_terms": len(q),
            })
            if len(hits) >= k:
                break
        return hits


def best_snippet(text, query_tokens, limit=MAX_SNIPPET):
    """Choisit la phrase (ou deux) du paragraphe qui contient le plus de mots de la question."""
    qset = set(query_tokens)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]
    if not sentences:
        return text[:limit]
    # On évite les titres, en-têtes de page et lignes trop courtes : ce ne sont pas des explications.
    good = [i for i, s in enumerate(sentences) if len(s) >= 40 and "| NationsGlory" not in s]
    candidates = good or list(range(len(sentences)))
    scores = {i: len(qset & set(tokenize(sentences[i]))) for i in candidates}
    best = max(candidates, key=lambda i: (scores[i], len(sentences[i])))
    snippet = sentences[best]
    if best + 1 < len(sentences) and len(snippet) + len(sentences[best + 1]) < limit:
        snippet += " " + sentences[best + 1]
    if len(snippet) > limit:
        snippet = snippet[:limit].rsplit(" ", 1)[0] + "…"
    return snippet


def format_hits(hits):
    """Message Discord : meilleur résultat avec extrait, puis un éventuel 2e lien."""
    if not hits:
        return None
    top = hits[0]
    lines = [f"📖 **{top['title']}**", top["snippet"], f"🔗 {top['url']}"]
    others = [h for h in hits[1:] if h["score"] >= 0.6 * top["score"]]
    if others:
        lines.append("Voir aussi : " + " · ".join(f"[{h['title']}]({h['url']})" for h in others[:2]))
    return "\n".join(lines)


if __name__ == "__main__":
    wiki = WikiSearch()
    query = " ".join(sys.argv[1:]) or input("Question : ")
    hits = wiki.search(query, k=5, min_coverage=0.0, min_score=0.0)
    if not hits:
        print("Aucun résultat (index absent ou aucun mot connu).")
    for h in hits:
        keep = "✔" if h["score"] >= MIN_SCORE and (h["coverage"] >= MIN_COVERAGE or h["in_title"]) else "✘ (sous les seuils)"
        print(f"{keep} score={h['score']} couverture={h['coverage']} — {h['title']}\n    {h['snippet']}\n    {h['url']}")