# VCMC-VP — Operational Platform

VCMC-VP is a two-part application: a static public frontend and a separate Python/SQLite backend. The Master VCMC remains the controlling source and is not modified by this repository.

## Public frontend

- GitHub Pages: https://nipersi4-dotcom.github.io/VCMC-VP/
- Source: `docs/index.html`
- Deployment: GitHub Actions workflow `.github/workflows/vcmc-pages.yml`
- The frontend includes the 13-room map, public access-request form, login/session UI, account/password settings, evidence, distribution calculator, reconciliation, security, system status, and payment simulation boundary.
- The backend URL is intentionally not assumed. Configure it in **System → Backend connection** only after confirming the correct deployed backend URL.

## Backend

- Source: `server.py`
- Runtime: Python standard library + SQLite
- Start after setting the required environment variables:
  ```sh
  export VCMC_ADMIN_EMAIL='your-approved-admin-email'
  export VCMC_ADMIN_PASSWORD='set-a-strong-secret-outside-the-repository'
  export VCMC_REAL_MONEY_ENABLED=false
  python server.py
  ```
- Health endpoint: `/health`
- Readiness endpoint: `/api/system/readiness`
- Cross-origin access is restricted to the explicit allowlist in `VCMC_ALLOWED_ORIGINS`; when set, use comma-separated exact HTTPS origins. The built-in default list includes the GitHub Pages origin and the VCMC-PUSAT Hugging Face Space origin. Do not use wildcard origins.
- CORS only permits the browser to call the API; authentication, role checks, and resource permissions still apply.

## Validation

Run:
```sh
python test_roadmap_3_10.py
python test_frontend_contract.py
```

The GitHub Actions checks passed on the merged frontend change. This verifies the repository test suite and JavaScript syntax; it does **not** prove that the deployed backend URL, database persistence, external partner access, Hugging Face copy, real-world pilot, PJP execution, or production operation is live and verified.

## Locked safety boundaries

- `VCMC_REAL_MONEY_ENABLED=false` by default.
- No real-money payment execution is implemented by the frontend.
- VCMC governance, allocation principles, and the Master VCMC are not changed here.
- `CLAIM ≠ EVIDENCE`; `READY ≠ PROVEN`; `UNKNOWN ≠ FAILED`; `RECORDED ≠ DONE ≠ PROVEN`.
- Registration ≠ approval; login ≠ partner status; partner status ≠ authority; authority ≠ unrestricted Case access.
- AI and automation are support only, not VCMC authority, owner, fund holder, approver, or payment executor.
- Real public HTTPS, production persistence, PJP execution, and a real pilot require separate external proof.
