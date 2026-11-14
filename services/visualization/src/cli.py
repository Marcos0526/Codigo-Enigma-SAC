"""CLI for visualization service."""

import asyncio
import json
import structlog
import click
from typing import Optional

import asyncpg

from services.visualization.src.config import settings
from services.visualization.src.visualization_service import (
    initialize_visualization_service,
    close_visualization_service,
    ChartPreviewRequest,
)
from services.visualization.src.connectors.data_connector import create_connector
from services.visualization.src.charts.chart_engine import create_chart_engine
from services.visualization.src.validation.column_validator import create_column_validator

logger = structlog.get_logger()


@click.group()
@click.option("--database-url", envvar="DATABASE_URL", required=True, help="PostgreSQL database URL")
@click.option("--pool-size", default=10, help="Connection pool size")
@click.pass_context
def cli(ctx, database_url: str, pool_size: int):
    """Visualization service CLI for interactive chart generation."""
    ctx.ensure_object(dict)
    ctx.obj["database_url"] = database_url
    ctx.obj["pool_size"] = pool_size


@cli.command()
@click.argument("dataset_id")
@click.argument("chart_type", type=click.Choice(["bar", "line", "scatter", "histogram"]))
@click.option("--x-axis", required=True, help="Column name for X axis")
@click.option("--y-axis", help="Column name for Y axis (required for bar, line, scatter)")
@click.option("--group-by", help="Column name for grouping/color")
@click.option("--limit", type=int, default=1000, help="Maximum rows to use")
@click.option("--offset", type=int, default=0, help="Row offset")
@click.option("--title", help="Chart title")
@click.option("--x-label", help="X axis label")
@click.option("--y-label", help="Y axis label")
@click.option("--width", type=int, default=800, help="Chart width")
@click.option("--height", type=int, default=400, help="Chart height")
@click.option("--output", type=click.Choice(["json", "vega"]), default="json", help="Output format")
@click.pass_context
def chart(ctx, dataset_id: str, chart_type: str, x_axis: str, y_axis: Optional[str],
          group_by: Optional[str], limit: int, offset: int, title: Optional[str],
          x_label: Optional[str], y_label: Optional[str], width: int, height: int,
          output: str):
    """Generate chart preview for a dataset."""

    async def _chart():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            service = await initialize_visualization_service(pool)

            options = {
                "limit": limit,
                "width": width,
                "height": height,
            }
            if title:
                options["title"] = title
            if x_label:
                options["xLabel"] = x_label
            if y_label:
                options["yLabel"] = y_label

            request = ChartPreviewRequest(
                dataset_id=dataset_id,
                chart_type=chart_type,
                x_axis=x_axis,
                y_axis=y_axis,
                group_by=group_by,
                options=options,
            )

            result = await service.generate_chart_preview(request)

            if output == "json":
                click.echo(json.dumps({
                    "datasetId": result.dataset_id,
                    "chartType": result.chart_type,
                    "spec": result.spec,
                    "data": result.data,
                    "columns": result.columns,
                    "warnings": result.warnings,
                    "metadata": result.metadata,
                }, indent=2, default=str))
            else:
                # Output Vega-Lite spec for embedding
                vega_spec = {
                    "spec": result.spec,
                    "data": {"values": result.data},
                }
                click.echo(json.dumps(vega_spec, indent=2))

        finally:
            await pool.close()
            await close_visualization_service()

    asyncio.run(_chart())


@cli.command()
@click.argument("dataset_id")
@click.option("--limit", type=int, default=100, help="Number of rows to preview")
@click.option("--offset", type=int, default=0, help="Row offset")
@click.pass_context
def preview(ctx, dataset_id: str, limit: int, offset: int):
    """Preview dataset data."""

    async def _preview():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            service = await initialize_visualization_service(pool)
            result = await service.get_dataset_preview(dataset_id, limit, offset)
            click.echo(json.dumps({
                "columns": result.columns,
                "dtypes": result.dtypes,
                "rows": result.rows,
                "totalRows": result.total_rows,
                "sampleRows": result.sample_rows,
                "columnInfo": {
                    name: {
                        "name": info.name,
                        "type": info.type.value,
                        "nullable": info.nullable,
                        "uniqueCount": info.unique_count,
                        "statistics": info.statistics,
                    }
                    for name, info in result.column_info.items()
                },
            }, indent=2, default=str))
        finally:
            await pool.close()
            await close_visualization_service()

    asyncio.run(_preview())


