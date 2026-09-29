"""X API v2 Client for posting to Twitter/X."""

import os
import requests
from typing import Optional, List, Dict, Any
import json


class XClientError(Exception):
    """X Client error."""
    pass


class XClient:
    """X API v2 client for creating posts and uploading media."""

    API_BASE_URL = "https://api.twitter.com/2"
    UPLOAD_API_BASE_URL = "https://upload.twitter.com/1.1"

    def __init__(self, bearer_token: Optional[str] = None, dry_run: bool = False):
        """
        Initialize X API client.

        Args:
            bearer_token: X API Bearer token (from .env if not provided)
            dry_run: If True, don't actually make POST/PUT requests
        """
        self.dry_run = dry_run

        if bearer_token:
            self.bearer_token = bearer_token
        else:
            self.bearer_token = os.getenv('X_API_BEARER_TOKEN')

        if not self.bearer_token and not dry_run:
            raise XClientError("X_API_BEARER_TOKEN not found in environment")

        self.headers = self._get_headers()
        self._authenticated_user_id = None
        self._authenticated_username = None

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        if not self.bearer_token:
            return {'Content-Type': 'application/json'}

        return {
            'Authorization': f'Bearer {self.bearer_token}',
            'Content-Type': 'application/json',
        }

    def _mask_token(self, token: str) -> str:
        """Mask token for logging (hide actual value)."""
        if not token or len(token) < 10:
            return '***'
        return '***[' + str(len(token)) + 'chars]***'

    def verify_credentials(self) -> bool:
        """
        Verify API credentials by making a simple API call.

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
        Get authenticated user info.

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
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            return data.get('data', {})

        except requests.exceptions.RequestException as e:
            raise XClientError(f"Failed to get authenticated user: {str(e)}")

    def create_post(self, text: str, media_ids: Optional[List[str]] = None,
                   reply_to_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a post on X API v2.

        Args:
            text: Post text (max 280 chars)
            media_ids: List of media IDs from upload_media
            reply_to_id: If provided, create as reply to this post ID

        Returns:
            Response dict with 'data' containing post ID
        """
        if len(text) > 280:
            raise XClientError(f"Post text exceeds 280 characters ({len(text)})")

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

        url = f"{self.API_BASE_URL}/tweets"

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            raise XClientError(f"Failed to create post: {str(e)}")

    def upload_media(self, file_path: str) -> str:
        """
        Upload media file to X API.

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
                response = requests.post(url, headers={'Authorization': self.headers.get('Authorization')},
                                        files=files, timeout=30)

            response.raise_for_status()

            data = response.json()
            media_id = data.get('media_id_string') or str(data.get('media_id'))

            if not media_id:
                raise XClientError("No media ID in response")

            return media_id

        except requests.exceptions.RequestException as e:
            raise XClientError(f"Failed to upload media: {str(e)}")
