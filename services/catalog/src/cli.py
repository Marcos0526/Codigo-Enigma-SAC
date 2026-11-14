"""CLI for catalog service."""

import asyncio
import json
import structlog
import click
from typing import Optional

from services.catalog.src.catalog_service import (
    CatalogService,
    initialize_catalog_service,
    close_catalog_service,
)
from services.catalog.src.models.catalog import (
    VerificationStatus,
    DataFormat,
    URLType,
    CATALOG_VERSION,
)

logger = structlog.get_logger()


@click.group()
@click.option("--database-url", envvar="DATABASE_URL", required=True, help="PostgreSQL database URL")
@click.option("--pool-size", default=10, help="Connection pool size")
@click.pass_context
def cli(ctx, database_url: str, pool_size: int):
    """Catalog service CLI for NASA PSI datasets."""
    ctx.ensure_object(dict)
    ctx.obj["database_url"] = database_url
    ctx.obj["pool_size"] = pool_size


@cli.command()
@click.pass_context
def init_db(ctx):
    """Initialize database schema."""
    from services.catalog.src.models.catalog import Base
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    async def _init():
        engine = create_async_engine(ctx.obj["database_url"])
        async with engine.begin() as conn:
            # Create extensions
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgvector"'))
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pg_trgm"'))
            # Tables are created via migration scripts
        await engine.dispose()
        click.echo("Database initialized")

    asyncio.run(_init())


@cli.command()
@click.option("--allowed-domains", help="Comma-separated allowed domains")
@click.pass_context
def ingest_psi(ctx, allowed_domains: Optional[str]):
    """Ingest the 26 selected PSI investigations."""
    domains = set(allowed_domains.split(",")) if allowed_domains else None

    async def _ingest():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            allowed_domains=domains,
            pool_size=ctx.obj["pool_size"],
        )
        try:
            results = await service.ingest_psi_investigations()
            successful = sum(1 for r in results if r.success)
            click.echo(f"Ingested {successful}/{len(results)} investigations")
            for r in results:
                if r.success:
                    click.echo(f"  ✅ {r.investigation.psi_id}: {r.investigation.title}")
                else:
                    click.echo(f"  ❌ {r.error}")
        finally:
            await close_catalog_service()

    asyncio.run(_ingest())


@cli.command()
@click.option("--psi-ids", help="Comma-separated PSI IDs to ingest datasets for")
@click.option("--allowed-domains", help="Comma-separated allowed domains")
@click.pass_context
def ingest_datasets(ctx, psi_ids: Optional[str], allowed_domains: Optional[str]):
    """Ingest datasets for investigations."""
    ids = psi_ids.split(",") if psi_ids else None
    domains = set(allowed_domains.split(",")) if allowed_domains else None

    async def _ingest():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            allowed_domains=domains,
            pool_size=ctx.obj["pool_size"],
        )
        try:
            results = await service.ingest_datasets(ids)
            total = sum(len(v) for v in results.values())
            successful = sum(sum(1 for r in v if r.success) for v in results.values())
            click.echo(f"Ingested {successful}/{total} datasets across {len(results)} investigations")
            for psi_id, inv_results in results.items():
                for r in inv_results:
                    if r.success:
                        click.echo(f"  ✅ {r.dataset.dataset_id} ({psi_id})")
                    else:
                        click.echo(f"  ❌ {psi_id}: {r.error}")
        finally:
            await close_catalog_service()

    asyncio.run(_ingest())


@cli.command()
@click.argument("url")
@click.option("--allowed-domains", help="Comma-separated allowed domains")
@click.pass_context
def validate_url(ctx, url: str, allowed_domains: Optional[str]):
    """Validate a dataset URL."""
    domains = set(allowed_domains.split(",")) if allowed_domains else None

    async def _validate():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            allowed_domains=domains,
            pool_size=ctx.obj["pool_size"],
        )
        try:
            result = await service.validate_url(url)
            click.echo(json.dumps(result, indent=2))
        finally:
            await close_catalog_service()

    asyncio.run(_validate())


@cli.command()
@click.argument("dataset_id")
@click.pass_context
def get_dataset(ctx, dataset_id: str):
    """Get dataset metadata by ID."""
    async def _get():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            pool_size=ctx.obj["pool_size"],
        )
        try:
            dataset = await service.get_dataset(dataset_id)
            if dataset:
                click.echo(json.dumps({
                    "dataset_id": dataset.dataset_id,
                    "psi_id": dataset.psi_id,
                    "name": dataset.name,
                    "description": dataset.description,
                    "url": dataset.url,
                    "url_type": dataset.url_type.value,
                    "format": dataset.format.value,
                    "numeric_columns": dataset.numeric_columns,
                    "verification_status": dataset.verification_status.value,
                    "tags": dataset.tags,
                }, indent=2))
            else:
                click.echo(f"Dataset not found: {dataset_id}")
        finally:
            await close_catalog_service()

    asyncio.run(_get())


@cli.command()
@click.argument("psi_id")
@click.pass_context
def list_datasets(ctx, psi_id: str):
    """List datasets for an investigation."""
    async def _list():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            pool_size=ctx.obj["pool_size"],
        )
        try:
            datasets = await service.list_datasets(psi_id=psi_id, limit=50)
            click.echo(f"Found {len(datasets)} datasets for {psi_id}:")
            for d in datasets:
                click.echo(f"  {d.dataset_id}: {d.name} ({d.format.value}) - {len(d.numeric_columns)} numeric cols")
        finally:
            await close_catalog_service()

    asyncio.run(_list())


@cli.command()
@click.pass_context
def list_investigations(ctx):
    """List all investigations."""
    async def _list():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            pool_size=ctx.obj["pool_size"],
        )
        try:
            investigations = await service.list_investigations(limit=50)
            click.echo(f"Found {len(investigations)} investigations:")
            for inv in investigations:
                click.echo(f"  {inv.psi_id}: {inv.title} [{inv.metadata_status.value}]")
        finally:
            await close_catalog_service()

    asyncio.run(_list())


@cli.command()
@click.pass_context
def health(ctx):
    """Check service health."""
    async def _health():
        service = await initialize_catalog_service(
            ctx.obj["database_url"],
            pool_size=ctx.obj["pool_size"],
        )
        try:
            result = await service.health_check()
            click.echo(json.dumps(result, indent=2))
        finally:
            await close_catalog_service()

    asyncio.run(_health())


if __name__ == "__main__":
    cli()