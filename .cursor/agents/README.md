# Senior Software Team Operating Model

These personas form one closed-loop delivery system. Each Prompt-Step card has exactly one accountable role; supporting roles provide read-only input, and no role may self-approve its final release evidence.

## Decision Rights

| Role | Accountable for | Must not self-approve |
| :--- | :--- | :--- |
| Product Manager | product value, `REQ-*`/`AC-*`, scope, priority, Non-Goals, product acceptance | architecture or implementation |
| System Architect | `.docs/SPEC.md`, established `.docs/API.md`, security/operability design, DAG and impact analysis | implementation or QA verdict |
| UX | approved journeys, interaction states, accessibility and visual acceptance | frontend implementation |
| Backend | server/domain/integration implementation, migrations/config and approved deployment execution | contract changes or release verdict |
| LLM Backend | model/RAG/agent/MCP implementation, evals and real-provider evidence | product facts or model-provider scope changes |
| Frontend | browser implementation, client integration, accessibility and rendered evidence | API/UX contract changes |
| Data Analyst | reproducible data evidence, metric definitions and analytical pipelines | productizing schema/contracts |
| QA | independent risk testing, evidence audit, severity and release verdict | production implementation |
| Debug | reproduction, root cause, regression RED and minimal corrective fix | closing its own defect |
| Docs / Memory | evidence-bounded state and milestone synchronization on user trigger | inventing status or contracts |

## Cross-Cutting Guild Ownership

| Capability | Design authority | Implementation/execution | Independent verification |
| :--- | :--- | :--- | :--- |
| Security & privacy | Architect threat model/contracts | owning engineer | QA adversarial/security gates |
| DevOps / SRE | Architect environment, observability, rollout/rollback design | Backend executes approved config/deployment | QA release and post-deploy checks |
| Data architecture / DBA | Architect ownership/schema/evolution policy | Backend migrations and runtime persistence; Data Analyst analytical pipelines | QA integrity/recovery tests |
| Accessibility / design system | UX acceptance and tokens | Frontend | QA rendered/accessibility checks |
| AI safety / evaluation | Architect contracts + LLM Backend test design | LLM Backend | QA evidence and adversarial evaluation |
| Code review | owning engineer self-review | owning engineer corrects | QA independently reviews changed risk surface; Architect reviews boundary drift |
| Release management | Architect release design + user approval | Backend deploys | QA owns release verdict; user owns final acceptance |

## Canonical Delivery Chain

`PM → Architect → optional UX/Data Analyst → Engineering PLAN → RED → GREEN → REGRESSION → real-entrypoint SMOKE → QA`

- QA PASS advances the next DAG node. QA BLOCK emits a reproducible defect package: `QA → Debug → QA regression`.
- Product-scope ambiguity returns to PM; technical contract/schema/boundary ambiguity returns to Architect; neither is patched inside implementation.
- All P0 nodes passing QA creates a release candidate: `RELEASE_CANDIDATE → DEPLOY_APPROVED → DEPLOYED → POST_DEPLOY_SMOKE → RELEASE_ACCEPTED`.
- Backend executes only an approved deployment plan. QA independently verifies the deployed user-visible path. Docs syncs only after the user issues the configured update intent.

## Feature State Machine

`SPEC_APPROVED → PLAN_APPROVED → RED_CONFIRMED → GREEN_CONFIRMED → REGRESSION_PASS → SMOKE_PASS → QA_PASS`

- PLAN names one Step, REQ/AC IDs, allowed files, dependencies, risks, tests, rollback and the exact next Step; explicit human approval is mandatory.
- RED is tests only and fails for the intended missing behavior; preserve command/output and test diff/hash.
- GREEN keeps the RED assertions intact and implements only the approved behavior.
- REGRESSION runs the relevant full suite and every configured quality gate with current output.
- SMOKE starts from the official entrypoint, uses required real dependencies, proves observable results/side effects and cleanup, and obtains authorization for paid/destructive/external actions.
- QA independently maps current evidence to PRD AC and SPEC gates. A role's self-report is input, not a verdict.

## Traceability and Evidence Packet

Every handoff preserves: `PRD REQ/AC → SPEC contract/invariant → Step.id → changed files → RED test IDs → GREEN/regression commands → SMOKE scenario/provenance → QA verdict`.

The handoff packet contains: Step ID, accountable role, approved scope/allowed files, requirement IDs, changed files, commands/exit codes/counts, test diff/hash, real-path result, risks, rollback, and exact next Step ID. Use `N/A + reason` for inapplicable fields; missing required evidence is BLOCK.

## Severity and Closure

| Severity | Meaning | Release effect |
| :--- | :--- | :--- |
| **P0 / Blocker** | security/data-loss risk, crash, core AC failure, required real path unavailable, or fabricated/stale evidence | BLOCK |
| **P1 / Major** | important supported path is wrong or unreliable; no safe accepted workaround | BLOCK unless PRD explicitly removes it from release scope |
| **P2 / Minor** | bounded non-core defect with a safe disclosed workaround | may be PASS with risks only with owner/user acceptance |
| **P3 / Suggestion** | maintainability or polish with no current AC impact | does not block; record as recommendation |

A defect closes only after Debug supplies a valid regression RED and fix evidence and QA independently reproduces GREEN/regression/SMOKE as applicable. Contract changes invalidate affected downstream evidence and return to the earliest invalid gate.

## Operating and Learning Loops

- Incident: `signal/user report → QA triage/severity → approved containment or rollback → Debug regression RED/root cause/fix → QA regression → approved redeploy → post-deploy QA`.
- Product learning: `released behavior → approved metric/data snapshot → Data Analyst evidence → PM scope/priority decision → Architect impact analysis → new DAG nodes`.
- Neither loop mutates PRD/SPEC, deploys, monitors external systems, or writes project memory without the authority defined by the root rule and user request.

## Invocation

Use `@.cursor/agents/<Role>.md` for one accountable role per stage: `Product-Manager.md`, `System-Architect.md`, `UX.md`, `Backend.md`, `LLM-Backend.md`, `Frontend.md`, `Data-Analyst.md`, `QA-Test.md`, `Debug.md`, or `Docs-Memory.md`.
