"use client";

import { useEffect, useRef, useState } from "react";
import { KEYWORD_CATEGORIES, type Report, type SpecialtyMatch } from "@/engine";
import { CATEGORY_LABELS, documentLabel, formatDuration, formatMonths } from "./format";

function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function ReportView({ report, markdown }: { report: Report; markdown: string }) {
  const heading = useRef<HTMLHeadingElement>(null);

  useEffect(() => heading.current?.focus(), [report]);

  return (
    <section className="results" aria-labelledby="results-heading">
      <div className="results-head">
        <h2 id="results-heading" ref={heading} tabIndex={-1}>
          Civilian keywords
        </h2>
        <div className="downloads">
          <button
            type="button"
            className="button secondary"
            onClick={() => download("civilian-keywords.md", markdown, "text/markdown")}
          >
            Download Markdown
          </button>
          <button
            type="button"
            className="button secondary"
            onClick={() => download("civilian-keywords.json", `${JSON.stringify(report, null, 2)}\n`, "application/json")}
          >
            Download JSON
          </button>
        </div>
      </div>

      <Summary report={report} />

      <h3>Military specialties</h3>
      <div className="table-wrap">
        <table className="specialties">
          <thead>
            <tr>
              <th scope="col">Entry on your documents</th>
              <th scope="col">Matched code</th>
              <th scope="col">Civilian occupations</th>
            </tr>
          </thead>
          <tbody>
            {report.matches.map((match, i) => (
              <SpecialtyRow key={`${match.specialty.title}-${i}`} match={match} />
            ))}
          </tbody>
        </table>
      </div>

      <h3>Keywords by category</h3>
      <div className="keywords">
        {KEYWORD_CATEGORIES.map((category) =>
          report.keywords[category].length > 0 ? (
            <section key={category} className="keyword-group" aria-labelledby={`keywords-${category}`}>
              <h4 id={`keywords-${category}`}>{CATEGORY_LABELS[category]}</h4>
              <ul className="chips">
                {report.keywords[category].map((keyword, i) => (
                  <li key={`${keyword.term}-${i}`}>{keyword.term}</li>
                ))}
              </ul>
            </section>
          ) : null,
        )}
      </div>

      <AtsString terms={report.ats_keywords} />

      {report.warnings.length > 0 ? (
        <section className="notes" aria-labelledby="notes-heading">
          <h3 id="notes-heading">Notes from the translator</h3>
          <ul>
            {report.warnings.map((warning, i) => (
              <li key={`${warning}-${i}`}>{warning}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <p className="caveat">
        These keywords suggest where the experience fits in civilian work. They don&rsquo;t confirm qualifications,
        so review them before they go on a resume or an application.
      </p>
      <p className="attribution">{report.attribution}</p>
    </section>
  );
}

function Summary({ report }: { report: Report }) {
  const context = report.profile.context;
  const net = report.profile.service_time.net_active;
  return (
    <dl className="summary">
      <div>
        <dt>Branch</dt>
        <dd>
          {context?.branch ?? "Not stated"}
          {context?.component ? ` (${context.component})` : ""}
        </dd>
      </div>
      <div>
        <dt>Pay grade</dt>
        <dd>
          {context?.pay_grade ?? "Not stated"}
          {context?.rank ? ` (${context.rank})` : ""}
        </dd>
      </div>
      <div>
        <dt>Net active service</dt>
        <dd>{net ? formatDuration(net) : "Not stated"}</dd>
      </div>
      <div>
        <dt>Documents read</dt>
        <dd>
          <ul>
            {report.documents.map((doc, i) => (
              <li key={`${doc.doc_id}-${i}`}>{documentLabel(doc)}</li>
            ))}
          </ul>
        </dd>
      </div>
    </dl>
  );
}

function SpecialtyRow({ match }: { match: SpecialtyMatch }) {
  const { specialty, occupations } = match;
  return (
    <tr>
      <td>
        <span className="record">{specialty.title}</span>
        {specialty.months !== null ? <span className="time">{formatMonths(specialty.months)}</span> : null}
      </td>
      <td>
        {match.code ? (
          <>
            <strong className="code">{match.code}</strong> {match.title}
          </>
        ) : (
          <span className="muted">Not matched</span>
        )}
      </td>
      <td>
        {occupations.length > 0 ? (
          <ul className="occupations">
            {occupations.slice(0, 5).map((occupation) => (
              <li key={occupation.onet}>
                {occupation.title} <span className="onet">{occupation.onet}</span>
              </li>
            ))}
          </ul>
        ) : (
          <span className="muted">None found</span>
        )}
      </td>
    </tr>
  );
}

function AtsString({ terms }: { terms: string[] }) {
  const [copy, setCopy] = useState<"idle" | "copied" | "failed">("idle");
  const text = terms.join(", ");

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopy("copied");
      setTimeout(() => setCopy("idle"), 2500);
    } catch {
      setCopy("failed");
    }
  }

  return (
    <section className="ats" aria-labelledby="ats-heading">
      <h3 id="ats-heading">Keyword string for job applications</h3>
      <p className="hint">Paste it into the skills or keywords field of an application, or a resume&rsquo;s keyword section.</p>
      <div className="ats-box">
        <p>{text}</p>
        <button type="button" className="button secondary" onClick={onCopy}>
          {copy === "copied" ? "Copied" : "Copy"}
        </button>
      </div>
      <p className="status" role="status">
        {copy === "copied" ? "Keyword string copied." : copy === "failed" ? "Copy didn't work here. Select the text and copy it." : ""}
      </p>
    </section>
  );
}
