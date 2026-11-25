import { z } from "zod";

export const DOC_TYPES = ["dd214", "dd215", "ngb22", "jst", "vmet", "eval", "resume", "facts-json"] as const;

export const KEYWORD_CATEGORIES = [
  "job_titles",
  "skills",
  "knowledge",
  "technologies",
  "work_activities",
  "leadership",
  "training",
  "recognition",
  "experience",
] as const;

const DocType = z.enum(DOC_TYPES);
const IsoDate = z.iso.date();
const Count = z.number().int().nonnegative();

const Source = z.object({
  doc_type: DocType,
  doc_id: z.string(),
  locator: z.string(),
  issued: IsoDate.nullable(),
  confidence: z.number(),
});

const resolved = <T extends z.ZodType>(value: T) => z.object({ value, sources: z.array(Source) });

const ServiceContext = z.object({
  branch: z.string().nullable(),
  component: z.string().nullable(),
  pay_grade: z.string().nullable(),
  rank: z.string().nullable(),
  as_of: IsoDate.nullable(),
  source: Source,
});

const OccupationHeld = z.object({
  code: z.string().nullable(),
  title: z.string(),
  months: Count.nullable(),
  start: IsoDate.nullable(),
  end: IsoDate.nullable(),
  source: Source,
});

const CivilianEquivalent = z.object({
  onet: z.string(),
  title: z.string(),
  for_code: z.string().nullable(),
  source: Source,
});

const TrainingCompleted = z.object({
  title: z.string(),
  weeks: z.number().nullable(),
  completed: IsoDate.nullable(),
  ace_id: z.string().nullable(),
  description: z.string().nullable(),
  source: Source,
});

const Award = z.object({ name: z.string(), count: Count, source: Source });

const Duration = z.object({ years: Count, months: Count, days: Count });

const Accomplishment = z.object({
  text: z.string(),
  metrics: z.array(z.object({ kind: z.enum(["people", "budget", "equipment"]), value: z.number() })),
  source: Source,
});

const SkillClaim = z.object({
  term: z.string(),
  kind: z.enum(["skill", "technology", "certification", "clearance"]),
  source: Source,
});

const Conflict = z.object({
  field: z.string(),
  values: z.array(z.string()),
  kept: z.string(),
  sources: z.array(Source),
});

const Profile = z.object({
  context: ServiceContext.nullable(),
  occupations: z.array(resolved(OccupationHeld)),
  civilian_equivalents: z.array(resolved(CivilianEquivalent)),
  training: z.array(resolved(TrainingCompleted)),
  awards: z.array(resolved(Award)),
  service_time: z.object({
    net_active: Duration.optional(),
    prior_active: Duration.optional(),
    foreign: Duration.optional(),
    sea: Duration.optional(),
  }),
  accomplishments: z.array(resolved(Accomplishment)),
  skill_claims: z.array(resolved(SkillClaim)),
  conflicts: z.array(Conflict),
});

const Document = z.object({
  doc_type: DocType,
  doc_id: z.string(),
  layout: z.string(),
  notes: z.array(z.string()),
});

const SpecialtyMatch = z.object({
  specialty: OccupationHeld,
  svc: z.string().nullable(),
  code: z.string().nullable(),
  title: z.string().nullable(),
  method: z.string().nullable(),
  occupations: z.array(
    z.object({
      onet: z.string(),
      title: z.string(),
      weight: z.number(),
      sources: z.array(z.string()),
    }),
  ),
});

const KeywordCategory = z.enum(KEYWORD_CATEGORIES);

const Keyword = z.object({
  term: z.string(),
  category: KeywordCategory,
  score: z.number(),
  sources: z.array(z.string()),
});

/** `KeywordReport.to_dict()` from dd214kw, plus the `attribution` that `to_json` adds. */
export const Report = z.object({
  profile: Profile,
  documents: z.array(Document),
  matches: z.array(SpecialtyMatch),
  keywords: z.record(KeywordCategory, z.array(Keyword)),
  ats_keywords: z.array(z.string()),
  warnings: z.array(z.string()),
  attribution: z.string(),
});

export type Report = z.infer<typeof Report>;
export type DocType = z.infer<typeof DocType>;
export type KeywordCategory = z.infer<typeof KeywordCategory>;
export type SpecialtyMatch = z.infer<typeof SpecialtyMatch>;
export type Duration = z.infer<typeof Duration>;
