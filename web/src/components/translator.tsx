"use client";

import { useEffect, useReducer, useRef, useState, type DragEvent } from "react";
import { engine, type Report, type TranslateFailure, type TranslateResult } from "@/engine";
import { formatBytes } from "./format";
import { ReportView } from "./report-view";
import { loadSamples } from "./samples";

const ACCEPT = ".pdf,.txt,.json,.png,.jpg,.jpeg,.tif,.tiff";

type Phase =
  | { kind: "editing" }
  | { kind: "translating" }
  | { kind: "done"; report: Report; markdown: string; fileName: string; producedOn: Date }
  | { kind: "failed"; error: TranslateFailure };

type State = { files: File[]; phase: Phase };

type Action =
  | { type: "add"; files: File[] }
  | { type: "remove"; index: number }
  | { type: "start" }
  | { type: "finish"; result: TranslateResult; fileName: string; producedOn: Date }
  | { type: "fail"; error: TranslateFailure };

const sameFile = (a: File, b: File) => a.name === b.name && a.size === b.size && a.lastModified === b.lastModified;

function reduce(state: State, action: Action): State {
  switch (action.type) {
    case "add": {
      const fresh = action.files.filter((file) => !state.files.some((kept) => sameFile(kept, file)));
      return { files: [...state.files, ...fresh], phase: { kind: "editing" } };
    }
    case "remove":
      return { files: state.files.filter((_, i) => i !== action.index), phase: { kind: "editing" } };
    case "start":
      return { ...state, phase: { kind: "translating" } };
    case "finish": {
      const { result, fileName, producedOn } = action;
      const phase: Phase = result.ok
        ? { kind: "done", report: result.report, markdown: result.markdown, fileName, producedOn }
        : { kind: "failed", error: result };
      return { ...state, phase };
    }
    case "fail":
      return { ...state, phase: { kind: "failed", error: action.error } };
    default: {
      const unhandled: never = action;
      return unhandled;
    }
  }
}

export function Translator() {
  const [{ files, phase }, dispatch] = useReducer(reduce, { files: [], phase: { kind: "editing" } });
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const busy = phase.kind === "translating";

  useEffect(() => {
    const keepPage = (event: globalThis.DragEvent) => event.preventDefault();
    window.addEventListener("dragover", keepPage);
    window.addEventListener("drop", keepPage);
    return () => {
      window.removeEventListener("dragover", keepPage);
      window.removeEventListener("drop", keepPage);
    };
  }, []);

  async function translate(chosen: File[]) {
    dispatch({ type: "start" });
    const result = await engine.translate(chosen);
    dispatch({ type: "finish", result, fileName: chosen[0]?.name ?? "", producedOn: new Date() });
  }

  async function trySamples() {
    let samples: File[];
    try {
      samples = await loadSamples();
    } catch {
      const message = "The sample documents couldn't be loaded. Restart the app and try again.";
      dispatch({ type: "fail", error: { ok: false, message } });
      return;
    }
    dispatch({ type: "add", files: samples });
    await translate(samples);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!busy) dispatch({ type: "add", files: Array.from(event.dataTransfer.files) });
  }

  function onDragLeave(event: DragEvent<HTMLDivElement>) {
    const into = event.relatedTarget;
    if (!(into instanceof Node && event.currentTarget.contains(into))) setDragging(false);
  }

  const failedFile = phase.kind === "failed" ? phase.error.file : undefined;

  return (
    <>
      <section className="upload" aria-labelledby="upload-heading">
        <div className="upload-main">
          <h2 id="upload-heading" className="visually-hidden">
            Your documents
          </h2>
          <div
            className="dropzone"
            data-dragging={dragging || undefined}
            onDragOver={(event) => {
              event.preventDefault();
              if (!busy) setDragging(true);
            }}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
          >
            <p className="dropzone-title">Drop your documents here</p>
            <p className="dropzone-or">
              or{" "}
              <button type="button" className="button secondary" disabled={busy} onClick={() => input.current?.click()}>
                Choose files
              </button>
            </p>
            <p className="hint">
              DD-214s, DD-215s and your VMET, as PDF, text or JSON. Scans work when OCR is installed. Up to 10 files, 10
              MB each.
            </p>
            <input
              ref={input}
              type="file"
              multiple
              accept={ACCEPT}
              hidden
              onChange={(event) => {
                dispatch({ type: "add", files: Array.from(event.currentTarget.files ?? []) });
                event.currentTarget.value = "";
              }}
            />
          </div>

          {files.length > 0 ? (
            <ul className="files" aria-label="Chosen documents">
              {files.map((file, index) => (
                <li key={`${file.name}-${file.size}-${file.lastModified}`} data-error={file.name === failedFile || undefined}>
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">{formatBytes(file.size)}</span>
                  <button
                    type="button"
                    className="button quiet"
                    disabled={busy}
                    aria-label={`Remove ${file.name}`}
                    onClick={() => dispatch({ type: "remove", index })}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          <div className="actions">
            {files.length > 0 ? (
              <button type="button" className="button primary" disabled={busy} onClick={() => translate(files)}>
                {busy ? "Translating…" : `Translate ${files.length === 1 ? "1 document" : `${files.length} documents`}`}
              </button>
            ) : (
              <>
                <button type="button" className="button secondary" onClick={trySamples}>
                  Try with sample documents
                </button>
                <p className="hint">Made-up records for a fictional Army staff sergeant.</p>
              </>
            )}
            <p className="status" role="status">
              {busy ? `Reading ${files.length === 1 ? "1 document" : `${files.length} documents`}…` : ""}
            </p>
          </div>

          {phase.kind === "failed" ? <Failure error={phase.error} /> : null}
        </div>

        <aside className="privacy" aria-labelledby="privacy-heading">
          <h2 id="privacy-heading">Stays on this computer</h2>
          <p>
            Your documents are read by the translator running on this computer. Nothing is uploaded to the internet,
            and nothing is stored. Each file is deleted as soon as its report is ready.
          </p>
        </aside>
      </section>

      {phase.kind === "done" ? (
        <ReportView
          report={phase.report}
          markdown={phase.markdown}
          fileName={phase.fileName}
          producedOn={phase.producedOn}
        />
      ) : null}
    </>
  );
}

function Failure({ error }: { error: TranslateFailure }) {
  return (
    <div className="failure" role="alert">
      <p className="failure-title">
        {error.file ? `Couldn't read ${error.file}` : "The translation didn't finish"}
      </p>
      <p>{error.message}</p>
      {error.file ? <p>Remove this file and translate again.</p> : null}
    </div>
  );
}
