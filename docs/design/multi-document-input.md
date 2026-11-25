# Design: multi-document input

Status: **accepted: Shape B** (evidence ledger → resolved profile) · 2026-11-25 · scope: `dd214kw` → v2c-translator core · steps 1-2: merged (PR #1) · step 3: merged (PR #2) · step 4: merged (PR #6/#7)

## Problem

Today one DD-214 produces one `ServiceRecord`, and everything downstream reads that
record's DD-214-shaped fields. The project needs to accept a service member's *set* of
documents and translate their whole career:

| Document | What it adds that a DD-214 doesn't |
|---|---|
| DD-214 / NGB-22 / DD-215 | (baseline) final grade, primary specialties + time, awards, course titles, service time, per separation period |
| JST | every course with ACE ID, description and credit recommendation; every occupation held, with dates and level |
| VMET (DD 2586) | occupations held, with **civilian equivalent titles and O*NET codes already attached**; training with ACE credit |
| Evaluations (NCOER/OER, EPB/OPB, FITREP/EVAL) | duty titles, scope (people, budget, equipment), accomplishment bullets |
| Resume | civilian jobs, certifications, technologies, self-described skills |

Documents overlap and disagree. The same specialty appears on a DD-214, the JST and the
VMET, and the same course on the DD-214 and the JST. A DD-215 corrects a DD-214. Two
DD-214s cover two separate periods.

## Trace: what the change touches

`ServiceRecord` (models.py) is the only connecting point. `parse.py` is its only writer;
the readers are:

| Reader | Fields read |
|---|---|
| `translate.translate` | `specialties`, `branch`, `pay_grade`, `warnings` |
| `rules.rule_keywords` | every field: grade, education, decorations, all four durations, branch, specialties |
| `render._summary` | `branch`, `component`, `grade`, `pay_grade`, `net_active`, `form_version` |
| `cli._cmd_translate` | `branch` (override) |

`index.py` (crosswalk + O*NET) and the occupation/keyword scoring inside `translate.py`
are document-agnostic and don't change.

## Shape A: widen the record

Every extractor returns a partial `ServiceRecord`, and a `merge(records)` function folds
them together. New documents add optional fields to the record.

```python
@dataclass
class ServiceRecord:                       # grows with each document type
    ...existing DD-214 fields...
    jst_courses: list[JstCourse]           # JST
    occupations_held: list[HeldOcc]        # JST, VMET
    civilian_equivalents: list[str]        # VMET
    accomplishments: list[str]             # evals, resume
    resume_skills: list[str]               # resume

def merge(records: list[ServiceRecord]) -> ServiceRecord: ...   # one policy per field
def translate(index, rec: ServiceRecord) -> KeywordReport: ...  # unchanged signature
```

- **For:** smallest diff, and the callers keep their signature.
- **Against:**
  - Each new document type edits the central type, `merge`, `rules` and `translate`
    (shotgun surgery).
  - The same fact lives in parallel fields (`education` vs `jst_courses`, `specialties`
    vs `occupations_held`), so every reader must know which documents exist and union
    them itself. That's two ways to do one task, and callers need to know the most.
  - Provenance is lost at merge, so "why is this keyword here?" can't name the
    document.

## Shape B: evidence ledger → resolved profile (accepted)

Extractors emit **facts**: a small closed set of document-agnostic kinds, each carrying
its source. One resolver owns deduplication and conflict policy and produces a `Profile`.
Translation and rules read fact kinds and never document types.

```
file ──detect──▶ Extractor(doc_type) ──▶ [Fact…] ─┐
file ──detect──▶ Extractor(doc_type) ──▶ [Fact…] ─┼─▶ resolve() ──▶ Profile ──▶ translate() ──▶ KeywordReport
json facts (OCR/LLM pipeline) ───────────────────┘                    (index)        rules()
```

### Types

```python
# evidence.py: the only place facts and provenance are defined
DocType = Literal["dd214", "dd215", "ngb22", "jst", "vmet", "eval", "resume", "facts-json"]

@dataclass(frozen=True, slots=True)
class Source:
    doc_type: DocType
    doc_id: str            # first 12 hex of sha256(file bytes); never a name or ID number
    locator: str           # "block 12", "JST: Military Experience", "EPB bullet 3"
    issued: date | None    # document date; drives recency in conflicts
    confidence: float      # 1.0 official structured field; <1.0 OCR / model-extracted

@dataclass(frozen=True, slots=True)
class ServiceContext:      branch: str; component: str | None; pay_grade: str | None
                           rank: str | None; as_of: date | None; source: Source
@dataclass(frozen=True, slots=True)
class OccupationHeld:      code: str | None; title: str; months: int | None
                           start: date | None; end: date | None; source: Source
@dataclass(frozen=True, slots=True)
class CivilianEquivalent:  onet: str; title: str                          # VMET
                           for_code: str | None; source: Source           # the code it is listed under
@dataclass(frozen=True, slots=True)
class TrainingCompleted:   title: str; weeks: float | None; completed: date | None
                           ace_id: str | None; description: str | None; source: Source
@dataclass(frozen=True, slots=True)
class Award:               name: str; count: int; source: Source
@dataclass(frozen=True, slots=True)
class ServiceTime:         kind: Literal["net_active", "prior_active", "foreign", "sea"]
                           duration: Duration; period_end: date | None; source: Source
@dataclass(frozen=True, slots=True)
class Accomplishment:      text: str; metrics: tuple[Metric, ...]; source: Source  # scrubbed
@dataclass(frozen=True, slots=True)
class SkillClaim:          term: str; kind: Literal["skill", "technology", "certification",
                           "clearance"]; source: Source

Fact = (ServiceContext | OccupationHeld | CivilianEquivalent | TrainingCompleted | Award
        | ServiceTime | Accomplishment | SkillClaim)
```

PII is excluded by construction: no fact kind has a field for a name, ID number, date of
birth, address, characterization or separation code. The two free-text kinds
(`Accomplishment.text`, `SkillClaim.term`) go through `scrub()` in their constructor
helper. That makes `evidence.py` the single owner of the privacy guarantee, instead of
trusting every extractor.

```python
# extractors/ : one module per document type, nothing else knows document layouts
class Extractor(Protocol):
    doc_type: DocType
    def sniff(self, text: str) -> float: ...                  # 0..1: is this my document?
    def extract(self, text: str, source: SourceFactory) -> list[Fact]: ...

EXTRACTORS: tuple[Extractor, ...] = (Dd214(), Vmet(), Jst(), Evaluation(), Resume(), FactsJson())
def detect(text: str) -> Extractor: ...                       # highest sniff, error if < 0.5
```

```python
# resolve.py: the only owner of dedup and conflict policy
@dataclass(frozen=True, slots=True)
class Resolved(Generic[T]):
    value: T
    sources: tuple[Source, ...]     # every document that supports it, for provenance and corroboration

@dataclass(frozen=True, slots=True)
class Profile:
    context: ServiceContext                           # most recent as_of, then issued
    occupations: tuple[Resolved[OccupationHeld], ...]
    civilian_equivalents: tuple[Resolved[CivilianEquivalent], ...]
    training: tuple[Resolved[TrainingCompleted], ...]
    awards: tuple[Resolved[Award], ...]
    service_time: Mapping[str, Duration]              # summed across distinct periods
    accomplishments: tuple[Resolved[Accomplishment], ...]
    skill_claims: tuple[Resolved[SkillClaim], ...]
    conflicts: tuple[Conflict, ...]                   # surfaced as warnings, never silently dropped

def resolve(facts: Iterable[Fact]) -> Profile: ...
```

### Resolution policy

Document-level deduplication lives in `resolve.py`:

| Fact | Identity key | On duplicate | On conflict |
|---|---|---|---|
| `ServiceContext` | — | keep latest by `as_of` / `issued` | report a branch disagreement as a `Conflict` |
| `OccupationHeld` | normalized code, else normalized title | union sources; months = max | — |
| `CivilianEquivalent` | (normalized `for_code`, `onet`) | union sources | — |
| `TrainingCompleted` | `ace_id`, else (normalized title, year) | union; prefer the fact with `ace_id`/`description` | — |
| `Award` | normalized name | count = max | — |
| `ServiceTime` | (kind, `period_end`) | DD-215 > DD-214 for the same period | sum across different periods |
| `Accomplishment`, `SkillClaim` | normalized text | union sources | — |

Cross-document occupation identity lives in `translate.py`. Whether "11B30 INFANTRYMAN"
on a DD-214 and "11B" on a VMET are one job is a crosswalk question, and the crosswalk
lives in `translate`. After matching, `translate` merges the `SpecialtyMatch`es that
resolve to the same (svc, code):

- It keeps the first specialty in profile order, with months = max across the group.
- It collects the VMET links of every specialty in the group.
- The order of the matches does not otherwise change.

One document can also list one code more than once. The VMET lists each stint in a job
as its own entry, so its extractor sums the months of entries for one code.

### Downstream changes

```python
def translate(index: Index, profile: Profile, top: int = 12) -> KeywordReport
def rule_keywords(profile: Profile) -> list[Keyword]
```

- **Occupation weighting** gains one source: `CivilianEquivalent` facts enter the
  existing link merge as `"vmet"` with base weight 0.9 (official, but per-person rather
  than per-code). A specialty takes the links whose `for_code` is its matched crosswalk
  code or its own code. Fan-out decay, the 55-xxxx analog swap and title relevance apply
  to them as to any other supplemental source.
- **Corroboration** comes for free: an occupation held on three documents carries three
  sources, which can lift its specialty weight.
- **`Keyword.sources`** names the document: "DD-214 block 14 · JST" instead of a bare
  course name.
- **`render`** summarises the `Profile` plus a list of the documents read.
- **`cli translate FILE...`** accepts several files; `--type` overrides detection.

### Why B

- **One owner per piece of state:**
  - Extractors own layout knowledge.
  - `evidence.py` owns fact shape and PII scrubbing.
  - `resolve.py` owns merging.
  - `translate`/`rules` own meaning.
- **One way to do each task:** every input, including the OCR/LLM path, becomes facts
  through the same door (`FactsJson` is just another extractor). There's no parallel
  `jst_courses`/`education` pair to keep in step.
- **Callers know least:** translation sees eight fact kinds and never learns that a
  JST, VMET or resume exists. Adding a document type adds one extractor module and
  usually no fact kind.
- **Cost vs A:** two new modules and a migration of four readers. The single connecting
  point keeps that migration small (see trace).

## Migration: verifiable steps

Each step ships on its own, with `docs/examples/*.md` regenerated and diffed.

1. **Facts in, behaviour unchanged.** Add `evidence.py`, `resolve.py`, and a `Dd214`
   extractor that wraps today's `parse_text`, converting its `ServiceRecord` into facts.
   Add a golden test: the DD-214 fixtures produce byte-identical Markdown before and
   after.
2. **Move the readers.** Switch `translate`, `rules`, `render` and `cli` to `Profile`,
   then delete `ServiceRecord` from the public path. Golden test still identical.
3. **Several files at once.** `translate FILE...`, `detect()`, and DD-215 correction
   handling. Test: a DD-214 plus DD-215 pair, and two DD-214s for separate periods.
4. **VMET extractor.** Structured, highest value: it brings its own O*NET links. Test
   that a VMET-only occupation shows up; a VMET plus DD-214 duplicate collapses to one
   match.
5. **JST extractor.** Courses with ACE IDs and descriptions, and occupations with dates.
   Training-to-skill extraction from ACE descriptions comes later, behind the ACE API
   key.
6. **Evaluation extractor.** Accomplishment bullets, plus `Metric` parsing ("supervised
   12", "$4.2M", "38 vehicles") that feeds leadership scope instead of pay-grade
   guesses.
7. **Resume extractor.** Civilian roles and skill claims, probably through the
   `facts-json` door from an LLM extraction step, with `confidence < 1`.

## Open questions

1. **Samples.** The VMET reader's labels come from publicly posted samples of the 2010
   edition. The reader still needs validation on a real, redacted VMET. The JST layout
   needs real (redacted) samples before step 5; ACE publishes sample JSTs.
2. **Rating scores.** Should evaluation numeric ratings ever be used? This design
   excludes them, the same way it excludes characterization.
3. **Model-extracted facts.** How much weight should a resume or LLM fact carry against
   an official document? This design uses `Source.confidence` as a multiplier; the
   value needs the evaluation harness to tune.
4. **Package name.** `dd214kw` stops describing the package after step 3. Renaming to
   `v2c` would fit the "migrate callers, then delete" step 2.
5. **DD-215 text.** Step 3 reads a DD-215 only as pre-extracted JSON. A text reader waits
   on a real (redacted) sample, because DoDI 1336.01 leaves the wording of a correction to
   each service.
