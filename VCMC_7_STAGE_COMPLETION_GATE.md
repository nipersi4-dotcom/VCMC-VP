# VCMC-VP — 7 STAGE COMPLETION GATE

Baseline: VCMC-VP MASTER BUILD V1 / RoadMap 01-10.

This document separates machine completion from external proof. No external deployment, payment, pilot, ecosystem adoption, or global scale is marked PASS without evidence from the real environment.

## Stage 1 — Build Core Machine
Status: PASS (build/test baseline)
Evidence: app/server.py, tests/test_master_build.py

## Stage 2 — Prove Machine
Status: PASS (local machine proof baseline)
Evidence: tests/test_master_build.py and tests/test_roadmap_3_10.py
Coverage: identity/login, rule/version, golden calculation, allocation, case/idempotency, state including UNKNOWN/HOLD, evidence hash, backup hash, reconciliation, provider execution gate.

## Stage 3 — Real Deployment
Status: READY / EXTERNAL PROOF REQUIRED
Prepared: Dockerfile, render.yaml, health endpoint, readiness endpoint.
Not claimed: public server URL or production deployment.

## Stage 4 — Entry Doors
Status: READY (architecture baseline)
Defined boundaries: Sovereign/Admin, Candidate/Partner, Pilot, Provider/PJP, Audit/Reconciliation.
Access does not imply authority; partner does not become VCMC; provider/PJP remains separate.

## Stage 5 — Real Pilot
Status: GATE READY / EXTERNAL PROOF REQUIRED
Required evidence: real need, real host, real capability, real activity, KPI, evidence, reconciliation.
Candidate != Pilot.

## Stage 6 — Ecosystem
Status: ARCHITECTURE READY / EXTERNAL PROOF REQUIRED
Prepared: multi-party roles, provider boundary, partner/pilot pathway, evidence/reconciliation model.

## Stage 7 — Global Distribution & Scale
Status: ARCHITECTURE READY / EXTERNAL PROOF REQUIRED
Prepared: provider-independent boundary, multi-party/workspace model, global/cross-border scope.
No claim of global adoption or scale is made until externally evidenced.

## Locked acceptance rules
- CLAIM != EVIDENCE
- READY != PROVEN
- UNKNOWN != FAILED
- PAYMENT SUCCESS != AUTOMATIC EVIDENCE
- VCMC != PJP
- ALLOCATION LOGIC != PAYMENT EXECUTION
- AI/automation != authority
