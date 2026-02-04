"""State storage for browser session"""
import json
import os
from pathlib import Path
from typing import Optional
import logging
import time
import base64

logger = logging.getLogger(__name__)


class StateStorage:
    """Service for working with browser session state"""
    
    def __init__(self, state_file_path: str):
        self._state_file = Path(state_file_path)
    
    async def load_state(self) -> Optional[dict]:
        """Load saved session state with validation"""
        if not self._state_file.exists():
            logger.info('📂 State file not found')
            return None
        
        try:
            with open(self._state_file, 'r') as f:
                state = json.load(f)
            
            # Validate state before using it
            if not self._is_state_valid(state):
                logger.warning('⚠️  State file exists but is invalid or expired')
                # Optionally delete invalid state
                return None
            
            logger.info('✅ State loaded and validated')
            return state
        except Exception as e:
            logger.warning(f'⚠️  Error loading state: {e}')
            return None
    
    def _is_state_valid(self, state: dict) -> bool:
        """
        Validate that state contains valid, non-expired cookies
        
        Checks:
        1. State has cookies
        2. Critical cookies exist and are not expired
        3. JWT refresh token is valid
        """
        if not state or 'cookies' not in state:
            logger.warning('⚠️  State missing cookies')
            return False
        
        cookies = state.get('cookies', [])
        if not cookies:
            logger.warning('⚠️  State has no cookies')
            return False
        
        current_time = int(time.time())
        
        # Check for critical cookies
        critical_cookies = ['wbx-refresh', 'wbx-validation-key']
        found_cookies = {}
        
        for cookie in cookies:
            name = cookie.get('name')
            if name in critical_cookies:
                found_cookies[name] = cookie
        
        # Verify critical cookies exist
        for critical_name in critical_cookies:
            if critical_name not in found_cookies:
                logger.warning(f'⚠️  Missing critical cookie: {critical_name}')
                return False
            
            cookie = found_cookies[critical_name]
            expires = cookie.get('expires', 0)
            
            # Check if cookie is expired (with 1 hour safety margin)
            safety_margin = 3600  # 1 hour
            if expires > 0 and current_time > (expires - safety_margin):
                logger.warning(f'⚠️  Cookie {critical_name} is expired or will expire soon')
                logger.info(f'   Current time: {current_time}, Expires: {expires}')
                return False
        
        # Additional validation: check JWT refresh token
        refresh_cookie = found_cookies.get('wbx-refresh')
        if refresh_cookie:
            if not self._validate_jwt(refresh_cookie.get('value', '')):
                logger.warning('⚠️  JWT refresh token is invalid')
                return False
        
        logger.info('✅ State validation passed')
        return True
    
    def _validate_jwt(self, token: str) -> bool:
        """
        Basic JWT validation - check if token is well-formed and not expired
        
        Note: This is a basic check. The server may still reject the token
        for other reasons (revoked, wrong signature, etc.)
        """
        if not token:
            return False
        
        try:
            # JWT has 3 parts separated by dots
            parts = token.split('.')
            if len(parts) != 3:
                logger.warning('⚠️  JWT has invalid format')
                return False
            
            # Decode payload (second part)
            # Add padding if necessary
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            
            payload_json = base64.b64decode(payload_b64)
            payload = json.loads(payload_json)
            
            # Check expiration if present
            current_time = int(time.time())
            
            # Check 'iat' (issued at) - token shouldn't be too old
            iat = payload.get('iat', 0)
            if iat > 0:
                # Token older than 90 days might be stale
                max_age = 90 * 24 * 3600  # 90 days
                if current_time - iat > max_age:
                    logger.warning(f'⚠️  JWT token is too old (issued {(current_time - iat) / 86400:.1f} days ago)')
                    return False
            
            logger.info('✅ JWT token structure is valid')
            return True
            
        except Exception as e:
            logger.warning(f'⚠️  Error validating JWT: {e}')
            return False
    
    async def save_state(self, state: dict):
        """Save session state"""
        try:
            # Create directory if it doesn't exist
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._state_file, 'w') as f:
                json.dump(state, f, indent=2)
            logger.info('✅ Session state saved')
        except Exception as e:
            logger.error(f'❌ Error saving state: {e}')
            raise
