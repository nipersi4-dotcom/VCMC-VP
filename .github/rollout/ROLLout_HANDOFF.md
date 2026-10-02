# VCMC-VP — Rollout Agent Handoff Contract

Status: ACTIVE
Purpose: deterministic GitHub ↔ Rollout handoff for VCMC-VP engineering work.

## Canonical source
- Repository: nipersi4-dotcom/VCMC-VP
- Canonical branch: main
- Working tree expected by Rollout: `~/VCMC-VP`

## Execution contract
1. Receive the task from GitHub Issue/PR context.
2. Read `AGENTS.md`.
3. Read `.github/copilot-instructions.md`.
4. Read `.github/agents/vcmc-vp-engineering.agent.md`.
5. Inspect the current repository state before changing anything.
6. Use one writer per worktree.
7. For implementation work, create a dedicated branch; never write directly to main.
8. Run the repository validation gates before reporting success.
9. Return evidence: branch, commit, changed files, tests, and runtime status.
10. If a required capability is unavailable, report BLOCKED with the exact missing capability; do not simulate success.

## Non-negotiable boundaries
- Do not modify the VCMC Master.
- Do not enable real-money execution.
- Do not execute real payments.
- Do not expose secrets, tokens, passwords, or credentials.
- Do not replace/rebuild/import the project.
- Do not claim READY/PROVEN without evidence.
- UNKNOWN is not FAILED.
- A successful payment/API call is not by itself proof of execution authority.

## First handshake task
Issue #8 is the initial read-only bridge test. It must produce evidence before any autonomous code-changing task is authorized.

## Handoff result format
```
bridge_status:
repository:
branch:
head:
working_tree:
compile_check:
tests:
real_money:
files_read:
changed_files:
evidence:
blockers:
```
