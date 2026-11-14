#!/usr/bin/env python3
"""
Test script to validate the search functionality with synthetic data.

This script:
1. Connects to the database
2. Generates embeddings for test queries
3. Performs vector similarity search
4. Validates results
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

import asyncpg
import structlog
from pgvector.asyncpg import register_vector

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.search.src.config import settings

logger = structlog.get_logger()

# Test queries covering different aspects of combustion science
TEST_QUERIES = [
    "combustion temperature measurements in microgravity",
    "soot formation in diffusion flames",
    "droplet extinction with suppressants",
    "cool flame behavior in liquid fuels",
    "smoke point of laminar jet flames",
    "flame spread over solid materials",
    "smoke aerosol particle size distribution",
    "large scale fabric burn sensor data",
    "gaseous cool flame temperature oscillations",
    "flame liftoff height in gas jet diffusion flames",
    "burning rate emulator temperature time series",
    "coflow laminar diffusion flame soot profiles",
    "flame extinguishment experiment droplet data",
    "cool flames investigation temperature transitions",
    "smoke point in coflow experiment measurements",
    "burning and suppression of solids flame spread",
    "smoke aerosol measurement experiment sizing",
    "spacecraft fire safety experiment fabric burn",
    "cool flames investigation with gases species concentrations",
    "structure and liftoff in combustion experiment",
]

EXPECTED_RESULTS = {
    "combustion temperature": ["psi-20-bre-temperature-csv"],
    "soot": ["psi-21-cld-soot-csv", "psi-107-spice-smoke-point-csv"],
    "droplet extinction": ["psi-69-flex-droplet-extinction-csv"],
    "cool flame": ["psi-39-cfi-cool-flame-csv", "psi-159-cfig-gaseous-cool-flame-csv"],
    "smoke point": ["psi-107-spice-smoke-point-csv"],
    "flame spread": ["psi-26-bass-solid-flame-spread-csv"],
    "aerosol": ["psi-102-same-smoke-aerosol-csv"],
    "fabric burn": ["psi-98-saffire-i-fabric-burn-csv"],
    "gaseous cool flame": ["psi-159-cfig-gaseous-cool-flame-csv"],
    "liftoff": ["psi-106-slice-liftoff-csv"],
}


async def generate_embedding(text: str, embedding_api_url: str) -> List[float]:
    """Generate embedding for query text."""
    import httpx
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            embedding_api_url,
            json={"texts": [text]},
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]


async def vector_search(
    conn: asyncpg.Connection,
    query_embedding: List[float],
    min_similarity: float = 0.3,
    match_count: int = 10,
) -> List[Dict[str, Any]]:
    """Execute vector similarity search."""
    # Pass the list directly - asyncpg handles vector conversion
    query = """
        SELECT
            d.dataset_id,
            d.psi_id,
            d.name,
            d.description,
            d.url,
            d.format,
            d.numeric_columns,
            1 - (de.embedding <=> $1::vector) AS score,
            pi.title AS investigation_title,
            d.verification_status
        FROM datasets d
        JOIN dataset_embeddings de ON de.dataset_id = d.id
        JOIN psi_investigations pi ON pi.psi_id = d.psi_id
        WHERE 1 - (de.embedding <=> $1::vector) >= $2
          AND d.verification_status = 'verified'
          AND d.numeric_columns IS NOT NULL
          AND array_length(d.numeric_columns, 1) > 0
        ORDER BY de.embedding <=> $1::vector
        LIMIT $3
    """
    
    rows = await conn.fetch(query, query_embedding, min_similarity, match_count)
    return [dict(row) for row in rows]


def evaluate_results(query: str, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate search results against expected results."""
    query_lower = query.lower()
    expected_datasets = []
    
    for keyword, datasets in EXPECTED_RESULTS.items():
        if keyword in query_lower:
            expected_datasets.extend(datasets)
    
    # Remove duplicates
    expected_datasets = list(set(expected_datasets))
    
    retrieved_ids = [r["dataset_id"] for r in results]
    
    # Calculate metrics
    relevant_retrieved = set(retrieved_ids) & set(expected_datasets)
    precision = len(relevant_retrieved) / len(retrieved_ids) if retrieved_ids else 0
    recall = len(relevant_retrieved) / len(expected_datasets) if expected_datasets else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    
    return {
        "query": query,
        "expected": expected_datasets,
        "retrieved": retrieved_ids,
        "relevant_retrieved": list(relevant_retrieved),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "num_results": len(results),
    }


async def main():
    """Run search tests."""
    database_url = os.getenv("DATABASE_URL", "postgresql://enigma:enigma@localhost:5432/enigma_sac")
    embedding_api_url = os.getenv("EMBEDDING_API_URL", "http://localhost:8080/embed")
    
    logger.info("starting_search_test",
                database_url=database_url,
                embedding_api_url=embedding_api_url)
    
    conn = await asyncpg.connect(database_url)
    await register_vector(conn)
    
    try:
        all_evaluations = []
        
        for query in TEST_QUERIES:
            logger.info("testing_query", query=query)
            
            # Generate embedding
            try:
                embedding = await generate_embedding(query, embedding_api_url)
            except Exception as e:
                logger.error("embedding_failed", query=query, error=str(e))
                continue
            
            # Search
            results = await vector_search(conn, embedding, min_similarity=0.3, match_count=10)
            
            # Evaluate
            evaluation = evaluate_results(query, results)
            all_evaluations.append(evaluation)
            
            logger.info("query_results",
                        query=query,
                        num_results=len(results),
                        top_results=[r["dataset_id"] for r in results[:3]],
                        precision=evaluation["precision"],
                        recall=evaluation["recall"],
                        f1=evaluation["f1"])
        
        # Summary
        print("\n" + "="*80)
        print("SEARCH TEST SUMMARY")
        print("="*80)
        
        total_precision = sum(e["precision"] for e in all_evaluations) / len(all_evaluations)
        total_recall = sum(e["recall"] for e in all_evaluations) / len(all_evaluations)
        total_f1 = sum(e["f1"] for e in all_evaluations) / len(all_evaluations)
        
        print(f"Average Precision: {total_precision:.3f}")
        print(f"Average Recall:    {total_recall:.3f}")
        print(f"Average F1:        {total_f1:.3f}")
        print()
        
        # Per-query details
        for e in all_evaluations:
            status = "✓" if e["f1"] > 0.5 else "✗"
            print(f"{status} {e['query'][:50]:50s} | P={e['precision']:.2f} R={e['recall']:.2f} F1={e['f1']:.2f} | Results: {e['num_results']}")
            if e["relevant_retrieved"]:
                print(f"    Relevant found: {e['relevant_retrieved']}")
            if e["expected"] and not e["relevant_retrieved"]:
                print(f"    Expected but not found: {e['expected']}")
        
        print("="*80)
        
        # Check dataset coverage
        all_retrieved = set()
        for e in all_evaluations:
            all_retrieved.update(e["retrieved"])
        
        print(f"\nTotal unique datasets retrieved across all queries: {len(all_retrieved)}")
        print(f"Datasets: {sorted(all_retrieved)}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())