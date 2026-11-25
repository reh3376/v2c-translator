# Military → Civilian Translator: Data Sources

_Compiled 2026-11-24. Status: ✅ downloaded and inspected · 🔑 free but needs a key or account · 🔒 restricted/CAC · ⚠️ caveat._

The pipeline has six layers. Each one needs different data:

1. **Ingest**: parse DD-214, JST and resumes into structured service history
2. **Decode**: military code → what the job actually is
3. **Crosswalk**: military code → civilian occupation (SOC / O*NET-SOC)
4. **Enrich**: civilian occupation → tasks, skills, software, wages, outlook
5. **Credentials & education**: certifications, licenses, college credit
6. **Match & evaluate**: live jobs, labeled pairs to score the model

---

## 1. Ingest: document structure

| Source | What it gives you | Access |
|---|---|---|
| **DoDI 1336.01** (DD Form 214/5 series) — esd.whs.mil/Portals/54/Documents/DD/issuances/dodi/133601p.pdf | Official block-by-block preparation rules: what goes in each field, formats, SPD codes | ✅ public PDF |
| **DOL UIPL 14-24, Attachment I** — dol.gov/.../UIPL 14-24/Attachment I | 2000 vs. 2022 DD-214 block comparison table (renumbering map) | ✅ public PDF |
| Service DD-214 prep guides (AF PSDG, USCG PSCINST 1900.1, Army DD-214 info sheet) | Real-world fill conventions, free-text blocks, continuation sheets | ✅ public PDFs |
| **ACE sample JSTs** — acenet.edu (Army-JST-Sample.pdf etc.) | JST layout: personal data, courses with ACE IDs, occupations, credit recs | ✅ public PDFs |
| Blank DD-214 PDF | Template for synthetic rendering | ⚠️ esd.whs.mil says to request it from USD(P&R); not posted publicly |

**⚠️ Two DD-214 layouts are in circulation; the parser must detect which one it has.** The 2022 "Certificate of Uniformed Service" revision (required by Feb 2025) renumbered most blocks and replaced SSN with the DoD ID:

| Field | 2000 form | 2022 form |
|---|---|---|
| SSN → DoD ID number | 3 | 3 |
| Grade/rank, pay grade | 4a/4b | 5a/5b |
| **Primary specialty** | **11** | **12** |
| Record of service (dates, net service, foreign/sea) | 12a–h | 13a–j (adds total active service, initial entry training) |
| Decorations/medals | 13 | 14 |
| **Military education** | **14** | **15** |
| Remarks | 18 | 20 |
| Type of separation / character of service | 23 / 24 | 25 / 26 |
| Separation authority / code / reentry code | 25 / 26 / 27 | 27 / 28 / 29 |
| Narrative reason | 28 | 30 |

Blocks 23–30 (old) carry characterization and separation codes and appear only on Member-4 copies. Treat them as sensitive and don't feed them to the occupation model.

**No public corpus of real DD-214s or JSTs exists, because they are PII.** Plan on generating synthetic documents from the crosswalk below plus the block specs, and collect consented real samples later for validation.

## 2. Decode: military occupation definitions

| Source | Coverage | Access |
|---|---|---|
| **DMDC MOC crosswalk** (`milx0724.csv`, Aug 2024) | All services; titles for every code (see §3) | ✅ |
| **Navy NEOCS Vol I (ratings) and Vol II (NECs)** — mynavyhr.navy.mil/References/NEOCS-Manual | Full rating/NEC descriptions; **Vol II has an Excel export of every NEC** | ✅ public |
| **DAFECD / DAFOCD** (Air & Space Force enlisted/officer classification directories) — afpc.af.mil/Classification | AFSC duties, qualifications, skill levels; updated Apr/Oct | ✅ public PDF |
| **USMC MOS Manual** (annual NAVMC 1200.1_; older MCO 1200.17E) — marines.mil | MOS duties, prerequisites, **and each MOS's related SOC codes** | ✅ public PDF |
| **Army DA PAM 611-21** (Smartbook) | Authoritative MOS specs, ASIs, SQIs | 🔒 milSuite/CAC. Public fallbacks: Army COOL MOS pages, Careers in the Military, Army Career Tracker career maps (often posted by state Guard sites) |
| Coast Guard ratings (Enlisted Qualifications Manual) | Rating descriptions | ✅ public, lower priority |
| **ASVAB CEP "Careers in the Military"** (careersinthemilitary.com) | Plain-language job descriptions across services | ✅ web (scrape-respectfully) |

