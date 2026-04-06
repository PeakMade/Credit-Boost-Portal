"""
Microsoft Entra bearer token validation for custom authentication extensions
Validates OAuth 2.0 access tokens issued by Microsoft identity platform
"""
import os
import logging
import jwt
import requests
import time
from functools import wraps
from flask import request, jsonify
from jwt import PyJWKClient
from datetime import datetime, timedelta
from threading import Lock

logger = logging.getLogger(__name__)

# ============================================================================
# JWKS CACHING FOR PERFORMANCE
# ============================================================================
# Cache JWKS keys in memory to avoid network round-trips on every request
# TTL: 1 hour (keys rotate infrequently)
# ============================================================================

_jwks_cache = {
    'keys': None,
    'expires_at': None,
    'lock': Lock()
}

JWKS_CACHE_TTL_SECONDS = 3600  # 1 hour


def warmup_jwks_cache():
    """
    Warm up JWKS cache on application startup
    Pre-fetches and caches JWKS keys to eliminate cold-start latency
    
    Returns:
        dict with warmup results: success (bool), duration_ms (float), error (str or None)
    """
    logger.info("🔥 jwks_warmup_started")
    warmup_start = time.time()
    
    try:
        # Get JWKS URI from environment
        tenant_id = os.environ.get('EXTERNAL_OIDC_TENANT_ID', '')
        if not tenant_id:
            error_msg = "EXTERNAL_OIDC_TENANT_ID not configured"
            logger.warning(f"⚠️ jwks_warmup_failed: {error_msg}")
            return {'success': False, 'duration_ms': 0, 'error': error_msg}
        
        jwks_uri = f"https://{tenant_id}.ciamlogin.com/{tenant_id}/discovery/v2.0/keys"
        
        # Fetch and cache JWKS
        jwks_data, cache_hit, fetch_ms, _, ttl = get_cached_jwks(jwks_uri)
        
        duration_ms = (time.time() - warmup_start) * 1000
        logger.info(f"✅ jwks_warmup_succeeded: duration={duration_ms:.1f}ms, keys_cached={len(jwks_data.get('keys', []))}, ttl={ttl:.0f}s")
        
        return {'success': True, 'duration_ms': duration_ms, 'error': None}
    
    except Exception as e:
        duration_ms = (time.time() - warmup_start) * 1000
        error_msg = str(e)
        logger.warning(f"⚠️ jwks_warmup_failed: {error_msg}, duration={duration_ms:.1f}ms")
        return {'success': False, 'duration_ms': duration_ms, 'error': error_msg}


def get_cached_jwks(jwks_uri):
    """
    Get JWKS keys from cache or fetch from network
    
    Returns:
        tuple: (jwks_data, cache_hit: bool, fetch_time_ms: float, cache_age_s: float, ttl_remaining_s: float)
    """
    with _jwks_cache['lock']:
        now = time.time()
        
        # Check cache validity
        if _jwks_cache['keys'] is not None and _jwks_cache['expires_at'] is not None:
            if now < _jwks_cache['expires_at']:
                cache_age = now - (_jwks_cache['expires_at'] - JWKS_CACHE_TTL_SECONDS)
                ttl_remaining = _jwks_cache['expires_at'] - now
                logger.info(f"✅ JWKS cache HIT (age={cache_age:.0f}s, ttl_remaining={ttl_remaining:.0f}s)")
                return _jwks_cache['keys'], True, 0.0, cache_age, ttl_remaining
        
        # Cache miss - fetch from network
        logger.info(f"⚠️ JWKS cache MISS - fetching from {jwks_uri}")
        fetch_start = time.time()
        
        try:
            jwks_response = requests.get(jwks_uri, timeout=5)
            jwks_response.raise_for_status()
            jwks_data = jwks_response.json()
            
            fetch_elapsed_ms = (time.time() - fetch_start) * 1000
            
            # Update cache
            _jwks_cache['keys'] = jwks_data
            _jwks_cache['expires_at'] = now + JWKS_CACHE_TTL_SECONDS
            
            logger.info(f"✅ JWKS fetched and cached: {fetch_elapsed_ms:.1f}ms, TTL={JWKS_CACHE_TTL_SECONDS}s")
            
            return jwks_data, False, fetch_elapsed_ms, 0.0, JWKS_CACHE_TTL_SECONDS
        
        except Exception as e:
            logger.error(f"❌ JWKS fetch failed: {e}")
            # If we have stale cache, return it as fallback
            if _jwks_cache['keys'] is not None:
                logger.warning(f"⚠️ Using stale JWKS cache as fallback")
                fetch_elapsed_ms = (time.time() - fetch_start) * 1000
                cache_age = now - (_jwks_cache['expires_at'] - JWKS_CACHE_TTL_SECONDS) if _jwks_cache['expires_at'] else 0
                return _jwks_cache['keys'], False, fetch_elapsed_ms, cache_age, 0.0
            raise


