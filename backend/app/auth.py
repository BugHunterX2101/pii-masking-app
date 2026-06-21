import os
import json
import urllib.request
import jwt
from fastapi import HTTPException, status
from functools import lru_cache

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "dev-ro5w3rfa3erdaxmg.us.auth0.com")
ALGORITHMS = ["RS256"]

@lru_cache(maxsize=1)
def _get_jwks():
    url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch JWKS from Auth0: {str(e)}")

def get_auth0_public_key(token: str):
    """Fetch the JWKS from Auth0 and find the RSA public key for the token."""
    jwks = _get_jwks()

    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header")

    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
            break

    if rsa_key:
        return jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(rsa_key))
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unable to find appropriate key")

def verify_auth0_token(token: str):
    """Verify the Auth0 JWT using the RSA public key."""
    public_key = get_auth0_public_key(token)
    try:
        # We don't enforce audience here since we are using the ID token for simplicity in this demo.
        # If we had an API set up in Auth0, we would check audience.
        payload = jwt.decode(
            token,
            public_key,
            algorithms=ALGORITHMS,
            options={"verify_aud": False} # Accept the Client ID audience for ID tokens
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
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
