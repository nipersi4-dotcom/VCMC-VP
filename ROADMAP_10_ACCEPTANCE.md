# ROADMAP 10 — ACCEPTANCE BASELINE
1. MASTER BUILD Structure — package included.
2. Render / Server — Docker + Render manifest included; external deployment still requires verification.
3. Public HTTPS — deployment verification required.
4. Login HP — deployment verification required.
5. Golden Test — automated local test included.
6. End-to-End Test — local core flow covered; production E2E remains.
7. Persistence Test — SQLite path covered; production persistence must be verified.
8. Failure / Recovery Test — backup/reconciliation baseline included; recovery drill remains required.
9. Evidence & Reconciliation — schemas and reconciliation endpoint included; full evidence workflow remains to be expanded/verified.
10. Pilot Readiness — NOT automatically PASS; requires real evidence, authority, compliance, provider/PJP readiness and a real pilot case.


## BUILD COMPLETION NOTE
RoadMap #3-#10 now has executable local coverage in `tests/test_roadmap_3_10.py`. The test covers server health, login, golden formula, idempotent case creation, allocation, UNKNOWN→HOLD handling, evidence SHA-256, simulated payment instruction gate, reconciliation, backup integrity, and readiness gate.
External deployment/proof is intentionally not represented as PASS by local tests.
