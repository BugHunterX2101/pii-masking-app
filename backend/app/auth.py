import os
import json
import time
import urllib.request
import jwt
from fastapi import HTTPException, status

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-ro5w3rfa3erdaxmg.us.auth0.com")
AUTH0_DOMAIN = AUTH0_DOMAIN.replace("https://", "").replace("http://", "").rstrip("/")
ISSUER = f"https://{AUTH0_DOMAIN}/"
ALGORITHMS = ["RS256"]
JWKS_TTL_SECONDS = int(os.getenv("JWKS_TTL_SECONDS", str(6 * 3600)))  # default 6h

# Time-based JWKS cache: Auth0 rotates signing keys, so an infinite lru_cache
# (the previous implementation) would keep verifying with a stale key forever
# after a rotation. We refetch when the cached copy is older than TTL, and also
# on a kid miss (with a single refetch guard so we never spin).
_jwks_cache = {"fetched_at": 0.0, "jwks": None}


def _fetch_jwks():
    url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch JWKS from Auth0: {str(e)}")


def _get_jwks(force: bool = False):
    now = time.time()
    cached = _jwks_cache.get("jwks")
    if not force and cached is not None and now - _jwks_cache["fetched_at"] < JWKS_TTL_SECONDS:
        return cached
    jwks = _fetch_jwks()
    _jwks_cache["jwks"] = jwks
    _jwks_cache["fetched_at"] = time.time()
    return jwks


def get_auth0_public_key(token: str):
    """Fetch the JWKS from Auth0 and find the RSA public key for the token."""
    jwks = _get_jwks()

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing kid claim")

    # Reject non-RS256 signing algorithms outright before doing any work.
    if unverified_header.get("alg") not in ALGORITHMS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unsupported signing algorithm")

    rsa_key = None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            rsa_key = {
                "kty": key.get("kty"),
                "kid": key.get("kid"),
                "use": key.get("use"),
                "n": key.get("n"),
                "e": key.get("e"),
            }
            break

    if not rsa_key:
        # The key may have rotated after our cache was fetched — refetch once.
        jwks = _get_jwks(force=True)
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                rsa_key = {
                    "kty": key.get("kty"),
                    "kid": key.get("kid"),
                    "use": key.get("use"),
                    "n": key.get("n"),
                    "e": key.get("e"),
                }
                break

    if rsa_key:
        return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(rsa_key))
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to find appropriate key")


def verify_auth0_token(token: str):
    """Verify the Auth0 JWT using the RSA public key.

    Enforces RS256, signature, expiry, issuer and (when configured) audience.
    """
    public_key = get_auth0_public_key(token)
    options = {"verify_aud": False}  # ID tokens carry the Client ID as audience
    audience = os.getenv("AUTH0_AUDIENCE")
    if audience:
        options = {"verify_aud": True}
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=ALGORITHMS,
            issuer=ISSUER,           # reject tokens minted by other tenants
            audience=audience,       # None is fine when verify_aud is off
            options=options,
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token issued by an unknown issuer")
    except jwt.JWTClaimsError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Incorrect claims: {str(e)}")
    except Exception as e:
        print(f"[AUTH ERROR] Token validation failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}")


def debug_decode(token: str) -> dict:
    """Decode token without verification — only used for the /api/auth/debug endpoint."""
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except Exception as e:
        return {"error": str(e)}
