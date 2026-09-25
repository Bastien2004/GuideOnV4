import torch
from tokenizer import tokenize
from vectorizer import vectorize
from model import Model
from response import *
from permissions import *


checkpoint = torch.load("model.pth")

vocabulary = checkpoint["vocabulary"]
intents = checkpoint["intents"]

model = Model(
    checkpoint["input_size"],
    checkpoint["hidden_size"],
    checkpoint["output_size"]
)
model.load_state_dict(checkpoint["model_state"])
model.eval()

def predict(phrase):
    tokens = tokenize(phrase)
    vector = vectorize(tokens, vocabulary)
    x = torch.tensor(vector).float().unsqueeze(0)

    with torch.no_grad():
        output = model(x)
        probabilities = torch.softmax(output, dim=1)
        predicted_class = probabilities.argmax(dim=1).item()

    confiance = probabilities[0][predicted_class].item()

    intent = intents[predicted_class]

    if confiance < 0.6:
        return "Je ne comprends pas, reformule ta question", confiance

    elif confiance < 0.85:
        return f"Je pense que tu veux {intent}. C'est bien ça ?", confiance

    response = RESPONSES[intent]
    permission = PERMISSIONS[intent]

    if permission["type"] == "aucune":
        return response, confiance

    return f"{response}\n⚠️ Permission requise : {permission['type']} ({permission['detail']})", confiance

if __name__ == "__main__":
    print("Chatbot prêt ! (tape 'exit' pour arrêter)")
    
    while True:
        phrase = input("Toi : ")
        
        if phrase.lower() in ["quit", "exit", "stop"]:
            break
        
        intent, confiance = predict(phrase)
        print(f"→ Intention détectée : {intent} (confiance : {confiance:.2%})")