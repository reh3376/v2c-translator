import type { DocType, Duration, KeywordCategory, Report } from "@/engine";

export const DOC_LABELS: Record<DocType, string> = {
  dd214: "DD-214",
  dd215: "DD-215",
  ngb22: "NGB-22",
  jst: "JST",
  vmet: "VMET",
  eval: "Evaluation",
  resume: "Resume",
  "facts-json": "Facts JSON",
};

export const CATEGORY_LABELS: Record<KeywordCategory, string> = {
  job_titles: "Civilian job titles",
  skills: "Transferable skills",
  knowledge: "Knowledge areas",
  technologies: "Technologies and tools",
  work_activities: "Work activities",
  leadership: "Leadership and management",
  training: "Training and certifications",
  recognition: "Recognition",
  experience: "Experience",
};

const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;

export function formatMonths(total: number): string {
  const years = Math.floor(total / 12);
  const months = total % 12;
  if (years === 0) return plural(months, "month");
  return months === 0 ? plural(years, "year") : `${plural(years, "year")}, ${plural(months, "month")}`;
}

export const formatDuration = (d: Duration) => formatMonths(d.years * 12 + d.months);

export function documentLabel(doc: Report["documents"][number]): string {
  const layout = doc.layout === "json" ? "from JSON" : `${doc.layout} layout`;
  return `${DOC_LABELS[doc.doc_type]}, ${layout}`;
}

const pad = (n: number) => String(n).padStart(2, "0");

/** `<first file's stem>-civilian-keywords-<local YYYY-MM-DD>.<ext>`, so reports for different people get different names. */
export function downloadName(firstFileName: string, ext: "md" | "json", date: Date): string {
  const trim = (s: string) => s.replace(/^[ -]+|[ -]+$/g, "");
  const cleaned = trim(
    firstFileName
      .normalize("NFC")
      .replace(/\.[^.]*$/, "")
      .replace(/[^\p{L}\p{M}\p{N} _-]/gu, "-")
      .replace(/-+/g, "-"),
  );
  const stem = trim(Array.from(cleaned).slice(0, 60).join("")) || "documents";
  const day = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  return `${stem}-civilian-keywords-${day}.${ext}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
