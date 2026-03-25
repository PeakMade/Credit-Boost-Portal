"""
Microsoft Entra External ID Authentication Module

This module provides authentication services using Microsoft Entra External ID
(formerly Azure AD B2C) for external user authentication.

Usage:
    from utils.entra_auth import EntraExternalAuth
    
    entra_auth = EntraExternalAuth(app)
    sign_in_url = entra_auth.get_sign_in_url()
"""

import os
import msal
from flask import session
import requests


class EntraExternalAuth:
    """
    Microsoft Entra External ID authentication handler
    
    Provides OAuth 2.0 / OpenID Connect authentication for external users
    including students and residents with any email domain.
    """
    
    def __init__(self, app=None):
        """
        Initialize the Entra External ID authentication handler
        
        Args:
            app: Flask application instance (optional)
        """
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """
        Initialize with Flask app and load configuration from environment
        
        Args:
            app: Flask application instance
        """
        self.client_id = os.environ.get('ENTRA_CLIENT_ID')
        self.client_secret = os.environ.get('ENTRA_CLIENT_SECRET')
        self.tenant_name = os.environ.get('ENTRA_TENANT_NAME')
        self.domain = os.environ.get('ENTRA_DOMAIN')
        
        # Validate required configuration
        if not all([self.client_id, self.client_secret, self.tenant_name, self.domain]):
            raise ValueError(
                "Missing required Entra External ID configuration. "
                "Ensure ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_TENANT_NAME, "
                "and ENTRA_DOMAIN are set in environment variables."
            )
        
        # Build authority URL
        self.authority_base = f"https://{self.domain}/{self.tenant_name}.onmicrosoft.com"
        
        # User flows
        self.signup_signin_flow = os.environ.get('ENTRA_SIGNUP_SIGNIN_FLOW', 'B2C_1_signup_signin')
        self.profile_edit_flow = os.environ.get('ENTRA_PROFILE_EDIT_FLOW', 'B2C_1_profile_edit')
        self.password_reset_flow = os.environ.get('ENTRA_PASSWORD_RESET_FLOW', 'B2C_1_password_reset')
        
        # Redirect URIs
        self.redirect_uri = os.environ.get('ENTRA_REDIRECT_URI', 'http://localhost:5000/auth/callback')
        self.post_logout_redirect = os.environ.get('ENTRA_POST_LOGOUT_REDIRECT_URI', 'http://localhost:5000/')
        
        # Scopes for API access
        self.scope = ["openid", "profile", "email"]
    
    def get_msal_app(self, flow_name=None):
        """
        Create MSAL Confidential Client Application instance
        
        Args:
            flow_name: Name of user flow (defaults to signup/signin flow)
            
        Returns:
            msal.ConfidentialClientApplication instance
        """
        if not flow_name:
            flow_name = self.signup_signin_flow
        
        authority_url = f"{self.authority_base}/{flow_name}"
        
        return msal.ConfidentialClientApplication(
            self.client_id,
            authority=authority_url,
            client_credential=self.client_secret
        )
    
    def get_sign_in_url(self, state=None):
        """
        Generate authorization URL for sign-in/sign-up flow
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            str: Authorization URL to redirect user to
        """
        msal_app = self.get_msal_app()
        
        auth_request_params = {
            "scopes": self.scope,
            "redirect_uri": self.redirect_uri,
            "response_type": "code"
        }
        
        if state:
            auth_request_params["state"] = state
        
        auth_url = msal_app.get_authorization_request_url(**auth_request_params)
        
        return auth_url
    
    def get_edit_profile_url(self, state=None):
        """
        Generate authorization URL for profile editing flow
        
        Args:
            state: Optional state parameter
            
        Returns:
            str: Authorization URL for profile editing
        """
        msal_app = self.get_msal_app(self.profile_edit_flow)
        
        auth_request_params = {
            "scopes": self.scope,
            "redirect_uri": self.redirect_uri,
            "response_type": "code"
        }
        
        if state:
            auth_request_params["state"] = state
        
        return msal_app.get_authorization_request_url(**auth_request_params)
    
    def get_password_reset_url(self, state=None):
        """
        Generate authorization URL for password reset flow
        
        Args:
            state: Optional state parameter
            
        Returns:
            str: Authorization URL for password reset
        """
        msal_app = self.get_msal_app(self.password_reset_flow)
        
        auth_request_params = {
            "scopes": self.scope,
            "redirect_uri": self.redirect_uri,
            "response_type": "code"
        }
        
        if state:
            auth_request_params["state"] = state
        
        return msal_app.get_authorization_request_url(**auth_request_params)
    
    def handle_auth_callback(self, auth_code):
        """
        Handle OAuth callback and exchange authorization code for tokens
        
        Args:
            auth_code: Authorization code from OAuth callback
            
        Returns:
            dict: User information and tokens, or None if authentication failed
            {
                'user_id': str,
                'email': str,
                'name': str,
                'given_name': str,
                'family_name': str,
                'access_token': str,
                'id_token': str,
                'refresh_token': str (optional)
            }
        """
        msal_app = self.get_msal_app()
        
        try:
            result = msal_app.acquire_token_by_authorization_code(
                auth_code,
                scopes=self.scope,
                redirect_uri=self.redirect_uri
            )
        except Exception as e:
            print(f"Token acquisition error: {str(e)}")
            return None
        
        if "error" in result:
            error_desc = result.get('error_description', result.get('error'))
            print(f"Authentication error: {error_desc}")
            return None
        
        # Extract user claims from ID token
        id_token_claims = result.get('id_token_claims', {})
        
        # Build user information dictionary
        user_info = {
            'user_id': id_token_claims.get('sub') or id_token_claims.get('oid'),
            'email': self._extract_email(id_token_claims),
            'name': id_token_claims.get('name', ''),
            'given_name': id_token_claims.get('given_name', ''),
            'family_name': id_token_claims.get('family_name', ''),
            'access_token': result.get('access_token'),
            'id_token': result.get('id_token'),
            'refresh_token': result.get('refresh_token'),
            'token_expires_in': result.get('expires_in', 3600)
        }
        
        return user_info
    
    def _extract_email(self, claims):
        """
        Extract email from ID token claims (handles different claim formats)
        
        Args:
            claims: ID token claims dictionary
            
        Returns:
            str: Email address or empty string
        """
        # Try different email claim formats
        email = claims.get('email')
        if email:
            return email
        
        emails = claims.get('emails', [])
        if emails and len(emails) > 0:
            return emails[0]
        
        signInNames = claims.get('signInNames', [])
        if signInNames and len(signInNames) > 0:
            return signInNames[0]
        
        return ''
    
    def refresh_access_token(self, refresh_token):
        """
        Refresh an expired access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            dict: New tokens, or None if refresh failed
        """
        if not refresh_token:
            return None
        
        msal_app = self.get_msal_app()
        
        try:
            result = msal_app.acquire_token_by_refresh_token(
                refresh_token,
                scopes=self.scope
            )
        except Exception as e:
            print(f"Token refresh error: {str(e)}")
            return None
        
        if "error" in result:
            print(f"Token refresh failed: {result.get('error_description')}")
            return None
        
        return {
            'access_token': result.get('access_token'),
            'refresh_token': result.get('refresh_token'),
            'expires_in': result.get('expires_in', 3600)
        }
    
    def get_sign_out_url(self):
        """
        Generate sign-out URL to log user out of Entra External ID
        
        Returns:
            str: Logout URL
        """
        logout_url = (
            f"{self.authority_base}/{self.signup_signin_flow}/oauth2/v2.0/logout"
            f"?post_logout_redirect_uri={self.post_logout_redirect}"
        )
        return logout_url
    
    def validate_token(self, access_token):
        """
        Validate an access token (basic check - for production use proper JWT validation)
        
        Args:
            access_token: Token to validate
            
        Returns:
            bool: True if token appears valid
        """
        # This is a basic check - in production, use proper JWT validation
        # with signature verification against Microsoft's public keys
        return bool(access_token and len(access_token) > 50)
    
    def get_user_from_graph(self, access_token):
        """
        Get user information from Microsoft Graph API
        Note: Requires appropriate Graph API permissions in app registration
        
        Args:
            access_token: Valid access token with Graph permissions
            
        Returns:
            dict: User profile from Graph API, or None if failed
        """
        if not access_token:
            return None
        
        graph_url = "https://graph.microsoft.com/v1.0/me"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        try:
            response = requests.get(graph_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Graph API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Graph API request failed: {str(e)}")
            return None
    
    def store_tokens_in_session(self, user_info):
        """
        Helper method to store authentication tokens in Flask session
        
        Args:
            user_info: User information dictionary from handle_auth_callback
        """
        session['authenticated'] = True
        session['user_id'] = user_info['user_id']
        session['user_email'] = user_info['email']
        session['user_name'] = user_info['name']
        session['access_token'] = user_info['access_token']
        session['refresh_token'] = user_info.get('refresh_token')
        session.permanent = True
    
    def clear_session(self):
        """
        Clear authentication session data
        """
        keys_to_remove = [
            'authenticated',
            'user_id',
            'user_email',
            'user_name',
            'access_token',
            'refresh_token',
            'role',
            'resident_id'
        ]
        
        for key in keys_to_remove:
            session.pop(key, None)
