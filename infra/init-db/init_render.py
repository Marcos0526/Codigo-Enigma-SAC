#!/usr/bin/env python3
"""Database initialization script for Render deployment."""

import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

async def init_db():
    """Initialize database with required extensions."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not set, skipping initialization")
        return
    
    # Convert to async URL
    async_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(
        async_url,
        poolclass=NullPool,
        echo=True
    )
    
    async with engine.begin() as conn:
        # Enable required extensions
        print("Creating uuid-ossp extension...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        
        print("Creating pgvector extension...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgvector";'))
        
        print("Creating pg_trgm extension...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm";'))
        
        print("Database extensions enabled successfully")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(init_db())