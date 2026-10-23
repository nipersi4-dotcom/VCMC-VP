"""Prove the public gateway can boot without privileged administrator secrets.

This test intentionally does not create a sovereign account. It verifies that
public signup/login can be validated while readiness truthfully remains HOLD
until an administrator is configured. Run with: python test_public_bootstrap.py
"""
import json
import os
import tempfile
import threading
import urllib.error
import urllib.request

with tempfile.TemporaryDirectory() as td:
    os.environ["VCMC_DB"] = os.path.join(td, "public-gateway.db")
    os.environ["VCMC_BACKUP_DIR"] = os.path.join(td, "backups")
    os.environ["VCMC_ADMIN_EMAIL"] = ""
    os.environ["VCMC_ADMIN_PASSWORD"] = ""
    os.environ["VCMC_REAL_MONEY_ENABLED"] = "false"
    os.environ.pop("RESEND_API_KEY", None)
    os.environ.pop("RESEND_FROM_EMAIL", None)
    os.environ.pop("VCMC_SMTP_HOST", None)
    os.environ.pop("VCMC_SMTP_PORT", None)
    os.environ.pop("VCMC_SMTP_USER", None)
    os.environ.pop("VCMC_SMTP_PASSWORD", None)
    os.environ.pop("VCMC_SMTP_FROM_EMAIL", None)

    import server

    server.init()
    db = server.conn()
    assert db.execute("SELECT COUNT(*) FROM users WHERE role='SOVEREIGN'").fetchone()[0] == 0
    db.close()

    srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}"

    def request(path, obj=None, token=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        req = urllib.request.Request(
            base + path,
            data=json.dumps(obj).encode() if obj is not None else None,
            headers=headers,
            method="POST" if obj is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    try:
        status, health = request("/health")
        assert status == 200 and health["status"] == "ok"
        assert health["admin_configured"] is False

        status, registered = request("/api/public/register", {
            "name": "Public Bootstrap Test",
            "email": "public-bootstrap@example.invalid",
            "password": "test-password-123",
            "context": "CANDIDATE",
            "accept_terms": True,
        })
        assert status == 201
        assert registered["status"] == "public_unverified"
        assert registered["email_verified"] is False
        assert registered["role"] == "PUBLIC"
        db = server.conn()
        row = db.execute(
            "SELECT role,status,email_verified FROM users WHERE email=?",
            ("public-bootstrap@example.invalid",),
        ).fetchone()
        assert row is not None
        assert row["role"] == "PUBLIC" and row["status"] == "PUBLIC"
        assert row["email_verified"] == 0
        db.close()
        # Email delivery failure may create only a restricted, unverified PUBLIC identity.

        status, logged_in = request("/api/login", {
            "email": "public-bootstrap@example.invalid",
            "password": "test-password-123",
            "context": "PUBLIC",
        })
        assert status == 200 and logged_in.get("token")
        token = logged_in["token"]

        status, me = request("/api/me", token=token)
        assert status == 200 and me["authenticated"] is True
        assert me["role"] != "SOVEREIGN"

        status, readiness = request("/api/system/readiness")
        assert status == 200
        assert readiness["admin_configured"] is False
        assert readiness["ready"] is False
        assert readiness["real_money_enabled"] is False

        status, logged_out = request("/api/logout", obj={}, token=token)
        assert status == 200 and logged_out["logged_out"] is True
        status, _ = request("/api/me", token=token)
        assert status == 401
    finally:
        srv.shutdown()
        srv.server_close()

print("VCMC-VP PUBLIC BOOTSTRAP TEST: PASS")
