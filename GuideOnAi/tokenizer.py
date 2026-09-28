import re
import unicodedata

from nltk.stem.snowball import SnowballStemmer

# SnowballStemmer('french') est basé sur des règles linguistiques connues
# (pas de téléchargement de corpus nécessaire, contrairement à d'autres
# outils nltk). Nécessite : pip install nltk
_stemmer = SnowballStemmer("french")

"""
    "Je veux fermer mon ticket" -> ["je", "veux", "ferm", "mon", "ticket"]
    "Ça va ?" -> ["ca", "va"]                (accents normalisés, ponctuation retirée)
    "comment vas-tu" -> ["comment", "vas", "tu"]   (tiret traité comme un séparateur)
    "pk jfais ça" -> ["pourquoi", "jfais", "ca"]   (abréviation développée avant stemming)

    Le stemming réduit "bannir"/"bannis"/"banni"/"bannirait" à une seule
    racine commune ("bani" par ex.) : un seul exemple d'entraînement par
    verbe suffit à couvrir toutes ses formes conjuguées, au lieu d'avoir
    besoin d'écrire une phrase par conjugaison dans le dataset.
"""

# Abréviations / langage Discord courant -> forme développée. Appliqué
# AVANT le stemming, sur des mots déjà en minuscules/sans accent/sans
# ponctuation. Une valeur peut contenir plusieurs mots ("sil te plait"),
# ils seront re-découpés puis stemmés individuellement.
#
# ⚠️ Liste construite à partir de connaissances générales sur le langage
# Discord/SMS francophone, PAS à partir de vrais messages de tes
# utilisateurs — à corriger/compléter avec les abréviations que tu vois
# réellement passer sur ton serveur.
_ABBREVIATIONS = {
    # Salutations
    "slt": "salut",
    "bjr": "bonjour",
    "bsr": "bonsoir",

    # Mots interrogatifs / connecteurs
    "pk": "pourquoi",
    "pq": "pourquoi",
    "pkoi": "pourquoi",
    "pcq": "parce que",
    "cmt": "comment",
    "kan": "quand",
    "qd": "quand",
    "ki": "qui",

    # Quantificateurs / pronoms
    "qqn": "quelquun",
    "qqch": "quelque chose",
    "tt": "tout",
    "tjs": "toujours",
    "tjrs": "toujours",
    "bcp": "beaucoup",
    "auj": "aujourdhui",

    # Expressions courantes
    "jsp": "sais pas",
    "dsl": "desole",
    "stp": "sil te plait",
    "svp": "sil vous plait",

    # Affirmation / négation
    "ouai": "oui",
    "ouais": "oui",
    "wep": "oui",
    "nn": "non",
    "nan": "non",

    # Vocabulaire modération/serveur
    "admin": "administrateur",
    "modo": "moderateur",
    "mp": "message prive",
}

# Mots purement expressifs (rires, exclamations) qui n'apportent aucun
# signal utile pour classer une intention — on les retire complètement
# plutôt que de les stemmer, pour ne pas polluer le vocabulaire de bruit.
_FILLER_WORDS = {
    "mdr", "ptdr", "lol", "xd", "haha", "hihi", "lel",
}


def _strip_accents(text):
    """
    Retire les accents (é -> e, ç -> c, à -> a, etc.) en passant par la forme
    Unicode décomposée (NFKD) puis en filtrant les caractères diacritiques.

    Fait AVANT le split : comme cette normalisation est appliquée à la fois
    à l'entraînement (via build_vocabulary) et à la prédiction, "ça" et "ca"
    deviennent le même token des deux côtés — plus besoin de dupliquer les
    phrases du dataset avec/sans accent.
    """
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _expand_word(word):
    """
    Développe une abréviation en sa forme complète (qui peut être
    plusieurs mots), ou renvoie le mot tel quel s'il n'est pas dans le
    dictionnaire. Renvoie toujours une liste de mots.
    """
    if word in _ABBREVIATIONS:
        return _ABBREVIATIONS[word].split()
    return [word]


def tokenize(text):
    text = text.lower()
    text = _strip_accents(text)

    # Remplace toute ponctuation (?, !, ., ', -, etc.) par un espace.
    # Effet notable : "vas-tu" -> "vas tu" (deux tokens au lieu d'un seul
    # token composé "vas-tu" qui ne matchait jamais "vas" tout seul), et
    # "j'aimerais" -> "j aimerais". On garde uniquement lettres/chiffres/espaces.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    raw_words = text.split()

    expanded_words = []
    for word in raw_words:
        if word in _FILLER_WORDS:
            continue
        expanded_words.extend(_expand_word(word))

    # Racinisation : "bannis"/"bannir"/"banni" -> même racine. C'est ce qui
    # multiplie la couverture réelle du vocabulaire sans devoir écrire une
    # phrase par conjugaison dans le dataset.
    return [_stemmer.stem(word) for word in expanded_words]


"""
{
    "je": 0,
    "veux": 1,
    "ticket": 2
}
mot -> numéro
"""
def build_vocabulary(dataset):
    vocabulary = {}

    for phrase in dataset:
        for word in phrase:
            if word not in vocabulary:
                vocabulary[word] = len(vocabulary)

    return vocabulary

"""
    Transforme une phrase en liste d'IDs.
    "je ferme ticket" --> [3, 8, 5]
    """
def encode(text, vocabulary):
    return [vocabulary[text[i]] for i in range(len(text)) if text[i] in vocabulary]