@cli.command()
@click.argument("dataset_id")
@click.pass_context
def columns(ctx, dataset_id: str):
    """Get column information for a dataset."""

    async def _columns():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            service = await initialize_visualization_service(pool)
            result = await service.get_column_info(dataset_id)
            click.echo(json.dumps(result, indent=2))
        finally:
            await pool.close()
            await close_visualization_service()

    asyncio.run(_columns())


@cli.command()
@click.argument("dataset_id")
@click.argument("chart_type", type=click.Choice(["bar", "line", "scatter", "histogram"]))
@click.option("--x-axis", required=True, help="Column name for X axis")
@click.option("--y-axis", help="Column name for Y axis")
@click.option("--group-by", help="Column name for grouping/color")
@click.pass_context
def validate(ctx, dataset_id: str, chart_type: str, x_axis: str, y_axis: Optional[str], group_by: Optional[str]):
    """Validate chart compatibility with dataset."""

    async def _validate():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            service = await initialize_visualization_service(pool)
            result = await service.validate_chart_compatibility(
                dataset_id=dataset_id,
                chart_type=chart_type,
                x_axis=x_axis,
                y_axis=y_axis,
                group_by=group_by,
            )
            click.echo(json.dumps({
                "compatible": result.compatible,
                "chartType": result.chart_type.value,
                "warnings": result.warnings,
                "requiredColumns": {
                    role: [t.value for t in types] for role, types in result.required_columns.items()
                },
                "providedColumns": {
                    role: {
                        "name": info.name,
                        "type": info.type.value,
                    } for role, info in result.provided_columns.items()
                },
            }, indent=2))
        finally:
            await pool.close()
            await close_visualization_service()

    asyncio.run(_validate())


@cli.command()
@click.argument("dataset_id")
@click.pass_context
def suggest(ctx, dataset_id: str):
    """Get suggested chart types for a dataset."""

    async def _suggest():
        pool = await asyncpg.create_pool(
            ctx.obj["database_url"],
            min_size=1,
            max_size=ctx.obj["pool_size"],
        )

        try:
            service = await initialize_visualization_service(pool)
            suggestions = await service.get_suggested_charts(dataset_id)
            click.echo(json.dumps(suggestions, indent=2))
        finally:
            await pool.close()
            await close_visualization_service()

    asyncio.run(_suggest())


@cli.command()
@click.argument("url")
@click.option("--limit", type=int, default=100, help="Number of rows to preview")
@click.pass_context
def test_connector(ctx, url: str, limit: int):
    """Test data connector with a URL."""

    async def _test():
        connector = create_connector(url)
        try:
            await connector.connect()
            preview = await connector.get_preview(limit=limit)
            click.echo(json.dumps({
                "columns": preview.columns,
                "dtypes": preview.dtypes,
                "rows": preview.rows,
                "totalRows": preview.total_rows,
                "sampleRows": preview.sample_rows,
                "columnInfo": {
                    name: {
                        "name": info.name,
                        "type": info.type.value,
                        "nullable": info.nullable,
                        "uniqueCount": info.unique_count,
                        "statistics": info.statistics,
                    }
                    for name, info in preview.column_info.items()
                },
            }, indent=2, default=str))
        finally:
            await connector.close()

    asyncio.run(_test())


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
            service = await initialize_visualization_service(pool)
            result = await service.health_check()
            click.echo(json.dumps(result, indent=2))
        finally:
            await pool.close()
            await close_visualization_service()

    asyncio.run(_health())


if __name__ == "__main__":
    cli()