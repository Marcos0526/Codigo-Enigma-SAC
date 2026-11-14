#!/usr/bin/env python3
"""
Test NVIDIA embedding provider with API key.

Usage:
    export NVIDIA_API_KEY="your-api-key-here"
    python scripts/test_nvidia_embedding.py
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

from search.src.config import settings
from search.src.embedding.service import NVIDIAEmbeddingProvider


async def main():
    # Get API key from environment
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("EMBEDDING_API_KEY")
    
    if not api_key:
        print("❌ Error: NVIDIA_API_KEY or EMBEDDING_API_KEY environment variable not set")
        print("\nUsage:")
        print("  export NVIDIA_API_KEY='your-nvidia-api-key'")
        print("  python scripts/test_nvidia_embedding.py")
        print("\nGet your API key from: https://build.nvidia.com/")
        sys.exit(1)
    
    print(f"🔧 Testing NVIDIA Embedding Provider")
    print(f"   Model: {settings.EMBEDDING_MODEL}")
    print(f"   Dimensions: {settings.EMBEDDING_DIMENSIONS}")
    print(f"   Base URL: {settings.NVIDIA_API_BASE_URL}")
    print(f"   API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else '***'}")
    print()
    
    # Create provider
    provider = NVIDIAEmbeddingProvider(
        api_key=api_key,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIMENSIONS,
        base_url=settings.NVIDIA_API_BASE_URL,
    )
    
    # Test health check
    print("🏥 Running health check...")
    try:
        healthy = await provider.health_check()
        if healthy:
            print("✅ Health check passed!")
        else:
            print("❌ Health check failed")
            return
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return
    
    # Test embeddings
    test_texts = [
        "combustion temperature measurements in microgravity",
        "soot formation in diffusion flames",
        "droplet extinction with suppressants",
    ]
    
    print(f"\n🧪 Generating embeddings for {len(test_texts)} test queries...")
    try:
        result = await provider.embed(test_texts)
        print(f"✅ Embeddings generated successfully!")
        print(f"   Model: {result.model}")
        print(f"   Dimensions: {result.dimensions}")
        print(f"   Token count: {result.token_count}")
        print(f"   Number of embeddings: {len(result.embeddings)}")
        
        # Show first embedding sample
        if result.embeddings:
            first_emb = result.embeddings[0]
            print(f"   First embedding (first 5 values): {first_emb[:5]}")
            print(f"   Embedding length: {len(first_emb)}")
        
    except Exception as e:
        print(f"❌ Embedding generation error: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Close provider
    await provider.close()
    print("\n✨ All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())