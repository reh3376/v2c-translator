"use client";

import { motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useReducer, useRef, useState, type DragEvent } from "react";
import { HOSTED_ONLY, type Copy } from "@/content/copy";
import { engine, type Report, type TranslateFailure, type TranslateResult } from "@/engine";
import { BranchBand } from "./branch-band";
import { formatBytes } from "./format";
import { pressable, sweep } from "./motion";
import { ReportView } from "./report-view";
import { loadSamples } from "./samples";
import { TurnstileGate } from "./turnstile-gate";

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

/**
 * `copy` says what this deploy can honestly promise about the reader's documents, and
 * `siteKey` is the public half of the Turnstile pair when there is a bot check to pass.
 * Both are read from the environment per request by `app/page.tsx` and handed down, so
 * one build serves either mode.
 */
export function Translator({ copy, siteKey }: { copy: Copy; siteKey: string | null }) {
  const [{ files, phase }, dispatch] = useReducer(reduce, { files: [], phase: { kind: "editing" } });
  const [dragging, setDragging] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [round, setRound] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const reduced = useReducedMotion() ?? false;
  const busy = phase.kind === "translating";
  const detected = phase.kind === "done" ? phase.report.profile.context?.branch : null;
  const onToken = useCallback((fresh: string | null) => setToken(fresh), []);

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
    // Said here rather than by the server, so a reader who hasn't ticked the box is told
    // so before their documents go over the wire instead of after.
    if (siteKey && !token) {
      dispatch({ type: "fail", error: { ok: false, message: HOSTED_ONLY.turnstileMissing } });
      return;
    }
    dispatch({ type: "start" });
    const result = await engine.translate(chosen, token);
    // A Turnstile token is good for one translation, so the widget has to be asked again.
    setToken(null);
    setRound((spent) => spent + 1);
    dispatch({ type: "finish", result, fileName: chosen[0]?.name ?? "", producedOn: new Date() });
  }

  async function trySamples() {
    let samples: File[];
    try {
      samples = await loadSamples();
    } catch {
      const message = "The sample documents couldn't be loaded. Reload the page and try again.";
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
      <BranchBand detected={detected} />

      <section className="upload" aria-labelledby="upload-heading">
        <div className="upload-main">
          <h2 id="upload-heading" className="visually-hidden">
            Your documents
          </h2>
          <motion.div
            className="dropzone"
            data-dragging={dragging || undefined}
            animate={{ scale: dragging ? 1.006 : 1 }}
            transition={{ duration: 0.16, ease: [0.22, 0.61, 0.36, 1] }}
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
              <motion.button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => input.current?.click()}
                {...pressable(reduced)}
              >
                Choose files
              </motion.button>
            </p>
            <p className="hint">{copy.dropzoneHint}</p>
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
          </motion.div>

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

          {siteKey ? <TurnstileGate siteKey={siteKey} onToken={onToken} round={round} /> : null}

          <div className="actions">
            {files.length > 0 ? (
              <motion.button
                type="button"
                className="button primary"
                disabled={busy}
                onClick={() => translate(files)}
                {...pressable(reduced)}
              >
                {busy ? "Translating…" : `Translate ${files.length === 1 ? "1 document" : `${files.length} documents`}`}
              </motion.button>
            ) : (
              <>
                <motion.button type="button" className="button secondary" onClick={trySamples} {...pressable(reduced)}>
                  Try with sample documents
                </motion.button>
                <p className="hint">Made-up records for a fictional Army staff sergeant.</p>
              </>
            )}
            <p className="status" role="status">
              {busy ? `Reading ${files.length === 1 ? "1 document" : `${files.length} documents`}…` : ""}
            </p>
          </div>

          <Progress busy={busy} />

          {phase.kind === "failed" ? <Failure error={phase.error} /> : null}
        </div>

        <aside className="privacy" aria-labelledby="privacy-heading">
          <h2 id="privacy-heading">{copy.privacy.heading}</h2>
          {copy.privacy.paragraphs.map((paragraph) => (
            <p key={paragraph}>{paragraph}</p>
          ))}
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

/**
 * The wait while the translator reads the documents. The track is always in the layout, so
 * starting and finishing moves nothing on the page. The wait is announced by the status line
 * beside the button, which is why this is hidden from screen readers.
 */
function Progress({ busy }: { busy: boolean }) {
  const reduced = useReducedMotion() ?? false;
  const slide = sweep(reduced);

  return (
    <div className="progress" data-busy={busy || undefined} aria-hidden="true">
      {busy ? slide ? <motion.span className="progress-bar" {...slide} /> : <span className="progress-bar still" /> : null}
    </div>
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
