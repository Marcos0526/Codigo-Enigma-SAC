"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import embed, { VisualizationSpec } from "vega-embed";

type DatasetOption = {
  id: string;
  title: string;
  investigation: string;
};

type Dataset = Pick<DatasetOption, "id" | "title"> & {
  columns: string[];
  rows: Array<Record<string, string | number | null>>;
};

type ChartType =
  | "line"
  | "scatter"
  | "bar"
  | "histogram"
  | "area"
  | "bubble"
  | "boxplot"
  | "heatmap";
type ThemeName = "crimson" | "carbon" | "burgundy" | "monochrome";

type ChartTheme = {
  label: string;
  accent: string;
  palette: string[];
  background: string;
  text: string;
  grid: string;
  surface: string;
  dark: boolean;
};

const chartThemes: Record<ThemeName, ChartTheme> = {
  crimson: {
    label: "Crimson",
    accent: "#ff525f",
    palette: ["#ff525f", "#ffb0b5", "#c12c41", "#e1dadd", "#88515b", "#8e8a8c"],
    background: "#141113",
    text: "#f1eaed",
    grid: "#33282c",
    surface: "#141113",
    dark: true,
  },
  carbon: {
    label: "Carbon",
    accent: "#f26571",
    palette: ["#f26571", "#ded5d8", "#ac394c", "#8e8a8c", "#ffabb3", "#74414b"],
    background: "#101010",
    text: "#f1eaed",
    grid: "#303030",
    surface: "#101010",
    dark: true,
  },
  burgundy: {
    label: "Burgundy",
    accent: "#ff8b97",
    palette: ["#ff8b97", "#dcd0d5", "#e34b61", "#b17886", "#b22c49", "#8e8a8c"],
    background: "#1c1015",
    text: "#f1eaed",
    grid: "#43232e",
    surface: "#1c1015",
    dark: true,
  },
  monochrome: {
    label: "Monochrome",
    accent: "#ded5d8",
    palette: ["#f1eaed", "#bcb3b7", "#ff525f", "#8e8a8c", "#ac394c", "#777174"],
    background: "#141113",
    text: "#f1eaed",
    grid: "#33282c",
    surface: "#141113",
    dark: true,
  },
};

const chartTypes: Array<{ value: ChartType; label: string }> = [
  { value: "scatter", label: "Scatter" },
  { value: "bubble", label: "Bubble" },
  { value: "line", label: "Line" },
  { value: "area", label: "Area" },
  { value: "bar", label: "Bar" },
  { value: "histogram", label: "Histogram" },
  { value: "boxplot", label: "Box plot" },
  { value: "heatmap", label: "Heatmap" },
];

