"""Publisher for executing posts via X API."""

import sqlite3
import json
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
import time
from .models import Post
from .validator import PostValidator


class PublisherError(Exception):
    """Publisher error."""
    pass


class TemporaryAPIError(Exception):
    """Temporary API error (retryable)."""
    pass


class PermanentAPIError(Exception):
    """Permanent API error (not retryable)."""
    pass


class Publisher:
    """Publish posts via X API."""

    # Import X client (mock or real)
    XCLIENT_CLASS = None  # Will be set at runtime

    MAX_DAILY_POSTS = 10
    MIN_INTERVAL_SECONDS = 60

    def __init__(self, db_path: str, target_account: str = "@naokichi_nok", dry_run: bool = False):
        """Initialize publisher."""
        self.db_path = db_path
        self.target_account = target_account
        self.dry_run = dry_run
        self.validator = PostValidator(target_account)

    def set_xclient_class(self, xclient_class):
        """Set X client class (for injection)."""
        self.XCLIENT_CLASS = xclient_class

    def tick(self) -> Tuple[int, List[str]]:
        """
        Execute one tick of publishing.
        Process posts that are scheduled and ready to publish.

        Returns:
            (published_count, error_messages)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        published_count = 0
        error_messages = []

        try:
            # Check daily limit
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT count FROM posting_limits WHERE post_date = ?", (today,))
            result = cursor.fetchone()
            daily_count = result[0] if result else 0

            if daily_count >= self.MAX_DAILY_POSTS:
                error_messages.append(f"Daily limit ({self.MAX_DAILY_POSTS}) reached")
                return 0, error_messages

            # Get posts ready to publish
            now = datetime.now().isoformat()
            cursor.execute("""
                SELECT id, status FROM posts
                WHERE status IN ('approved', 'scheduled')
                AND scheduled_at <= ?
                ORDER BY scheduled_at ASC
                LIMIT 1
            """, (now,))

            posts_to_publish = cursor.fetchall()

            for post_row in posts_to_publish:
                post_id, status = post_row

                try:
                    # Load full post
                    post = self._load_post(cursor, post_id)

                    # Check interval
                    can_publish, interval_msg = self._check_interval(cursor)
                    if not can_publish:
                        error_messages.append(interval_msg)
                        continue

                    # Publish
                    if not self.dry_run:
                        x_post_id, response_meta = self._publish_post(post)
                        self._update_post_published(cursor, post_id, x_post_id, response_meta)
                        self._update_daily_limit(cursor, today, daily_count + 1)
                        daily_count += 1

                    published_count += 1

                except TemporaryAPIError as e:
                    # Increment retry count, don't fail
                    retry_count = self._get_retry_count(cursor, post_id)
                    if retry_count < 3:
                        self._update_retry(cursor, post_id, str(e))
                        error_messages.append(f"Post {post_id}: Temporary error (retry {retry_count + 1}/3): {str(e)}")
                    else:
                        self._mark_failed(cursor, post_id, "TEMP_ERROR_MAX_RETRIES", str(e))
                        error_messages.append(f"Post {post_id}: Exceeded max retries: {str(e)}")

                except PermanentAPIError as e:
                    self._mark_failed(cursor, post_id, "PERMANENT_ERROR", str(e))
                    error_messages.append(f"Post {post_id}: Permanent error: {str(e)}")

                except Exception as e:
                    self._mark_failed(cursor, post_id, "UNKNOWN_ERROR", str(e))
                    error_messages.append(f"Post {post_id}: Unknown error: {str(e)}")

            if not self.dry_run:
                conn.commit()

        finally:
            conn.close()

        return published_count, error_messages

    def _load_post(self, cursor: sqlite3.Cursor, post_id: str) -> Post:
        """Load post from database."""
        cursor.execute("""
            SELECT id, source, target_account, scheduled_at, main_text, content_hash,
                   parts_count, approved, approved_at, approved_by,
                   images_json, image_reviewed, status, x_post_id, error_code, error_message, retry_count
            FROM posts WHERE id = ?
        """, (post_id,))

        row = cursor.fetchone()
        if not row:
            raise PublisherError(f"Post {post_id} not found")

        (id_, source, target_account, scheduled_at, main_text, content_hash,
         parts_count, approved, approved_at, approved_by,
         images_json, image_reviewed, status, x_post_id, error_code, error_message, retry_count) = row

        # Load parts
        cursor.execute("SELECT part_number, text FROM post_details WHERE post_id = ? ORDER BY part_number", (post_id,))
        part_rows = cursor.fetchall()
        from .models import PostPart, PostImage
        parts = [PostPart(part_num, text) for part_num, text in part_rows]

        # Load images
        images = []
        if images_json:
            for img_dict in json.loads(images_json):
                images.append(PostImage.from_dict(img_dict))

        post = Post(
            id=id_,
            source=source,
            target_account=target_account,
            scheduled_at=scheduled_at,
            main_text=main_text,
            parts=parts,
            content_hash=content_hash,
            approved=bool(approved),
            approved_at=approved_at,
            approved_by=approved_by,
            images=images,
            image_reviewed=bool(image_reviewed),
            status=status,
            x_post_id=x_post_id,
            error_code=error_code,
            error_message=error_message,
            retry_count=retry_count or 0,
        )

        return post

    def _check_interval(self, cursor: sqlite3.Cursor) -> Tuple[bool, str]:
        """Check minimum interval between posts."""
        cursor.execute("""
            SELECT published_at FROM posts
            WHERE status = 'posted'
            ORDER BY published_at DESC LIMIT 1
        """)

        result = cursor.fetchone()
        if not result:
            return True, ""

        last_posted_at_str = result[0]
        last_posted_at = datetime.fromisoformat(last_posted_at_str)
        time_since_last = datetime.now() - last_posted_at

        if time_since_last.total_seconds() < self.MIN_INTERVAL_SECONDS:
            return False, f"Interval too short: {time_since_last.total_seconds()}s (min {self.MIN_INTERVAL_SECONDS}s)"

        return True, ""

    def _publish_post(self, post: Post) -> Tuple[str, dict]:
        """
        Publish post via X API.

        Returns:
            (x_post_id, response_metadata)
        """
        if not self.XCLIENT_CLASS:
            raise PublisherError("XClient not set")

        client = self.XCLIENT_CLASS()

        # Build tweet text (may be multi-part)
        tweet_text = post.main_text
        if len(post.parts) > 1:
            # Add parts to form thread
            tweet_text = post.main_text

        # Prepare media
        media_ids = []
        if post.images:
            for img in post.images:
                try:
                    media_id = client.upload_media(img.file_path)
                    media_ids.append(media_id)
                except Exception as e:
                    raise TemporaryAPIError(f"Failed to upload media: {str(e)}")

        try:
            # Post to X
            response = client.create_post(
                text=tweet_text,
                media_ids=media_ids if media_ids else None
            )

            x_post_id = response.get('id') or response.get('data', {}).get('id')
            if not x_post_id:
                raise PermanentAPIError("No post ID in response")

            return x_post_id, response

        except Exception as e:
            error_str = str(e)
            # Classify error as temporary or permanent
            if any(code in error_str for code in ['429', '503', 'timeout', 'connection']):
                raise TemporaryAPIError(error_str)
            else:
                raise PermanentAPIError(error_str)

    def _update_post_published(self, cursor: sqlite3.Cursor, post_id: str, x_post_id: str, response_meta: dict):
        """Update post as published."""
        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE posts SET
                status = 'posted',
                published_at = ?,
                x_post_id = ?,
                response_metadata_json = ?,
                updated_at = ?
            WHERE id = ?
        """, (now, x_post_id, json.dumps(response_meta), now, post_id))

    def _update_daily_limit(self, cursor: sqlite3.Cursor, post_date: str, new_count: int):
        """Update daily posting count."""
        cursor.execute("""
            INSERT INTO posting_limits (id, post_date, count, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(post_date) DO UPDATE SET count = excluded.count
        """, (f"limit_{post_date}", post_date, new_count, datetime.now().isoformat()))

    def _get_retry_count(self, cursor: sqlite3.Cursor, post_id: str) -> int:
        """Get current retry count."""
        cursor.execute("SELECT retry_count FROM posts WHERE id = ?", (post_id,))
        result = cursor.fetchone()
        return result[0] if result else 0

    def _update_retry(self, cursor: sqlite3.Cursor, post_id: str, error_message: str):
        """Update post with retry attempt."""
        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE posts SET
                retry_count = retry_count + 1,
                error_message = ?,
                last_attempt_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (error_message, now, now, post_id))

    def _mark_failed(self, cursor: sqlite3.Cursor, post_id: str, error_code: str, error_message: str):
        """Mark post as failed."""
        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE posts SET
                status = 'failed',
                error_code = ?,
                error_message = ?,
                last_attempt_at = ?,
                updated_at = ?
            WHERE id = ?
        """, (error_code, error_message, now, now, post_id))