class EntraTokenValidator:
    """Validates bearer tokens from Microsoft Entra External ID custom authentication extensions"""
    
    def __init__(self):
        # Use the External ID tenant for token validation (where custom auth extension is configured)
        self.tenant_id = os.environ.get('AUTH_EXTENSION_TENANT_ID')
        # Use the custom authentication extension API client ID for token validation
        # This is the App ID that Azure uses as the target resource/audience
        self.client_id = os.environ.get('AUTH_EXTENSION_API_CLIENT_ID')
        
        # External ID (CIAM) uses ciamlogin.com domain, not login.microsoftonline.com
        # Token issuer format: https://{tenant}.ciamlogin.com/{tenant}/v2.0
        self.issuer = f"https://{self.tenant_id}.ciamlogin.com/{self.tenant_id}/v2.0"
        
        # JWKS endpoint for External ID (CIAM) uses ciamlogin.com domain
        self.jwks_uri = f"https://{self.tenant_id}.ciamlogin.com/{self.tenant_id}/discovery/v2.0/keys"
        
        # External ID tokens use simplified audience - just the client ID, not full Application ID URI
        self.audience = self.client_id
        
        # Cache for JWKS client (PyJWT's client has built-in caching, but we add our own layer)
        self._jwks_client = None
    
    @property
    def jwks_client(self):
        """Lazy-load JWKS client for token signature validation"""
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_uri, cache_keys=True, lifespan=3600)
        return self._jwks_client
    
    def validate_token(self, token):
        """
        Validate a bearer token from Microsoft Entra
        
        Args:
            token: JWT bearer token string
            
        Returns:
            tuple: (decoded_payload: dict or None, metrics: dict)
        """
        metrics = {
            'jwks_cache_hit': False,
            'jwks_fetch_ms': 0.0,
            'total_validation_ms': 0.0
        }
        
        validation_start = time.time()
        
        if not self.tenant_id or not self.client_id:
            logger.error("❌ Azure tenant/client ID not configured for token validation")
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            return None, metrics
        
        try:
            # Decode token header to see what key ID it's using
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get('kid')
            logger.info(f"🔍 Token uses signing key: kid={kid}, alg={unverified_header.get('alg')}")
            
            # Decode token payload without verification to see issuer/audience
            unverified_payload = jwt.decode(token, options={"verify_signature": False})
            logger.info(f"🔍 Token claims: iss={unverified_payload.get('iss')[:50]}..., aud={unverified_payload.get('aud')}, exp={unverified_payload.get('exp')}")
            
            # Get JWKS with caching
            jwks_data, cache_hit, fetch_time, cache_age, ttl_remaining = get_cached_jwks(self.jwks_uri)
            metrics['jwks_cache_hit'] = cache_hit
            metrics['jwks_fetch_ms'] = fetch_time
            metrics['jwks_cache_age_s'] = cache_age
            metrics['jwks_ttl_remaining_s'] = ttl_remaining
            
            if not cache_hit:
                available_kids = [key.get('kid') for key in jwks_data.get('keys', [])]
                logger.info(f"📊 JWKS contains {len(available_kids)} keys: {available_kids[:5]}{'...' if len(available_kids) > 5 else ''}")
            
            # Get signing key from JWKS
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate token
            decoded = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True
                }
            )
            
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            
            logger.info(f"✅ Token validated: {metrics['total_validation_ms']:.1f}ms (jwks_cache={'HIT' if cache_hit else 'MISS'})")
            
            return decoded, metrics
        
        except jwt.ExpiredSignatureError:
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            logger.warning("⚠️ Token has expired")
            return None, metrics
        except jwt.InvalidAudienceError:
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            logger.warning(f"⚠️ Invalid audience. Expected: {self.audience}")
            return None, metrics
        except jwt.InvalidIssuerError:
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            logger.warning(f"⚠️ Invalid issuer. Expected: {self.issuer}")
            return None, metrics
        except jwt.InvalidSignatureError:
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            logger.warning("⚠️ Invalid token signature")
            return None, metrics
        except Exception as e:
            metrics['total_validation_ms'] = (time.time() - validation_start) * 1000
            logger.error(f"❌ Token validation error: {e}")
            return None, metrics


# Singleton instance
_token_validator = None


def get_token_validator():
    """Get singleton token validator instance"""
    global _token_validator
    if _token_validator is None:
        _token_validator = EntraTokenValidator()
    return _token_validator


def require_bearer_token(f):
    """
    Decorator to require and validate bearer token for custom authentication extension endpoints
    
    Adds validation metrics to request.entra_metrics for performance tracking
    Captures request start time for true end-to-end wall-clock measurement
    
    Usage:
        @app.route('/api/verify-resident', methods=['POST'])
        @require_bearer_token
        def verify_resident():
            # Token is already validated
            # Access metrics via request.entra_metrics
            # Access true start time via request.request_start_time
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Capture TRUE request start time (before any processing)
        request_start_time = time.time()
        request.request_start_time = request_start_time
        
        # Allow OPTIONS requests without token (CORS preflight)
        if request.method == 'OPTIONS':
            logger.info("🔓 OPTIONS request - bypassing token validation (CORS preflight)")
            return f(*args, **kwargs)
        
        logger.info("🔐 Starting bearer token validation")
        
        # Extract bearer token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            logger.warning("❌ Missing or invalid Authorization header")
            return jsonify({
                "error": "unauthorized",
                "error_description": "Bearer token required"
            }), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        logger.info(f"✅ Bearer token extracted: {len(token)} chars")
        
        # Validate token (returns tuple: decoded_token, metrics)
        validator = get_token_validator()
        logger.info(f"🔍 Validating against audience={validator.audience[:30]}...")
        
        decoded_token, metrics = validator.validate_token(token)
        
        if decoded_token is None:
            logger.error("❌ Token validation FAILED")
            return jsonify({
                "error": "invalid_token",
                "error_description": "The provided token is invalid or expired"
            }), 401
        
        # Log key token claims
        logger.info(f"✅ Token valid: aud={decoded_token.get('aud', 'N/A')[:30]}..., oid={decoded_token.get('oid', 'N/A')[:20]}...")
        
        # Store token and metrics in request context for endpoint access
        request.entra_token = decoded_token
        request.entra_metrics = metrics  # jwks_cache_hit, jwks_fetch_ms, total_validation_ms
        
        logger.info("🎯 Proceeding to endpoint handler")
        return f(*args, **kwargs)
    
    return decorated_function
