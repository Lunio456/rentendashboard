"""Configuration management for RentenDashboard."""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config() -> Dict[str, Any]:
    """
    Load configuration from environment variables and return structured config.
    
    Returns:
        Dict containing configuration sections for oauth, banks, and app settings.
    """
    # Load environment variables from .env file
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded configuration from {env_path}")
    else:
        logger.warning("No .env file found, using environment variables only")
    
    # Defaults mapped from Commerzbank Securities Sandbox swagger
    # host: api-sandbox.commerzbank.com, basePath: /securities-api/v4
    # tokenUrl: https://api-sandbox.commerzbank.com/auth/realms/sandbox/protocol/openid-connect/token
    # authorizationUrl: https://api-sandbox.commerzbank.com/auth/realms/sandbox/protocol/openid-connect/auth
    sandbox_api_base = 'https://api-sandbox.commerzbank.com/securities-api/v4'
    sandbox_auth_url = 'https://api-sandbox.commerzbank.com/auth/realms/sandbox/protocol/openid-connect/auth'
    sandbox_token_url = 'https://api-sandbox.commerzbank.com/auth/realms/sandbox/protocol/openid-connect/token'

    config = {
        'oauth': {
            'timeout': int(os.getenv('OAUTH_TIMEOUT', 30)),
            'retry_attempts': int(os.getenv('OAUTH_RETRY_ATTEMPTS', 3)),
        },
        'banks': {
            'primary': {
                'name': os.getenv('BANK_NAME', 'commerzbank_sandbox'),
                'client_id': os.getenv('BANK_CLIENT_ID'),
                'client_secret': os.getenv('BANK_CLIENT_SECRET'),
                'redirect_uri': os.getenv('BANK_REDIRECT_URI', 'https://localhost:8443/callback'),
                'api_base_url': os.getenv('BANK_API_BASE_URL', sandbox_api_base),
                'authorization_url': os.getenv('BANK_AUTH_URL', sandbox_auth_url),
                'token_url': os.getenv('BANK_TOKEN_URL', sandbox_token_url),
                'scope': os.getenv('BANK_SCOPE', ''),
                # Optional password grant for sandbox convenience
                'username': os.getenv('BANK_USERNAME'),
                'password': os.getenv('BANK_PASSWORD'),
                # API type hint for connector behavior
                'api_type': os.getenv('BANK_API_TYPE', 'commerzbank_securities'),
            }
        },
        'security': {
            'secret_key': os.getenv('SECRET_KEY'),
            'token_encryption_key': os.getenv('TOKEN_ENCRYPTION_KEY'),
        },
        'app': {
            'debug': os.getenv('DEBUG', 'False').lower() == 'true',
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'console_output_format': os.getenv('CONSOLE_OUTPUT_FORMAT', 'table'),
            'data_refresh_interval': int(os.getenv('DATA_REFRESH_INTERVAL', 300)),
            # TLS for local HTTPS callback
            'tls_cert_path': os.getenv('TLS_CERT_PATH', ''),
            'tls_key_path': os.getenv('TLS_KEY_PATH', ''),
        }
    }
    
    # Provide ephemeral defaults for development if secrets are missing
    if not config['security']['secret_key']:
        import secrets as _secrets
        config['security']['secret_key'] = _secrets.token_hex(32)
        logger.warning("No SECRET_KEY found; generated an ephemeral key for this run.")

    # Validate configuration and log warnings for missing optional values
    _validate_config(config)
    
    return config


def _validate_config(config: Dict[str, Any]) -> None:
    """
    Validate that required configuration values are present.
    
    Args:
        config: Configuration dictionary to validate.
        
    Raises:
        ValueError: If required configuration is missing.
    """
    # For sandbox we allow missing client_id/secret and use simulated auth
    if not config['banks']['primary']['client_id'] or not config['banks']['primary']['client_secret']:
        logger.warning("BANK_CLIENT_ID/SECRET not set. Will use simulated OAuth unless sandbox username/password are provided.")
    if not config['banks']['primary']['api_base_url']:
        raise ValueError("BANK_API_BASE_URL missing; cannot proceed.")
    logger.info("Configuration validation completed")


def get_bank_config(bank_name: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get configuration for a specific bank.
    
    Args:
        bank_name: Name of the bank to get config for.
        config: Main configuration dictionary.
        
    Returns:
        Bank configuration dictionary or None if not found.
    """
    return config['banks'].get(bank_name)