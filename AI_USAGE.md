# AI Usage

The take-home brief expects AI assistance and asks what was delegated, what was checked, and where AI suggestions were overridden. Codex was used as a development partner. This note describes the repository's recorded workflow and examples in [docs/ai/](docs/ai/), not a claim that AI output was accepted without review. The project owner remains responsible for product decisions, code comprehension, and final verification.

## How AI was used

AI assistance was used as a development partner across three substantial workstreams:

1. **Core scheduling logic** — turn the brief and business rules into a testable specification, design and implementation plan; draft and run tests before implementing the backend; implement domain, persistence, service, and refresh workflows; then trace requirements against the resulting code and test evidence.
2. **Roster-first UI** — specify manager workflows and service boundaries, plan UI and manual-edit previews, write interaction and service tests, then implement the NiceGUI workflow and refine dense roster and assignment dialogs.
3. **Scheduling algorithm v2** — translate the algorithm-upgrade brief into explicit objectives and constraints, design deterministic construction/refinement and diagnostics, create reference/example-based tests, implement the algorithm, and perform a requirement-focused summary review.

The assistant was also used for repository exploration, test failure diagnosis, change summaries, and identifying follow-up risks. It did not replace decisions about the business rules or the owner's responsibility to inspect the diff and run the checks.

## Human review and decisions

The workflow is designed so the owner reviews staged outputs before work proceeds. AI drafts are proposals; requirements, trade-offs, and acceptance criteria must be understood and approved by the owner.

- **Resolve conflicting requirements explicitly:** the core scheduling specification records the owner-approved behavior that a confirmed demand re-import or post-import threshold change replaces the current roster and snapshots the previous state. This differs from a retain-roster rule in the source BRD; the conflict is documented rather than hidden in implementation.
- **Keep the draft honest:** the generator is documented as a deterministic, bounded heuristic, not an optimizer with a global-optimality guarantee. Diagnostics distinguish optimizer costs from the established coverage metrics, and the unavoidable-shortage figure is described as a conservative lower bound.
- **Treat tests as evidence, not proof by themselves:** Stage 6 review of algorithm v2 found that the full suite passed while a refinement-cap test did not prove construction had completed. A focused reproduction showed a feasible coverage addition was skipped. The implementation and tests were then corrected so construction reaches negative-cost ADD closure before the refinement move cap applies.
- **Keep open work visible:** the UI workstream has Stage 1–4 artifacts and implementation evidence in the change log, but no `06-summary.md` in its task folder. The change log records later UI changes and checks; that is not represented here as a completed per-task traceability summary.

## Repository workflow: skills and stage templates

The repository's `.agents/` materials constrain how assistance is requested and reviewed:

| Resource | Purpose in the workflow |
|---|---|
| [Codebase explorer skill](.agents/skills/01-codebase-explorer/SKILL.md) | Read the project and relevant tests first; map existing responsibilities and identify what is already implemented before proposing changes. |
| [Planning skill](.agents/skills/02-planning/SKILL.md) | Turn the request into scope, alternatives, measurable acceptance criteria, a sequence, and explicit risks before implementation. |
| [Python implementation skill](.agents/skills/03-python-implementation/SKILL.md) | Keep Python changes typed, idiomatic, scoped, and consistent with existing conventions; use explicit errors and avoid unrelated refactors. |
| [Testing and debugging skill](.agents/skills/04-testing-debugging/SKILL.md) | Derive happy-path, boundary, failure, state, and regression cases; reproduce issues and test root causes instead of symptoms. |
| [Code review skill](.agents/skills/05-code-review/SKILL.md) | Compare a diff with its requirements, check error paths and edge cases, and state findings and remaining test gaps. |

These are paired with six staged prompt templates:

