"""
    "Je veux fermer mon ticket" -> ["je", "veux", "fermer", "mon", "ticket"]
    """
def tokenize(text):
        return text.lower().split()


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