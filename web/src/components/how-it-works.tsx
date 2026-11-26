"use client";

import { motion, useReducedMotion, useScroll, useTransform, type MotionValue } from "motion/react";
import { useRef, type ReactNode } from "react";
import { arrive, cellWindow, fan } from "./motion";
import { useAnimated } from "./use-animated";

/**
 * What the translator does, in three steps, on the way down the page.
 *
 * Each step moves differently, because three sections that behave identically are one section
 * shown three times: the documents fan out of a stack, the form lights block by block as the
 * step passes up the window, and the keywords arrive one after another above the string they
 * make. Nothing pins, nothing takes the scroll over, and the whole thing is plain text and
 * drawn shapes, so scrolling straight past it costs nothing.
 *
 * Every value shown here is invented. No part of this reads anyone's documents.
 */

const DOCUMENTS = [
  { label: "DD-214", note: "Separation" },
  { label: "DD-215", note: "Correction" },
  { label: "VMET", note: "Training" },
];

/** The boxes of a service record, as the translator works through them. Shapes, not a real form. */
const BLOCKS = 24;
const NAMED: Record<number, string> = { 4: "Grade", 11: "Specialty", 18: "Service" };

const KEYWORDS = [
  "Security Guards",
  "Supply Chain",
  "Team Leadership",
  "Logistics",
  "Inventory Control",
  "Training Delivery",
];

export function HowItWorks() {
  const reduced = useReducedMotion() ?? false;
  const moving = useAnimated() && !reduced;
  const animated = useAnimated();

  return (
    <section className="story" aria-labelledby="story-heading">
      <h2 id="story-heading">How it works</h2>
      <p className="story-lede">
        Three steps, and all three happen on this computer. The pictures below use made-up values,
        not yours.
      </p>

      <Step
        n={1}
        title="Add your documents"
        body="Your DD-214s, any DD-215 corrections and your VMET, as PDF, text or JSON. Scans work when OCR is installed."
      >
        <Stack animated={animated} reduced={reduced} />
      </Step>

      <Step
        n={2}
        title="Read block by block"
        body="The translator reads each block of each form in turn: branch, pay grade, dates, and every specialty with the time served in it. Where two documents disagree, the later one wins and the report says so."
      >
        <Form moving={moving} />
      </Step>

      <Step
        n={3}
        title="Get your keywords"
        body="Each specialty is matched to civilian occupations, and the whole record becomes job titles, skills and technologies, plus one keyword string ready to paste into an application."
      >
        <Keywords animated={animated} reduced={reduced} />
      </Step>
    </section>
  );
}

function Step({ n, title, body, children }: { n: number; title: string; body: string; children: ReactNode }) {
  return (
    <div className="story-step">
      <div className="story-words">
        <p className="story-number" aria-hidden="true">
          {n}
        </p>
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
      <div className="story-art" aria-hidden="true">
        {children}
      </div>
    </div>
  );
}

/** Step one: a stack of documents, fanning open as it arrives. */
function Stack({ animated, reduced }: { animated: boolean; reduced: boolean }) {
  return (
    <div className="doc-stack">
      {DOCUMENTS.map((document, i) => (
        <motion.div key={document.label} className="doc" {...fan(animated, reduced, i)}>
          <span className="doc-label">{document.label}</span>
          <span className="doc-note">{document.note}</span>
          <span className="doc-rules" />
        </motion.div>
      ))}
    </div>
  );
}

/** Step two: the blocks of a form, lighting one after another as the step passes up the window. */
function Form({ moving }: { moving: boolean }) {
  const step = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: step, offset: ["start end", "end start"] });

  return (
    <div className="form-grid" ref={step}>
      {Array.from({ length: BLOCKS }, (_, i) => (
        <Cell key={i} index={i} pass={scrollYProgress} moving={moving} label={NAMED[i]} />
      ))}
    </div>
  );
}

function Cell({
  index,
  pass,
  moving,
  label,
}: {
  index: number;
  pass: MotionValue<number>;
  moving: boolean;
  label?: string;
}) {
  const lit = useTransform(pass, cellWindow(index, BLOCKS), [0, 1]);

  return (
    <div className="form-cell" data-named={label ? "" : undefined}>
      <motion.span className="form-fill" style={moving ? { opacity: lit } : undefined} />
      {label ? <span className="form-label">{label}</span> : null}
    </div>
  );
}

/** Step three: the keywords arriving one after another, above the string they make. */
function Keywords({ animated, reduced }: { animated: boolean; reduced: boolean }) {
  return (
    <div className="keyword-build">
      <ul className="chips">
        {KEYWORDS.map((keyword, i) => (
          <motion.li key={keyword} {...arrive(animated, reduced, i * 0.06)}>
            {keyword}
          </motion.li>
        ))}
      </ul>
      <p className="keyword-line">{KEYWORDS.join(", ")}</p>
      <motion.p className="keyword-caption" {...arrive(animated, reduced, KEYWORDS.length * 0.06)}>
        Ready to paste into an application.
      </motion.p>
    </div>
  );
}
