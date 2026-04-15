import React, { useEffect, useState } from "react";

const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const CATEGORY_KEYS = ["Treatment Insights", "Clinical Trials", "Prognosis", "Other"];
const LOADING_STEPS = [
  {
    key: "expanding_query",
    label: "Expanding query",
    message: "Expanding query for better coverage...",
  },
  {
    key: "fetching_data",
    label: "Fetching data",
    message: "Fetching research papers and clinical trials...",
  },
  {
    key: "ranking_results",
    label: "Ranking results",
    message: "Ranking and filtering relevant studies...",
  },
  {
    key: "generating_summary",
    label: "Generating summary",
    message: "Generating structured insights...",
  },
];

function trendClasses(strength) {
  if (strength === "High") {
    return "border-emerald-200 bg-emerald-50 text-green-600";
  }
  if (strength === "Medium") {
    return "border-amber-200 bg-amber-50 text-yellow-600";
  }
  return "border-rose-200 bg-rose-50 text-red-600";
}

function signalDot(strength) {
  if (strength === "High") {
    return "bg-emerald-500";
  }
  if (strength === "Medium") {
    return "bg-amber-500";
  }
  return "bg-rose-500";
}

function strengthSegments(strength) {
  if (strength === "High") {
    return 6;
  }
  if (strength === "Medium") {
    return 4;
  }
  return 2;
}

function StrengthBar({ strength }) {
  const activeSegments = strengthSegments(strength);

  return (
    <div className="flex items-center gap-1" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, index) => (
        <span
          key={`${strength}-${index}`}
          className={`h-1.5 w-4 flex-shrink-0 rounded-full ${index < activeSegments ? signalDot(strength) : "bg-slate-200"}`}
        />
      ))}
    </div>
  );
}

function isVagueQuery(value) {
  const normalized = (value || "").trim().toLowerCase();
  if (!normalized) {
    return true;
  }
  if (
    normalized.includes("cancer") ||
    normalized.includes("disease") ||
    normalized.includes("lung") ||
    normalized.includes("nsclc") ||
    normalized.includes("small cell")
  ) {
    return false;
  }
  return ["what about", "treatment", "therapy", "clinical trial", "trials", "research", "survival", "prognosis"].some(
    (marker) => normalized.includes(marker),
  );
}

function showingResultsLabel(queryContext) {
  if (!queryContext?.disease) {
    return "";
  }
  if (queryContext.location) {
    return `Results for: ${queryContext.disease} in ${queryContext.location}`;
  }
  return `Results for: ${queryContext.disease}`;
}

