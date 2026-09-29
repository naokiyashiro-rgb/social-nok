"""Validator for posting pipeline."""

import os
from typing import List, Tuple
from .models import Post


class ValidationError(Exception):
    """Validation error."""
    pass


class PostValidator:
    """Validator for posts."""

    MAX_DAILY_POSTS = 10
    MIN_INTERVAL_MINUTES = 5

    def __init__(self, target_account: str = "@naokichi_nok"):
        """Initialize validator."""
        self.target_account = target_account

    def validate_required_fields(self, post: Post) -> Tuple[bool, str]:
        """Validate required fields."""
        if not post.id:
            return False, "Missing 'id'"
        if not post.scheduled_at:
            return False, "Missing 'scheduled_at'"
        if not post.approved:
            return False, "Post not approved (approved=false)"
        if not post.main_text:
            return False, "Missing 'main_text'"
        if not post.source:
            return False, "Missing 'source'"
        if not post.target_account:
            return False, "Missing 'target_account'"
        if not post.content_hash:
            return False, "Missing 'content_hash'"

        return True, ""

    def validate_parts_count(self, post: Post) -> Tuple[bool, str]:
        """Validate parts count (1-3)."""
        parts_count = post.get_parts_count()
        if parts_count < 1 or parts_count > 3:
            return False, f"Invalid parts_count: {parts_count} (must be 1-3)"
        return True, ""

    def validate_images_exist(self, post: Post) -> Tuple[bool, str]:
        """Validate image files exist."""
        if not post.images:
            return True, ""

        for img in post.images:
            if not os.path.exists(img.file_path):
                return False, f"Image file not found: {img.file_path}"

        return True, ""

    def validate_image_reviewed(self, post: Post) -> Tuple[bool, str]:
        """Validate image_reviewed flag when images exist."""
        if post.images and not post.image_reviewed:
            return False, "Images provided but image_reviewed=false"
        return True, ""

    def validate_target_account(self, post: Post) -> Tuple[bool, str]:
        """Validate target account matches expected account."""
        if post.target_account != self.target_account:
            return False, f"Wrong target_account: {post.target_account} (expected {self.target_account})"
        return True, ""

    def validate_all(self, post: Post) -> Tuple[bool, str]:
        """Validate all rules."""
        validators = [
            self.validate_required_fields,
            self.validate_parts_count,
            self.validate_images_exist,
            self.validate_image_reviewed,
            self.validate_target_account,
        ]

        for validator in validators:
            is_valid, msg = validator(post)
            if not is_valid:
                return False, msg

        return True, ""
