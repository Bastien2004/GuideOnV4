import re
import unicodedata


def _strip_accents(text):
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))

"""
    "Je veux fermer mon ticket" -> ["je", "veux", "fermer", "mon", "ticket"]
    """
def tokenize(text):
    text = text.lower()
    text = _strip_accents(text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    return text.split()


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