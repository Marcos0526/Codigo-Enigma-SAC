#!/bin/bash
# Database initialization script for Render deployment
# Enables pgvector and other required extensions

set -e

echo "Initializing database extensions..."

# Create a temporary Python script
cat > /tmp/init_db.py << 'PYTHON_SCRIPT'
import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

async def init_extensions():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("No DATABASE_URL provided")
        return
    
    # Convert to async URL
    async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(async_url, poolclass=NullPool)
    
    async with engine.begin() as conn:
        print("Creating uuid-ossp extension...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        
        print("Creating pgvector extension...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgvector";'))
        
        print("Creating pg_trgm extension...")
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm";'))
        
        print("Database extensions enabled successfully")
    
    await engine.dispose()

asyncio.run(init_extensions())
PYTHON_SCRIPT

# Run the initialization
pip install --quiet asyncpg sqlalchemy
python /tmp/init_db.py