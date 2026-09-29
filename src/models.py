"""Data models for posting pipeline."""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json


@dataclass
class PostPart:
    """Single part of a post (text)."""
    part_number: int
    text: str


@dataclass
class PostImage:
    """Image metadata for a post."""
    file_path: str
    alt_text: Optional[str] = None

    def to_dict(self):
        return {
            'file_path': self.file_path,
            'alt_text': self.alt_text
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            file_path=d['file_path'],
            alt_text=d.get('alt_text')
        )


@dataclass
class Post:
    """Full post model."""
    id: str
    source: str
    target_account: str
    scheduled_at: str
    main_text: str
    parts: List[PostPart]
    content_hash: str

    # Optional fields
    approved: bool = False
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    images: List[PostImage] = field(default_factory=list)
    image_reviewed: bool = False

    # Status tracking
    status: str = 'draft'
    publishing_status: Optional[str] = None
    published_at: Optional[str] = None
    x_post_id: Optional[str] = None
    response_metadata: Optional[dict] = None

    # Error tracking
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    last_attempt_at: Optional[str] = None

    # Timestamps
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'source': self.source,
            'target_account': self.target_account,
            'scheduled_at': self.scheduled_at,
            'main_text': self.main_text,
            'parts': [{'part_number': p.part_number, 'text': p.text} for p in self.parts],
            'content_hash': self.content_hash,
            'approved': self.approved,
            'approved_at': self.approved_at,
            'approved_by': self.approved_by,
            'images': [img.to_dict() for img in self.images],
            'image_reviewed': self.image_reviewed,
            'status': self.status,
            'publishing_status': self.publishing_status,
            'published_at': self.published_at,
            'x_post_id': self.x_post_id,
            'response_metadata': self.response_metadata,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'last_attempt_at': self.last_attempt_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    @classmethod
    def from_dict(cls, d):
        """Create from dictionary."""
        return cls(
            id=d['id'],
            source=d['source'],
            target_account=d['target_account'],
            scheduled_at=d['scheduled_at'],
            main_text=d['main_text'],
            parts=[PostPart(p['part_number'], p['text']) for p in d['parts']],
            content_hash=d['content_hash'],
            approved=d.get('approved', False),
            approved_at=d.get('approved_at'),
            approved_by=d.get('approved_by'),
            images=[PostImage.from_dict(img) for img in d.get('images', [])],
            image_reviewed=d.get('image_reviewed', False),
            status=d.get('status', 'draft'),
            publishing_status=d.get('publishing_status'),
            published_at=d.get('published_at'),
            x_post_id=d.get('x_post_id'),
            response_metadata=d.get('response_metadata'),
            error_code=d.get('error_code'),
            error_message=d.get('error_message'),
            retry_count=d.get('retry_count', 0),
            last_attempt_at=d.get('last_attempt_at'),
            created_at=d.get('created_at'),
            updated_at=d.get('updated_at'),
        )

    def get_parts_count(self):
        """Get number of parts."""
        return len(self.parts)