export default function SyntheticChartExplorer({
  datasetId,
  colorMode = "dark",
}: {
  datasetId: string;
  colorMode?: "dark" | "light";
}) {
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [chartType, setChartType] = useState<ChartType>("scatter");
  const [xAxis, setXAxis] = useState("");
  const [yAxis, setYAxis] = useState("");
  const [groupBy, setGroupBy] = useState("");
  const [sizeBy, setSizeBy] = useState("");
  const [rowLimit, setRowLimit] = useState(1000);
  const [chartHeight, setChartHeight] = useState(360);
  const [pointSize, setPointSize] = useState(90);
  const [lineWidth, setLineWidth] = useState(2);
  const [opacity, setOpacity] = useState(0.75);
  const [themeName, setThemeName] = useState<ThemeName>("crimson");
  const [chartTitle, setChartTitle] = useState("");
  const [showGrid, setShowGrid] = useState(true);
  const [showLegend, setShowLegend] = useState(true);
  const [showTooltips, setShowTooltips] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!datasetId) return;

    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetch(`/api/synthetic-data?dataset=${encodeURIComponent(datasetId)}`, {
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok)
          throw new Error(`Could not load this dataset (${response.status}).`);
        return (await response.json()) as Dataset;
      })
      .then((loadedDataset) => {
        setDataset(loadedDataset);
        const numericColumns = loadedDataset.columns.filter((column) =>
          loadedDataset.rows.some((row) => typeof row[column] === "number"),
        );
        const categoricalColumns = loadedDataset.columns.filter((column) =>
          loadedDataset.rows.some((row) => typeof row[column] === "string"),
        );
        const preferredX = numericColumns.find((column) =>
          /time|position|diameter|distance/i.test(column),
        );
        const preferredY =
          numericColumns.find(
            (column) =>
              column !== preferredX &&
              !/^(run_id|test_number|sample_id|index)$/i.test(column),
          ) ?? numericColumns.find((column) => column !== preferredX);
        setXAxis(
          preferredX ?? numericColumns[0] ?? loadedDataset.columns[0] ?? "",
        );
        setYAxis(preferredY ?? "");
        setGroupBy(categoricalColumns[0] ?? "");
        setSizeBy(
          numericColumns.find(
            (column) =>
              column !== preferredX &&
              column !== preferredY &&
              !/^(run_id|test_number|sample_id|index)$/i.test(column),
          ) ?? "",
        );
        setRowLimit(Math.min(1000, loadedDataset.rows.length));
        setChartTitle("");
      })
      .catch((requestError: unknown) => {
        if (!controller.signal.aborted) {
          setDataset(null);
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Could not load this dataset.",
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [datasetId]);

  const numericColumns = useMemo(
    () =>
      dataset?.columns.filter((column) =>
        dataset.rows.some((row) => typeof row[column] === "number"),
      ) ?? [],
    [dataset],
  );
  const preferredNumericX =
    numericColumns.find((column) =>
      /time|position|diameter|distance/i.test(column),
    ) ??
    numericColumns[0] ??
    "";
  const categoricalColumns = useMemo(
    () =>
      dataset?.columns.filter((column) =>
        dataset.rows.some((row) => typeof row[column] === "string"),
      ) ?? [],
    [dataset],
  );
  const xColumns =
    chartType === "histogram" || chartType === "bubble"
      ? numericColumns
      : chartType === "boxplot"
        ? categoricalColumns.length
          ? categoricalColumns
          : (dataset?.columns ?? [])
        : (dataset?.columns ?? []);
  const yColumns =
    chartType === "heatmap" ? (dataset?.columns ?? []) : numericColumns;
  const plottedRows = useMemo(() => {
    if (!dataset) return [];
    const count = Math.min(rowLimit, dataset.rows.length);
    if (count === dataset.rows.length) return dataset.rows;
    const interval = dataset.rows.length / count;
    return Array.from(
      { length: count },
      (_, index) => dataset.rows[Math.floor(index * interval)],
    );
  }, [dataset, rowLimit]);
  const theme = useMemo(() => {
    const selectedTheme = chartThemes[themeName];
    if (colorMode === "dark") return selectedTheme;
    const accent = {
      crimson: "#b82542",
      carbon: "#51434a",
      burgundy: "#94233e",
      monochrome: "#372d32",
    }[themeName];
    return {
      ...selectedTheme,
      accent,
      palette: [accent, "#e86c82", "#7b4657", "#b48d9b", "#50444b", "#a6425d"],
      background: "#fffafb",
      surface: "#fffafb",
      text: "#30242a",
      grid: "#e8dce1",
      dark: false,
    };
  }, [themeName, colorMode]);
  const histogram = chartType === "histogram";
  const heatmap = chartType === "heatmap";
  const xType: "nominal" | "quantitative" =
    chartType === "boxplot" || !numericColumns.includes(xAxis)
      ? "nominal"
      : "quantitative";
  const yType: "nominal" | "quantitative" = numericColumns.includes(yAxis)
    ? "quantitative"
    : "nominal";

  useEffect(() => {
    const container = chartContainerRef.current;
    if (!container || !dataset || !plottedRows.length || !xAxis) return;
    if (!histogram && !yAxis) return;
    setError("");

    const spec: VisualizationSpec = {
      $schema: "https://vega.github.io/schema/vega-lite/v6.json",
      data: { values: plottedRows },
      width: "container",
      height: chartHeight,
      ...(xType === "quantitative" &&
      !histogram &&
      !heatmap &&
      chartType !== "boxplot"
        ? {
            params: [
              {
                name: "zoom",
                select: { type: "interval", encodings: ["x"] },
                bind: "scales",
              },
            ],
          }
        : {}),
      mark:
        chartType === "scatter" || chartType === "bubble"
          ? {
              type: "point",
              filled: true,
              opacity,
              size: pointSize,
              color: theme.accent,
            }
          : chartType === "line"
            ? {
                type: "line",
                point: true,
                opacity,
                strokeWidth: lineWidth,
                color: theme.accent,
              }
            : chartType === "area"
              ? {
                  type: "area",
                  opacity,
                  color: theme.accent,
                  stroke: theme.accent,
                  strokeWidth: lineWidth,
                }
              : chartType === "boxplot"
                ? { type: "boxplot", opacity }
                : chartType === "heatmap"
                  ? {
                      type: "rect",
                      opacity,
                      stroke: theme.background,
                      strokeWidth: 1,
                    }
                  : { type: "bar", opacity, color: theme.accent },
      encoding: {
        x: {
          field: xAxis,
          type: xType,
          ...(histogram
            ? { bin: true }
            : heatmap && xType === "quantitative"
              ? { bin: { maxbins: 24 } }
              : {}),
          title: xAxis,
        },
        y: histogram
          ? { aggregate: "count", type: "quantitative", title: "Count" }
          : {
              field: yAxis,
              type: yType,
              ...(heatmap && yType === "quantitative"
                ? { bin: { maxbins: 24 } }
                : {}),
              ...(chartType === "area" ? { stack: null } : {}),
              title: yAxis,
            },
        ...(heatmap
          ? {
              color: {
                aggregate: "count",
                type: "quantitative",
                title: "Samples",
                ...(showLegend ? {} : { legend: null }),
              },
            }
          : groupBy
            ? {
                color: {
                  field: groupBy,
                  type: "nominal",
                  title: groupBy,
                  scale: { range: theme.palette },
                  ...(showLegend ? {} : { legend: null }),
                },
              }
            : {}),
        ...(chartType === "bubble" && sizeBy
          ? {
              size: {
                field: sizeBy,
                type: "quantitative",
                ...(showLegend ? {} : { legend: null }),
              },
            }
          : {}),
        tooltip: showTooltips
          ? [
              { field: xAxis, type: xType },
              ...(!histogram ? [{ field: yAxis, type: yType }] : []),
              ...(groupBy && !heatmap
                ? [{ field: groupBy, type: "nominal" as const }]
                : []),
            ]
          : null,
      },
      ...(chartTitle.trim() ? { title: chartTitle.trim() } : {}),
      background: theme.background,
      config: {
        axis: {
          grid: showGrid,
          gridColor: theme.grid,
          labelColor: theme.text,
          titleColor: theme.text,
          domainColor: theme.grid,
          tickColor: theme.grid,
        },
        title: { color: theme.text, fontSize: 18, anchor: "start" },
        legend: { labelColor: theme.text, titleColor: theme.text },
        view: { stroke: null },
      },
    };

    let disposed = false;
    let finalize: (() => void) | undefined;
    embed(container, spec, {
      actions: false,
      tooltip: { theme: theme.dark ? "dark" : "light" },
    })
      .then((result) => {
        if (disposed) {
          result.view.finalize();
        } else {
          finalize = () => result.view.finalize();
        }
      })
      .catch((renderError: unknown) => {
        if (!disposed) {
          setError(
            renderError instanceof Error
              ? renderError.message
              : "Could not render this chart.",
          );
        }
      });

    return () => {
      disposed = true;
      finalize?.();
      container.replaceChildren();
    };
  }, [
    chartHeight,
    chartTitle,
    chartType,
    dataset,
    groupBy,
    heatmap,
    histogram,
    lineWidth,
    opacity,
    plottedRows,
    pointSize,
    showGrid,
    showLegend,
    showTooltips,
    sizeBy,
    theme,
    xAxis,
    xType,
    yAxis,
    yType,
  ]);

  function changeChartType(nextChartType: ChartType) {
    setChartType(nextChartType);
    if (
      (nextChartType === "histogram" || nextChartType === "bubble") &&
      !numericColumns.includes(xAxis)
    ) {
      setXAxis(preferredNumericX);
    }
    if (nextChartType === "boxplot" && !categoricalColumns.includes(xAxis)) {
      setXAxis(categoricalColumns[0] ?? dataset?.columns[0] ?? "");
    }
    if (
      nextChartType === "heatmap" &&
      (!dataset?.columns.includes(yAxis) || yAxis === xAxis)
    ) {
      setYAxis(dataset?.columns.find((column) => column !== xAxis) ?? "");
    }
  }

  return (
    <section className="section synthetic-explorer">
      <div className="section-heading">
        <div>
          <p className="eyebrow">INTERACTIVE DATA EXPLORATION</p>
          <h2>Explore the patterns.</h2>
        </div>
        <span className="status">Synthetic test data</span>
      </div>
      <p className="muted explorer-intro">
        Examine the selected dataset through an interactive visualization.
        Adjust the variables, chart type, and sample size to explore patterns
        relevant to your research.
      </p>

      <div className="explorer-layout">
        <div className="panel explorer-controls">
          <h3>Variables &amp; visualization</h3>
          <p className="muted">
            Selected dataset: {dataset?.title ?? datasetId}
          </p>
          <label>
            Chart type
            <select
              value={chartType}
              onChange={(event) =>
                changeChartType(event.target.value as ChartType)
              }
            >
              {chartTypes.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            X-axis
            <select
              value={xAxis}
              onChange={(event) => setXAxis(event.target.value)}
            >
              {xColumns.map((column) => (
                <option key={column}>{column}</option>
              ))}
            </select>
          </label>
          {!histogram && (
            <label>
              {heatmap ? "Y-axis / rows" : "Y-axis"}
              <select
                value={yAxis}
                onChange={(event) => setYAxis(event.target.value)}
              >
                {yColumns.map((column) => (
                  <option key={column}>{column}</option>
                ))}
              </select>
            </label>
          )}
          {chartType === "bubble" && (
            <label>
              Bubble size
              <select
                value={sizeBy}
                onChange={(event) => setSizeBy(event.target.value)}
              >
                <option value="">Fixed size</option>
                {numericColumns.map((column) => (
                  <option key={column}>{column}</option>
                ))}
              </select>
            </label>
          )}
          {!heatmap && (
            <label>
              Color by
              <select
                value={groupBy}
                onChange={(event) => setGroupBy(event.target.value)}
              >
                <option value="">Single color</option>
                {categoricalColumns.map((column) => (
                  <option key={column}>{column}</option>
                ))}
              </select>
            </label>
          )}

          <div className="control-divider" />
          <h3>Design</h3>
          <label>
            Color theme
            <select
              value={themeName}
              onChange={(event) =>
                setThemeName(event.target.value as ThemeName)
              }
            >
              {Object.entries(chartThemes).map(([value, option]) => (
                <option key={value} value={value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Chart title
            <input
              type="text"
              value={chartTitle}
              onChange={(event) => setChartTitle(event.target.value)}
              placeholder="Optional title"
            />
          </label>
          <SliderControl
            label="Rows to plot"
            value={Math.min(rowLimit, dataset?.rows.length ?? rowLimit)}
            min={100}
            max={dataset?.rows.length ?? 5000}
            step={100}
            onChange={setRowLimit}
            format={(value) => value.toLocaleString()}
          />
          <SliderControl
            label="Chart height"
            value={chartHeight}
            min={260}
            max={560}
            step={20}
            onChange={setChartHeight}
            format={(value) => `${value}px`}
          />
          {(chartType === "scatter" || chartType === "bubble") && (
            <SliderControl
              label="Point area"
              value={pointSize}
              min={20}
              max={240}
              step={10}
              onChange={setPointSize}
              format={(value) => `${value} px²`}
            />
          )}
          {(chartType === "line" || chartType === "area") && (
            <SliderControl
              label="Line width"
              value={lineWidth}
              min={1}
              max={6}
              step={1}
              onChange={setLineWidth}
              format={(value) => `${value}px`}
            />
          )}
          <SliderControl
            label="Opacity"
            value={opacity}
            min={0.2}
            max={1}
            step={0.05}
            onChange={setOpacity}
            format={(value) => `${Math.round(value * 100)}%`}
          />
          <div className="toggle-list">
            <label>
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(event) => setShowGrid(event.target.checked)}
              />{" "}
              Grid lines
            </label>
            <label>
              <input
                type="checkbox"
                checked={showLegend}
                onChange={(event) => setShowLegend(event.target.checked)}
              />{" "}
              Legend
            </label>
            <label>
              <input
                type="checkbox"
                checked={showTooltips}
                onChange={(event) => setShowTooltips(event.target.checked)}
              />{" "}
              Tooltips
            </label>
          </div>
        </div>

        <div className={`panel explorer-chart-panel theme-${themeName}`}>
          <div className="explorer-chart-heading">
            <div>
              <h3>
                {chartTitle.trim() ||
                  dataset?.title ||
                  "Preparing the selected dataset…"}
              </h3>
              <p className="muted">
                {loading
                  ? "Loading data..."
                  : dataset
                    ? `${plottedRows.length.toLocaleString()} of ${dataset.rows.length.toLocaleString()} rows sampled`
                    : "Select a dataset to begin."}
              </p>
            </div>
            {dataset && (
              <span className="tag">{dataset.columns.length} columns</span>
            )}
          </div>
          {error && <div className="alert error">{error}</div>}
          <div
            ref={chartContainerRef}
            className="synthetic-chart"
            aria-label="Interactive data chart"
            style={{
              backgroundColor: theme.surface,
              minHeight: chartHeight + 20,
            }}
          />
          {dataset && (
            <p className="muted chart-hint">
              Hover for values · drag to zoom on X · controls update the chart
              instantly.
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

function SliderControl({
  label,
  value,
  min,
  max,
  step,
  onChange,
  format,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
  format: (value: number) => string;
}) {
  return (
    <label className="range-control">
      <span className="range-heading">
        <span>{label}</span>
        <output>{format(value)}</output>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
