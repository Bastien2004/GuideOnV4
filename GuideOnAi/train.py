from tokenizer import *
from model import *
from vectorizer import *
from dataset import *

import random
from collections import defaultdict

import torch
import torch.nn as nn

# ══════════════════════════════════════════════════════════════════════════
# ⚙️ Hyperparamètres à valider empiriquement via la passe de diagnostic
# ══════════════════════════════════════════════════════════════════════════

HIDDEN_SIZE = 256
EPOCHS = 3000
LEARNING_RATE = 0.1

# Pourcentage de chaque intention mis de côté pour la validation (diagnostic
# uniquement — le modèle final sauvegardé est réentraîné sur 100% des données).
VAL_RATIO = 0.2

# En dessous de ce nombre de phrases pour une intention, on ne met rien en
# validation pour elle (pas assez d'exemples pour se permettre d'en retirer
# sans affamer l'entraînement de cette classe).
MIN_PHRASES_FOR_VAL_SPLIT = 5

SEED = 42


def stratified_split(dataset, val_ratio, min_for_split, seed):
    """
    Sépare le dataset en (train, val) intention par intention, pour être
    sûr que chaque classe est bien représentée des deux côtés (un split
    aléatoire global pourrait, par malchance, mettre 0 exemple d'une
    intention rare en train ou en val).
    """
    rng = random.Random(seed)

    by_label = defaultdict(list)
    for phrase, label in dataset:
        by_label[label].append(phrase)

    train_data, val_data = [], []
    skipped_labels = []

    for label, phrase_list in by_label.items():
        phrase_list = list(phrase_list)
        rng.shuffle(phrase_list)
        n = len(phrase_list)

        if n < min_for_split:
            train_data.extend((p, label) for p in phrase_list)
            skipped_labels.append((label, n))
            continue

        n_val = max(1, round(n * val_ratio))
        val_data.extend((p, label) for p in phrase_list[:n_val])
        train_data.extend((p, label) for p in phrase_list[n_val:])

    rng.shuffle(train_data)
    rng.shuffle(val_data)
    return train_data, val_data, skipped_labels


def build_xy(dataset, vocabulary):
    phrases = [p for p, _ in dataset]
    labels = [l for _, l in dataset]

    phrases_tokenisees = [tokenize(phrase) for phrase in phrases]
    vectors = [vectorize(tokens, vocabulary) for tokens in phrases_tokenisees]
    targets = [INTENTS.index(label) for label in labels]

    X = torch.tensor(vectors).float()
    Y = torch.tensor(targets)
    return X, Y


def accuracy(model, X, Y):
    with torch.no_grad():
        predictions = model(X)
        predicted_classes = predictions.argmax(dim=1)
        return (predicted_classes == Y).float().mean().item()


if __name__ == "__main__":

    # ══════════════════════════════════════════════════════════════════
    # 🔬 PASSE 1 — Diagnostic (train/val split) : sert UNIQUEMENT à
    # valider hidden_size/epochs, ce modèle n'est pas sauvegardé.
    # ══════════════════════════════════════════════════════════════════

    train_data, val_data, skipped_labels = stratified_split(
        DATASET, VAL_RATIO, MIN_PHRASES_FOR_VAL_SPLIT, SEED
    )

    print(f"[DIAGNOSTIC] {len(train_data)} phrases en train, {len(val_data)} en validation")
    if skipped_labels:
        print(
            f"[DIAGNOSTIC] {len(skipped_labels)} intentions trop petites "
            f"(< {MIN_PHRASES_FOR_VAL_SPLIT} phrases) exclues du split, gardées 100% en train :"
        )
        for label, n in sorted(skipped_labels, key=lambda x: x[1]):
            print(f"    - {label} ({n} phrases)")

    # Vocabulaire construit UNIQUEMENT sur le train du diagnostic — sinon la
    # validation "triche" en connaissant déjà des mots qu'elle n'est censée
    # voir qu'au moment du test.
    train_phrases_tokenisees = [tokenize(p) for p, _ in train_data]
    diag_vocabulary = build_vocabulary(train_phrases_tokenisees)

    X_train, Y_train = build_xy(train_data, diag_vocabulary)
    X_val, Y_val = build_xy(val_data, diag_vocabulary) if val_data else (None, None)

    diag_model = Model(len(diag_vocabulary), HIDDEN_SIZE, len(INTENTS))
    loss_function = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(diag_model.parameters(), lr=LEARNING_RATE)

    print(f"\n[DIAGNOSTIC] hidden_size={HIDDEN_SIZE}, epochs={EPOCHS}\n")

    for epoch in range(EPOCHS):
        predictions = diag_model(X_train)
        loss = loss_function(predictions, Y_train)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if epoch % 200 == 0 or epoch == EPOCHS - 1:
            train_acc = accuracy(diag_model, X_train, Y_train)
            msg = f"Epoch {epoch:4d} — loss: {loss.item():.4f} — train_acc: {train_acc:.2%}"
            if X_val is not None:
                val_acc = accuracy(diag_model, X_val, Y_val)
                msg += f" — val_acc: {val_acc:.2%}"
            print(msg)

    if X_val is not None:
        final_val_acc = accuracy(diag_model, X_val, Y_val)
        print(f"\n[DIAGNOSTIC] Accuracy finale sur les phrases jamais vues : {final_val_acc:.2%}")
        print(
            "[DIAGNOSTIC] Si ce chiffre est nettement plus bas que le train_acc final, "
            "le modèle sur-apprend (réduis hidden_size et/ou epochs)."
        )
        print(
            "[DIAGNOSTIC] Si train_acc ET val_acc plafonnent bas tous les deux, "
            "le modèle sous-apprend (augmente hidden_size, ou vérifie le dataset)."
        )
    else:
        print("\n[DIAGNOSTIC] Aucune donnée de validation (dataset trop petit) — diagnostic ignoré.")

    # ══════════════════════════════════════════════════════════════════
    # 🚀 PASSE 2 — Entraînement final sur 100% des données (celui-ci est
    # sauvegardé dans model.pth). Utilise les mêmes hyperparamètres que
    # ceux validés ci-dessus.
    # ══════════════════════════════════════════════════════════════════

    print("\n" + "=" * 60)
    print("[FINAL] Entraînement du modèle de production sur 100% du dataset")
    print("=" * 60 + "\n")

    phrases = [element[0] for element in DATASET]
    print("NOMBRE DE PHRASES :", len(phrases))
    labels = [element[1] for element in DATASET]

    phrases_tokenisees = [tokenize(phrase) for phrase in phrases]
    vocabulary = build_vocabulary(phrases_tokenisees)
    vectors = [vectorize(phrase, vocabulary) for phrase in phrases_tokenisees]
    targets = [INTENTS.index(label) for label in labels]

    X = torch.tensor(vectors).float()
    Y = torch.tensor(targets)

    input_size = len(vocabulary)
    hidden_size = HIDDEN_SIZE
    output_size = len(INTENTS)
    model = Model(input_size, hidden_size, output_size)

    loss_function = nn.CrossEntropyLoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=LEARNING_RATE)

    epochs = EPOCHS
    for epoch in range(epochs):
        predictions = model(X)
        loss = loss_function(predictions, Y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

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