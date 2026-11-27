/**
 * Every sentence that has to say something different depending on where the app runs.
 *
 * The local app reads documents on the reader's own computer, and the page has always
 * said so. The hosted app reads them on a server in Germany. "Stays on this computer"
 * would be a lie there, and a privacy promise that is a lie is the one bug in this
 * repository that could actually hurt someone. So both wordings live here, keyed by
 * mode, and `copy.test.ts` holds each to what its mode can honestly claim: the hosted
 * copy may not say the documents stay put, and the local copy may not talk about
 * uploading.
 *
 * `HOSTED_ONLY` holds the sentences that have no local counterpart, because nothing on
 * one person's own computer turns them away: the robot check, the queue and the limit.
 * They are here rather than beside the code that sends them because the robot check's
 * wording is shown in two places, by the page before it uploads anything and by the
 * server if a token is missing anyway, and one wording means one place.
 */

import type { Mode } from "@/server/config";

export interface PrivacyNote {
  readonly heading: string;
  readonly paragraphs: readonly string[];
}

export interface Copy {
  /** `<meta name="description">`. */
  readonly metaDescription: string;
  /** The panel beside the drop zone. */
  readonly privacy: PrivacyNote;
  /** Under "Resources for veterans", where every link leaves the page. */
  readonly resourcesLede: string;
  /** Under "How it works". */
  readonly storyLede: string;
  /** Under the drop zone, on what to add and how much. */
  readonly dropzoneHint: string;
  /** Step one of "How it works". */
  readonly addDocumentsBody: string;
  /** What the server says when the CLI fails for a reason it cannot explain. */
  readonly genericFailure: string;
}

const LOCAL: Copy = {
  metaDescription:
    "Turn DD-214s, DD-215s and a VMET into civilian job titles, skills and keywords. Runs on this computer.",
  privacy: {
    heading: "Stays on this computer",
    paragraphs: [
      "Your documents are read by the translator running on this computer. Nothing is uploaded to the internet, and nothing is stored. Each file is deleted as soon as its report is ready.",
    ],
  },
  resourcesLede:
    "These sites are run by other people. Opening one leaves this page; your documents stay on this computer.",
  storyLede: "Three steps, and all three happen on this computer. The pictures below use made-up values, not yours.",
  dropzoneHint:
    "DD-214s, DD-215s and your VMET, as PDF, text or JSON. Scans work when OCR is installed. Up to 10 files, 10 MB each.",
  addDocumentsBody:
    "Your DD-214s, any DD-215 corrections and your VMET, as PDF, text or JSON. Scans work when OCR is installed.",
  genericFailure: "The translator stopped before it finished. The terminal running this app shows the details.",
};

const HOSTED: Copy = {
  metaDescription:
    "Turn DD-214s, DD-215s and a VMET into civilian job titles, skills and keywords. Nothing is stored.",
  privacy: {
    heading: "What happens to your documents",
    paragraphs: [
      "Your documents are sent over HTTPS to this server, read in memory, and deleted as soon as your report is ready. Nothing is stored, logged or shared.",
      "Don't upload a document you aren't comfortable sending.",
    ],
  },
  resourcesLede:
    "These sites are run by other people. Opening one leaves this page, and nothing about your documents goes with you.",
  storyLede:
    "Three steps, and all three happen on this server while you wait. The pictures below use made-up values, not yours.",
  dropzoneHint:
    "DD-214s, DD-215s and your VMET, as PDF, text or JSON. Scans are read with OCR. Up to 10 files, 10 MB each.",
  addDocumentsBody:
    "Your DD-214s, any DD-215 corrections and your VMET, as PDF, text or JSON. Scans are read with OCR.",
  genericFailure: "The translator stopped before it finished. Try again, or try fewer files at once.",
};

export const COPY: Readonly<Record<Mode, Copy>> = { local: LOCAL, hosted: HOSTED };

/**
 * What only a hosted deploy can say to a reader. None of it names a Cloudflare error
 * code, a queue depth or an address: a reader can act on "try again in a few minutes"
 * and on nothing else here.
 */
export const HOSTED_ONLY = {
  /** The widget is on the page and nobody has ticked it. */
  turnstileMissing: "Tick the box that says you're not a robot, then translate again.",
  /** Cloudflare looked at the token and said no. */
  turnstileRejected: "That robot check didn't go through. Reload the page and try again.",
  /** Cloudflare could not be reached, so the check failed closed. */
  turnstileUnreachable: "The robot check couldn't be reached just now. Try again in a moment.",
  /** The label above the widget. */
  turnstileLabel: "Before you translate, confirm you're not a robot.",
  /** The queue is full. */
  busy: "The translator is busy. Try again in a minute.",
  /** This visitor has had their share for now. */
  tooMany: "You've translated several times just now. Try again in a few minutes.",
} as const;

/**
 * What the hint under the drop zone adds where a deploy caps the pages in one document,
 * which hosted mode does by default.
 *
 * It is a function and not one of the sentences above because the limit is read from the
 * environment per request, as `V2C_MAX_PAGES`. `app/page.tsx` hands the result down.
 */
export function pagesHint(maxPages: number): string {
  return `Up to ${maxPages} pages per document.`;
}

/** Every sentence of one mode's copy, for a test that wants to search the lot. */
export function sentences(copy: Copy): readonly string[] {
  return [
    copy.metaDescription,
    copy.privacy.heading,
    ...copy.privacy.paragraphs,
    copy.resourcesLede,
    copy.storyLede,
    copy.dropzoneHint,
    copy.addDocumentsBody,
    copy.genericFailure,
  ];
}
