"""
cogs/api/api_chatbot.py — API Chatbot IA.
"""
from __future__ import annotations

import logging

import torch
from fastapi import Depends, HTTPException
from pydantic import BaseModel

from cogs.api.base import app, require_token
from GuideOnAi.tokenizer import tokenize
from GuideOnAi.vectorizer import vectorize
from GuideOnAi.model import Model
from GuideOnAi.response import RESPONSES
from GuideOnAi.permissions import PERMISSIONS

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# 🧠 CHARGEMENT DU MODÈLE (une seule fois, au démarrage du module)
# ══════════════════════════════════════════════════════════════════════════

_checkpoint = torch.load("model.pth", map_location="cpu")

_vocabulary = _checkpoint["vocabulary"]
_intents = _checkpoint["intents"]

_model = Model(
    _checkpoint["input_size"],
    _checkpoint["hidden_size"],
    _checkpoint["output_size"],
)
_model.load_state_dict(_checkpoint["model_state"])
_model.eval()


# ══════════════════════════════════════════════════════════════════════════
# 📋 MODÈLES PYDANTIC
# ══════════════════════════════════════════════════════════════════════════

class PredictRequest(BaseModel):
    phrase: str


class PredictResponse(BaseModel):
    intent: str
    response: str
    confidence: float
    permission_required: bool
    permission_type: str | None = None
    permission_detail: str | None = None


# ══════════════════════════════════════════════════════════════════════════
# 🔧 LOGIQUE DE PRÉDICTION (reprend exactement predict() de ton script)
# ══════════════════════════════════════════════════════════════════════════

def _predict(phrase: str) -> PredictResponse:
    tokens = tokenize(phrase)
    vector = vectorize(tokens, _vocabulary)
    x = torch.tensor(vector).float().unsqueeze(0)

    with torch.no_grad():
        output = _model(x)
        probabilities = torch.softmax(output, dim=1)
        predicted_class = probabilities.argmax(dim=1).item()

    confidence = probabilities[0][predicted_class].item()
    intent = _intents[predicted_class]

    if confidence < 0.6:
        return PredictResponse(
            intent="unknown",
            response="Je ne comprends pas, reformule ta question",
            confidence=confidence,
            permission_required=False,
        )

    if confidence < 0.85:
        return PredictResponse(
            intent=intent,
            response=f"Je pense que tu veux {intent}. C'est bien ça ?",
            confidence=confidence,
            permission_required=False,
        )

    response_text = RESPONSES[intent]
    permission = PERMISSIONS[intent]

    if permission["type"] == "aucune":
        return PredictResponse(
            intent=intent,
            response=response_text,
            confidence=confidence,
            permission_required=False,
        )

    return PredictResponse(
        intent=intent,
        response=response_text,
        confidence=confidence,
        permission_required=True,
        permission_type=permission["type"],
        permission_detail=permission["detail"],
    )


# ══════════════════════════════════════════════════════════════════════════
# 🔄 ENDPOINTS — Chatbot IA
# ══════════════════════════════════════════════════════════════════════════

@app.post(
    "/chatbot/predict",
    dependencies=[Depends(require_token)],
    response_model=PredictResponse,
)
async def predict_intent(request: PredictRequest):
    """Prédit l'intention d'une phrase et retourne la réponse associée."""
    if not request.phrase.strip():
        raise HTTPException(status_code=400, detail="`phrase` ne peut pas être vide.")

    try:
        return _predict(request.phrase)
    except Exception as exc:
        log.exception("Erreur lors de la prédiction du chatbot")
        raise HTTPException(status_code=500, detail="Erreur interne lors de la prédiction.") from exc