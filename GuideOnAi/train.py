from tokenizer import *
from model import *
from vectorizer import *
from dataset import *

import torch
import torch.nn as nn

if __name__ == "__main__":

    # Étape 1 : séparer phrases et labels
    #Phrases : je veux créer un ticket"
    #Labels : ticket_create
    phrases = [element[0] for element in DATASET]
    print("NOMBRE DE PHRASES :", len(phrases))
    labels = [element[1] for element in DATASET]

    # Étape 2 : tokeniser chaque phrase (string -> liste de mots)
    phrases_tokenisees = [tokenize(phrase) for phrase in phrases]

    # Étape 3 : construire le vocabulaire à partir des phrases tokenisées
    vocabulary = build_vocabulary(phrases_tokenisees)

    # Étape 4 : vectoriser chaque phrase tokenisée (BoW)
    vectors = [vectorize(phrase, vocabulary) for phrase in phrases_tokenisees]

    # Étape 5 : transformer les labels texte en nombres via INTENTS
    targets = [INTENTS.index(label) for label in labels]

    # Étape 6 : transformer tout ça en tenseurs PyTorch
    X = torch.tensor(vectors).float()
    Y = torch.tensor(targets)

    input_size = len(vocabulary)
    hidden_size = 256
    output_size = len(INTENTS)
    model = Model(input_size, hidden_size, output_size)

    loss_function = nn.CrossEntropyLoss() # loss_function : mesure l'erreur entre ce que le modèle prédit et la vraie réponse.
    optimizer = torch.optim.SGD(model.parameters(), lr=0.1) # l'outil qui va ajuster les poids du modèle à chaque étape

    epochs = 3000
    for epoch in range(epochs):
        predictions = model(X)                     # 1. le modèle devine, sur TOUTES les phrases d'un coup
        loss = loss_function(predictions, Y)       # 2. on mesure l'erreur

        optimizer.zero_grad()                      # 3. on efface les anciens ajustements
        loss.backward()                            # 4. on calcule les nouveaux ajustements
        optimizer.step()                           # 5. on les applique aux poids du modèle

        if epoch % 50 == 0:
            print(f"Epoch {epoch} — loss: {loss.item():.4f}")

    torch.save({
        "model_state": model.state_dict(),
        "vocabulary": vocabulary,
        "intents": INTENTS,
        "input_size": input_size,
        "hidden_size": hidden_size,
        "output_size": output_size,
    }, "model.pth")

    checkpoint = torch.load("model.pth")
    print(checkpoint.keys())