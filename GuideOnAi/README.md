# GuideON AI — Assistant d'intentions

## 1. Ce que c'est (et ce que ce n'est pas)

GuideON AI est un **classificateur d'intentions**. Il lit une phrase, détermine laquelle des ~120 intentions connues lui ressemble le plus, puis renvoie :

- la **réponse pré-écrite** associée (`response.py`),
- la **permission requise** pour la commande concernée (`permissions.py`).

Ce n'est **pas** un modèle génératif. Il n'invente jamais de texte, il ne se souvient pas des messages précédents, et il ne peut dire que ce que tu as écrit à l'avance.

> Conséquence directe : **la qualité des réponses dépend avant tout de la qualité du dataset** (`dataset.py`). Ce README explique surtout comment l'enrichir proprement.

---

## 2. Architecture

```
GuideOnAi/
├── dataset.py       # INTENTS (liste des intentions) + DATASET (phrases d'exemple)
├── response.py      # RESPONSES : texte renvoyé pour chaque intention
├── permissions.py   # PERMISSIONS : permission requise pour chaque intention
├── tokenizer.py     # nettoyage du texte, abréviations, racinisation, vocabulaire
├── vectorizer.py    # phrase -> vecteur de 0/1 (sac de mots)
├── model.py         # petit réseau de neurones
├── train.py         # entraînement (diagnostic puis modèle final) -> model.pth
├── predict.py       # prédiction en ligne de commande, avec seuils de confiance
├── test.py          # test de généralisation sur des phrases reformulées
└── model.pth        # GÉNÉRÉ : poids + vocabulaire + liste des intentions

cogs/api/guideonAi_api.py   # endpoint FastAPI  POST /chatbot/predict
```

Chaîne complète quand l'assistant est utilisé depuis le site :

```
Navigateur (admin) → widget JS → Laravel  POST /admin/chatbot/predict
                                      ↓ (le token API reste côté serveur)
                              FastAPI  POST /chatbot/predict → _predict() → JSON
```

| Fichier | Contient | Faut-il réentraîner si je le modifie ? |
|---|---|---|
| `dataset.py` | intentions + phrases d'exemple | **Oui** |
| `tokenizer.py` | abréviations, mots ignorés, nettoyage | **Oui** (le vocabulaire change) |
| `model.py`, `train.py` | architecture, hyperparamètres | **Oui** |
| `response.py` | texte des réponses | Non |
| `permissions.py` | permissions affichées | Non |
| `predict.py` / `guideonAi_api.py` | seuils de confiance | Non (redémarrer le bot) |

---

## 3. Comment une phrase est traitée

Exemple : `"Je voudrais fermer mon ticket !"`

1. **Tokenisation** (`tokenizer.py`) : minuscules → accents retirés (`ça` = `ca`) → ponctuation remplacée par des espaces (`vas-tu` = `vas tu`) → abréviations développées (`cmt` → `comment`) → rires/interjections supprimés (`mdr`, `lol`) → **racinisation** (`fermer`, `fermé`, `fermons` donnent la même racine).
2. **Vectorisation** (`vectorizer.py`) : on construit un vecteur de la taille du vocabulaire, avec `1` si le mot est présent dans la phrase, `0` sinon. Les mots **absents du vocabulaire sont ignorés en silence**.
3. **Modèle** (`model.py`) : `Linear(vocabulaire → 256)` → `ReLU` → `Dropout(0.2)` → `Linear(256 → nombre d'intentions)`.
4. **Softmax** : transforme les scores en probabilités. L'intention retenue est la plus probable, et sa probabilité est la **confiance**.
5. **Seuils** (`predict.py`) :

