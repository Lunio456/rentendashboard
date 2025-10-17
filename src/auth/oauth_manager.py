"""OAuth authentication manager for bank API connections."""

import asyncio
import logging
import json
import secrets
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode
from cryptography.fernet import Fernet
import aiohttp
from authlib.integrations.base_client import OAuthError
import webbrowser
from .callback_server import run_https_callback_server

logger = logging.getLogger(__name__)


class OAuthManager:
    """Manages OAuth 2.0 authentication flow for bank APIs."""
    
    def __init__(self, oauth_config: Dict[str, Any]):
        """
        Initialize OAuth manager with configuration.
        
        Args:
            oauth_config: OAuth configuration dictionary containing timeout and retry settings.
        """
        self.config = oauth_config
        self.timeout = oauth_config.get('timeout', 30)
        self.retry_attempts = oauth_config.get('retry_attempts', 3)
        
        # Initialize encryption for token storage
        self._encryption_key = self._generate_encryption_key()
        self._cipher_suite = Fernet(self._encryption_key)
        
        # Store tokens in memory (in production, use secure storage)
        self._tokens: Dict[str, bytes] = {}
        
        logger.info("OAuth Manager initialized")
    
    def _generate_encryption_key(self) -> bytes:
        """Generate or retrieve encryption key for token storage.

        In production load from env configuration (TOKEN_ENCRYPTION_KEY). If not
        present, generate a volatile key valid for this process only.
        """
        try:
            # Try to reuse key from environment if provided as base64 urlsafe key
            import os
            key = os.getenv('TOKEN_ENCRYPTION_KEY')
            if key:
                # If the provided key looks like a valid Fernet key (urlsafe base64), use it.
                try:
                    from base64 import urlsafe_b64decode

                    _ = urlsafe_b64decode(key)
                    return key.encode('utf-8')
                except Exception:
                    # Derive a valid 32-byte key from the provided string using SHA256
                    import hashlib
                    from base64 import urlsafe_b64encode

                    digest = hashlib.sha256(key.encode('utf-8')).digest()
                    derived = urlsafe_b64encode(digest)
                    logger.warning("TOKEN_ENCRYPTION_KEY provided but not valid Fernet key; derived key from value.")
                    return derived
        except Exception:
            pass
        return Fernet.generate_key()
    
    def _encrypt_token(self, token: Dict[str, Any]) -> bytes:
        """Encrypt token data for secure storage."""
        token_str = json.dumps(token).encode('utf-8')
        return self._cipher_suite.encrypt(token_str)
    
    def _decrypt_token(self, encrypted_token: bytes) -> Dict[str, Any]:
        """Decrypt stored token data."""
        token_str = self._cipher_suite.decrypt(encrypted_token).decode('utf-8')
        return json.loads(token_str)
    
    def generate_authorization_url(self, bank_config: Dict[str, Any]) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL for bank login.
        
        Args:
            bank_config: Bank-specific configuration including client_id, redirect_uri, etc.
            
        Returns:
            Tuple of (authorization_url, state) where state is used for CSRF protection.
        """
        # Generate state parameter for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Prepare OAuth parameters
        params = {
            'response_type': 'code',
            'client_id': bank_config['client_id'],
            'redirect_uri': bank_config['redirect_uri'],
            'state': state,
        }
        # Include scope only if configured; some providers reject unknown scopes
        scope = bank_config.get('scope')
        if scope:
            params['scope'] = scope
        
        authorization_url = f"{bank_config['authorization_url']}?{urlencode(params)}"
        
        logger.info(f"Generated authorization URL for bank: {bank_config['name']}")
        return authorization_url, state
    
    async def exchange_code_for_token(
        self, 
        authorization_code: str, 
        bank_config: Dict[str, Any],
        state: str
    ) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Args:
            authorization_code: Authorization code received from bank.
            bank_config: Bank-specific configuration.
            state: State parameter for CSRF validation.
            
        Returns:
            Dictionary containing access token and related information.
            
        Raises:
            OAuthError: If token exchange fails.
        """
        token_data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'redirect_uri': bank_config['redirect_uri'],
            'client_id': bank_config['client_id'],
            'client_secret': bank_config['client_secret'],
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            try:
                async with session.post(
                    bank_config['token_url'], 
                    data=token_data, 
                    headers=headers
                ) as response:
                    if response.status == 200:
                        token_response = await response.json()
                        
                        # Store encrypted token
                        bank_name = bank_config['name']
                        encrypted_token = self._encrypt_token(token_response)
                        self._tokens[bank_name] = encrypted_token
                        
                        logger.info(f"Successfully obtained token for {bank_name}")
                        return token_response
                    else:
                        error_text = await response.text()
                        raise OAuthError(f"Token exchange failed: {response.status} - {error_text}")
                        
            except asyncio.TimeoutError:
                raise OAuthError("Token exchange timed out")
            except Exception as e:
                logger.error(f"Token exchange error: {e}")
                raise OAuthError(f"Token exchange failed: {str(e)}")

    async def password_grant_for_token(self, bank_config: Dict[str, Any]) -> Dict[str, Any]:
        """Use OAuth2 password grant to obtain a token (sandbox convenience only).

        Requires bank_config to include 'username' and 'password'.
        """
        if not bank_config.get('username') or not bank_config.get('password'):
            raise OAuthError("Username/password not provided for password grant")

        data = {
            'grant_type': 'password',
            'username': bank_config['username'],
            'password': bank_config['password'],
            'client_id': bank_config['client_id'],
            'client_secret': bank_config['client_secret'],
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
        }
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.post(bank_config['token_url'], data=data, headers=headers) as resp:
                if resp.status == 200:
                    token_response = await resp.json()
                    bank_name = bank_config['name']
                    self._tokens[bank_name] = self._encrypt_token(token_response)
                    logger.info(f"Obtained token via password grant for {bank_name}")
                    return token_response
                else:
                    txt = await resp.text()
                    raise OAuthError(f"Password grant failed: {resp.status} - {txt}")
    
    async def refresh_token(self, bank_name: str, bank_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Args:
            bank_name: Name of the bank to refresh token for.
            bank_config: Bank-specific configuration.
            
        Returns:
            Dictionary containing new access token.
            
        Raises:
            OAuthError: If token refresh fails.
        """
        if bank_name not in self._tokens:
            raise OAuthError(f"No stored token found for {bank_name}")
        
        try:
            current_token = self._decrypt_token(self._tokens[bank_name])
            refresh_token = current_token.get('refresh_token')
            
            if not refresh_token:
                raise OAuthError(f"No refresh token available for {bank_name}")
            
            token_data = {
                'grant_type': 'refresh_token',
                'refresh_token': refresh_token,
                'client_id': bank_config['client_id'],
                'client_secret': bank_config['client_secret'],
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(
                    bank_config['token_url'], 
                    data=token_data, 
                    headers=headers
                ) as response:
                    if response.status == 200:
                        token_response = await response.json()
                        
                        # Store updated encrypted token
                        encrypted_token = self._encrypt_token(token_response)
                        self._tokens[bank_name] = encrypted_token
                        
                        logger.info(f"Successfully refreshed token for {bank_name}")
                        return token_response
                    else:
                        error_text = await response.text()
                        raise OAuthError(f"Token refresh failed: {response.status} - {error_text}")
                        
        except Exception as e:
            logger.error(f"Token refresh error for {bank_name}: {e}")
            raise OAuthError(f"Token refresh failed: {str(e)}")

    async def authorization_code_flow(self, bank_config: Dict[str, Any], app_config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a complete auth code flow with local HTTPS callback."""
        auth_url, state = self.generate_authorization_url(bank_config)
        # Start callback server
        redirect = bank_config['redirect_uri']
        parsed = __import__('urllib.parse').parse.urlparse(redirect)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 8443
        cert = app_config.get('tls_cert_path')
        key = app_config.get('tls_key_path')
        if not cert or not key:
            raise OAuthError("TLS_CERT_PATH/TLS_KEY_PATH must be configured for HTTPS redirect")

        # Log and try to open browser
        logger.info("Open this URL to authenticate (copy/paste if it doesn't open automatically): %s", auth_url)
        try:
            opened = webbrowser.open(auth_url)
            if not opened:
                logger.warning("Couldn't launch a browser automatically. Please copy/paste the URL above into your browser.")
        except Exception as e:
            logger.warning("Browser launch failed: %s. Please copy/paste the URL above into your browser.", e)

        # Await callback
        result = await run_https_callback_server(host, port, cert, key)
        if result.get('error'):
            raise OAuthError(f"Authorization error: {result.get('error_description') or result['error']}")
        code = result.get('code')
        if not code:
            raise OAuthError("No authorization code received")
        token = await self.exchange_code_for_token(code, bank_config, state)
        return token
    
    def get_access_token(self, bank_name: str) -> Optional[str]:
        """
        Get current access token for a bank.
        
        Args:
            bank_name: Name of the bank.
            
        Returns:
            Access token string or None if not available.
        """
        if bank_name not in self._tokens:
            return None
        
        try:
            token_data = self._decrypt_token(self._tokens[bank_name])
            return token_data.get('access_token')
        except Exception as e:
            logger.error(f"Error retrieving token for {bank_name}: {e}")
            return None
    
    def is_token_valid(self, bank_name: str) -> bool:
        """
        Check if stored token is valid and not expired.
        
        Args:
            bank_name: Name of the bank.
            
        Returns:
            True if token is valid, False otherwise.
        """
        # This is a simplified check - in production, verify token expiration
        return bank_name in self._tokens and self.get_access_token(bank_name) is not None
    
    async def simulate_oauth_flow(self, bank_name: str, bank_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulate OAuth flow for development/testing purposes.
        
        In production, this would involve actual user authentication through the bank's OAuth flow.
        This method creates a mock token for testing the rest of the application.
        
        Args:
            bank_name: Name of the bank.
            bank_config: Bank configuration.
            
        Returns:
            Mock token dictionary.
        """
        logger.warning(f"SIMULATION: Simulating OAuth flow for {bank_name} - NOT FOR PRODUCTION")
        
        # Generate a mock token for development
        mock_token = {
            'access_token': f'mock_access_token_{secrets.token_urlsafe(16)}',
            'token_type': 'Bearer',
            'expires_in': 3600,
            'refresh_token': f'mock_refresh_token_{secrets.token_urlsafe(16)}',
            'scope': 'accounts transactions balances'
        }
        
        # Store the mock token
        encrypted_token = self._encrypt_token(mock_token)
        self._tokens[bank_name] = encrypted_token
        
        logger.info(f"Mock OAuth token generated for {bank_name}")
        return mock_token