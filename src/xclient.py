"""X API v2 Client with OAuth 1.0a User Context for posting."""

import os
import requests
from typing import Optional, List, Dict, Any
import json
import hashlib
import hmac
import base64
import time
import random
import string
from urllib.parse import quote


class XClientError(Exception):
    """X Client error."""
    pass


class XClient:
    """
    X API v2 client with dual authentication modes:
    - OAuth 1.0a User Context (for posting)
    - Bearer Token (for reading only)
    """

    API_BASE_URL = "https://api.twitter.com/2"
    UPLOAD_API_BASE_URL = "https://upload.twitter.com/1.1"
    REQUEST_TOKEN_URL = "https://api.twitter.com/oauth/request_token"
    ACCESS_TOKEN_URL = "https://api.twitter.com/oauth/access_token"
    AUTHORIZE_URL = "https://twitter.com/oauth/authorize"

    def __init__(self,
                 oauth1_mode: bool = False,
                 bearer_token: Optional[str] = None,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 access_token: Optional[str] = None,
                 access_token_secret: Optional[str] = None,
                 dry_run: bool = False):
        """
        Initialize X API client.

        Args:
            oauth1_mode: If True, use OAuth 1.0a for posting. If False, Bearer Token for reading.
            bearer_token: Bearer token (for reading, from X_API_BEARER_TOKEN)
            api_key: OAuth 1.0a API Key (from X_API_KEY)
            api_secret: OAuth 1.0a API Secret (from X_API_SECRET)
            access_token: OAuth 1.0a Access Token (from X_ACCESS_TOKEN)
            access_token_secret: OAuth 1.0a Access Token Secret (from X_ACCESS_TOKEN_SECRET)
            dry_run: If True, don't actually make POST requests
        """
        self.dry_run = dry_run
        self.oauth1_mode = oauth1_mode

        # Bearer Token (read-only)
        if bearer_token:
            self.bearer_token = bearer_token
        else:
            self.bearer_token = os.getenv('X_BEARER_TOKEN')

        # OAuth 1.0a credentials (for posting)
        if api_key:
            self.api_key = api_key
        else:
            self.api_key = os.getenv('X_API_KEY')

        if api_secret:
            self.api_secret = api_secret
        else:
            self.api_secret = os.getenv('X_API_SECRET')

        if access_token:
            self.access_token = access_token
        else:
            self.access_token = os.getenv('X_ACCESS_TOKEN')

        if access_token_secret:
            self.access_token_secret = access_token_secret
        else:
            self.access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')

        # Validate credentials
        if not dry_run:
            if oauth1_mode:
                if not all([self.api_key, self.api_secret, self.access_token, self.access_token_secret]):
                    raise XClientError("OAuth 1.0a credentials not found in environment")
            else:
                if not self.bearer_token:
                    raise XClientError("Bearer token not found in environment")

        self._authenticated_user_id = None
        self._authenticated_username = None

    def _mask_token(self, token: str) -> str:
        """Mask token for logging (hide actual value)."""
        if not token or len(token) < 10:
            return '***'
        return '***[' + str(len(token)) + 'chars]***'

    def _get_bearer_headers(self) -> dict:
        """Get headers for Bearer Token (read-only)."""
        headers = {'Content-Type': 'application/json'}
        if self.bearer_token:
            headers['Authorization'] = f'Bearer {self.bearer_token}'
        return headers

    def _generate_oauth1_header(self, method: str, url: str, params: Optional[Dict] = None) -> str:
        """
        Generate OAuth 1.0a Authorization header.

        Args:
            method: HTTP method (GET, POST)
            url: Request URL
            params: Request body params for POST

        Returns:
            OAuth 1.0a Authorization header string
        """
        # OAuth parameters
        nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
        timestamp = str(int(time.time()))

        oauth_params = {
            'oauth_consumer_key': self.api_key,
            'oauth_token': self.access_token,
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': timestamp,
            'oauth_nonce': nonce,
            'oauth_version': '1.0'
        }

        # Combine all parameters for signature
        all_params = oauth_params.copy()
        if params:
            all_params.update(params)

        # Create parameter string
        param_string = '&'.join(
            f'{quote(str(k), safe="")}={quote(str(v), safe="")}'
            for k, v in sorted(all_params.items())
        )

        # Create signature base string
        base_string = f"{method}&{quote(url, safe='')}&{quote(param_string, safe='')}"

        # Create signing key
        signing_key = f"{quote(self.api_secret, safe='')}&{quote(self.access_token_secret, safe='')}"

        # Generate signature
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode('utf-8'),
                base_string.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')

        oauth_params['oauth_signature'] = signature

        # Build Authorization header
        auth_header = 'OAuth ' + ', '.join(
            f'{k}="{quote(str(v), safe="")}"'
            for k, v in sorted(oauth_params.items())
        )

        return auth_header

    def verify_credentials(self) -> bool:
        """
        Verify API credentials by making a real API call.
        Uses Bearer Token (read-only endpoint).

        Returns:
            True if credentials are valid
        """
        try:
            user_data = self.get_authenticated_user()
            if user_data:
                self._authenticated_user_id = user_data.get('id')
                self._authenticated_username = user_data.get('username')
                return True
            return False
        except Exception as e:
            raise XClientError(f"Credential verification failed: {str(e)}")

    def get_authenticated_user(self) -> Dict[str, Any]:
        """
        Get authenticated user info via real X API.
        Uses Bearer Token (app-only or user context).

        Returns:
            User dict with 'id' and 'username'
        """
        if self.dry_run:
            return {
                'id': '1234567890',
                'username': 'naokichi_nok',
                'name': 'Test User'
            }

        url = f"{self.API_BASE_URL}/users/me"
        params = {
            'user.fields': 'username,created_at,public_metrics'
        }

        try:
            headers = self._get_bearer_headers()
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            result = data.get('data', {})

            return result

        except requests.exceptions.RequestException as e:
            raise XClientError(f"Failed to get authenticated user: {str(e)}")

    def create_post(self, text: str, media_ids: Optional[List[str]] = None,
                   reply_to_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a post via X API v2 using OAuth 1.0a User Context.

        Args:
            text: Post text (max 280 chars)
            media_ids: List of media IDs from upload_media
            reply_to_id: If provided, create as reply to this post ID

        Returns:
            Response dict with 'data' containing post ID
        """
        if len(text) > 280:
            raise XClientError(f"Post text exceeds 280 characters ({len(text)})")

        url = f"{self.API_BASE_URL}/tweets"

        payload = {'text': text}

        if reply_to_id:
            payload['reply'] = {'in_reply_to_tweet_id': reply_to_id}

        if media_ids:
            payload['media'] = {
                'media_ids': media_ids
            }

        if self.dry_run:
            return {
                'data': {
                    'id': '9999999999999999999',
                    'text': text
                }
            }

        try:
            # Use OAuth 1.0a for posting
            if self.oauth1_mode:
                auth_header = self._generate_oauth1_header('POST', url)
                headers = {
                    'Authorization': auth_header,
                    'Content-Type': 'application/json'
                }
            else:
                # Fallback to Bearer Token (not ideal for posting but supported in some cases)
                headers = self._get_bearer_headers()

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            raise XClientError(f"Failed to create post: {str(e)}")

    def upload_media(self, file_path: str) -> str:
        """
        Upload media file to X API.
        Requires OAuth 1.0a User Context.

        Args:
            file_path: Path to image file

        Returns:
            Media ID string
        """
        if not os.path.exists(file_path):
            raise XClientError(f"Media file not found: {file_path}")

        if self.dry_run:
            return 'media_id_dry_run_12345'

        url = f"{self.UPLOAD_API_BASE_URL}/media/upload.json"

        try:
            with open(file_path, 'rb') as f:
                files = {'media_data': f}

                # Use OAuth 1.0a for media upload
                if self.oauth1_mode:
                    auth_header = self._generate_oauth1_header('POST', url)
                    headers = {'Authorization': auth_header}
                else:
                    headers = {'Authorization': f'Bearer {self.bearer_token}'}

                response = requests.post(url, headers=headers, files=files, timeout=30)

            response.raise_for_status()

            data = response.json()
            media_id = data.get('media_id_string') or str(data.get('media_id'))

            if not media_id:
                raise XClientError("No media ID in response")

            return media_id

        except requests.exceptions.RequestException as e:
            raise XClientError(f"Failed to upload media: {str(e)}")
