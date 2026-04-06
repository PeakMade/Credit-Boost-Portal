"""
Microsoft Entra bearer token validation for custom authentication extensions
Validates OAuth 2.0 access tokens issued by Microsoft identity platform
"""
import os
import logging
import jwt
import requests
from functools import wraps
from flask import request, jsonify
from jwt import PyJWKClient
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class EntraTokenValidator:
    """Validates bearer tokens from Microsoft Entra External ID custom authentication extensions"""
    
    def __init__(self):
        # Use the External ID tenant for token validation (where custom auth extension is configured)
        self.tenant_id = os.environ.get('AUTH_EXTENSION_TENANT_ID')
        # Use the custom authentication extension API client ID for token validation
        # This is the App ID that Azure uses as the target resource/audience
        self.client_id = os.environ.get('AUTH_EXTENSION_API_CLIENT_ID')
        
        # For custom authentication extensions, the token issuer is the External ID tenant
        self.issuer = f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"
        
        # JWKS endpoint for token signature validation (from External ID tenant)
        self.jwks_uri = f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"
        
        # Audience should match the Application ID URI from the app registration
        # Azure uses the format: api://{hostname}/{client_id}
        self.audience = f"api://creditboostportal-hde4crgcc2hyajh4.eastus-01.azurewebsites.net/{self.client_id}"
        
        # Cache for JWKS client
        self._jwks_client = None
    
    @property
    def jwks_client(self):
        """Lazy-load JWKS client for token signature validation"""
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_uri, cache_keys=True)
        return self._jwks_client
    
    def validate_token(self, token):
        """
        Validate a bearer token from Microsoft Entra
        
        Args:
            token: JWT bearer token string
            
        Returns:
            dict: Decoded token payload if valid
            None: If validation fails
        """
        if not self.tenant_id or not self.client_id:
            logger.error("❌ Azure tenant/client ID not configured for token validation")
            return None
        
        try:
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
            
            logger.info(f"✅ Token validated successfully")
            logger.debug(f"Token claims: appid={decoded.get('appid')}, oid={decoded.get('oid')}")
            
            return decoded
        
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ Token has expired")
            return None
        except jwt.InvalidAudienceError:
            logger.warning(f"⚠️ Invalid audience. Expected: {self.audience}")
            return None
        except jwt.InvalidIssuerError:
            logger.warning(f"⚠️ Invalid issuer. Expected: {self.issuer}")
            return None
        except jwt.InvalidSignatureError:
            logger.warning("⚠️ Invalid token signature")
            return None
        except Exception as e:
            logger.error(f"❌ Token validation error: {e}")
            return None


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
    
    **DIAGNOSTIC MODE: Enhanced logging for isolation testing**
    
    Usage:
        @app.route('/api/verify-resident', methods=['POST'])
        @require_bearer_token
        def verify_resident():
            # Token is already validated, proceed with logic
            pass
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Allow OPTIONS requests without token (CORS preflight)
        if request.method == 'OPTIONS':
            logger.info("🔓 DIAGNOSTIC: OPTIONS request - bypassing token validation (CORS preflight)")
            return f(*args, **kwargs)
        
        logger.info("🔐 DIAGNOSTIC: Starting bearer token validation")
        
        # Extract bearer token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            logger.warning("❌ DIAGNOSTIC: Missing or invalid Authorization header")
            logger.warning(f"   Header value: {auth_header[:30] if auth_header else 'None'}...")
            return jsonify({
                "error": "unauthorized",
                "error_description": "Bearer token required"
            }), 401
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        logger.info(f"✅ DIAGNOSTIC: Bearer token extracted (length: {len(token)} chars)")
        
        # Validate token
        validator = get_token_validator()
        logger.info(f"🔍 DIAGNOSTIC: Token validation config:")
        logger.info(f"   Expected audience: {validator.audience}")
        logger.info(f"   Expected issuer: {validator.issuer}")
        logger.info(f"   Tenant ID: {validator.tenant_id}")
        logger.info(f"   Client ID: {validator.client_id}")
        
        decoded_token = validator.validate_token(token)
        
        if decoded_token is None:
            logger.error("❌ DIAGNOSTIC: Token validation FAILED")
            logger.error("   Reason: See validation errors above")
            return jsonify({
                "error": "invalid_token",
                "error_description": "The provided token is invalid or expired"
            }), 401
        
        # Log token claims safely
        logger.info("✅ DIAGNOSTIC: Token validation SUCCEEDED")
        logger.info(f"   Token claims:")
        logger.info(f"   - aud (audience): {decoded_token.get('aud', 'N/A')}")
        logger.info(f"   - iss (issuer): {decoded_token.get('iss', 'N/A')}")
        logger.info(f"   - appid: {decoded_token.get('appid', 'N/A')}")
        logger.info(f"   - azp (authorized party): {decoded_token.get('azp', 'N/A')}")
        logger.info(f"   - oid (object ID): {decoded_token.get('oid', 'N/A')[:20]}...")
        logger.info(f"   - exp (expires): {decoded_token.get('exp', 'N/A')}")
        
        # Token is valid, store in request context for endpoint to access if needed
        request.entra_token = decoded_token
        
        logger.info("🎯 DIAGNOSTIC: Proceeding to endpoint handler")
        return f(*args, **kwargs)
    
    return decorated_function
