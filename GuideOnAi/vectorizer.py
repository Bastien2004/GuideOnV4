"""
    Transforme une liste de mots en vecteur Bag of Words.
"""
def vectorize(text, vocabulary): 
    return [1 if i in text else 0 for i in vocabulary]