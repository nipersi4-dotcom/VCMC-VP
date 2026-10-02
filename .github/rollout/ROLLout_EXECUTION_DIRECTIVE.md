# VCMC-VP — GitHub → Rollout Execution Directive

Status: ACTIVE  
Canonical repository: `nipersi4-dotcom/VCMC-VP`  
Canonical branch: `main`

## Purpose

Rollout is the execution and deployment path for the engineering plan maintained in GitHub. When Rollout is connected to this repository, its agent should use the current GitHub `main` state and the repository instructions as the working source of truth.

The objective is to make the GitHub plan move forward through Rollout efficiently, visibly, and with evidence — not to create a second competing plan.

## Operating direction

1. Read and follow, in order:
   - `AGENTS.md`
   - `.github/copilot-instructions.md`
   - `.github/agents/vcmc-vp-engineering.agent.md`
   - `.github/rollout/ROLLout_HANDOFF.md`
   - the current repository code, tests, roadmap, and open engineering work.

2. Treat GitHub `main` as the canonical engineering state unless a newer approved branch/PR is explicitly assigned.

3. Use Rollout to execute the work described by the repository plan:
   - inspect;
   - implement the smallest necessary change;
   - run the relevant tests;
   - verify the result;
   - return structured evidence;
   - prepare/push a branch and PR when the task requires a code change.

4. Do not unnecessarily stop work because another tool, provider, or execution path is unavailable. Continue with the repository work that can be completed safely and record exactly what remains.

5. Do not create a replacement application, new repository, parallel architecture, or import/rebuild cycle. Extend the existing VCMC-VP system.

6. Preserve existing working functionality. In particular, do not remove the professional password visibility eye control, login/session flow, Lobby, Rooms, calculator, reconciliation boundary, security/readiness checks, or evidence/reconciliation behavior unless an approved change explicitly requires it.

7. Keep the implementation path broad enough to complete the roadmap: do not artificially restrict engineering work to the first small feature when the repository already contains the architecture and acceptance gates for the next stages.

## Safety and governance boundaries

These remain absolute:

- Do not modify or override the VCMC Master.
- AI is support/execution assistance, never the VCMC authority.
- `VCMC_REAL_MONEY_ENABLED` remains `false` unless separately and explicitly authorized through the established governance process.
- Never execute real payments.
- Never expose, print, commit, or transmit secrets.
- Never claim READY or PROVEN without evidence.
- Never turn a simulation into a claim of real payment execution.
- Preserve the separation between determining, calculating, holding funds, paying, and receiving.

## Completion language

Use factual status only:

- DONE = completed and verified.
- RECORDED = stored as an artifact/record.
- TESTED = a specified test passed.
- PROVEN = only when the relevant real-world evidence exists.
- BLOCKED = a specific required capability is genuinely unavailable; state the smallest next action needed.

Never simulate a successful Rollout↔GitHub handoff. If the connection is active, show evidence of the repository, branch, commit, and execution result.

## Immediate priority

The first operational objective is:

**GitHub current plan → Rollout agent reads it → Rollout executes against the existing VCMC-VP workspace → tests → evidence → GitHub PR/merge → Rollout deployment/release.**

Keep the path moving forward and keep the repository history auditable.
