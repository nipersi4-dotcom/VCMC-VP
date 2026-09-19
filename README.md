# VCMC-VP MASTER BUILD — RECONSTRUCTED BASE

Operational/test baseline reconstructed from the VCMC machine architecture and security/deployment principles. Real-money execution is OFF by default.

Run: `python app/server.py`
Test: `python tests/test_master_build.py`

Golden Rp100m: Zakat Rp2.5m; Mitra Rp39m; Pusat Rp39m; Amal Rp19.5m. Pusat: IP Rp15.6m; Development Rp15.6m; Reserve Rp7.8m.

This package is not proof of production deployment, HTTPS, external persistence, PJP execution, or pilot readiness.


## ROADMAP #3-#10 BUILD COMPLETION
This build adds executable local verification for: public-server readiness configuration, login/session, golden calculation, end-to-end case/allocation flow, persistence/backup, UNKNOWN/HOLD recovery states, evidence hashing, reconciliation, provider execution gate, and pilot readiness gating.

Build test command:
`python tests/test_master_build.py && python tests/test_roadmap_3_10.py`

Expected:
`VCMC-VP MASTER BUILD TEST: PASS`
`VCMC-VP ROADMAP #3-#10 BUILD TEST: PASS`

External proof remains separate: public HTTPS, production persistence, real PJP execution, and a real Pilot require actual deployment/provider/case evidence.