## 3. Crosswalk: military → civilian (the core)

All of the following are **downloaded and verified** with `fetch_public_data.py`. License: CC BY 4.0, attribution required.

| File | Rows | What it is |
|---|---|---|
| `military_crosswalk.zip` → `milx0724.csv` | **40,077** (23,350 active; 13,573 distinct active codes) | DMDC master: MOC → DoD occupational code → up to 4 SOC + 4 O*NET-SOC links, with start/end dates and change history |
| `cool_supplemental_data.xlsx` | 25,652 links / 2,165 code-service titles | Extra MOC → O*NET links from the five service COOL sites |
| `citm_supplemental_data.xlsx` | 39,324 links / 7,785 code-service titles | Extra links from ASVAB CEP Careers in the Military |
| `army_ksa_crosswalk.xlsx` | 812 | Army MOS → O*NET via a knowledge/skills/abilities analysis |
| `vow222.xls` | 982 | **VOW Act enhanced crosswalk**: 68 MOCs → 962 civilian occupations, each with **minimum pay grade** and an **attainability rating** after one term of service. Best ready-made human-labeled eval set. |

Live equivalent: **O*NET Web Services v2** `/veterans/military` (🔑 free key; v2 launched Nov 2025 and needs a new key separate from v1).

**⚠️ Coverage gap that shapes the design.** Only 55% of active codes have an O*NET link. Primary occupations are well covered: Army MOS 89%, Air Force AFSC 98%, Space Force 98%, Marines 98%, Navy 99%, Coast Guard 100%. The unlinked 45% are almost all *modifier* codes:

- Army ASI (J) and SQI (Q)
- Air Force SEI (Y) and Space Force SEI (U)
- Navy AQD (V) and officer designators (P)
- Prefixes (X, L)

These codes should **roll up to the parent MOS/AFSC/rating for the occupation match**. Use their titles as **skill and qualification signals**. For example, a Jumpmaster ASI or a Nuclear NEC should boost specific skills, not pick the occupation. SVC code `D` (DoD conversion codes) and `G` (OPM GS/WG series) are reference rows, and `G` is useful for mapping to federal jobs.

SVC legend (from Read Me): A Army MOS/AOC · C USCG · D DoD occ code · F AFSC · G OPM series · H Space Force · J Army ASI · K NSPS · L SF prefix · M USMC MOS · N Navy rating/NEC/NOBC · O SF officer activity · P Navy officer designator · Q Army SQI · S Navy subspecialty · U SF SEI · V Navy AQD · X AF prefix · Y AF SEI · Z AF officer activity. MPC: E enlisted, O officer, W warrant.

## 4. Enrich: civilian occupation profiles

| Source | Contents | Access |
|---|---|---|
| **O*NET 31.0 database** (`db_31_0_text.zip`) | 1,016 occupations; 18,838 task statements; 54,269 job titles; 31,821 software-skill links; Essential/Transferable Skills, Knowledge, Work Activities (GWA→IWA→DWA), Job Zones, Related Occupations | ✅ CC BY 4.0 |
| O*NET civilian crosswalks: ESCO, CIP, RAPIDS (apprenticeship), OOH | Bridge to EU skills, degree programs, apprenticeships, BLS outlook | ✅ downloaded |
| **BLS OEWS May 2025** | Wages (10/25/50/75/90th pct) for ~830 SOC occupations by nation, state, and metro | ✅ public. ⚠️ bls.gov blocks scripted downloads from this workspace; download XLSX manually or use CareerOneStop LMI API |
| BLS Employment Projections 2024–34 | Growth and openings per SOC | ✅ public (same caveat) |
| **Lightcast Open Skills** | 33k+ skills, 75k+ titles; skill extraction from text | 🔑 free tier (limited extractions/month); full free access for nonprofits/public-good |

