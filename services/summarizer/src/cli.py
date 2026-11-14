"""CLI for summarizer service."""

import asyncio
import json
import structlog
import click
from typing import Optional

import asyncpg

from services.summarizer.src.config import settings
from services.summarizer.src.summarizer_service import (
    initialize_summarizer_service,
    close_summarizer_service,
    SummaryRequest,
)
from services.summarizer.src.profiling.dataset_profiler import create_profiler
from services.summarizer.src.llm.client import get_llm_client

logger = structlog.get_logger()


@click.group()
@click.option("--database-url", envvar="DATABASE_URL", required=True, help="PostgreSQL database URL")
@click.option("--pool-size", default=10, help="Connection pool size")
@click.pass_context
def cli(ctx, database_url: str, pool_size: int):
    """Summarizer service CLI for evidence-based dataset summaries."""
    ctx.ensure_object(dict)
    ctx.obj["database_url"] = database_url
    ctx.obj["pool_size"] = pool_size


@cli.command()
@click.argument("dataset_id")
@click.option("--include-stats/--no-stats", default=True, help="Include computed statistics")
@click.option("--max-length", type=int, default=1000, help="Maximum summary length")
@click.option("--output", type=click.Choice(["json", "text"]), default="json", help="Output format")
@click.pass_context
def summarize(ctx, dataset_id: str, include_stats: bool, max_length: int, output: str):
    """Generate evidence-based summary for a dataset."""

    async def _summarize():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            service = await initialize_summarizer_service(pool)

            request = SummaryRequest(
                dataset_id=dataset_id,
                include_statistics=include_stats,
                max_length=max_length,
            )

            result = await service.generate_summary(request)

            if output == "json":
                click.echo(json.dumps(result.__dict__, indent=2, default=str))
            else:
                _print_text_summary(result)

        finally:
            await pool.close()
            await close_summarizer_service()

    asyncio.run(_summarize())


def _print_text_summary(result):
    """Print summary as formatted text."""
    click.echo(f"Title: {result.title}")
    click.echo(f"Dataset ID: {result.dataset_id}")
    click.echo(f"Generated: {result.generated_at}")
    click.echo(f"Generation Time: {result.generation_time_ms:.2f}ms")
    click.echo()
    click.echo("EXECUTIVE SUMMARY:")
    click.echo(result.executive_summary)
    click.echo()
    click.echo(f"Key Variables: {', '.join(result.key_variables)}")
    click.echo()
    click.echo("COVERAGE:")
    for k, v in result.coverage.items():
        click.echo(f"  {k}: {v}")
    click.echo()
    click.echo("FINDINGS:")
    for finding in result.findings:
        click.echo(f"  - {finding.get('description', '')}")
        click.echo(f"    Evidence: {finding.get('evidence', '')}")
        click.echo(f"    Source: {finding.get('source', '')}")
    click.echo()
    click.echo("LIMITATIONS:")
    for lim in result.limitations:
        click.echo(f"  - {lim}")
    click.echo()
    click.echo("WARNINGS:")
    for warn in result.warnings:
        click.echo(f"  - {warn}")
    click.echo()
    click.echo("SOURCES:")
    for src in result.sources:
        click.echo(f"  - {src.get('type', '')}: {src.get('reference', '')}")


@cli.command()
@click.argument("dataset_id")
@click.option("--sample-size", type=int, default=10000, help="Sample size for profiling")
@click.pass_context
def profile(ctx, dataset_id: str, sample_size: int):
    """Profile a dataset (compute statistics)."""

    async def _profile():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            from services.summarizer.src.summarizer_service import SummarizerService
            service = SummarizerService(pool)

            # Get column profiles
            profiles = await service._get_column_profiles(dataset_id)

            # Get dataset profile
            profile = await service._get_dataset_profile(dataset_id)

            click.echo(json.dumps({
                "dataset_id": dataset_id,
                "row_count": profile.row_count if profile else None,
                "column_count": profile.column_count if profile else None,
                "columns": [
                    {
                        "name": c.name,
                        "type": c.dtype.value,
                        "nullable": c.nullable,
                        "null_fraction": c.null_fraction,
                        "unique_count": c.unique_count,
                        "min_val": c.min_val,
                        "max_val": c.max_val,
                        "mean": c.mean,
                        "median": c.median,
                        "std": c.std,
                        "q1": c.q1,
                        "q3": c.q3,
                        "top_values": c.top_values,
                        "entropy": c.entropy,
                    }
                    for c in profiles
                ],
            }, indent=2, default=str))

        finally:
            await pool.close()

    asyncio.run(_profile())


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
            service = await initialize_summarizer_service(pool)
            result = await service.health_check()
            click.echo(json.dumps(result, indent=2))
        finally:
            await pool.close()
            await close_summarizer_service()

    asyncio.run(_health())


@cli.command()
@click.pass_context
def init_llm(ctx):
    """Initialize and test LLM client."""

    async def _init():
        client = get_llm_client()
        healthy = await client.health_check()
        click.echo(f"LLM Provider: {settings.LLM_PROVIDER}")
        click.echo(f"Model: {settings.LLM_MODEL}")
        click.echo(f"Healthy: {healthy}")
        await client.close()

    asyncio.run(_init())


@cli.command()
@click.pass_context
def test_prompt(ctx):
    """Test prompt generation for a dataset."""

    async def _test():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            from services.summarizer.src.summarizer_service import SummarizerService
            service = SummarizerService(pool)

            # Test with a known dataset
            dataset_id = "psi-20-bre-temperature-csv"

            profiles = await service._get_column_profiles(dataset_id)
            profile = await service._get_dataset_profile(dataset_id)
            metadata = await service._get_dataset_metadata(dataset_id)

            if not metadata:
                click.echo("Dataset not found")
                return

            from services.summarizer.src.prompts.summary_prompts import (
                PromptContext, build_prompt, generate_descriptive_summary
            )

            context = PromptContext(
                dataset_id=metadata["dataset_id"],
                name=metadata["name"],
                description=metadata["description"] or "",
                psi_id=metadata["psi_id"],
                investigation_title=metadata.get("investigation_title", ""),
                format=metadata["format"],
                url=metadata["url"],
                url_type=metadata["url_type"],
                source=metadata["source"] or "NASA PSI",
                license=metadata["license"] or "Public Domain",
                access_policy=metadata["access_policy"],
                tags=metadata["tags"] or [],
                verification_status=metadata["verification_status"],
                row_count=profile.row_count if profile else 0,
                columns=profiles,
                profiling_version=profile.profiling_version if profile else "1.0",
                catalog_version=settings.CATALOG_VERSION,
            )

            system, user = build_prompt(context)
            click.echo("=== SYSTEM PROMPT ===")
            click.echo(system[:500] + "..." if len(system) > 500 else system)
            click.echo()
            click.echo("=== USER PROMPT ===")
            click.echo(user[:1000] + "..." if len(user) > 1000 else user)
            click.echo()
            click.echo("=== DESCRIPTIVE SUMMARY ===")
            click.echo(generate_descriptive_summary(context))

        finally:
            await pool.close()

    asyncio.run(_test())


if __name__ == "__main__":
    cli()