| Confiance | Comportement |
|---|---|
| < 60 % | « Je ne comprends pas, reformule ta question » |
| 60 % – 85 % | « Je pense que tu veux … C'est bien ça ? » |
| ≥ 85 % | réponse de `RESPONSES` (+ permission requise si elle n'est pas `"aucune"`) |

Deux propriétés à garder en tête pour tout le reste du guide :

- Le modèle **ne voit pas l'ordre des mots** : `"ferme le ticket"` et `"le ticket ferme"` sont identiques pour lui.
- Il ne voit que la **présence** des mots (0 ou 1). Répéter un mot ne change rien.

---

## 4. Installation et commandes

```bash
pip install torch nltk
```

À lancer depuis le dossier `GuideOnAi/` :

```bash
python train.py     # entraîne et écrit model.pth (long : 2 passes de 3000 epochs)
python predict.py   # discuter avec le modèle en ligne de commande
python test.py      # rapport de réussite sur des phrases reformulées
```

`train.py` fait **deux passes** :

1. **Diagnostic** : entraîne sur ~80 % des phrases et mesure `val_acc` sur les ~20 % restantes (jamais vues). C'est le seul chiffre qui indique si le modèle **généralise**. Ce modèle n'est pas sauvegardé.
2. **Final** : réentraîne sur 100 % des phrases et sauvegarde `model.pth`.

---

## 5. Améliorer l'assistant

### 5.1 Ajouter des phrases à une intention existante

Ouvre `dataset.py` et ajoute des tuples `(phrase, intention)` dans la section voulue :

```python
("le problème est réglé, tu peux le clôturer", "ticket_close"),
("on peut terminer ce ticket", "ticket_close"),
```

Puis `python train.py`.

**Règles d'or**

- **Vise 8 à 15 phrases variées par intention.** Certaines intentions n'en ont que 2 aujourd'hui (`iris_test`, `dev_kick`, `dev_join_serv`…) : ce sont les plus fragiles, commence par elles. Les intentions de moins de 5 phrases sont d'ailleurs exclues de la validation, donc `val_acc` ne les mesure pas.
- **La variété compte plus que la quantité.** Comme le modèle ne regarde que la présence des mots, deux phrases qui utilisent les mêmes mots n'apportent rien. Cinq phrases différentes valent mieux que vingt quasi-doublons.
- **Varie les formulations** : impératif (`ferme ce ticket`), question (`comment fermer un ticket`), envie (`je veux fermer mon ticket`), familier (`dégage ce ticket`), court (`ticket résolu, ferme-le`).
- **Ne commence pas toutes les phrases d'une intention par la même formule.** Si dix phrases de `ticket_create` commencent par `je veux`, le modèle apprend que `je veux` est un indice de `ticket_create`.
- **Garde au moins un mot discriminant par intention.** Dans `ticket_close`, `ticket` est présent dans 13 intentions, il ne départage rien. C'est `fermer` / `clôturer` qui fait la différence : mets-le en avant.
- **Ne mets jamais la même phrase (ou une phrase équivalente) dans deux intentions.** Le modèle recevrait deux étiquettes contradictoires pour la même entrée.
- **Inutile d'ajouter** les variantes avec/sans accent, les majuscules, la ponctuation ou les conjugaisons : le tokenizer s'en charge. En revanche, il **ne gère pas les synonymes** (`virer` / `expulser` / `dégager`) : ceux-là doivent être dans le dataset.

### 5.2 Ajouter une nouvelle intention

Une intention vit dans **quatre fichiers**. Si tu en oublies un, ça plante :

| # | Fichier | À faire | Si oublié |
|---|---|---|---|
| 1 | `dataset.py` → `INTENTS` | ajouter le nom de l'intention | elle n'est jamais prédite, et `train.py` plante (`ValueError: '…' is not in list`) |
| 2 | `dataset.py` → `DATASET` | ajouter 8+ phrases d'exemple | l'intention n'est jamais apprise |
| 3 | `response.py` → `RESPONSES` | ajouter le texte de réponse | `KeyError` à la prédiction (confiance ≥ 85 %) |
| 4 | `permissions.py` → `PERMISSIONS` | ajouter `{"type", "detail", "verified"}` | `KeyError` à la prédiction (confiance ≥ 85 %) |

Valeurs possibles pour `"type"` : `"aucune"`, `"discord_admin"`, `"interne"`, `"boutique"`. Mets `"verified": True` uniquement si tu as vérifié le check dans le code de la commande.

Exemple complet :

```python
# dataset.py
INTENTS = [..., "ticket_transcript"]
DATASET = [..., ("envoie-moi la transcription du ticket", "ticket_transcript"), ...]

# response.py
"ticket_transcript": "Utilise `/ticket transcript` pour obtenir la transcription de ce ticket (réservé au staff).",

# permissions.py
"ticket_transcript": {"type": "interne", "detail": "is_staff (staff ticket)", "verified": False},
```

Après toute modification de `INTENTS`, **réentraîne obligatoirement** : un ancien `model.pth` n'a pas la même forme de sortie, et le chargement échoue (`size mismatch`).

**Script de vérification** (à enregistrer en `check_data.py` à côté de `dataset.py`, à lancer avant chaque entraînement) :

```python
from collections import Counter
from dataset import INTENTS, DATASET
from response import RESPONSES
from permissions import PERMISSIONS
from tokenizer import tokenize

counts = Counter(label for _, label in DATASET)

print("Intentions sans réponse      :", sorted(set(INTENTS) - set(RESPONSES)))
print("Intentions sans permission   :", sorted(set(INTENTS) - set(PERMISSIONS)))
print("Labels du dataset inconnus   :", sorted(set(counts) - set(INTENTS)))
print("Intentions sans phrase       :", sorted(set(INTENTS) - set(counts)))
print("Réponses/permissions orphelines :",
      sorted((set(RESPONSES) | set(PERMISSIONS)) - set(INTENTS)))

# Deux phrases qui donnent exactement les mêmes mots (après nettoyage)
# mais des intentions différentes = étiquettes contradictoires.
seen = {}
for phrase, label in DATASET:
    bag = frozenset(tokenize(phrase))
    if bag in seen and seen[bag][1] != label:
        print(f"CONFLIT : {phrase!r} ({label})  ~  {seen[bag][0]!r} ({seen[bag][1]})")
    seen.setdefault(bag, (phrase, label))

print("\nIntentions avec moins de 6 phrases :")
for label in INTENTS:
    if counts[label] < 6:
        print(f"  {label}: {counts[label]}")
```

### 5.3 Ajouter du vocabulaire

**Il n'y a pas de fichier de vocabulaire à éditer.** Le vocabulaire est reconstruit à chaque entraînement à partir de tous les mots des phrases de `DATASET` (après tokenisation), puis sauvegardé dans `model.pth`.

Conséquence : un mot n'existe pour le modèle **que s'il apparaît dans une phrase d'entraînement**. Un mot inconnu au moment de la prédiction est ignoré, et un message composé uniquement de mots inconnus donne un vecteur vide, donc une confiance très basse.

Il y a trois leviers, à choisir selon le cas :

| Cas | Où | Exemple |
|---|---|---|
| Mot nouveau, **synonyme** ou terme métier | phrases dans `DATASET` | `dégage` pour `mod_kick` |
| **Forme abrégée / argot** d'un mot que le dataset connaît déjà | `_ABBREVIATIONS` dans `tokenizer.py` | `"cmt": "comment"` |
| Mot **sans intérêt** (rire, interjection) | `_FILLER_WORDS` dans `tokenizer.py` | `"mdr"`, `"lol"` |

Règles pour `_ABBREVIATIONS` :

- La clé est en **minuscules, sans accent, sans ponctuation** (le dictionnaire est appliqué après la normalisation).
- La valeur est la forme complète, qui peut contenir plusieurs mots (`"stp": "sil te plait"`).
- **La valeur doit exister dans le dataset.** Développer `pk` en `pourquoi` n'aide que si `pourquoi` apparaît dans des phrases d'entraînement, sinon le mot développé est lui-même inconnu.
- Toute modification du tokenizer change le vocabulaire : **réentraîne**.

### 5.4 Corriger une confusion entre deux intentions

1. Lance `python test.py` : chaque échec affiche l'intention attendue, l'intention obtenue et la confiance.
2. Compare les phrases des deux intentions et repère les **mots qu'elles partagent** (c'est ce qui les rapproche).
3. Ajoute à l'intention **attendue** des phrases qui mettent en avant le mot qui la distingue (ex. pour `ticket_ban` face à `ticket_close` : `interdire`, `plus jamais`, `droit d'ouvrir`).
4. Si une intention « aspire » des phrases qui ne la concernent pas, ajoute des phrases contrastées à l'intention concurrente.
5. Relance `train.py`, puis `test.py`, et compare.

L'en-tête de `dataset.py` liste les paires déjà problématiques (`ngstaff_rank` / `ngstaff_derank`, `ticket_panel_*`, `exp_level` / `exp_leaderboard`…). Mets-le à jour quand tu en règles ou en découvres une.

### 5.5 Utiliser de vrais messages (le levier le plus efficace)

Les phrases que tu imagines ne ressemblent jamais tout à fait à ce que les gens tapent. La meilleure source de données, ce sont les messages réels que le bot n'a pas compris.

Dans `_predict()` (`guideonAi_api.py`), enregistre les messages quand la confiance est sous 85 % :

```python
import json, time

