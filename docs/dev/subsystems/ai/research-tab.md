# Research tab pipeline

The matter Research tab is the research surface (the AI-chat research
mode is retired; see
[Research chat (retired)](../../../decisions/research-chat-retired.md)).
Its architecture: one user-approved search, then a deterministic pipeline
in which the model makes only bounded judgments, with two human
checkpoints (the query variants, then the cases to read). It was rebuilt
on 2026-08-17 to close the quality gap with the retired chat; the failure
being chased was a recent slip opinion (no syllabus, no reporter citation,
near-zero cite count) that answered a fee-shifting question yet was
invisible to the old snippet-and-excerpt pipeline.

## Where the code is

| Module | Holds |
|---|---|
| `apps/case/research/tasks.py` | The pipeline stages, budgets, the stale-run reaper, treatment checks, the saved-case summary |
| `apps/case/research/views.py` | The tab, the two approval screens, result rows, bookmarking, briefs, citation validation |
| `apps/case/research/models.py` | `ResearchQuery`, `ResearchResult`, `CitationVerification`, `CaseBrief` |
| `apps/case/research/briefing.py` | The full-opinion abstract prompt, `parse_brief()`, `PROCEDURAL_VEHICLE_RULES` |
| `apps/case/research/query_syntax.py` | `COURTLISTENER_SYNTAX_RULES`, `QUERY_DESIGN_RULES` |
| `apps/case/research/courtlistener.py`, `jurisdictions.py` | Opinion search and forward citations; the state court lists |
| `apps/case/courtlistener.py`, `courtlistener_throttle.py` | Cluster, opinion and citation fetches; the process-wide request throttle |
| `templates/case/research/` | `refinement.html`, `case-selection.html`, `result-row.html`, `results.html`, the history and review tabs |

## Data model

A `ResearchQuery` belongs to a matter (`CASCADE`) and carries the question,
`state` and `include_federal`, the approved `query_variants` (JSON), a
`status` from `STATUS_CHOICES` and the `final_summary`. Each
`ResearchResult` (`CASCADE` to its query) is one cluster: the search
fields, `source` (search, date slice, citing case, cited authority),
`hit_count` and `matched_variants`, `triage_score`, `recommended`, the
`relevance` verdict with its `brief`, `eval_reason` and
`key_authorities`, and the treatment fields. `CitationVerification` rows
hang off a result for the review tab. A `CaseBrief` belongs to the matter
and points at its result with `SET_NULL`, so a brief outlives the run it
came from. Runs are per user: the views scope queries and briefs to
`created_by`.

## Flow

1. **Refine** (`_refine_and_pause()`, Flash): first a library-mining pass
   (`_mine_library()`) picks up to `LIBRARY_NOTE_PICK_MAX` (2) library
   notes whose text feeds the proposal (statutes, terms of art, key cases:
   the retired chat's library-pass advantage). Then the refiner proposes
   three to five labeled query variants (Colloquial, Statutory, Doctrinal,
   Broad), eager about code sections: one variant centres on the
   governing statute's bare number. The prompt carries
   `COURTLISTENER_SYNTAX_RULES`, `QUERY_DESIGN_RULES` and
   `PROCEDURAL_VEHICLE_RULES`. The run pauses at `status="refined"`; the
   approval screen (`refinement.html`, `research_confirm()`) shows each
   variant as a checkbox and an editable text row, so the user prunes,
   edits or composes the set.
2. **Search** (`_process_query()`): every selected variant runs twice, a
   relevance page (`VARIANT_SCORE_LIMIT`, 15) plus a thin newest-first
   slice (`VARIANT_DATE_LIMIT`, 8) that rescues recent opinions the score
   disfavours. All results merge, deduped by cluster, each recording
   `hit_count` and `matched_variants`: a case surfaced by several
   differently-worded queries is a strong free relevance signal. Searches
   are the cheap lever (one credit each); the expensive stages stay
   hard-capped.
3. **Triage** (Flash, snippet only, `_triage_by_snippet()`): each
   candidate gets a 0 to 10 promise score plus a reason from the keyword
   snippet (a missing snippet scores a neutral 5; slip opinions have
   none). Below `TRIAGE_REJECT_BELOW` (3) the row becomes
   `relevance="rejected"` with the reason. Nothing is deleted.
4. **The selection gate** (`status="selecting"`, `case-selection.html`,
   `research_select_cases()`): the second checkpoint. Reads are the
   expensive stage, so the user picks which cases get pulled. The card
   shows every candidate with its pre-read signals (citation, court, date,
   cite count, "Matched N queries", promise score, triage reason); the
   pipeline's own pick (`recommended`: top `BRIEF_MAX` by hit count, then
   promise, then search order, with a `RECENT_GUARANTEE` swap of the three
   newest, via `_rank_candidates()`) arrives prechecked, and ruled-out rows
   are selectable too so a wrong triage call can be overridden. The view
   caps a selection at `BRIEF_MAX` (15) at a time. Unselected candidates
   become "Not selected" and stay briefable from the per-card button.
5. **Brief** (`_run_brief_phase()` then `_brief_result()`, Flash): each
   selected case is briefed from its entire cluster, every sub-opinion
   concatenated under `BRIEF_OPINION_CHAR_CAP` (250k), with the structured
   abstract prompt in `briefing.py` (case, posture, vehicle, verbatim
   holding, relevance, cautions, scope, plus a parseable relevance verdict
   and key authorities). `parse_brief()` maps the verdict to
   high/medium/low and stores the brief, rationale and authorities on the
   row.
