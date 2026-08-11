"""Verified-email-provider policy.

Auth0's `email_verified` flag only proves the user controls the mailbox — the
mailbox itself can live on any provider, including disposable/temporary-mail
services. This module enforces the second gate used at signup:

  1. The email must be syntactically valid.
  2. The domain must be a known, verified provider (allowlist) OR a domain
     with a real MX record.
  3. The domain must not be on the disposable/temporary-mail blocklist.

The allowlist and blocklist are environment-configurable
(VERIFIED_EMAIL_PROVIDERS, DISPOSABLE_EMAIL_DOMAINS, comma-separated) and the
MX check is cached per domain so the hot path (login sync) stays fast.
"""

import os
import re
import time

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

_DEFAULT_VERIFIED_PROVIDERS = (
    # Google
    "gmail.com,googlemail.com,"
    # Microsoft
    "outlook.com,outlook.in,hotmail.com,live.com,msn.com,office365.com,"
    # Yahoo / AOL
    "yahoo.com,yahoo.co.in,yahoo.co.uk,ymail.com,rocketmail.com,aol.com,"
    # Apple
    "icloud.com,me.com,mac.com,"
    # Secure / business mail
    "protonmail.com,proton.me,pm.me,zoho.com,fastmail.com,hey.com,"
    "gmx.com,gmx.net,web.de,mail.com,rediffmail.com,tutanota.com,"
    "runbox.com,posteo.de,mailfence.com,startmail.com"
)

_DEFAULT_DISPOSABLE_DOMAINS = (
    "mailinator.com,10minutemail.com,guerrillamail.com,guerrillamail.net,"
    "guerrillamail.org,guerrillamail.biz,tempmail.com,temp-mail.org,"
    "yopmail.com,throwawaymail.com,maildrop.cc,mailnesia.com,trashmail.com,"
    "getnada.com,sharklasers.com,spam4.me,moakt.com,emailondeck.com,"
    "mailcatch.com,mintemail.com,dropmail.me,dispostable.com,mailmetrash.com,"
    "fakeinbox.com,mohmal.com,emlpro.com,mytemp.email,spambox.us,"
    "tempinbox.com,trashymail.com,wegwerfmail.de,meltmail.com,maileater.com"
)

_VERIFIED_PROVIDERS = frozenset(
    d.strip().lower()
    for d in os.getenv("VERIFIED_EMAIL_PROVIDERS", _DEFAULT_VERIFIED_PROVIDERS).split(",")
    if d.strip()
)

_DISPOSABLE_DOMAINS = frozenset(
    d.strip().lower()
    for d in os.getenv("DISPOSABLE_EMAIL_DOMAINS", _DEFAULT_DISPOSABLE_DOMAINS).split(",")
    if d.strip()
)

_MX_CACHE: dict = {}
_MX_TTL_SECONDS = 3600  # 1 hour


def _domain_has_mx(domain: str, timeout: float = 3.0) -> bool:
    """Resolve the domain's MX records, cached for an hour."""
    now = time.time()
    cached = _MX_CACHE.get(domain)
    if cached and cached[0] > now:
        return cached[1]
    try:
        import dns.resolver  # dnspython

        answers = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        has_mx = len(answers) > 0
    except Exception:
        has_mx = False
    _MX_CACHE[domain] = (now + _MX_TTL_SECONDS, has_mx)
    return has_mx


def validate_email(email: str) -> tuple[bool, str]:
    """Return (allowed, reason) for an email under the verified-provider policy."""
    email = (email or "").strip().lower()
    if not _EMAIL_RE.fullmatch(email):
        return False, "invalid email format"
    domain = email.rsplit("@", 1)[1].lower()
    if domain in _DISPOSABLE_DOMAINS:
        return False, "disposable email providers are not allowed"
    if domain in _VERIFIED_PROVIDERS:
        return True, "verified provider"
    if _domain_has_mx(domain):
        return True, "verified via MX record"
    return False, "email domain is not a verified provider and has no MX record"