1. [01-spec prompt and specification guide](.agents/templates/01-spec-template/01-spec-prompt.md) asks for functional and non-functional requirements, edge cases, acceptance criteria, assumptions, and open questions. Its companion [brief-file prompt](.agents/templates/01-spec-template/01-spec-docs.md) directs the assistant to read supplied source documents and not invent requirements when they are unclear.
2. [02-design prompt](.agents/templates/02-design-template/02-design-prompt.md) requires an end-to-end design, data and interface boundaries, failure behavior, security/reliability considerations, alternatives, and risks—without source edits.
3. [03-plan prompt](.agents/templates/03-plan-template/03-plan-prompt.md) maps requirements to small implementation steps and verification, names the files and risks, and flags conflicts or dependencies.
4. [04-tests prompt](.agents/templates/04-test-template/04-test-prompt.md) requires a traceable test matrix and a red run that fails for the missing feature rather than a collection or setup error. Tests are reviewed before implementation.
5. [05-implementation prompt](.agents/templates/05-impl-template/05-impl-prompt.md) limits each request to one approved plan step, asks the assistant to stop on conflicts or scope expansion, and requires test/lint/static-check results.
6. [06-summary prompt](.agents/templates/06-summary-template/06-summary-prompt.md) prohibits source/test edits during final review and asks for requirement traceability, full-suite evidence, limitations, and proposed lessons for the project instructions.

The [AI workflow guide](.agents/guides/ai-workflow-guide.md) describes the approval gates and owner-run verification; the [AI review guide](.agents/guides/ai-review-guide.md) gives checklists for finding unsupported assumptions, weak tests, security gaps, and misleading summaries. Each stage is intended to stop for review before the next stage begins. Implementation is split into planned steps rather than delegated as one unbounded change.

## Artifacts and evidence

The AI-generated planning and review artifacts are grouped by task:

- [Core scheduling logic](docs/ai/core-scheduling-logic/01-spec.md) contains the backend specification, [design](docs/ai/core-scheduling-logic/02-design.md), [plan](docs/ai/core-scheduling-logic/03-plan.md), [test matrix and red-run record](docs/ai/core-scheduling-logic/04-tests.md), and [Stage 6 summary](docs/ai/core-scheduling-logic/06-summary.md). It documents schedule isolation, validation, CSV import, demand and metrics, deterministic generation, persistence, and refresh safety. The Stage 4 test-only run reported expected missing-feature failures; the later implementation stage reported 77 passing tests, and the summary recorded 81 passing with three opt-in benchmarks skipped.
- [Staff scheduling UI](docs/ai/staff-scheduling-ui/01-spec.md) contains the UI specification, [design](docs/ai/staff-scheduling-ui/02-design.md), [plan](docs/ai/staff-scheduling-ui/03-plan.md), and [test/red-run record](docs/ai/staff-scheduling-ui/04-tests.md). The initial test-only run recorded 37 expected feature failures. Implementation and subsequent UI refinements are recorded in [the change log](docs/ai/CHANGELOG.md); a per-task Stage 6 summary is not present.
- [Scheduling algorithm v2](docs/ai/scheduling-algorithm-v2/01-spec.md) contains the algorithm requirements, [design](docs/ai/scheduling-algorithm-v2/02-design.md), [plan](docs/ai/scheduling-algorithm-v2/03-plan.md), [test matrix](docs/ai/scheduling-algorithm-v2/04-tests.md), and [Stage 6 summary](docs/ai/scheduling-algorithm-v2/06-summary.md). The summary records both the original cap-boundary finding and its later regression-tested resolution; the [change log](docs/ai/CHANGELOG.md) records the focused follow-up and verification.

The staged folders contain specification, design, plan, test, and summary artifacts; they do not contain a separate transcript for every implementation prompt. The append-only [AI change log](docs/ai/CHANGELOG.md) records material implementation work, tests and checks run, and follow-ups. Its results are historical, task-specific evidence: later changes can make earlier test counts or audit statuses stale. For the latest recorded full-suite check, consult the newest relevant change-log entry and rerun the documented commands before submission.

## Verification approach

AI suggestions were checked through several complementary mechanisms:

- Requirements and acceptance criteria were traced to implementation and tests in the task artifacts.
- Red-stage test output was checked to distinguish intended feature gaps from import, fixture, or test-collection errors.
- Implementation stages ran the repository's pytest, Ruff lint/format, and Python syntax checks; performance benchmarks were opt-in and not rerun after every change.
- A focused reproduction and regression test caught and fixed the algorithm construction-cap issue even though an earlier full suite passed.
- UI workflow checks and a local HTTP smoke check are recorded in the change log. Later UI refinements were verified by automated tests; a live browser walkthrough was not recorded for every subsequent change.

Before submission, the owner should run the commands in [README.md](README.md), start the app, verify the current UI and sample-data workflow, inspect the final diff, and be prepared to explain and modify the code. Passing tests do not establish global schedule optimality, all-platform behavior, or untested visual/accessibility details.