6. **Enrich** (`_run_enrichment()`, chained as a second qcluster task):
   forward `cites:()` searches from the `CITING_SEED_MAX` (2) strongest
   high cases (how slip opinions get found when they cite the line) and
   backward `lookup_citation` of the authorities the high briefs rest on
   (`CHASE_AUTHORITY_MAX`, 4). `cites:()` takes opinion ids, never cluster
   ids; `cites:(cluster_id)` silently returns nothing (verified live on
   2026-08-17). New clusters join as rows with provenance badges ("Citing
   case", "Cited authority") and get the same full-opinion briefs.
7. **Treatment**: `check_negative_treatment()` on every high row.
8. **Answer** (`_generate_final_answer()`, `ANSWER_MODEL`, Gemini Pro):
   direct answer first, naming the exact vehicle, then per-case
   discussions under 200 words each; slip opinions and zero-cite cases are
   flagged as new and not yet settled law; unchecked or negative treatment
   is noted.

## Budgets (`tasks.py` constants)

About 50 CourtListener requests per typical run, spaced by the 0.25 s
throttle in `courtlistener_throttle.py`: two searches per variant plus up
to `BRIEF_MAX` briefs (cluster and opinions), two citing searches, up to
`CITING_BRIEF_MAX` (4) chased briefs, up to four lookups and the
treatment walks. About 55 Flash calls and one Pro call.

## Background work

The pipeline runs on qcluster (`_queue()`, group `research`), not on
daemon threads, so a gunicorn reload no longer kills runs mid-flight.
Each phase is its own task so it stays inside the 600 s `Q_CLUSTER`
timeout: refine, search, briefs, then enrichment chained from the brief
phase. Restart qcluster after deploying a change to this module, or the
old code keeps running the new rows.

Every status write goes through `_update_query()`, which bumps
`updated_at` (a queryset `.update()` skips `auto_now`) because the reaper
reads it as the run's heartbeat: `reap_stale_queries()`, called from the
tab views, flags a run stranded for `RESEARCH_STALE_MINUTES` (30) in an
active status as an error. `refined` and `selecting` are deliberately
absent from `ACTIVE_QUERY_STATUSES`: both wait on the user, indefinitely.

Bookmarking (`research_save_to_caselaws()`) builds the `CaseLaw` row from
`fetch_cluster()` on the result's cluster id, so citation-less slip
opinions save; the cluster's `court` field is an API URL, so the display
name comes from the result and the court id from the URL tail. The same
rule is mirrored by the agent's `save-caselaw` block.

Jurisdictions (`jurisdictions.py`): a state lists its supreme and
appellate courts and home circuit; **Federal** adds the state's district
courts, that circuit and the Supreme Court. District lists are filled in
as users need them (one state so far); verify any new id against the
CourtListener courts endpoint, because a typo silently narrows every
search that uses the filter.

## Access

The Research tab, saved cases and the cluster viewer are gated on the
Research permission by `PermissionMiddleware.PERMISSION_PATTERNS`
(`apps/accounts/middleware.py`), and the matter must be the user's. Result,
brief and verification views additionally scope to `query__created_by`
or `created_by`, so one user's run is not another's. See the
[permissions reference](../../../reference/permissions.md).

## Things that bite

- **`cites:()` wants opinion ids.** A cluster id in that filter returns an
  empty page with no error; `_chase_citing_cases()` takes the ids from the
  cluster's `sub_opinions`.
- **A required colloquial phrase can hide the controlling case.** The
  benchmark opinion (below) never uses the word "compel"; it names the
  statute fourteen times. `QUERY_DESIGN_RULES` therefore has the statute
  number ride as an OR-alternative inside the phrase group. Keep that rule
  when editing the refiner prompt.
- **The waiting statuses must never be reaped.** Adding a new pause means
  leaving its status out of `ACTIVE_QUERY_STATUSES`, or the reaper errors
  it after thirty minutes.
- **The throttle is per process.** `courtlistener_throttle.py` spaces
  requests within one process; two qcluster workers, the vetting thread
  pool and the agent's research tools each keep their own clock, so the
  account's per-minute limit is the real ceiling.
- **Briefs are capped per selection, not per run.** The selection view
  refuses more than `BRIEF_MAX` ticks because one task briefs them under
  one time limit; the rest are briefed one at a time from their cards
  (2026-10-02 change).

## Benchmark

The acceptance question: "If I file a motion to compel and the other side
supplements their responses to moot the motion, can I still seek attorney
fees?" (Georgia + Federal). A passing run surfaces Birg v. Emory
University (a June 2026 slip opinion on O.C.G.A. 9-11-37, CourtListener
cluster 10875036) with a high brief quoting the holding, flags its slip
status, and answers on the right vehicle.

Lesson from the first benchmark run (2026-08-17): the refined query
required the phrase "motion to compel", and the opinion never uses the
word "compel" at all (it says "9-11-37" fourteen times). A required
colloquial phrase group makes such a case unfindable by both the
relevance page and the date slice; the statute number must ride as an
OR-alternative inside that group. `"9-11-37" AND "attorney fees" AND
moot*` puts the case in the top five by relevance. The forward chase could
not have rescued that run either: the opinion cites none of the
compel-phrase cluster's cases.

## Related

- [Research](../../../guide/research.md) in the user guide shows the tab.
- [AI providers and research](../../../admin/integrations/ai.md) for the
  CourtListener key and tier.
- [Agentic chat](agent-chat.md) reuses the search client and jurisdictions
  as tools; [AI chat and context](context.md) covers the shared models.

Tests: `apps/case/tests/test_research_pipeline.py`, `test_treatment.py`,
`test_research_run_state.py`, `test_research_selection_cap.py`,
`test_research_brief_access.py`, `test_research_permission.py`.