def _log_unsure(phrase: str, intent: str, confidence: float) -> None:
    # ./data est monté en volume dans docker-compose.yml, donc le fichier survit aux redéploiements
    with open("data/unrecognized.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(
            {"t": time.time(), "phrase": phrase, "intent": intent, "confidence": round(confidence, 3)},
            ensure_ascii=False,
        ) + "\n")
```

Une fois par semaine : relis le fichier, range chaque phrase dans la bonne intention de `DATASET` (ou crée l'intention manquante), vide le fichier, réentraîne. Ces messages sont des données utilisateur : ne les garde que le temps nécessaire.

### 5.6 Tester sérieusement

- Les phrases de `test.py` doivent être **différentes** de celles du dataset : on mesure la généralisation, pas la mémoire.
- Quand tu corriges un échec, **ajoute la phrase fautive à `TEST_CASES`** pour détecter les régressions.
- Garde un œil sur `val_acc` (diagnostic de `train.py`) : si elle est nettement sous `train_acc`, le modèle apprend par cœur au lieu de généraliser, et il manque de variété dans les phrases.

---

## 6. Réglages

| Réglage | Où | Effet |
|---|---|---|
| Seuils 0.6 / 0.85 | `predict.py` **et** `guideonAi_api.py` (logique dupliquée, à modifier aux deux endroits) | Plus haut = plus prudent, plus de « je ne comprends pas » |
| `HIDDEN_SIZE`, `EPOCHS`, `LEARNING_RATE` | haut de `train.py` | Capacité et durée d'apprentissage |
| `VAL_RATIO`, `MIN_PHRASES_FOR_VAL_SPLIT` | haut de `train.py` | Découpe du diagnostic |
| `Dropout(0.2)` | `model.py` | Régularisation |

Si la confiance reste basse **même sur des phrases du dataset**, le modèle n'a pas fini de converger. Remplace l'optimiseur SGD par Adam dans les deux passes de `train.py` :

```python
optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
```

---

## 7. Déploiement (Docker)

- Le `Dockerfile` exécute `cd GuideOnAi && python train.py` **pendant le build** : chaque build réentraîne le modèle (2 passes de 3000 epochs) et `model.pth` est généré dans `/app/GuideOnAi/`.
- `requirements.txt` doit contenir au minimum `torch` et `nltk`. Sur un VPS sans GPU, installe la version CPU de torch (`--index-url https://download.pytorch.org/whl/cpu`) pour alléger l'image.
- Si `train.py` plante, **le build échoue** et aucun conteneur n'est créé. Regarde la fin de la sortie de `docker compose up -d --build`.
- Après une modification du dataset : `docker compose up -d --build`. **Jamais `docker compose down -v`** : l'option `-v` supprime le volume de la base PostgreSQL.
- `guideonAi_api.py` doit retrouver `model.pth` et les modules (`tokenizer`, `vectorizer`, `model`, `response`, `permissions`). Comme tout vit dans `GuideOnAi/`, vérifie que les imports et le chemin de `torch.load` pointent bien vers ce dossier.

