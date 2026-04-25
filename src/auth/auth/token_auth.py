from aiohttp import web
# Auto-imports for extracted module
from collections import deque
from typing import Dict
from typing import List
from typing import Optional
import base64
import hashlib
import hmac
import json
import os
import time
import uuid
try:
    import jwt
    HAS_JWT = True
except ImportError:
    HAS_JWT = False


class TokenAuth:
    """JWT-based token auth with rotation for P2P security.
    Replaces simple HMAC with:
    - Signed JWT tokens (HS256 or Ed25519)
    - Automatic token rotation every N hours
    - Token blacklist for revocation
    - Fallback to HMAC for v3.2 compatibility
    """
    
    def __init__(self, secret: str, token_lifetime: int = 86400,
                 rotation_interval: int = 3600):
        self.secret = secret.encode() if isinstance(secret, str) else secret
        self.token_lifetime = token_lifetime  # 24h default
        self.rotation_interval = rotation_interval  # Rotate signing key every hour
        self.current_key_id = str(uuid.uuid4())[:8]
        self.key_history: deque = deque(maxlen=5)  # Keep last 5 keys for validation
        self.blacklisted_tokens: set = set()
        self.key_history.append({
            'key_id': self.current_key_id,
            'secret': self.secret,
            'created': time.time()
        })
        self.last_rotation = time.time()
    
    def _check_rotation(self):
        """Rotate signing key if interval exceeded"""
        if time.time() - self.last_rotation >= self.rotation_interval:
            old_key_id = self.current_key_id
            self.current_key_id = str(uuid.uuid4())[:8]
            new_secret = f"{self.secret.decode()}-{self.current_key_id}".encode()
            self.key_history.append({
                'key_id': self.current_key_id,
                'secret': new_secret,
                'created': time.time()
            })
            self.secret = new_secret
            self.last_rotation = time.time()
            logger.info(f"🔑 Token key rotated: {old_key_id} → {self.current_key_id}")
    
    def generate_token(self, node_name: str, scopes: List[str] = None) -> str:
        """Generate a JWT token for a peer"""
        self._check_rotation()
        now = time.time()
        payload = {
            'sub': node_name,
            'iat': now,
            'exp': now + self.token_lifetime,
            'kid': self.current_key_id,
            'scopes': scopes or ['query', 'sync', 'ping']
        }
        if HAS_JWT:
            token = jwt.encode(payload, self.secret, algorithm='HS256')
        else:
            # Fallback: base64-encoded payload + HMAC signature
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
            sig = hmac.new(self.secret, payload_b64.encode(), hashlib.sha256).hexdigest()
            token = f"{payload_b64}.{sig}"
        return token
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify a JWT token. Returns payload if valid, None otherwise."""
        if token in self.blacklisted_tokens:
            return None
        
        # Try current key first, then history
        for key_entry in reversed(list(self.key_history)):
            try:
                if HAS_JWT:
                    payload = jwt.decode(token, key_entry['secret'], 
                                        algorithms=['HS256'],
                                        options={'require': ['exp', 'sub']})
                else:
                    # Fallback verification
                    parts = token.split('.')
                    if len(parts) != 2:
                        continue
                    payload_b64, sig = parts
                    expected_sig = hmac.new(key_entry['secret'], 
                                           payload_b64.encode(), 
                                           hashlib.sha256).hexdigest()
                    if not hmac.compare_digest(sig, expected_sig):
                        continue
                    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                    
                # Check expiry
                if payload.get('exp', 0) < time.time():
                    continue
                return payload
            except Exception:
                continue
        return None
    
    def revoke_token(self, token: str):
        """Blacklist a token"""
        self.blacklisted_tokens.add(token)
    
    def auth_headers(self, node_name: str, path: str) -> Dict[str, str]:
        """Generate auth headers for outgoing requests"""
        token = self.generate_token(node_name)
        return {
            'Authorization': f'Bearer {token}',
            'X-UnityBrain-Version': '3.3.0'
        }
    
    def verify_request(self, request: web.Request, secret: str = None) -> Optional[Dict]:
        """Verify an incoming request's auth. Returns payload or None."""
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
            payload = self.verify_token(token)
            if payload:
                return payload
            # JWT failed — fall through to HMAC below
        # Fallback: verify legacy HMAC headers for v3.2 compat
        hmac_auth = request.headers.get('X-UnityBrain-Auth', '')
        hmac_ts = request.headers.get('X-UnityBrain-TS', '')
        if hmac_auth and hmac_ts and secret:
            try:
                ts = float(hmac_ts)
                if abs(time.time() - ts) > 300:
                    return None
                # Use request.path for consistent signing (not full URL which varies by host)
                path = request.path
                msg = f"{path}:{hmac_ts}"
                expected = hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
                if hmac.compare_digest(hmac_auth, expected):
                    return {'sub': 'legacy', 'scopes': ['query', 'sync', 'ping']}
            except (ValueError, TypeError):
                return None
        return None


# ============================================================================
# ============== DYNAMIC DISCOVERY (Point 3) ================================
# ============================================================================
