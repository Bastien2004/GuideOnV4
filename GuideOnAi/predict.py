"""
predict.py — Cerveau de GuideOnAi, complet et autonome (aucun autre fichier à ajouter à part search.py).

Utilisé de deux façons :
  - en terminal :  python predict.py
  - par l'API du bot :  from GuideOnAi import predict as chatbot  ->  chatbot.predict_message(phrase, session_id)

Ce que fait predict_message(phrase, session) :
  1. le modèle donne une intention et une confiance ;
  2. si le bot a posé une question de confirmation au tour précédent (« Je pense que tu veux X, c'est bien
     ça ? ») et que la réponse est « oui », il donne la réponse de X ;
  3. si le bot hésite (< 60 %) et qu'on parlait d'un sujet (tickets, modération...), les intentions de ce
     sujet sont favorisées : « comment configurer ce panel ? » après une question sur les tickets ;
  4. sinon : réponse directe (≥ 85 %), proposition (60–85 %), page du wiki ou « je ne comprends pas » (< 60 %).

`session` = une clé quelconque par personne (id Discord, id de session du site). Sans clé : pas de mémoire.
Le bot retient le SUJET et la dernière phrase en attente de confirmation, en mémoire vive, 10 minutes
(oublié au redémarrage). Il ne garde pas l'historique des messages.
"""

import re
import time
from pathlib import Path

try:                                   # importé par le bot : « from GuideOnAi import predict »
    from .tokenizer import tokenize
    from .vectorizer import vectorize
    from .response import RESPONSES
    from .permissions import PERMISSIONS
    from .search import WikiSearch, format_hits
except ImportError:                    # lancé comme script : « python predict.py »
    from tokenizer import tokenize
    from vectorizer import vectorize
    from response import RESPONSES
    from permissions import PERMISSIONS
    from search import WikiSearch, format_hits

HERE = Path(__file__).parent

# ── Seuils de confiance ──────────────────────────────────────────────────────
SEUIL_INCERTAIN = 0.4   # en dessous : le bot ne propose rien (sauf une page du wiki)
SEUIL_PROPOSE = 0.6     # entre les deux : "Je pense que tu veux X, c'est bien ça ?"
SEUIL_SUR = 0.85        # au-dessus : le bot répond directement

# ── Mémoire de conversation ──────────────────────────────────────────────────
MEMOIRE_SECONDES = 600  # une conversation inactive est oubliée après 10 minutes
MEMOIRE_MAX = 5000      # nombre maximum de conversations gardées en même temps
POIDS_SUJET = 6.0       # poids donné aux commandes du sujet en cours quand le bot hésite
GROUPES = {             # le sujet = le préfixe de l'intention (ticket_add -> "ticket")
    "ticket", "mod", "config", "giveaway", "birthday", "exp", "invite", "eco", "rappel",
    "qr", "ng", "ngstaff", "alpha", "iris", "dev", "medialink",
}

# ── État (chargé une seule fois) ─────────────────────────────────────────────
_torch = None
_model = None
_vocabulary = None
_intents = []
_wiki = None
_sessions = {}


def load(model_path=None):
    """Charge model.pth (une seule fois). Appelée automatiquement au premier message, ou au démarrage de l'API."""
    global _torch, _model, _vocabulary, _intents
    if _model is not None:
        return
    import torch
    try:
        from .model import Model
    except ImportError:
        from model import Model
    checkpoint = torch.load(model_path or HERE / "model.pth", map_location="cpu")
    _vocabulary = checkpoint["vocabulary"]
    _intents = checkpoint["intents"]
    _model = Model(checkpoint["input_size"], checkpoint["hidden_size"], checkpoint["output_size"])
    _model.load_state_dict(checkpoint["model_state"])
    _model.eval()
    _torch = torch


def _probs(phrase):
    """Probabilités du modèle pour chaque intention (liste de floats)."""
    load()
    x = _torch.tensor(vectorize(tokenize(phrase), _vocabulary)).float().unsqueeze(0)
    with _torch.no_grad():
        return _torch.softmax(_model(x), dim=1)[0].tolist()


