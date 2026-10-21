"""
cogs/api/api_chatbot.py — API Chatbot IA (avec mémoire de conversation).

Toute la logique (modèle, seuils, recherche wiki, mémoire) est dans GuideOnAi/predict.py : l'API ne fait
que l'appeler. Plus de code recopié à deux endroits.

NOUVEAU : le champ optionnel `session_id` de la requête. Pour que le bot retienne la conversation, celui
qui appelle l'API doit envoyer le MÊME `session_id` à chaque message d'une même personne (par exemple son
id Discord, ou l'id de session du site). Sans `session_id`, rien ne change : aucune mémoire, comme avant.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from cogs.api.base import app, require_token
from GuideOnAi import predict as chatbot

log = logging.getLogger(__name__)

# Chargement du modèle (une seule fois, au démarrage)
chatbot.load()


# ============================================================
# 📋 MODÈLES PYDANTIC
# ============================================================

class PredictRequest(BaseModel):
    phrase: str
    session_id: str | None = None      # identifiant stable de la conversation (facultatif)


class PredictResponse(BaseModel):
    intent: str
    response: str
    confidence: float
    permission_required: bool
    permission_type: str | None = None
    permission_detail: str | None = None
    kind: str | None = None            # direct / confirmed / suggestion / wiki / unknown
    used_context: bool = False         # le sujet de la conversation a servi à comprendre la phrase


# ============================================================
# 🔄 ENDPOINTS — Chatbot IA
# ============================================================

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
        return PredictResponse(**chatbot.predict_message(request.phrase, request.session_id))
    except Exception as exc:
        log.exception("Erreur lors de la prédiction du chatbot")
        raise HTTPException(status_code=500, detail="Erreur interne lors de la prédiction.") from exc