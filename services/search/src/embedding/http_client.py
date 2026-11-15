"""HTTP embeddings shared by API queries and catalog ingestion."""

from typing import List

import httpx


async def embed_text(text: str, config, *, input_type: str, api_url: str = None) -> List[float]:
    """Use asymmetric NVIDIA query/passage modes with the same model and size."""
    headers = {}
    if config.EMBEDDING_PROVIDER.lower() == "nvidia":
        if not config.EMBEDDING_API_KEY:
            raise ValueError("Configure EMBEDDING_API_KEY in .env for NVIDIA embeddings")
        url = f"{config.NVIDIA_API_BASE_URL.rstrip('/')}/embeddings"
        headers["Authorization"] = f"Bearer {config.EMBEDDING_API_KEY}"
        payload = {
            "input": [text],
            "model": config.EMBEDDING_MODEL,
            "input_type": input_type,
            "dimensions": config.EMBEDDING_DIMENSIONS,
            "encoding_format": "float",
            "truncate": "END",
        }
    else:
        url = api_url or config.EMBEDDING_API_URL
        payload = {"texts": [text]}
        if config.EMBEDDING_API_KEY:
            headers["Authorization"] = f"Bearer {config.EMBEDDING_API_KEY}"

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    if config.EMBEDDING_PROVIDER.lower() == "nvidia":
        embedding = data["data"][0]["embedding"]
    else:
        embedding = data["embeddings"][0]
    if len(embedding) != config.EMBEDDING_DIMENSIONS:
        raise ValueError("Embedding dimensions differ from EMBEDDING_DIMENSIONS; check the model and index")
    return embedding