def _get_wiki():
    """Recherche dans le wiki. Sans wiki_index.json elle est désactivée, sans erreur."""
    global _wiki
    if _wiki is None:
        _wiki = WikiSearch()
    return _wiki


# ── Outils ───────────────────────────────────────────────────────────────────
def _groupe(intent):
    """'ticket_panel_create' -> 'ticket' ; 'wiki', 'greeting', 'how_are_you'... -> None (pas de sujet)."""
    if not intent or "_" not in intent:
        return None
    tete = intent.split("_", 1)[0]
    return tete if tete in GROUPES else None


def _session(cle):
    """Mémoire de la conversation `cle` (créée ou remise à zéro si elle a expiré)."""
    now = time.time()
    s = _sessions.get(cle)
    if s is None or now - s["t"] > MEMOIRE_SECONDES:
        if len(_sessions) >= MEMOIRE_MAX:                       # ménage : expirées, puis les plus anciennes
            for k in [k for k, v in _sessions.items() if now - v["t"] > MEMOIRE_SECONDES]:
                del _sessions[k]
            for k in sorted(_sessions, key=lambda k: _sessions[k]["t"])[: MEMOIRE_MAX // 10 + 1] if len(_sessions) >= MEMOIRE_MAX else []:
                del _sessions[k]
        s = {"groupe": None, "attente": None, "phrase_attente": None, "t": now}
        _sessions[cle] = s
    s["t"] = now
    return s


def oublier(cle):
    """Efface la mémoire d'une conversation."""
    _sessions.pop(cle, None)


def _retenir(s, intent):
    """Retient le sujet si c'est une commande ; les politesses (bonjour, merci...) ne le changent pas."""
    g = _groupe(intent)
    if s is not None and g:
        s["groupe"] = g


def _etiquette(intent):
    """« utiliser `/ticket panel create` » (lu dans la réponse du bot) plutôt que le nom interne de l'intention."""
    m = re.search(r"`(/[^`]+)`", RESPONSES.get(intent, ""))
    return f"utiliser `{m.group(1)}`" if m else intent


def wiki_answer(phrase, strict=True):
    """
    Message wiki prêt à envoyer si le wiki contient la réponse, sinon None.
    strict=True : la page doit viser le TITRE de la question (ou la recouvrir presque entièrement) ;
    sinon on accepte aussi une page qui recouvre bien une question d'au moins deux mots utiles.
    Évite de détourner une vraie commande, ou une phrase vague, vers une page sans rapport.
    """
    hits = _get_wiki().search(phrase)
    if not hits:
        return None
    top = hits[0]
    if strict:
        ok = top.get("in_title") or (top["coverage"] >= 0.9 and top["score"] >= 8 and top.get("n_terms", 2) >= 2)
    else:
        ok = top.get("in_title") or (top["coverage"] >= 0.75 and top.get("n_terms", 2) >= 2)
    return format_hits(hits) if ok else None


def _resultat(intent, reponse, confiance, kind, contexte=False, permission=False):
    perm = PERMISSIONS.get(intent) if permission else None
    requise = bool(perm) and perm["type"] != "aucune"
    return {
        "intent": intent,
        "response": reponse,
        "confidence": confiance,
        "permission_required": requise,
        "permission_type": perm["type"] if requise else None,
        "permission_detail": perm["detail"] if requise else None,
        "kind": kind,                  # direct / confirmed / suggestion / wiki / unknown
        "used_context": contexte,      # le sujet de la conversation a servi à comprendre la phrase
    }


def _direct(intent, confiance, phrase, kind="direct", contexte=False):
    if intent == "wiki":
        page = wiki_answer(phrase)
        if page:
            return _resultat("wiki", page, confiance, "wiki", contexte)
    texte = RESPONSES.get(intent, f"Je pense que tu veux {intent}.")
    return _resultat(intent, texte, confiance, kind, contexte, permission=True)


def _proposer(s, intent, confiance, phrase, contexte):
    if s is not None:
        s["attente"], s["phrase_attente"] = intent, phrase
        _retenir(s, intent)
    return _resultat(intent, f"Je pense que tu veux {_etiquette(intent)}. C'est bien ça ?", confiance, "suggestion", contexte)


# ── Prédiction ───────────────────────────────────────────────────────────────
def predict_message(phrase, session=None):
    """Renvoie un dict : intent, response, confidence, permission_*, kind, used_context."""
    probs = _probs(phrase)
    haut = max(range(len(probs)), key=probs.__getitem__)
    intent, confiance = _intents[haut], probs[haut]
    s = _session(session) if session is not None else None

    # 1) réponse à une question de confirmation (« oui » après « Je pense que tu veux X... »)
    if s and s["attente"]:
        attente, phrase_attente = s["attente"], s["phrase_attente"]
        s["attente"] = s["phrase_attente"] = None
        if intent == "yes_confirm" and confiance >= SEUIL_PROPOSE:
            _retenir(s, attente)
            return _direct(attente, confiance, phrase_attente, kind="confirmed", contexte=True)
        # « non », ou un autre message : la question est abandonnée

    # 2) suite vague : on favorise le sujet en cours
    contexte = False
    if s and s["groupe"] and confiance < SEUIL_PROPOSE:
        poids = [p * POIDS_SUJET if _groupe(i) == s["groupe"] else p for p, i in zip(probs, _intents)]
        total = sum(poids) or 1.0
        poids = [p / total for p in poids]
        b = max(range(len(poids)), key=poids.__getitem__)
        if _groupe(_intents[b]) == s["groupe"] and poids[b] > confiance:
            intent, confiance, contexte = _intents[b], poids[b], True

    # 3) seuils habituels
    if confiance < SEUIL_PROPOSE:
        # Le classifieur n'est pas sûr : c'est peut-être une question sur le jeu (craft, machine, missile...)
        #  - confiance très basse : une page du wiki qui recouvre bien la question suffit
        #  - confiance moyenne : le classifieur a peut-être raison, la page doit viser le titre
        page = wiki_answer(phrase, strict=(confiance >= SEUIL_INCERTAIN))
        if page:
            return _resultat("wiki", page, confiance, "wiki", contexte)
        if confiance >= SEUIL_INCERTAIN:
            return _proposer(s, intent, confiance, phrase, contexte)
        return _resultat("unknown", "Je ne comprends pas, reformule ta question", confiance, "unknown", contexte)

    if confiance < SEUIL_SUR:
        if intent == "wiki":
            page = wiki_answer(phrase)
            if page:
                return _resultat("wiki", page, confiance, "wiki", contexte)
        return _proposer(s, intent, confiance, phrase, contexte)

    _retenir(s, intent)
    return _direct(intent, confiance, phrase, contexte=contexte)


def predict(phrase, session="cli"):
    """Version terminal : renvoie (texte, confiance, détails). `session=None` = sans mémoire."""
    r = predict_message(phrase, session)
    texte = r["response"]
    if r["permission_required"]:
        texte += f"\n⚠️ Permission requise : {r['permission_type']} ({r['permission_detail']})"
    return texte, r["confidence"], r


if __name__ == "__main__":
    load()
    print("Chatbot prêt ! (tape 'exit' pour arrêter, '/reset' pour oublier la conversation)")

    while True:
        phrase = input("Toi : ")

        if phrase.lower() in ["quit", "exit", "stop"]:
            break
        if phrase.strip() == "/reset":
            oublier("cli")
            print("→ Conversation oubliée.")
            continue

        texte, confiance, r = predict(phrase)
        note = " — sujet de la conversation pris en compte" if r["used_context"] else ""
        print(f"→ {texte}\n   (confiance : {confiance:.2%}{note})")