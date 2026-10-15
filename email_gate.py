"""
email_gate.py — the email check we added to Flaminga after the "Mr. Focker" incident.

Flaminga is the AI sales assistant of Paperclip Business Media (https://paperclip-business.com).
Before she creates a personalised AI Readiness Report or passes a lead to our sales desk,
every email address goes through this gate.

Design principle: FAIL-OPEN.
Only a definite "this domain does not exist / cannot receive mail" blocks an address.
Timeouts, resolver hiccups or a missing library let the address through — we would rather
accept one fake lead than turn away a real customer.

Requires: pip install dnspython
License: MIT
"""

import logging
import re
import time

log = logging.getLogger(__name__)

# Deliberately tolerant (no RFC 5322 monster): local@domain.tld, TLD >= 2 chars,
# no spaces, exactly one @. Catches real-world mistakes without rejecting real addresses.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

# Common typo domains -> intended domain. We never correct silently;
# the agent asks the visitor ("Did you mean ...?").
# Do NOT add real domains (e.g. gmx.com, gmail.de) — that causes an endless loop.
TYPO_DOMAINS = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmal.com": "gmail.com",
    "gmaill.com": "gmail.com", "gmail.co": "gmail.com", "gnail.com": "gmail.com",
    "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com", "hotmail.co": "hotmail.com",
    "outlok.com": "outlook.com", "outllok.com": "outlook.com", "outlook.co": "outlook.com",
    "yaho.com": "yahoo.com", "yahooo.com": "yahoo.com", "yahoo.co": "yahoo.com",
    "icloud.co": "icloud.com", "iclould.com": "icloud.com",
    "gmx.d": "gmx.de", "gmz.de": "gmx.de", "web.d": "web.de", "t-onlin.de": "t-online.de",
}

# Throwaway services and placeholder domains: no real lead, no report.
# Kept compact on purpose — the most common services cover the vast majority of cases.
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.de", "guerrillamail.net",
    "sharklasers.com", "grr.la", "10minutemail.com", "10minutemail.net",
    "temp-mail.org", "temp-mail.io", "tempmail.com", "tempmail.net",
    "yopmail.com", "yopmail.fr", "trashmail.com", "trashmail.de", "trashmail.net",
    "getnada.com", "maildrop.cc", "dispostable.com", "throwawaymail.com",
    "fakeinbox.com", "emailondeck.com", "wegwerfmail.de", "minuteinbox.com",
    "burnermail.io", "discard.email", "mytemp.email",
    "example.com", "example.org", "example.net", "test.com", "domain.com", "localhost",
}
RESERVED_TLDS = (".test", ".example", ".invalid", ".localhost", ".local")

_MX_CACHE: dict = {}          # domain -> (timestamp, result)
_MX_CACHE_TTL = 6 * 3600


def domain_accepts_mail(domain: str):
    """True  = domain has MX (or A/AAAA as fallback, RFC 5321)
       False = domain does not exist or definitely cannot receive mail
       None  = unclear (DNS problem) -> caller treats it as OK (fail-open)"""
    domain = domain.lower().rstrip(".")
    hit = _MX_CACHE.get(domain)
    if hit and time.time() - hit[0] < _MX_CACHE_TTL:
        return hit[1]
    try:
        import dns.resolver
    except ImportError:
        return None                          # dnspython missing -> don't block

    resolver = dns.resolver.Resolver()
    resolver.lifetime = 4.0                  # total time per lookup; the chat must not hang
    result = None
    try:
        answers = resolver.resolve(domain, "MX")
        # Null MX (RFC 7505, exchange "."): the domain explicitly refuses mail.
        hosts = [str(r.exchange).rstrip(".") for r in answers]
        result = any(h for h in hosts)
    except dns.resolver.NXDOMAIN:
        result = False                       # domain does not exist
    except dns.resolver.NoAnswer:
        # No MX -> per RFC 5321 the A/AAAA record may accept mail.
        no_answers = 0
        for rtype in ("A", "AAAA"):
            try:
                resolver.resolve(domain, rtype)
                result = True
                break
            except dns.resolver.NoAnswer:
                no_answers += 1
            except dns.resolver.NXDOMAIN:
                result = False
                break
            except Exception:
                result = None                # unclear -> fail-open
                break
        if result is None and no_answers == 2:
            result = False                   # neither MX nor A/AAAA
    except Exception as e:                   # timeout, no nameservers, network error ...
        log.warning("MX check unclear for %s: %s", domain, e)
        result = None

    if result is not None:                   # cache only definite answers
        _MX_CACHE[domain] = (time.time(), result)
    return result


def validate_email(raw) -> tuple:
    """Returns (status, detail):
      ("ok",         normalised_address)  -> go ahead
      ("typo",       suggested_address)   -> likely typo; ask the visitor
      ("invalid",    None)                -> malformed; ask again
      ("empty",      None)                -> no address given
      ("disposable", domain)              -> throwaway / placeholder; ask for a real one
      ("nodomain",   domain)              -> domain doesn't exist / no mail server; ask again
    """
    email = str(raw or "").strip().strip("<>").strip()
    if not email:
        return ("empty", None)

    if "@" in email:
        local, _, domain = email.rpartition("@")
        suggestion = TYPO_DOMAINS.get(domain.lower())
        if suggestion and local:
            return ("typo", f"{local}@{suggestion}")

    if not _EMAIL_RE.match(email):                                   # 1. format
        return ("invalid", None)

    domain = email.rpartition("@")[2].lower()
    if domain in DISPOSABLE_DOMAINS or domain.endswith(RESERVED_TLDS):  # 2. throwaway
        return ("disposable", domain)

    if domain_accepts_mail(domain) is False:                         # 3. MX (fail-open)
        return ("nodomain", domain)

    return ("ok", email)


if __name__ == "__main__":
    for addr in ["dkdkkd@fkldl.com", "max@gmial.com", "test@mailinator.com",
                 "not-an-email", "hello@paperclip-business.com"]:
        print(f"{addr:32} -> {validate_email(addr)}")