## 5. Credentials & education

| Source | Contents | Access |
|---|---|---|
| **CareerOneStop Certification Finder** | Certifications by occupation with certifying org, requirements, ANSI accreditation, in-demand flag | ✅ bulk download (`XLS_Certification_Finder_Data_07112025ACC.xlsx`) + 🔑 API |
| CareerOneStop License Finder, Skills Gap API (occupation A vs B: wage/skill/cert gaps) | State licenses; gap analysis | 🔑 free API |
| **DoD COOL** (cool.osd.mil: Army, Navy, AF, USMC, USCG) | Credentials mapped to each MOC, funding eligibility | ⚠️ web only, no bulk export found. The MOC→O*NET part is already in `cool_supplemental_data.xlsx`. Pair it with CareerOneStop certs via O*NET code, or scrape COOL politely. Not reachable from this workspace. |
| **ACE Military Guide** (~25k course + 3.6k occupation exhibits since 1954) | Course descriptions, learning outcomes, credit recommendations. Key for decoding JST lines. | 🔑 **ACE API portal** (apiportal.acenet.edu: CourseExhibit and OccupationExhibit endpoints). Request access at apisupport@acenet.edu |
| DoD SkillBridge, USMAP | Internship partners and apprenticeship trades by MOC | ✅ web |

## 6. Match & evaluate

| Source | Use | Access |
|---|---|---|
| **USAJOBS API** (Search + HistoricJoa) | Live and historical federal postings by OPM series; veterans hiring paths. Joins to the crosswalk's `G` rows. | 🔑 free key |
| CareerOneStop Jobs API / National Labor Exchange | Private-sector postings by O*NET/keyword | 🔑 free key |
| `vow222.xls`, `army_ksa_crosswalk.xlsx` | Gold-standard eval pairs (military code → civilian occupation, with pay-grade and attainability labels) | ✅ |
| Public resume datasets (Kaggle/HF LiveCareer ~2.5k, JobHop/JobHop v2 ~360–440k ESCO-coded career paths) | Resume-parser training; JobHop gives occupation-transition priors via the ESCO→O*NET crosswalk | ✅ (check each license) |
| Mendeley "data for ai military job" (2026) | Synthetic military records paired with civilian postings | ⚠️ Indian armed forces; useful only as a format reference |

---

## Recommended build order

1. **Load** `milx0724.csv` + the COOL/CitM supplements + O*NET 31.0 into one store (DuckDB/SQLite). Key everything on O*NET-SOC.
2. **Add** the NEC Excel, DAFECD/DAFOCD and USMC MOS Manual text as the "decode" layer, giving each code a description to embed.
3. **Build** a synthetic DD-214/JST generator from the block specs plus real code/course distributions. This gives you parser training data without PII.
4. **Sign up for keys:** O*NET Web Services v2, CareerOneStop, Lightcast Open Skills, USAJOBS, ACE API (allow lead time for ACE).
5. **Evaluate** against VOW222 (top-k occupation recall, pay-grade-aware).

## Gaps to track
- No authoritative public Army MOS text (DA PAM 611-21 is behind CAC).
- No bulk DoD COOL export.
- DMDC crosswalk last refreshed Aug 2024. Codes added after that will be missing; check service manuals for newer codes.
- DD-214s and JSTs contain PII (DoD ID/SSN, characterization of service). Ingest needs redaction, and characterization/reentry codes should be kept out of matching to avoid discriminatory outcomes.
