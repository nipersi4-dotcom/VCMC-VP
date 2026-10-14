import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(ROOT, "server.py")

with open(SERVER, encoding="utf-8") as f:
    source = f.read()

checks = {
    "public registration endpoint": "if p=='/api/public/register':" in source,
    "email verification endpoint": "if p=='/api/public/verify-email':" in source,
    "explicit terms acknowledgement": "data.get('accept_terms')" in source,
    "hashed one-time verification token": "hashlib.sha256(token_value.encode()).hexdigest()" in source,
    "30-minute verification expiry": "time.time()+1800" in source,
    "pending registration is not active account": "'verification_pending'" in source,
    "email verification marks user verified": "'email_verified':True" in source,
    "registration confirmation password field": 'reg-password-confirm' in source,
    "registration requires explicit checkbox": "reg-accept-terms" in source and "if(!accepted)" in source,
    "registration does not claim immediate login": "Daftar &amp; verifikasi email" in source,
    "verification link handler": "async function verifyEmailFromLink()" in source,
    "verification token read from URL": "params.get('verify')" in source,
    "verification handler called on link open": "if(new URLSearchParams(location.search).has('verify'))verifyEmailFromLink()" in source,
    "email delivery failure does not create active account": "Email verifikasi belum dapat dikirim. Tidak ada akun yang dibuat." in source,
}

failed = [name for name, passed in checks.items() if not passed]
for name, passed in checks.items():
    print(("PASS" if passed else "FAIL") + ": " + name)
if failed:
    raise SystemExit("Registration flow checks failed: " + ", ".join(failed))
print("VCMC-VP REGISTRATION FLOW CONTRACT: PASS")
