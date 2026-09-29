"""Import posting queue from JSON to SQLite."""

import json
import sqlite3
from typing import List, Tuple
from datetime import datetime
from .models import Post
from .validator import PostValidator


class QueueImporter:
    """Import posts from posting_queue.json to SQLite database."""

    def __init__(self, db_path: str, queue_path: str):
        """Initialize importer."""
        self.db_path = db_path
        self.queue_path = queue_path
        self.validator = PostValidator()

    def load_queue(self) -> List[dict]:
        """Load posts from queue JSON file."""
        try:
            with open(self.queue_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('posts', [])
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {self.queue_path}: {e}")

    def import_posts(self, dry_run: bool = False) -> Tuple[int, List[str]]:
        """
        Import posts from queue to database.

        Returns:
            (success_count, error_messages)
        """
        queue_posts = self.load_queue()
        success_count = 0
        error_messages = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            for item in queue_posts:
                try:
                    post = Post.from_dict(item)

                    # Validate
                    is_valid, msg = self.validator.validate_all(post)
                    if not is_valid:
                        error_messages.append(f"Post {post.id}: {msg}")
                        continue

                    if not dry_run:
                        self._insert_post(cursor, post)

                    success_count += 1

                except Exception as e:
                    error_messages.append(f"Error importing post: {str(e)}")

            if not dry_run:
                conn.commit()

        finally:
            conn.close()

        return success_count, error_messages

    def _insert_post(self, cursor: sqlite3.Cursor, post: Post):
        """Insert post into database."""
        now = datetime.now().isoformat()

        images_json = None
        if post.images:
            images_json = json.dumps([img.to_dict() for img in post.images])

        # Insert main post record
        cursor.execute("""
            INSERT OR REPLACE INTO posts (
                id, source, target_account, scheduled_at, main_text, content_hash,
                parts_count, approved, approved_at, approved_by,
                images_json, image_reviewed, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            post.id,
            post.source,
            post.target_account,
            post.scheduled_at,
            post.main_text,
            post.content_hash,
            post.get_parts_count(),
            1 if post.approved else 0,
            post.approved_at,
            post.approved_by,
            images_json,
            1 if post.image_reviewed else 0,
            post.status,
            post.created_at or now,
            post.updated_at or now,
        ))

        # Insert part details
        for part in post.parts:
            cursor.execute("""
                INSERT OR REPLACE INTO post_details (id, post_id, part_number, text, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                f"{post.id}_part{part.part_number}",
                post.id,
                part.part_number,
                part.text,
                now,
            ))
