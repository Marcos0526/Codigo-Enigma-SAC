#!/usr/bin/env python3
"""
Check database state - verify investigations, datasets, and embeddings are loaded.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
import structlog
from pgvector.asyncpg import register_vector

sys.path.insert(0, str(Path(__file__).parent.parent / "services"))

logger = structlog.get_logger()


async def main():
    database_url = os.getenv("DATABASE_URL", "postgresql://enigma:enigma@localhost:5432/enigma_sac")
    
    logger.info("checking_database", database_url=database_url)
    
    conn = await asyncpg.connect(database_url)
    await register_vector(conn)
    
    try:
        # Check investigations
        investigations = await conn.fetch("SELECT psi_id, title, metadata_status FROM psi_investigations ORDER BY psi_id")
        print(f"\n{'='*80}")
        print(f"PSI INVESTIGATIONS ({len(investigations)} total)")
        print(f"{'='*80}")
        for inv in investigations:
            print(f"  {inv['psi_id']:10s} | {inv['metadata_status']:10s} | {inv['title'][:60]}")
        
        # Check datasets
        datasets = await conn.fetch("""
            SELECT dataset_id, psi_id, name, format, numeric_columns, verification_status, 
                   array_length(numeric_columns, 1) as num_numeric_cols
            FROM datasets 
            ORDER BY psi_id, dataset_id
        """)
        print(f"\n{'='*80}")
        print(f"DATASETS ({len(datasets)} total)")
        print(f"{'='*80}")
        for ds in datasets:
            print(f"  {ds['dataset_id']:45s} | {ds['psi_id']:6s} | {ds['format']:6s} | "
                  f"numeric_cols={ds['num_numeric_cols'] or 0} | {ds['verification_status']}")
        
        # Check embeddings
        embeddings = await conn.fetch("""
            SELECT d.dataset_id, de.model, de.version, vector_dims(de.embedding) as dims
            FROM dataset_embeddings de
            JOIN datasets d ON d.id = de.dataset_id
            ORDER BY d.dataset_id
        """)
        print(f"\n{'='*80}")
        print(f"EMBEDDINGS ({len(embeddings)} total)")
        print(f"{'='*80}")
        for emb in embeddings:
            print(f"  {emb['dataset_id']:45s} | {emb['model']:30s} | v{emb['version']:5s} | {emb['dims']} dims")
        
        # Check dataset schemas
        schemas = await conn.fetch("""
            SELECT d.dataset_id, count(*) as num_columns,
                   count(*) filter (where column_type = 'numeric') as numeric_cols,
                   count(*) filter (where column_type = 'categorical') as cat_cols,
                   count(*) filter (where column_type = 'text') as text_cols
            FROM dataset_schemas ds
            JOIN datasets d ON d.id = ds.dataset_id
            GROUP BY d.dataset_id
            ORDER BY d.dataset_id
        """)
        print(f"\n{'='*80}")
        print(f"DATASET SCHEMAS")
        print(f"{'='*80}")
        for sch in schemas:
            print(f"  {sch['dataset_id']:45s} | cols={sch['num_columns']} "
                  f"(numeric={sch['numeric_cols']}, cat={sch['cat_cols']}, text={sch['text_cols']})")
        
        # Check dataset profiles
        profiles = await conn.fetch("""
            SELECT d.dataset_id, dp.row_count, dp.column_count, dp.byte_size
            FROM dataset_profiles dp
            JOIN datasets d ON d.id = dp.dataset_id
            ORDER BY d.dataset_id
        """)
        print(f"\n{'='*80}")
        print(f"DATASET PROFILES ({len(profiles)} total)")
        print(f"{'='*80}")
        for prof in profiles:
            print(f"  {prof['dataset_id']:45s} | rows={prof['row_count']:>6} | "
                  f"cols={prof['column_count']} | size={prof['byte_size']:,} bytes")
        
        # Summary stats
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"  Investigations: {len(investigations)}")
        print(f"  Verified investigations: {sum(1 for i in investigations if i['metadata_status'] == 'verified')}")
        print(f"  Datasets: {len(datasets)}")
        print(f"  Verified datasets: {sum(1 for d in datasets if d['verification_status'] == 'verified')}")
        print(f"  Datasets with embeddings: {len(embeddings)}")
        print(f"  Datasets with schemas: {len(schemas)}")
        print(f"  Datasets with profiles: {len(profiles)}")
        
        # Total rows across all datasets
        total_rows = sum(p['row_count'] for p in profiles)
        total_size = sum(p['byte_size'] for p in profiles)
        print(f"  Total data rows: {total_rows:,}")
        print(f"  Total data size: {total_size:,} bytes ({total_size/1024/1024:.1f} MB)")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())