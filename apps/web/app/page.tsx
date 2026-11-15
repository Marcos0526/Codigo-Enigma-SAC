"use client";

import {
  ChangeEvent,
  FormEvent,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import DatasetChartExplorer from "./dataset-chart-explorer";
import MarkdownContent from "./markdown-content";

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
type SchemaColumn = { column_name?: string; name?: string };
type DatasetSchema = { columns: SchemaColumn[]; rowCount?: number };
type ChatMessage = { role: "user" | "assistant"; content: string };
type ChatCompletionResponse = {
  choices: Array<{ message: { content: string } }>;
};

const examples = [
  {
    label: "Microgravity combustion",
    query:
      "Find numerical datasets about combustion temperature measurements in microgravity.",
  },
  {
    label: "Flame extinction",
    query: "Show datasets about flame extinction and spacecraft fire safety.",
  },
  {
    label: "Smoke & aerosols",
    query: "Find smoke aerosol measurements and particle size data.",
  },
];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail?.error?.message ?? `Request failed (${response.status})`,
    );
  }
  return response.json();
}

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [selected, setSelected] = useState<SearchResult | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [schema, setSchema] = useState<DatasetSchema | null>(null);
  const [searching, setSearching] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [error, setError] = useState("");
  const [colorMode, setColorMode] = useState<"dark" | "light">("dark");
  const [logo, setLogo] = useState("");
  const [heroImage, setHeroImage] = useState("");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const contextVersion = useRef(0);

  useEffect(() => {
    let savedMode: "dark" | "light" = "dark";
    try {
      if (window.localStorage.getItem("enigma-color-mode") === "light")
        savedMode = "light";
    } catch {
      /* Dark mode remains available when storage is disabled. */
    }
    setColorMode(savedMode);
    document.documentElement.dataset.theme = savedMode;
  }, []);

  function toggleColorMode() {
    const nextMode = colorMode === "dark" ? "light" : "dark";
    setColorMode(nextMode);
    document.documentElement.dataset.theme = nextMode;
    try {
      window.localStorage.setItem("enigma-color-mode", nextMode);
    } catch {
      /* Theme still changes for this visit. */
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    async function loadImages() {
      try {
        const response = await fetch("/api/site-images", {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) return;
        const images = (await response.json()) as {
          logo: string | null;
          background: string | null;
        };
        if (controller.signal.aborted) return;
        setLogo((current) =>
          current.startsWith("blob:") ? current : (images.logo ?? ""),
        );
        setHeroImage((current) =>
          current.startsWith("blob:") ? current : (images.background ?? ""),
        );
      } catch {
        // Keep placeholders or existing previews if the image folder is unavailable.
      }
    }
    void loadImages();
    const interval = window.setInterval(() => void loadImages(), 10000);
    window.addEventListener("focus", loadImages);
    return () => {
      controller.abort();
      window.clearInterval(interval);
      window.removeEventListener("focus", loadImages);
    };
  }, []);

  useEffect(
    () => () => {
      if (logo.startsWith("blob:")) URL.revokeObjectURL(logo);
    },
    [logo],
  );
  useEffect(() => {
    chatContainerRef.current?.scrollTo({
      top: chatContainerRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [chatMessages, chatLoading]);

  const columns = useMemo(
    () =>
      (schema?.columns ?? []).map(
        (column) => column.column_name ?? column.name ?? "",
      ),
    [schema],
  );
  const rankedResults = useMemo(
    () => [...(results?.datasets ?? [])].sort((a, b) => b.score - a.score),
    [results],
  );

  function uploadLogo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file || !file.type.startsWith("image/")) return;
    const url = URL.createObjectURL(file);
    setLogo(url);
  }

  function resetConversation() {
    setChatMessages([]);
    setChatInput("");
    setChatLoading(false);
    setSummarizing(false);
  }

  async function search(event: FormEvent) {
    event.preventDefault();
    if (!query.trim() || searching) return;
    const version = ++contextVersion.current;
    setSearching(true);
    setError("");
    setResults(null);
    setSelected(null);
    setSummary(null);
    setSchema(null);
    setSchemaLoading(false);
    resetConversation();
    setSubmittedQuery(query.trim());
    try {
      const response = await request<SearchResponse>("/search", {
        method: "POST",
        body: JSON.stringify({
          query: query.trim(),
          options: { maxResults: 100 },
        }),
      });
      if (version === contextVersion.current) setResults(response);
    } catch (requestError) {
      if (version === contextVersion.current)
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The search could not be completed. Please try again.",
        );
    } finally {
      if (version === contextVersion.current) setSearching(false);
    }
  }

  async function selectDataset(dataset: SearchResult) {
    const version = ++contextVersion.current;
    setSelected(dataset);
    setSchema(null);
    setSummary(null);
    setError("");
    setSchemaLoading(true);
    resetConversation();
    try {
      const datasetSchema = await request<DatasetSchema>(
        `/datasets/${encodeURIComponent(dataset.id)}/schema`,
      );
      if (version === contextVersion.current) setSchema(datasetSchema);
    } catch (requestError) {
      if (version === contextVersion.current)
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The dataset schema is currently unavailable.",
        );
    } finally {
      if (version === contextVersion.current) setSchemaLoading(false);
    }
  }

  async function generateSummary() {
    if (!selected || summarizing) return;
    const version = contextVersion.current;
    setSummarizing(true);
    setError("");
    try {
      const response = await request<Summary>(
        `/datasets/${encodeURIComponent(selected.id)}/summary`,
        {
          method: "POST",
          body: JSON.stringify({
            datasetId: selected.id,
            options: { includeStatistics: true },
          }),
        },
      );
      if (version === contextVersion.current) setSummary(response);
    } catch (requestError) {
      if (version === contextVersion.current)
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The summary could not be generated. Please try again.",
        );
    } finally {
      if (version === contextVersion.current) setSummarizing(false);
    }
  }

  async function sendChatMessage(event: FormEvent) {
    event.preventDefault();
    if (!chatInput.trim() || chatLoading || !selected || !summary) return;
    const version = contextVersion.current;
    const history: ChatMessage[] = [
      ...chatMessages,
      { role: "user", content: chatInput.trim() },
    ];
    setChatInput("");
    setChatLoading(true);
    setChatMessages(history);
    try {
      const compactSummary = summary
        ? {
            title: summary.title,
            executiveSummary: summary.executiveSummary.slice(0, 1200),
            keyVariables: summary.keyVariables,
            findings: summary.findings.slice(0, 8),
            limitations: summary.limitations.slice(0, 3),
            warnings: summary.warnings.slice(0, 3),
          }
        : null;
      const response = await request<ChatCompletionResponse>(
        "/chat/completions",
        {
          method: "POST",
          body: JSON.stringify({
            messages: [
              {
                role: "system",
                content: `You are a research assistant for NASA Physical Sciences Informatics. Respond in English with a formal, approachable research tone. Distinguish observations, hypotheses, and general knowledge. Do not invent measurements or infer causation from semantic relevance. Selected dataset: ${selected.name} (${selected.psiId}). Description: ${selected.description}. Evidence-based summary: ${JSON.stringify(compactSummary)}`,
              },
              ...history,
            ],
            max_tokens: 1000,
          }),
        },
      );
      const content = response.choices[0]?.message?.content;
      if (!content)
        throw new Error(
          "The assistant returned an empty response. Please try again.",
        );
      if (version === contextVersion.current)
        setChatMessages((previous) => [
          ...previous,
          { role: "assistant", content },
        ]);
    } catch (requestError) {
      if (version === contextVersion.current)
        setError(
          requestError instanceof Error
            ? requestError.message
            : "The assistant is currently unavailable.",
        );
    } finally {
      if (version === contextVersion.current) setChatLoading(false);
    }
  }

  return (
    <main className="shell">
      <nav className="site-nav" aria-label="Main navigation">
        <div className="brand">
          <label className="logo-slot" title="Choose a project logo">
            {logo ? (
              <img src={logo} alt="Project logo" />
            ) : (
              <span>
                LOGO<span className="slot-plus">+</span>
              </span>
            )}
            <input
              className="visually-hidden"
              type="file"
              accept="image/*"
              aria-label="Upload project logo"
              onChange={uploadLogo}
            />
          </label>
          <div>
            <span className="brand-name">
              ENIGMA<span className="brand-dot"> / </span>SAC
            </span>
            <span className="brand-caption">PHYSICAL SCIENCES DISCOVERY</span>
          </div>
        </div>
        <div className="nav-actions">
          <a className="nav-link" href="#research-search">
            Explore the catalog <span aria-hidden="true">↗</span>
          </a>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleColorMode}
            aria-pressed={colorMode === "light"}
          >
            <span aria-hidden="true">{colorMode === "dark" ? "☼" : "◐"}</span>
            {colorMode === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
      </nav>

      <header
        className={`hero ${heroImage ? "has-image" : ""}`}
        style={
          heroImage
            ? {
                backgroundImage: `linear-gradient(90deg, var(--hero-overlay-start), var(--hero-overlay-end)), url("${heroImage}")`,
              }
            : undefined
        }
      >
        <div className="visual-coordinates">
          <span>PSI / RESEARCH ARCHIVE</span>
          <span>01 — DISCOVERY</span>
        </div>
        <div className="hero-content">
          <p className="eyebrow">
            <span className="signal-dot" /> NASA PHYSICAL SCIENCES INFORMATICS
          </p>
          <h1>
            Your research question.
            <br />
            <span>A new connection.</span>
          </h1>
          <p className="hero-copy">
            Connect your research interests with the experimental knowledge
            available through NASA’s Physical Sciences Informatics repository.
          </p>
          <p className="hero-detail">
            Describe the phenomenon, variable, or scientific question you want
            to investigate. Our semantic search connects your intent with
            dataset descriptions, helping you identify relevant evidence and
            decide what to explore next.
          </p>
          <a className="hero-cta" href="#research-search">
            Begin your investigation <span aria-hidden="true">↘</span>
          </a>
          <div className="hero-topics">
            <span>MICROGRAVITY</span>
            <span>COMBUSTION</span>
            <span>EXPERIMENTAL DATA</span>
          </div>
        </div>
        <div className="visual-caption">
          <span className="signal-dot" /> A QUESTION IS WHERE DISCOVERY BEGINS.
        </div>
      </header>

      <div className="research-path" aria-label="Research workflow">
        <div>
          <span className="step-number">01</span>
          <p>
            <strong>Describe your interest</strong>
            <span>Start with a research question.</span>
          </p>
        </div>
        <div>
          <span className="step-number">02</span>
          <p>
            <strong>Discover relevant datasets</strong>
            <span>Review matches by relevance.</span>
          </p>
        </div>
        <div>
          <span className="step-number">03</span>
          <p>
            <strong>Explore the evidence</strong>
            <span>Visualize, summarize, and discuss.</span>
          </p>
        </div>
      </div>

      <section
        className="section search-section"
        id="research-search"
        aria-labelledby="search-title"
      >
        <div className="section-heading">
          <div>
            <p className="eyebrow">01 / DATA DISCOVERY</p>
            <h2 id="search-title">What would you like to investigate?</h2>
          </div>
          <span className="section-index" aria-hidden="true">
            [ EXPLORE ]
          </span>
        </div>
        <p className="section-copy">
          Use natural language to describe your research interest. Include the
          conditions or measurements that matter to your work.
        </p>
        <form className="search-form" onSubmit={search}>
          <span className="search-icon" aria-hidden="true">
            ⌕
          </span>
          <input
            aria-label="Search datasets"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="e.g., How does microgravity affect flame extinction?"
          />
          <button type="submit" disabled={searching || !query.trim()}>
            {searching ? "Searching the catalog…" : "Find datasets"}
            <span aria-hidden="true"> ↗</span>
          </button>
        </form>
        <div className="examples">
          <span>Suggested interests</span>
          {examples.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => setQuery(example.query)}
            >
              {example.label}
              <span aria-hidden="true"> ↗</span>
            </button>
          ))}
        </div>
        <p className="catalog-note">
          <span className="signal-dot" /> Current research preview: 26
          combustion science investigations. Search and visualization use 34
          real data files from 10 investigations in data/psi_databases.
        </p>
      </section>

      {error && (
        <div className="alert error" role="alert">
          {error}
        </div>
      )}
      <div role="status" className="visually-hidden">
        {searching
          ? "Searching for relevant datasets."
          : results
            ? `${results.total_matches} matching datasets found.`
            : ""}
      </div>

      {results && (
        <section className="section" aria-labelledby="results-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">RESEARCH MATCHES</p>
              <h2 id="results-title">
                {results.total_matches}{" "}
                {results.total_matches === 1 ? "dataset" : "datasets"} to
                explore<span className="red-period">.</span>
              </h2>
            </div>
            <span className="status">Highest relevance first ↓</span>
          </div>
          <p className="section-copy">
            Matches for “{submittedQuery}” are ranked by semantic correlation
            with your research interest, from highest to lowest. Scores indicate
            similarity of meaning, rather than statistical correlation between
            measurements.
          </p>
          {rankedResults.length === 0 ? (
            <div className="empty">
              <h3>No matching datasets found.</h3>
              <p>
                Try a broader phenomenon, a related variable, or different
                experimental conditions.
              </p>
            </div>
          ) : (
            <div className="results-grid">
              {rankedResults.map((dataset, index) => (
                <article
                  className={`result-card ${selected?.id === dataset.id ? "selected" : ""}`}
                  key={dataset.id}
                >
                  <div className="card-topline">
                    <span className="result-rank">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <span className="tag">{dataset.psiId}</span>
                    <span className="score">
                      {dataset.score.toFixed(3)} relevance
                    </span>
                  </div>
                  <h3>{dataset.name}</h3>
                  <p>{dataset.description}</p>
                  <div className="meta">
                    <span>{dataset.format.toUpperCase()}</span>
                    <span>
                      {dataset.numericColumns.length} numerical variables
                    </span>
                  </div>
                  <div className="card-actions">
                    <a
                      href={`https://psi.nasa.gov/physci/repo/data/investigations/${encodeURIComponent(dataset.psiId)}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      PSI investigation ↗
                    </a>
                    <button
                      type="button"
                      aria-pressed={selected?.id === dataset.id}
                      onClick={() => selectDataset(dataset)}
                    >
                      {selected?.id === dataset.id
                        ? "Selected ✓"
                        : "Explore dataset"}
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {selected && (
        <section
          className="section workspace"
          aria-labelledby="workspace-title"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">02 / SELECTED DATASET</p>
              <h2 id="workspace-title">{selected.name}</h2>
            </div>
            <span className="tag">{selected.psiId}</span>
          </div>
          <div className="panel dataset-overview">
            <div>
              <h3>Understand the data before drawing conclusions.</h3>
              <p className="muted">
                {schemaLoading
                  ? "Loading the dataset schema…"
                  : `${schema?.rowCount?.toLocaleString() ?? "Unknown"} rows · ${columns.length} variables`}
              </p>
              <div className="column-list">
                {columns.map((column) => (
                  <span key={column}>{column}</span>
                ))}
              </div>
            </div>
            <div className="summary-action">
              <button
                type="button"
                onClick={generateSummary}
                disabled={summarizing || schemaLoading}
              >
                {summarizing
                  ? "Preparing your summary…"
                  : summary
                    ? "Regenerate research summary ↗"
                    : "Generate research summary ↗"}
              </button>
              <p className="muted">
                Review the evidence, then open a focused conversation.
              </p>
            </div>
          </div>
          {summary && (
            <div className="panel summary" aria-live="polite">
              <p className="eyebrow">EVIDENCE-BASED RESEARCH SUMMARY</p>
              <MarkdownContent>{summary.executiveSummary}</MarkdownContent>
              <details className="summary-evidence">
                <summary>Dataset evidence &amp; data notes</summary>
                {summary.keyVariables.length > 0 && (
                  <p>
                    <strong>Key variables</strong>
                    <br />
                    {summary.keyVariables.join(", ")}
                  </p>
                )}
                {summary.findings.map((finding, index) => (
                  <div className="finding" key={`${index}-${finding.source}`}>
                    <strong>{finding.description}</strong>
                    <span>
                      {finding.evidence} · {finding.source}
                    </span>
                  </div>
                ))}
                {summary.limitations.length > 0 && (
                  <p className="muted">
                    <strong>Research limitations</strong>
                    <br />
                    {summary.limitations.join(" ")}
                  </p>
                )}
                {summary.warnings.length > 0 && (
                  <p className="muted">
                    <strong>Data notes</strong>
                    <br />
                    {summary.warnings.join(" ")}
                  </p>
                )}
              </details>
              <section
                className="chat-section summary-chat"
                aria-labelledby="chat-title"
              >
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">03 / RESEARCH CONVERSATION</p>
                    <h3 id="chat-title">
                      Take the next question further
                      <span className="red-period">.</span>
                    </h3>
                  </div>
                  <span className="tag">Powered by Groq</span>
                </div>
                <p className="section-copy">
                  Discuss the summary, clarify variables, and consider further
                  lines of inquiry for {selected.name}.
                </p>
                <div className="chat-container">
                  <div
                    ref={chatContainerRef}
                    className="chat-messages"
                    role="log"
                    aria-live="polite"
                    aria-label="Research conversation"
                  >
                    {chatMessages.length === 0 && (
                      <div className="chat-welcome">
                        <span
                          className="chat-welcome-symbol"
                          aria-hidden="true"
                        >
                          ↗
                        </span>
                        <h3>Your evidence. Your next question.</h3>
                        <p>
                          The dataset summary is ready. Ask about its findings,
                          experimental context, or limitations.
                        </p>
                        <p className="muted">
                          For example: “Which variables would help me
                          investigate the observed trends?”
                        </p>
                      </div>
                    )}
                    {chatMessages.map((message, index) => (
                      <div
                        key={`${message.role}-${index}`}
                        className={`chat-message ${message.role}`}
                      >
                        <span className="chat-role">
                          {message.role === "user"
                            ? "Researcher"
                            : "Research assistant"}
                        </span>
                        <div className="chat-bubble">
                          <MarkdownContent>{message.content}</MarkdownContent>
                        </div>
                      </div>
                    ))}
                    {chatLoading && (
                      <div className="chat-message assistant">
                        <span className="chat-role">Research assistant</span>
                        <div className="chat-bubble">
                          <p>Considering your question…</p>
                        </div>
                      </div>
                    )}
                  </div>
                  <form onSubmit={sendChatMessage} className="chat-input-form">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(event) => setChatInput(event.target.value)}
                      placeholder="Ask a follow-up question about this research…"
                      disabled={chatLoading}
                      aria-label="Research follow-up question"
                    />
                    <button
                      type="submit"
                      disabled={chatLoading || !chatInput.trim()}
                    >
                      {chatLoading ? "Preparing response…" : "Send question ↗"}
                    </button>
                  </form>
                </div>
              </section>
            </div>
          )}
        </section>
      )}

      {selected && (
        <DatasetChartExplorer
          key={selected.id}
          datasetId={selected.id}
          colorMode={colorMode}
        />
      )}

      <footer className="site-footer">
        <span className="brand-name">ENIGMA / SAC</span>
        <p>Connecting research questions with physical science evidence.</p>
        <span>
          NASA PSI research exploration · Independent research prototype
        </span>
      </footer>
    </main>
  );
}