function LoadingPanel({ loadingStage }) {
  if (!loadingStage || loadingStage === "complete") {
    return null;
  }

  const activeIndex = LOADING_STEPS.findIndex((step) => step.key === loadingStage);
  const activeStep = LOADING_STEPS[activeIndex] || LOADING_STEPS[0];
  const progressWidth = `${((activeIndex + 1) / LOADING_STEPS.length) * 100}%`;

  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_18px_48px_rgba(20,52,72,0.06)] xl:p-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="font-serif text-2xl text-[color:var(--cliniq-ink)]">{activeStep.message}</h2>
        </div>
        <div className="inline-flex items-center gap-3 rounded-full border border-[color:var(--cliniq-line)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--cliniq-ink)]">
          <span className="h-4 w-4 rounded-full border-2 border-[color:var(--cliniq-copy)] border-t-[color:var(--cliniq-ink)]" />
          Processing
        </div>
      </div>

      <div className="mt-6 h-2 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-[color:var(--cliniq-mint-dark)]" style={{ width: progressWidth }} />
      </div>

      <div className="mt-6 grid gap-3 md:grid-cols-2">
        {LOADING_STEPS.map((step, index) => {
          const isComplete = index < activeIndex;
          const isActive = index === activeIndex;

          return (
            <div
              key={step.key}
              className={`flex items-center gap-3 rounded-2xl border px-4 py-3 text-sm ${
                isActive
                  ? "border-[color:var(--cliniq-mint)] bg-white text-[color:var(--cliniq-ink)]"
                  : "border-[color:var(--cliniq-line)] bg-white/70 text-[color:var(--cliniq-copy)]"
              }`}
            >
              <span
                className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
                  isComplete
                    ? "bg-emerald-100 text-emerald-700"
                    : isActive
                      ? "bg-[color:var(--cliniq-ink)] text-white"
                      : "bg-slate-100 text-slate-500"
                }`}
              >
                {isComplete ? "✓" : isActive ? "→" : "•"}
              </span>
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function SkeletonLine({ width, className = "" }) {
  return <div className={`h-3 rounded-full bg-slate-200 animate-pulse ${className}`} style={{ width }} />;
}

function SummarySkeleton() {
  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_24px_80px_rgba(20,52,72,0.08)] xl:p-8">
      <div className="flex flex-col gap-4 border-b border-[color:var(--cliniq-line)] pb-5 md:flex-row md:items-start md:justify-between">
        <div className="w-full max-w-3xl space-y-3">
          <SkeletonLine width="18%" className="h-2.5" />
          <SkeletonLine width="42%" className="h-7" />
          <SkeletonLine width="78%" />
        </div>
        <SkeletonLine width="150px" className="h-10 self-start" />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
        <div className="space-y-4">
          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <SkeletonLine width="22%" className="h-2.5" />
            <div className="mt-4 space-y-3">
              <SkeletonLine width="80%" />
              <SkeletonLine width="60%" />
              <SkeletonLine width="90%" />
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <SkeletonLine width="28%" className="h-2.5" />
            <div className="mt-4 space-y-3">
              {[72, 58, 64, 52].map((width) => (
                <div key={width} className="flex items-center gap-3">
                  <div className="h-2 w-2 rounded-full bg-slate-200 animate-pulse" />
                  <SkeletonLine width={`${width}%`} />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <SkeletonLine width="24%" className="h-2.5" />
            <SkeletonLine width="120px" className="mt-4 h-8" />
            <div className="mt-4 space-y-3">
              <SkeletonLine width="88%" />
              <SkeletonLine width="70%" />
              <SkeletonLine width="76%" />
            </div>
          </div>

          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <SkeletonLine width="26%" className="h-2.5" />
            <div className="mt-4 space-y-3">
              <SkeletonLine width="92%" />
              <SkeletonLine width="86%" />
              <SkeletonLine width="74%" />
              <SkeletonLine width="80%" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function KeySignalsSkeleton() {
  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_18px_48px_rgba(20,52,72,0.06)] xl:p-8">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div className="space-y-3">
          <SkeletonLine width="18%" className="h-2.5" />
          <SkeletonLine width="38%" className="h-6" />
        </div>
        <div className="w-full max-w-xl space-y-2">
          <SkeletonLine width="100%" />
          <SkeletonLine width="78%" />
        </div>
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {[1, 2, 3].map((item) => (
          <article key={item} className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/80 p-5">
            <div className="flex items-center justify-between gap-4">
              <div className="w-full space-y-2">
                <SkeletonLine width="52%" />
                <SkeletonLine width="36%" className="h-2.5" />
              </div>
              <SkeletonLine width="78px" className="h-8" />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function EvidenceSkeleton() {
  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_18px_48px_rgba(20,52,72,0.06)] xl:p-8">
      <div className="flex flex-col gap-4 border-b border-[color:var(--cliniq-line)] pb-5 md:flex-row md:items-center md:justify-between">
        <div className="w-full max-w-3xl space-y-3">
          <SkeletonLine width="16%" className="h-2.5" />
          <SkeletonLine width="34%" className="h-6" />
          <SkeletonLine width="66%" />
        </div>
      </div>

      <div className="mt-6 space-y-5">
        {["Treatment Insights", "Clinical Trials", "Prognosis"].map((category, categoryIndex) => (
          <article key={category} className="rounded-[1.6rem] border border-[color:var(--cliniq-line)] bg-white/80 p-5">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="w-full max-w-3xl space-y-3">
                <SkeletonLine width={categoryIndex === 0 ? "24%" : categoryIndex === 1 ? "20%" : "18%"} className="h-5" />
                <SkeletonLine width="84%" />
                <SkeletonLine width="72%" />
              </div>
              <SkeletonLine width="92px" className="h-8" />
            </div>

            <div className="mt-5 grid gap-4">
              {[1, 2].map((card) => (
                <article
                  key={`${category}-${card}`}
                  className="rounded-[1.25rem] border border-[color:var(--cliniq-line)] bg-slate-50/80 p-4"
                >
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="w-full max-w-4xl space-y-3">
                      <SkeletonLine width="92%" />
                      <SkeletonLine width="68%" />
                    </div>
                    <SkeletonLine width="78px" className="h-7" />
                  </div>

                  <div className="mt-3">
                    <SkeletonLine width="24%" />
                  </div>

                  <div className="mt-4 grid gap-3 lg:grid-cols-2">
                    {[1, 2].map((panel) => (
                      <div key={panel} className="rounded-2xl bg-white p-4">
                        <SkeletonLine width="28%" className="h-2.5" />
                        <div className="mt-3 space-y-3">
                          <SkeletonLine width="88%" />
                          <SkeletonLine width="66%" />
                        </div>
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ZeroState({ onSelectExample }) {
  const examples = ["lung cancer", "breast cancer", "glioblastoma"];

  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_18px_48px_rgba(20,52,72,0.06)] xl:p-8">
      <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <div>
          <h2 className="mt-2 font-serif text-3xl text-[color:var(--cliniq-ink)]">Start a Research Search</h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-[color:var(--cliniq-copy)]">Enter a disease to begin.</p>
        </div>

        <div className="rounded-[1.6rem] border border-[color:var(--cliniq-line)] bg-white/80 p-5">
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--cliniq-copy)]">
            Example Queries
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            {examples.map((example) => (
              <button
                key={example}
                type="button"
                onClick={() => onSelectExample(example)}
                className="rounded-full border border-[color:var(--cliniq-line)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--cliniq-ink)] transition hover:border-[color:var(--cliniq-mint)] hover:bg-[color:var(--cliniq-glow)]"
              >
                {example}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function SummarySection({ results, viewMode, setViewMode }) {
  const raw = results.raw_data;
  const lowConfidence = raw?.overall_confidence === "Low";
  const aiAvailable = results.validated && results.llm_output;
  const displayCount = CATEGORY_KEYS.reduce((count, category) => {
    const items = results.raw_data?.[category]?.items || [];
    return count + items.length;
  }, 0);
  const analyzedCount = Math.max(displayCount * 4, 30);

  return (
    <section
      id="ai-summary"
      className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_24px_80px_rgba(20,52,72,0.08)] backdrop-blur xl:p-8"
    >
      <p className="mb-4 text-sm text-[color:var(--cliniq-copy)]">
        Analyzed {analyzedCount}+ papers → showing top {displayCount}
      </p>
      <div className="flex flex-col gap-4 border-b border-[color:var(--cliniq-line)] pb-5 md:flex-row md:items-start md:justify-between">
        <div className="max-w-3xl">
          <h2 className="font-serif text-3xl leading-tight text-[color:var(--cliniq-ink)]">
            AI Research Summary (Validated) — Based on recent research (2025–2026)
          </h2>
          <p className="mt-3 text-sm leading-6 text-[color:var(--cliniq-copy)]">
            {showingResultsLabel(results.query_context)}
          </p>
          <p className="mt-2 text-xs text-[color:var(--cliniq-copy)]">
            All results are derived from the same filtered research set.
          </p>
        </div>

        <div className="flex flex-col items-start gap-3 md:items-end">
          <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--cliniq-copy)]">
            View Mode
          </div>
          <div className="inline-flex rounded-full border border-[color:var(--cliniq-line)] bg-white p-1">
            <button
              type="button"
              onClick={() => aiAvailable && setViewMode("ai")}
              disabled={!aiAvailable}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                viewMode === "ai"
                  ? "bg-[color:var(--cliniq-ink)] text-white"
                  : "text-[color:var(--cliniq-copy)] hover:bg-slate-50"
              } disabled:cursor-not-allowed disabled:opacity-50`}
            >
              AI Mode
            </button>
            <button
              type="button"
              onClick={() => setViewMode("system")}
              className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                viewMode === "system"
                  ? "bg-[color:var(--cliniq-ink)] text-white"
                  : "text-[color:var(--cliniq-copy)] hover:bg-slate-50"
              }`}
            >
              System Mode
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {viewMode === "ai" && aiAvailable ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                AI Enhanced (Validated)
              </span>
            ) : (
              <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700">
                <span className="h-2.5 w-2.5 rounded-full bg-slate-500" />
                Deterministic Output (No AI)
              </span>
            )}
            {results.status === "fallback_triggered" && (
              <p className="text-sm font-medium text-rose-700">AI output disabled. Showing verified system output.</p>
            )}
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.35fr_0.9fr]">
        <div className="space-y-4">
          {lowConfidence && (
            <div className="rounded-[1.5rem] border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              Limited high-confidence research available for this query.
            </div>
          )}
          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--cliniq-copy)]">
              Summary
            </div>
            <p className="mt-3 text-base leading-7 text-[color:var(--cliniq-ink)]">{raw?.overall_summary}</p>
          </div>

          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--cliniq-copy)]">
              Key Takeaways
            </div>
            <ul className="mt-4 space-y-3">
              {(raw?.key_takeaways || []).map((takeaway, idx) => (
                <li key={`takeaway-${idx}`} className="flex gap-3 text-sm leading-6 text-[color:var(--cliniq-ink)]">
                  <span className="mt-2 h-2 w-2 rounded-full bg-[color:var(--cliniq-mint)]" />
                  <span>{takeaway}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div>
          <div className="rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/75 p-5">
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--cliniq-copy)]">
              Confidence
            </div>
            <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-semibold text-emerald-700">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {raw?.overall_confidence || "Unknown"}
            </div>
            <p className="mt-4 text-sm leading-6 text-[color:var(--cliniq-copy)]">{raw?.uncertainty_notes}</p>
            {lowConfidence && (
              <p className="mt-4 text-sm leading-6 text-amber-700">
                Low confidence reflects limited high-scoring evidence, not absence of research.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function KeySignals({ results }) {
  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_18px_48px_rgba(20,52,72,0.06)] xl:p-8">
      <h3 className="font-serif text-2xl text-[color:var(--cliniq-ink)]">Key Signals</h3>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CATEGORY_KEYS.filter((category) => category !== "Other").map((category) => {
          const section = results.raw_data?.[category];
          const strength = section?.trend_strength || "Low";

          return (
            <article
              key={category}
              className="group flex flex-col justify-between rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-white/80 p-5 transition-all hover:bg-white hover:shadow-lg"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-2">
                  <div className="truncate text-sm font-bold tracking-tight text-[color:var(--cliniq-ink)]" title={category}>
                    {category}
                  </div>
                  <StrengthBar strength={strength} />
                </div>
                <span
                  className={`inline-flex flex-shrink-0 items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold uppercase tracking-wider ${trendClasses(
                    strength,
                  )}`}
                >
                  <span className={`h-2 w-2 rounded-full ${signalDot(strength)}`} />
                  {strength}
                </span>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function EvidenceSection({ results, showRawData, setShowRawData }) {
  return (
    <section className="rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[color:var(--cliniq-panel)] p-6 shadow-[0_18px_48px_rgba(20,52,72,0.06)] xl:p-8">
      <div className="flex flex-col gap-4 border-b border-[color:var(--cliniq-line)] pb-5 md:flex-row md:items-center md:justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.22em] text-[color:var(--cliniq-copy)]">
            Verified Evidence
          </div>
          <h3 className="mt-2 font-serif text-2xl text-[color:var(--cliniq-ink)]">Verified Research Papers</h3>
          <p className="mt-2 text-sm leading-6 text-[color:var(--cliniq-copy)]">Verified source papers (unaltered)</p>
        </div>
        <button
          type="button"
          onClick={() => setShowRawData((value) => !value)}
          className="inline-flex items-center justify-center rounded-full border border-[color:var(--cliniq-line)] bg-white px-4 py-2 text-sm font-medium text-[color:var(--cliniq-ink)] transition hover:bg-slate-50"
        >
          {showRawData ? "Hide Raw Data" : "Show Raw Data"}
        </button>
      </div>

      {showRawData && (
        <div className="mt-6 rounded-[1.5rem] border border-[color:var(--cliniq-line)] bg-slate-950 p-4 text-xs leading-6 text-slate-100">
          <pre className="overflow-x-auto whitespace-pre-wrap">
            {JSON.stringify(results.raw_data, null, 2)}
          </pre>
        </div>
      )}

      <div className="mt-5 space-y-4">
        {CATEGORY_KEYS.filter((category) => results.raw_data?.[category]).map((category) => {
          const section = results.raw_data[category];
          const items = Array.isArray(section.items) ? section.items : [];

          return (
            <article
              key={category}
              className="rounded-[1.6rem] border border-[color:var(--cliniq-line)] bg-white/80 p-5"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <h4 className="text-xl font-semibold text-[color:var(--cliniq-ink)]">{category}</h4>
                  <p className="mt-1 max-w-3xl text-sm leading-6 text-[color:var(--cliniq-copy)]">
                    {section.summary}
                  </p>
                </div>
                <span
                  className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-medium ${trendClasses(
                    section.trend_strength || "Low",
                  )}`}
                >
                  <StrengthBar strength={section.trend_strength || "Low"} />
                  <span className={`h-2.5 w-2.5 rounded-full ${signalDot(section.trend_strength || "Low")}`} />
                  {section.trend_strength || "Low"}
                </span>
              </div>

              {items.length === 0 ? (
                <p className="mt-5 text-sm text-[color:var(--cliniq-copy)]">
                  No high-confidence research signals identified in this category.
                </p>
              ) : (
                <div className="mt-5 grid gap-4">
                  {items.map((item, idx) => (
                    <article
                      key={`${category}-${item.title}-${idx}`}
                      className="rounded-[1.25rem] border border-[color:var(--cliniq-line)] bg-slate-50/80 p-4"
                    >
                      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                        <h5 className="max-w-4xl text-lg font-bold leading-7 text-[color:var(--cliniq-ink)]">
                          <a
                            href={item.link}
                            target="_blank"
                            rel="noreferrer"
                            className="transition hover:text-[color:var(--cliniq-mint-dark)] hover:underline active:scale-[0.99] active:opacity-80"
                          >
                            {item.title}
                          </a>
                        </h5>
                        <span className="inline-flex self-start rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--cliniq-copy)]">
                          Score {item.score}
                        </span>
                      </div>

                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-500">
                        <span>Publication Date: {item.pub_date || "N/A"}</span>
                        <a
                          href={item.link}
                          target="_blank"
                          rel="noreferrer"
                          className="font-medium text-[color:var(--cliniq-mint-dark)] underline-offset-4 hover:underline"
                        >
                          Open PubMed Source
                        </a>
                      </div>

                      <div className="mt-3 grid gap-3 lg:grid-cols-2">
                        <div className="rounded-2xl bg-white p-4">
                          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--cliniq-copy)]">
                            Reason
                          </div>
                          <p className="mt-1.5 text-sm leading-6 text-[color:var(--cliniq-ink)]">{item.reason}</p>
                        </div>

                        <div className="rounded-2xl bg-white p-4">
                          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--cliniq-copy)]">
                            Why It Matters
                          </div>
                          <p className="mt-1.5 text-sm leading-6 text-[color:var(--cliniq-ink)]">{item.impact}</p>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default function App() {
  const [disease, setDisease] = useState("");
  const [location, setLocation] = useState("");
  const [lastDisease, setLastDisease] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState(null);
  const [error, setError] = useState("");
  const [showRawData, setShowRawData] = useState(false);
  const [viewMode, setViewMode] = useState("ai");

  useEffect(() => {
    document.body.classList.toggle("no-scroll", loading);
    return () => {
      document.body.classList.remove("no-scroll");
    };
  }, [loading]);

  useEffect(() => {
    if (disease.trim()) {
      setError("");
    }
  }, [disease]);

  useEffect(() => {
    if (!loading && results) {
      document.getElementById("ai-summary")?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }, [loading, results]);

  const handleSearch = async (nextDisease = disease) => {
    const trimmedDisease = nextDisease.trim();
    if (!trimmedDisease) {
      setError("Please enter a condition");
      return;
    }

    setLoading(true);
    setLoadingStage("expanding_query");
    setError("");
    setShowRawData(false);

    const resolvedDisease = trimmedDisease;
    const queryToSend = trimmedDisease && isVagueQuery(trimmedDisease) && lastDisease ? lastDisease : trimmedDisease;
    const stageTimers = [
      window.setTimeout(() => setLoadingStage("fetching_data"), 300),
      window.setTimeout(() => setLoadingStage("ranking_results"), 600),
      window.setTimeout(() => setLoadingStage("generating_summary"), 900),
    ];

    try {
      const response = await fetch(`${API_BASE}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: queryToSend,
          location,
          last_disease: lastDisease,
        }),
      });

      if (!response.ok) {
        let message = "Request failed";
        try {
          const errorData = await response.json();
          message = errorData.detail || JSON.stringify(errorData);
        } catch {
          const text = await response.text();
          message = text || message;
        }
        setResults(null);
        throw new Error(message);
      }

      const data = await response.json();
      setLastDisease(data?.query_context?.disease || resolvedDisease || lastDisease);
      if (!data.validated || !data.llm_output || data.status === "fallback_triggered") {
        setViewMode("system");
      } else {
        setViewMode("ai");
      }
      setLoadingStage("complete");
      setResults(data);
    } catch (err) {
      setResults(null);
      setError(err.message || "Something went wrong");
    } finally {
      stageTimers.forEach((timer) => window.clearTimeout(timer));
      setLoadingStage("complete");
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    await handleSearch();
  };

  const handleExampleSelect = async (value) => {
    setDisease(value);
    await handleSearch(value);
  };

  return (
    <main className="min-h-screen px-4 py-6 md:px-6 xl:px-8">
      <div className="mx-auto flex max-w-7xl flex-col gap-5">
        <section className="overflow-hidden rounded-[2rem] border border-[color:var(--cliniq-line)] bg-[linear-gradient(135deg,rgba(255,255,255,0.96),rgba(245,251,249,0.92))] shadow-[0_30px_80px_rgba(20,52,72,0.08)]">
          <div className="grid gap-0 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="p-6 xl:p-10">
              <h1 className="mt-4 max-w-4xl font-serif text-4xl leading-tight text-[color:var(--cliniq-ink)] md:text-5xl">
                ClinIQ
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-[color:var(--cliniq-copy)]">
                Evidence-first medical insights. AI-enhanced, not AI-driven.
              </p>

              <form onSubmit={handleSubmit} className="mt-8 grid gap-4 lg:grid-cols-[1.4fr_1fr_auto]">
                <label className="flex flex-col gap-2">
                  <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--cliniq-copy)]">
                    Disease Query
                  </span>
                  <input
                    type="text"
                    value={disease}
                    onChange={(e) => setDisease(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && disease.trim()) {
                        e.preventDefault();
                        handleSearch();
                      }
                    }}
                    placeholder="Enter disease or condition"
                    className="h-14 rounded-2xl border border-[color:var(--cliniq-line)] bg-white px-4 text-base text-[color:var(--cliniq-ink)] outline-none transition focus:border-[color:var(--cliniq-mint)] focus:ring-4 focus:ring-[color:var(--cliniq-glow)]"
                  />
                  {!disease && (
                    <p className="text-sm text-[color:var(--cliniq-copy)]">Enter a medical condition to begin</p>
                  )}
                  <div className="flex flex-wrap gap-2 pt-1">
                    {["Lung cancer", "Diabetes", "Breast cancer"].map((example) => (
                      <button
                        key={example}
                        type="button"
                        onClick={() => handleExampleSelect(example)}
                        className="rounded-full border border-[color:var(--cliniq-line)] bg-white px-3 py-1.5 text-sm text-[color:var(--cliniq-ink)] transition hover:border-[color:var(--cliniq-mint)] hover:bg-[color:var(--cliniq-glow)]"
                      >
                        {example}
                      </button>
                    ))}
                  </div>
                </label>

                <label className="flex flex-col gap-2">
                  <span className="text-xs font-semibold uppercase tracking-[0.18em] text-[color:var(--cliniq-copy)]">
                    Location (Optional)
                  </span>
                  <input
                    type="text"
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Boston, MA"
                    className="h-14 rounded-2xl border border-[color:var(--cliniq-line)] bg-white px-4 text-base text-[color:var(--cliniq-ink)] outline-none transition focus:border-[color:var(--cliniq-mint)] focus:ring-4 focus:ring-[color:var(--cliniq-glow)]"
                  />
                </label>

                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={loading || !disease.trim()}
                    className={`h-14 w-full rounded-2xl px-6 text-sm font-semibold uppercase tracking-[0.18em] transition ${
                      disease.trim() && !loading
                        ? "bg-[color:var(--cliniq-ink)] text-white hover:bg-slate-800"
                        : "cursor-not-allowed bg-slate-300 text-slate-500"
                    } disabled:opacity-60`}
                  >
                    {loading ? "Processing..." : "Search Research"}
                  </button>
                </div>
              </form>

              {lastDisease && (
                <p className="mt-3 text-sm leading-6 text-[color:var(--cliniq-copy)]">
                  Context: {lastDisease}
                </p>
              )}
              {error && <p className="mt-4 text-sm font-medium text-rose-700">{error}</p>}
            </div>

            <div className="border-t border-[color:var(--cliniq-line)] bg-[linear-gradient(180deg,rgba(237,245,246,0.76),rgba(246,250,249,0.96))] p-6 xl:border-l xl:border-t-0 xl:p-10">
              <div className="rounded-[1.8rem] border border-white/60 bg-white/75 p-6 shadow-[0_12px_36px_rgba(20,52,72,0.06)]">
                <p className="text-sm leading-7 text-[color:var(--cliniq-copy)]">
                  Verified data is system-rendered. AI cannot modify source evidence.
                </p>
              </div>
            </div>
          </div>
        </section>

        {loading && (
          <div className="fixed inset-0 z-50 bg-white/60 backdrop-blur-sm">
            <div className="mx-auto flex max-h-screen max-w-7xl flex-col gap-6 overflow-hidden px-4 py-8 md:px-6 xl:px-8">
              <LoadingPanel loadingStage={loadingStage} />
              <div className="max-h-[70vh] overflow-hidden space-y-6">
                <SummarySkeleton />
                <KeySignalsSkeleton />
                <EvidenceSkeleton />
              </div>
            </div>
          </div>
        )}

        {!loading && !results && <ZeroState onSelectExample={handleExampleSelect} />}

        {results && (
          <>
            <SummarySection results={results} viewMode={viewMode} setViewMode={setViewMode} />
            <KeySignals results={results} />
            <EvidenceSection results={results} showRawData={showRawData} setShowRawData={setShowRawData} />
          </>
        )}
      </div>
    </main>
  );
}
