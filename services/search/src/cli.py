"""CLI for search service."""

import asyncio
import json
import structlog
import click
from typing import Optional

import asyncpg

from services.search.src.config import settings
from services.search.src.search_service import initialize_search_service, close_search_service
from services.search.src.embedding.service import initialize_embedding_service
from services.search.src.classification.query_classifier import QueryClassifier

logger = structlog.get_logger()


@click.group()
@click.option("--database-url", envvar="DATABASE_URL", required=True, help="PostgreSQL database URL")
@click.option("--pool-size", default=10, help="Connection pool size")
@click.pass_context
def cli(ctx, database_url: str, pool_size: int):
    """Search service CLI for semantic search."""
    ctx.ensure_object(dict)
    ctx.obj["database_url"] = database_url
    ctx.obj["pool_size"] = pool_size


@cli.command()
@click.argument("query")
@click.option("--min-score", type=float, default=0.3, help="Minimum similarity score")
@click.option("--max-results", type=int, default=50, help="Maximum results to return")
@click.option("--psi-ids", help="Comma-separated PSI IDs to filter")
@click.option("--formats", help="Comma-separated formats to filter")
@click.option("--hybrid/--no-hybrid", default=True, help="Use hybrid search")
@click.option("--rerank/--no-rerank", default=False, help="Enable reranking")
@click.option("--output", type=click.Choice(["json", "table"]), default="json", help="Output format")
@click.pass_context
def search(ctx, query: str, min_score: float, max_results: int, psi_ids: Optional[str],
           formats: Optional[str], hybrid: bool, rerank: bool, output: str):
    """Perform semantic search."""

    async def _search():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            from services.search.src.search_service import initialize_search_service
            service = await initialize_search_service(pool)

            filters = {}
            if psi_ids:
                filters["psi_ids"] = psi_ids.split(",")
            if formats:
                filters["formats"] = formats.split(",")

            options = {
                "minScore": min_score,
                "maxResults": max_results,
                "hybrid": hybrid,
                "rerank": rerank,
            }

            result = await service.search(query, filters, options)

            if output == "json":
                click.echo(json.dumps(result.__dict__, indent=2, default=str))
            else:
                _print_table(result)

        finally:
            await pool.close()
            await close_search_service()

    asyncio.run(_search())


def _print_table(result):
    """Print search results as a table."""
    click.echo(f"Query: {result.query}")
    click.echo(f"Status: {result.status}")
    click.echo(f"Total Matches: {result.total_matches}")
    click.echo(f"Processing Time: {result.search_metadata.get('processingTimeMs', 0):.2f}ms")
    click.echo()

    if result.datasets:
        click.echo(f"{'ID':<30} {'PSI':<10} {'Score':<8} {'Name'}")
        click.echo("-" * 80)
        for ds in result.datasets:
            click.echo(f"{ds['id']:<30} {ds['psiId']:<10} {ds['score']:<8.4f} {ds['name'][:50]}")
    else:
        click.echo("No matches found.")


@cli.command()
@click.argument("dataset_id")
@click.option("--count", type=int, default=10, help="Number of similar datasets")
@click.option("--min-similarity", type=float, default=0.5, help="Minimum similarity")
@click.pass_context
def similar(ctx, dataset_id: str, count: int, min_similarity: float):
    """Find datasets similar to a given dataset."""

    async def _similar():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            from services.search.src.search_service import initialize_search_service
            service = await initialize_search_service(pool)

            results = await service.get_similar_datasets(dataset_id, count, min_similarity)
            click.echo(json.dumps(results, indent=2))

        finally:
            await pool.close()
            await close_search_service()

    asyncio.run(_similar())


@cli.command()
@click.argument("query")
@click.pass_context
def classify(ctx, query: str):
    """Classify a query into combustion subtopics."""
    classifier = QueryClassifier()
    result = classifier.classify(query)

    click.echo(json.dumps({
        "subtopic": result.subtopic.value,
        "confidence": result.confidence,
        "is_combustion_related": result.is_combustion_related,
        "all_scores": {k.value: v for k, v in result.all_scores.items()},
        "suggested_filters": result.suggested_filters,
    }, indent=2))


@cli.command()
@click.pass_context
def evaluation_queries(ctx):
    """Get evaluation queries for testing."""
    classifier = QueryClassifier()
    queries = classifier.get_evaluation_queries()
    click.echo(json.dumps(queries, indent=2))


@cli.command()
@click.pass_context
def health(ctx):
    """Check service health."""

    async def _health():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            from services.search.src.search_service import initialize_search_service
            service = await initialize_search_service(pool)
            result = await service.health_check()
            click.echo(json.dumps(result, indent=2))
        finally:
            await pool.close()
            await close_search_service()

    asyncio.run(_health())


@cli.command()
@click.pass_context
def init_embedding(ctx):
    """Initialize and test embedding service."""

    async def _init():
        from services.search.src.embedding.service import initialize_embedding_service
        service = await initialize_embedding_service()
        healthy = await service.health_check()
        click.echo(f"Embedding service healthy: {healthy}")
        click.echo(f"Provider: {settings.EMBEDDING_PROVIDER}")
        click.echo(f"Model: {settings.EMBEDDING_MODEL}")
        click.echo(f"Dimensions: {settings.EMBEDDING_DIMENSIONS}")

    asyncio.run(_init())


if __name__ == "__main__":
    cli()