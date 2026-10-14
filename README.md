---
title: VCMC-VP — Operational Platform
emoji: 🌐
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# VCMC-VP — Operational Platform

VCMC-VP is a two-part application: a static public frontend and a separate Python/SQLite backend. The Master VCMC remains the controlling source and is not modified by this repository.

## Deployment architecture

- **Public frontend:** GitHub Pages, served from `docs/index.html`.
- **Backend source of truth:** this GitHub repository, `server.py`.
- **Alternative backend host:** Hugging Face Spaces (Docker), prepared through the manually triggered GitHub Actions OIDC publisher workflow.
- **Additional host option:** Render Web Service from the same repository and Dockerfile.
- Host synchronization is not considered live until the deployment workflow succeeds and `/health` plus `/api/system/readiness` are checked on the deployed URL.

## Public frontend

- GitHub Pages: https://nipersi4-dotcom.github.io/VCMC-VP/
- Deployment: GitHub Actions workflow `.github/workflows/vcmc-pages.yml`
- The frontend includes the 13-room map, public access-request form, login/session UI, account/password settings, evidence, distribution calculator, reconciliation, security, system status, and payment simulation boundary.
- The backend URL must point to a confirmed deployed backend; GitHub Pages itself does not run the Python API.

## Backend

- Source: `server.py`
- Runtime: Python standard library + SQLite
- Required runtime environment variables:
  - `VCMC_ADMIN_EMAIL`
  - `VCMC_ADMIN_PASSWORD` (secret; never commit it to the repository)
  - `VCMC_REAL_MONEY_ENABLED=false`
- Email verification also requires valid `RESEND_API_KEY` and `RESEND_FROM_EMAIL` values from an approved sender identity.
- Health endpoint: `/health`
- Readiness endpoint: `/api/system/readiness`
- Use `PORT` supplied by the host. The Docker image defaults to 7860 for Hugging Face Spaces; Render injects its own `PORT`.
- CORS is restricted to explicit HTTPS origins. Do not use wildcard origins.
- SQLite is local-file storage. A host with ephemeral disk is suitable only for limited validation until persistent storage or a managed database migration is proven.

## Alternative deployment to Hugging Face Spaces

Workflow: `.github/workflows/publish-to-hf.yml` (manual dispatch only; does not publish automatically on every push).

It uses Hugging Face Trusted Publishers (GitHub Actions OIDC) so no long-lived Hugging Face token needs to be stored in GitHub. Before dispatching, configure the matching Trusted Publisher on the Space settings:
- Provider: GitHub Actions
- Repository: `nipersi4-dotcom/VCMC-VP`
- Branch: `main`
- Workflow: `publish-to-hf.yml`

The Space also needs its runtime secrets configured securely. A successful upload is not proof that the service starts; verify the Space build, health endpoint, readiness endpoint, database persistence, CORS, and account/email flows separately.

## Validation

Run:
```sh
python test_roadmap_3_10.py
python test_frontend_contract.py
```

Repository checks do not prove that the deployed backend, account registration, email verification, database persistence, partner access, PJP execution, or a real pilot is live and verified.

## Locked safety boundaries

- `VCMC_REAL_MONEY_ENABLED=false` by default.
- No real-money payment execution is implemented by the frontend.
- VCMC governance, allocation principles, and the Master VCMC are not changed here.
- `CLAIM ≠ EVIDENCE`; `READY ≠ PROVEN`; `UNKNOWN ≠ FAILED`; `RECORDED ≠ DONE ≠ PROVEN`.
- Registration ≠ approval; login ≠ partner status; partner status ≠ authority; authority ≠ unrestricted Case access.
- AI and automation are support only, not VCMC authority, owner, fund holder, approver, or payment executor.
