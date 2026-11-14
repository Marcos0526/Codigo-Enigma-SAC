#!/usr/bin/env python3
"""
Simple embedding server using sentence-transformers.
"""

import os
import logging
from typing import List

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
DEVICE = os.getenv("EMBEDDING_DEVICE", "cpu")
PORT = int(os.getenv("PORT", "8080"))

# Global model
model = None


class EmbedRequest(BaseModel):
    texts: List[str]


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    version: str = "1.0.0"
    dimensions: int
    token_count: int = 0


app = FastAPI(title="Enigma SAC Embedding Service")


@app.on_event("startup")
async def startup_event():
    global model
    logger.info(f"Loading embedding model: {MODEL_NAME} on {DEVICE}")
    model = SentenceTransformer(MODEL_NAME, device=DEVICE)
    model.max_seq_length = 512
    logger.info(f"Model loaded. Embedding dimension: {model.get_sentence_embedding_dimension()}")


@app.get("/health")
async def health_check():
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy", "model": MODEL_NAME}


@app.post("/embed", response_model=EmbedResponse)
async def embed(request: EmbedRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    if not request.texts:
        return EmbedResponse(
            embeddings=[],
            model=MODEL_NAME,
            dimensions=model.get_sentence_embedding_dimension(),
        )
    
    # Generate embeddings
    embeddings = model.encode(request.texts, convert_to_numpy=True, normalize_embeddings=True)
    
    # Estimate token count
    token_count = sum(len(t.split()) for t in request.texts)
    
    return EmbedResponse(
        embeddings=embeddings.tolist(),
        model=MODEL_NAME,
        dimensions=embeddings.shape[1],
        token_count=token_count,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)