"use client";

import { FormEvent, useMemo, useState, useEffect, useRef } from "react";
import embed, { VisualizationSpec } from "vega-embed";

type SearchResult = {
  id: string;
  psiId: string;
  name: string;
  description: string;
  url: string;
  format: string;
  numericColumns: string[];
  score: number;
  investigationTitle?: string;
  verificationStatus: string;
};

type SearchResponse = {
  status: "matches_found" | "no_matches";
  total_matches: number;
  datasets: SearchResult[];
};

type Summary = {
  title: string;
  executiveSummary: string;
  keyVariables: string[];
  findings: { description: string; evidence: string; source: string }[];
  limitations: string[];
  warnings: string[];
  sources: { type: string; reference: string }[];
};

type SchemaColumn = { column_name?: string; name?: string; column_type?: string; type?: string };
type DatasetSchema = { columns: SchemaColumn[]; rowCount?: number };

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const examples = [
  "Find numerical datasets about combustion temperature measurements in microgravity.",
  "Show datasets about flame extinction and spacecraft fire safety.",
  "Find smoke aerosol measurements and particle size data."
];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail?.error?.message ?? `Request failed (${response.status})`);
  }
  return response.json();
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [schema, setSchema] = useState<DatasetSchema | null>(null);
  const [chart, setChart] = useState<Record<string, unknown> | null>(null);
  const [chartType, setChartType] = useState("line");
  const [xAxis, setXAxis] = useState("");
  const [yAxis, setYAxis] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (chart && chartContainerRef.current) {
      const spec = chart.spec as VisualizationSpec;
      // Include data from API response in the spec
      const specWithData = {
        ...spec,
        data: { values: chart.data as unknown[] }
      } as VisualizationSpec;
      embed(chartContainerRef.current, specWithData, { actions: false, mode: "vega-lite" }).catch(console.error);
    }
  }, [chart]);

  const columns = useMemo(
    () => (schema?.columns ?? []).map((column) => column.column_name ?? column.name ?? ""),
    [schema]
  );

  async function search(event?: FormEvent) {
    event?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError("");
    setResults(null);
    setSelected(null);
    setSummary(null);
    setSchema(null);
    setChart(null);
    try {
      const response = await request<SearchResponse>("/search", {
        method: "POST",
        body: JSON.stringify({ query: query.trim(), options: { maxResults: 100 } })
      });
      setResults(response);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Search failed.");
    } finally {
      setLoading(false);
    }
  }

  async function selectDataset(dataset: SearchResult) {
    setSelected(dataset);
    setSummary(null);
    setChart(null);
    setError("");
    try {
      const datasetSchema = await request<DatasetSchema>(
        `/datasets/${encodeURIComponent(dataset.id)}/schema`
      );
      setSchema(datasetSchema);
      const firstColumns = datasetSchema.columns ?? [];
      setXAxis(firstColumns[0]?.column_name ?? firstColumns[0]?.name ?? dataset.numericColumns[0] ?? "");
      setYAxis(
        firstColumns[1]?.column_name ??
          firstColumns[1]?.name ??
          dataset.numericColumns[1] ??
          dataset.numericColumns[0] ??
          ""
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Schema unavailable.");
    }
  }

  async function generateSummary() {
    if (!selected) return;
    setLoading(true);
    setError("");
    try {
      setSummary(
        await request<Summary>(`/datasets/${encodeURIComponent(selected.id)}/summary`, {
          method: "POST",
          body: JSON.stringify({ datasetId: selected.id, options: { includeStatistics: true } })
        })
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Summary generation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function generateChart() {
    if (!selected || !xAxis) return;
    setLoading(true);
    setError("");
    try {
      setChart(
        await request<Record<string, unknown>>("/charts/preview", {
          method: "POST",
          body: JSON.stringify({
            datasetId: selected.id,
            chartType,
            xAxis,
            yAxis: yAxis || undefined,
            options: { limit: 500 }
          })
        })
      );
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Chart generation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">NASA PSI · COMBUSTION SCIENCE</p>
        <h1>Discover evidence-ready datasets.</h1>
        <p className="hero-copy">
          Search the 26 selected investigations, inspect verified numerical sources, and move from
          discovery to summaries and charts.
        </p>
        <form className="search-form" onSubmit={search}>
          <input
            aria-label="Search datasets"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask about combustion science data..."
          />
          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? "Searching..." : "Search"}
          </button>
        </form>
        <div className="examples">
          {examples.map((example) => (
            <button key={example} type="button" onClick={() => setQuery(example)}>
              {example}
            </button>
          ))}
        </div>
      </header>

      {error && <div className="alert error">{error}</div>}

      {results && (
        <section className="section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">SEARCH RESULTS</p>
              <h2>{results.total_matches} eligible datasets</h2>
            </div>
            <span className="status">{results.status === "no_matches" ? "No matches" : "Numeric data verified"}</span>
          </div>
          {results.datasets.length === 0 ? (
            <div className="empty">No verified numerical dataset matched this question.</div>
          ) : (
            <div className="results-grid">
              {results.datasets.map((dataset) => (
                <article className={`result-card ${selected?.id === dataset.id ? "selected" : ""}`} key={dataset.id}>
                  <div className="card-topline">
                    <span className="tag">{dataset.psiId}</span>
                    <span className="score">{Math.round(dataset.score * 100)}%</span>
                  </div>
                  <h3>{dataset.name}</h3>
                  <p>{dataset.description}</p>
                  <div className="meta">
                    <span>{dataset.format.toUpperCase()}</span>
                    <span>{dataset.numericColumns.length} numeric columns</span>
                  </div>
                  <div className="card-actions">
                    <a href={dataset.url} target="_blank" rel="noreferrer">View source ↗</a>
                    <button type="button" onClick={() => selectDataset(dataset)}>Select dataset</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {selected && (
        <section className="section workspace">
          <div className="section-heading">
            <div>
              <p className="eyebrow">DATASET WORKSPACE</p>
              <h2>{selected.name}</h2>
            </div>
            <span className="tag">{selected.psiId}</span>
          </div>
          <div className="workspace-grid">
            <div className="panel">
              <h3>Schema</h3>
              <p className="muted">{schema?.rowCount ?? "Unknown"} rows · {columns.length} columns</p>
              <div className="column-list">
                {columns.length ? columns.map((column) => <span key={column}>{column}</span>) : <span>Schema unavailable</span>}
              </div>
              <button type="button" onClick={generateSummary} disabled={loading}>Generate evidence-based summary</button>
            </div>
            <div className="panel">
              <h3>Chart builder</h3>
              <label>Chart type<select value={chartType} onChange={(event) => setChartType(event.target.value)}><option>line</option><option>bar</option><option>scatter</option><option>histogram</option></select></label>
              <label>X-axis<select value={xAxis} onChange={(event) => setXAxis(event.target.value)}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>
              {chartType !== "histogram" && <label>Y-axis<select value={yAxis} onChange={(event) => setYAxis(event.target.value)}>{columns.map((column) => <option key={column}>{column}</option>)}</select></label>}
              <button type="button" onClick={generateChart} disabled={loading || !xAxis}>Preview chart</button>
              {chart && (
              <div className="chart-container">
                <div ref={chartContainerRef} className="chart-renderer" />
              </div>
            )}
            </div>
          </div>
          {summary && (
            <div className="panel summary">
              <p className="eyebrow">EVIDENCE-BASED SUMMARY</p>
              <h3>{summary.title}</h3>
              <p>{summary.executiveSummary}</p>
              {summary.keyVariables.length > 0 && <p><strong>Key variables:</strong> {summary.keyVariables.join(", ")}</p>}
              {summary.findings.map((finding) => <div className="finding" key={`${finding.description}-${finding.source}`}><strong>{finding.description}</strong><span>{finding.evidence} · {finding.source}</span></div>)}
              {summary.limitations.length > 0 && <p className="muted"><strong>Limitations:</strong> {summary.limitations.join(" ")}</p>}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
