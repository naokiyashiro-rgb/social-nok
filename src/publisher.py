"""Publisher for executing posts via X API."""

import sqlite3
import json
from typing import Optional, Tuple, List
from datetime import datetime
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

    XCLIENT_CLASS = None

    MAX_DAILY_POSTS = 10
    MIN_INTERVAL_SECONDS = 60

    def __init__(self, db_path: str, target_account: str = "@naokichi_nok",
                 xclient=None, dry_run: bool = False):
        """Initialize publisher."""
        self.db_path = db_path
        self.target_account = target_account
        self.dry_run = dry_run
        self.validator = PostValidator(target_account)
        self.xclient = xclient

    def set_xclient_class(self, xclient_class):
        """Set X client class (for injection)."""
        self.XCLIENT_CLASS = xclient_class

    def set_xclient(self, xclient):
        """Set X client instance."""
        self.xclient = xclient

    def verify_credentials(self) -> Tuple[bool, str]:
        """
        Verify API credentials and check target account.

        Returns:
            (success, message)
        """
        if not self.xclient:
            return False, "XClient not initialized"

        try:
            # Verify credentials
            if not self.xclient.verify_credentials():
                return False, "Credential verification failed"

            # Get authenticated user
            user_data = self.xclient.get_authenticated_user()
            auth_username = user_data.get('username')

            if not auth_username:
                return False, "Could not get authenticated username"

            # Check if matches target account
            auth_account = f"@{auth_username}"
            if auth_account != self.target_account:
                return False, f"Wrong account: {auth_account} (expected {self.target_account})"

            return True, f"Authenticated as {auth_account}"

        except Exception as e:
            return False, f"Credential check failed: {str(e)}"

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
            # Check daily limit (main posts only)
            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("SELECT count FROM posting_limits WHERE post_date = ?", (today,))
            result = cursor.fetchone()
            daily_count = result[0] if result else 0

            if daily_count >= self.MAX_DAILY_POSTS:
                error_messages.append(f"Daily limit ({self.MAX_DAILY_POSTS}) main posts reached")
                return 0, error_messages

            # Verify credentials if not dry run
            if not self.dry_run:
                if not self.xclient:
                    error_messages.append("XClient not initialized")
                    return 0, error_messages

                creds_ok, creds_msg = self.verify_credentials()
                if not creds_ok:
                    error_messages.append(f"Credential check: {creds_msg}")
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
                        x_post_ids = self._publish_post(post, cursor)
                        self._update_post_published(cursor, post_id, x_post_ids)
                        self._update_daily_limit(cursor, today, daily_count + 1)
                        daily_count += 1
                    else:
                        # In dry-run, just generate payloads
                        x_post_ids = self._generate_payloads(post)

                    published_count += 1

                except TemporaryAPIError as e:
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
        """Check minimum interval between main posts."""
        cursor.execute("""
            SELECT published_at FROM posts
            WHERE status = 'posted'
            AND parts_count = 1
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

    def _generate_payloads(self, post: Post) -> List[dict]:
        """Generate payloads for dry-run (no actual API calls)."""
        payloads = []

        for part in post.parts:
            payload = {
                'text': part.text,
                'part_number': part.part_number,
            }

            if part.part_number == 1 and post.images:
                # First part can have images
                payload['media_ids'] = ['media_id_placeholder'] * len(post.images)

            if part.part_number > 1:
                # Thread parts are replies
                payload['reply_to_id'] = f'x_post_id_part_{part.part_number - 1}'

            payloads.append(payload)

        return payloads

    def _publish_post(self, post: Post, cursor: sqlite3.Cursor) -> List[str]:
        """
        Publish post via X API (may be multi-part thread).

        Returns:
            List of x_post_ids for each part
        """
        if post.get_parts_count() == 1:
            return self._publish_single_post(post)
        else:
            return self._publish_thread_post(post, cursor)

    def _publish_single_post(self, post: Post) -> List[str]:
        """Publish single (non-thread) post."""
        if not self.xclient:
            raise PublisherError("XClient not initialized")

        # Upload media if present
        media_ids = []
        if post.images:
            try:
                for img in post.images:
                    media_id = self.xclient.upload_media(img.file_path)
                    media_ids.append(media_id)
            except Exception as e:
                raise TemporaryAPIError(f"Media upload failed: {str(e)}")

        # Create post
        try:
            response = self.xclient.create_post(
                text=post.main_text,
                media_ids=media_ids if media_ids else None
            )

            x_post_id = response.get('data', {}).get('id')
            if not x_post_id:
                raise PermanentAPIError("No post ID in response")

            return [x_post_id]

        except Exception as e:
            error_str = str(e)
            if any(code in error_str for code in ['429', '503', 'timeout', 'connection']):
                raise TemporaryAPIError(error_str)
            else:
                raise PermanentAPIError(error_str)

    def _publish_thread_post(self, post: Post, cursor: sqlite3.Cursor) -> List[str]:
        """Publish thread post (2-3 parts with replies)."""
        if not self.xclient:
            raise PublisherError("XClient not initialized")

        x_post_ids = []
        prev_post_id = None

        for i, part in enumerate(post.parts):
            try:
                # Upload media for first part only
                media_ids = []
                if i == 0 and post.images:
                    try:
                        for img in post.images:
                            media_id = self.xclient.upload_media(img.file_path)
                            media_ids.append(media_id)
                    except Exception as e:
                        raise TemporaryAPIError(f"Media upload failed: {str(e)}")

                # Create post
                response = self.xclient.create_post(
                    text=part.text,
                    media_ids=media_ids if media_ids else None,
                    reply_to_id=prev_post_id
                )

                x_post_id = response.get('data', {}).get('id')
                if not x_post_id:
                    raise PermanentAPIError(f"No post ID for part {part.part_number}")

                x_post_ids.append(x_post_id)
                prev_post_id = x_post_id

                # Update post_details with x_post_id for this part
                cursor.execute("""
                    UPDATE post_details SET x_post_id = ?
                    WHERE post_id = ? AND part_number = ?
                """, (x_post_id, post.id, part.part_number))

            except Exception as e:
                error_str = str(e)
                if any(code in error_str for code in ['429', '503', 'timeout', 'connection']):
                    raise TemporaryAPIError(f"Part {part.part_number}: {error_str}")
                else:
                    raise PermanentAPIError(f"Part {part.part_number}: {error_str}")

        return x_post_ids

    def _update_post_published(self, cursor: sqlite3.Cursor, post_id: str, x_post_ids: List[str]):
        """Update post as published."""
        now = datetime.now().isoformat()

        # Main post ID is the first one
        main_x_post_id = x_post_ids[0] if x_post_ids else None

        cursor.execute("""
            UPDATE posts SET
                status = 'posted',
                published_at = ?,
                x_post_id = ?,
                updated_at = ?
            WHERE id = ?
        """, (now, main_x_post_id, now, post_id))

    def _update_daily_limit(self, cursor: sqlite3.Cursor, post_date: str, new_count: int):
        """Update daily posting count (main posts only)."""
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