---

## 8. Limites connues et pièges

**Limites du principe**

- **Pas de mémoire** : chaque message est analysé seul. Quand le bot demande « C'est bien ça ? », un « oui » ne répond pas à cette question. Les intentions `yes_confirm` / `no_deny` sont un pansement qui donne une réponse cohérente, rien de plus.
- **Réponses figées** : pas de génération, pas de code, pas de réponse hors de `RESPONSES`.
- **Pas de notion de « hors sujet »** : une phrase étrangère à toutes les intentions est rattachée à la plus proche, parfois avec une forte confiance. Piste : créer une intention `hors_sujet` avec des phrases sans rapport, pour que le modèle ait le droit de dire « ce n'est pas pour moi ».
- **Mots collés ou très déformés** (`aurevoir`, fautes de frappe) : inconnus du vocabulaire, donc ignorés. Si une faute revient souvent, ajoute-la à `DATASET` ou à `_ABBREVIATIONS`.
- **Messages d'un seul mot** : un seul mot actif donne un signal faible. Les intentions courtes (`bonjour`, `merci`) doivent avoir plusieurs variantes d'un mot.
- Le message « Je pense que tu veux `ticket_create` » affiche le nom technique de l'intention. Une table de libellés lisibles serait plus agréable pour l'utilisateur.

**Bug à corriger dans `train.py`**

La fonction `accuracy()` n'appelle pas `model.eval()`, donc le Dropout reste actif pendant la mesure et `train_acc` / `val_acc` sont sous-estimés. Remplace-la par :

```python
def accuracy(model, X, Y):
    model.eval()
    with torch.no_grad():
        predicted_classes = model(X).argmax(dim=1)
    model.train()
    return (predicted_classes == Y).float().mean().item()
```

**À mettre à jour dans `test.py`**

Les « cas pièges » (`EDGE_CASES`) contiennent `"bonjour"` et `"merci beaucoup"` comme exemples hors-sujet alors que ce sont maintenant de vraies intentions (`greeting`, `thanks`). Et `TEST_CASES` ne couvre aucune des 16 intentions de conversation : ajoutes-en des reformulées.

**Erreurs fréquentes**

| Symptôme | Cause | Solution |
|---|---|---|
| `KeyError: 'xxx'` à la prédiction | intention absente de `RESPONSES` ou `PERMISSIONS` | l'ajouter (voir `check_data.py`) |
| `ValueError: 'xxx' is not in list` dans `train.py` | label du `DATASET` absent de `INTENTS` | l'ajouter à `INTENTS` ou corriger la faute de frappe |
| `size mismatch` au chargement | `model.pth` plus ancien que `INTENTS` ou le tokenizer | relancer `train.py` |
| « Je ne comprends pas » sur une phrase banale | mots inconnus ou intention avec trop peu de phrases | ajouter des phrases variées |
| Mauvaise intention avec forte confiance | mots partagés entre deux intentions | phrases contrastées (§5.4) |
| `ModuleNotFoundError: nltk` | dépendance manquante | `pip install nltk` / `requirements.txt` |

---

## 9. Aide-mémoire

| Je veux… | Je modifie | Je relance |
|---|---|---|
| qu'une phrase soit mieux comprise | `DATASET` (phrases de la bonne intention) | `train.py`, puis `test.py` |
| une nouvelle intention | `INTENTS`, `DATASET`, `RESPONSES`, `PERMISSIONS` | `check_data.py`, `train.py`, `test.py` |
| changer le texte d'une réponse | `RESPONSES` | rien (redémarrer le bot) |
| comprendre une abréviation | `_ABBREVIATIONS` (la valeur doit exister dans le dataset) | `train.py` |
| ignorer un mot parasite | `_FILLER_WORDS` | `train.py` |
| être plus (ou moins) prudent | seuils dans `predict.py` et `guideonAi_api.py` | redémarrer le bot |
| déployer | rien de plus | `docker compose up -d --build` |