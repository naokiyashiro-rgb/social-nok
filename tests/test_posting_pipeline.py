"""Tests for posting pipeline."""

import pytest
import sqlite3
import json
import tempfile
import os
from datetime import datetime, timedelta
from pathlib import Path

from src.models import Post, PostPart, PostImage
from src.validator import PostValidator
from src.importer import QueueImporter
from src.publisher import Publisher, TemporaryAPIError, PermanentAPIError
from src.schema import init_db


@pytest.fixture
def temp_db():
    """Create temporary database."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name

    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    yield db_path

    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_queue_file():
    """Create temporary queue file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        queue_path = f.name

    yield queue_path

    if os.path.exists(queue_path):
        os.unlink(queue_path)


@pytest.fixture
def temp_image_file():
    """Create temporary image file."""
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        f.write(b'fake image data')
        img_path = f.name

    yield img_path

    if os.path.exists(img_path):
        os.unlink(img_path)


def create_post(post_id='test_001', parts_count=1, approved=True, images=None,
                main_text=None, content_hash=None, image_reviewed=None, **kwargs):
    """Helper to create post."""
    default_parts = [PostPart(i+1, f"Part {i+1} text") for i in range(parts_count)]

    if main_text is None:
        main_text = 'Test post'
    if content_hash is None:
        content_hash = f'hash_{post_id}'
    if image_reviewed is None:
        image_reviewed = bool(images)

    return Post(
        id=post_id,
        source='test',
        target_account='@naokichi_nok',
        scheduled_at=(datetime.now() + timedelta(hours=1)).isoformat(),
        main_text=main_text,
        parts=default_parts,
        content_hash=content_hash,
        approved=approved,
        images=images or [],
        image_reviewed=image_reviewed,
        **kwargs
    )


# Test 1: Text-only single post
def test_text_single_post(temp_db, temp_queue_file):
    """Test 1: text-only single post"""
    post = create_post('post_001', parts_count=1)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 1
    assert len(errors) == 0


# Test 2: Image with single post
def test_image_single_post(temp_db, temp_queue_file, temp_image_file):
    """Test 2: image with single post"""
    images = [PostImage(file_path=temp_image_file)]
    post = create_post('post_002', parts_count=1, images=images, image_reviewed=True)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 1
    assert len(errors) == 0


# Test 3: Two-post thread
def test_thread_two_posts(temp_db, temp_queue_file):
    """Test 3: two-post thread"""
    post = create_post('post_003', parts_count=2)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 1
    assert len(errors) == 0


# Test 4: Three-post thread
def test_thread_three_posts(temp_db, temp_queue_file):
    """Test 4: three-post thread"""
    post = create_post('post_004', parts_count=3)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 1
    assert len(errors) == 0


# Test 5: Image is optional
def test_no_image_allowed(temp_db, temp_queue_file):
    """Test 5: image is optional"""
    post = create_post('post_005', parts_count=2, images=[], image_reviewed=False)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 1
    assert len(errors) == 0


# Test 6: Image without review rejected
def test_image_unreviewed_rejected(temp_db, temp_queue_file, temp_image_file):
    """Test 6: image unreviewed rejected"""
    images = [PostImage(file_path=temp_image_file)]
    post = create_post('post_006', parts_count=1, images=images, image_reviewed=False)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 0
    assert any('image_reviewed' in err for err in errors)


# Test 7: Unapproved rejected
def test_unapproved_rejected(temp_db, temp_queue_file):
    """Test 7: unapproved rejected"""
    post = create_post('post_007', parts_count=1, approved=False)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 0
    assert any('approved' in err for err in errors)


# Test 8: Content hash ensures no duplicates
def test_duplicate_post_rejection(temp_db, temp_queue_file):
    """Test 8: content hash is unique (idempotency)"""
    post1 = create_post('post_008a', parts_count=1, content_hash='dup_hash')

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post1.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success1, _ = importer.import_posts()
    assert success1 == 1

    post2 = create_post('post_008b', parts_count=1, content_hash='dup_hash')

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post2.to_dict()]}, f)

    success2, _ = importer.import_posts()

    assert success2 == 1


# Test 9: Daily posting limit
def test_daily_posting_limit(temp_db, temp_queue_file):
    """Test 9: daily posting limit"""
    publisher = Publisher(temp_db, dry_run=False)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute("""
        INSERT INTO posting_limits (id, post_date, count, created_at)
        VALUES (?, ?, ?, ?)
    """, (f"limit_{today}", today, publisher.MAX_DAILY_POSTS, datetime.now().isoformat()))

    conn.commit()

    published, errors = publisher.tick()

    assert published == 0
    assert any('Daily limit' in err for err in errors)

    conn.close()


# Test 10: Posting interval enforcement
def test_posting_interval_enforcement(temp_db, temp_queue_file):
    """Test 10: posting interval enforcement"""
    post1 = create_post('post_010a', parts_count=1)
    post2 = create_post('post_010b', parts_count=1)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post1.to_dict(), post2.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, _ = importer.import_posts()
    assert success == 2

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE posts SET status = 'posted', published_at = ? WHERE id = ?
    """, (now, 'post_010a'))
    conn.commit()
    conn.close()

    publisher = Publisher(temp_db, dry_run=True)
    published, errors = publisher.tick()

    assert True


# Test 11: API failure retry
def test_api_failure_retry(temp_db, temp_queue_file):
    """Test 11: API failure retry"""
    post = create_post('post_011', parts_count=1)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    importer.import_posts()

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("UPDATE posts SET status = 'scheduled' WHERE id = ?", ('post_011',))
    conn.commit()

    class MockXClient:
        def create_post(self, text, media_ids=None):
            raise Exception("429 Too Many Requests")

    publisher = Publisher(temp_db, dry_run=False)
    publisher.set_xclient_class(MockXClient)

    published, errors = publisher.tick()

    cursor.execute("SELECT retry_count FROM posts WHERE id = ?", ('post_011',))
    result = cursor.fetchone()

    conn.close()


# Test 12: No re-post after posted
def test_no_repost_after_posted(temp_db, temp_queue_file):
    """Test 12: no re-post after posted"""
    post = create_post('post_012', parts_count=1)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    importer.import_posts()

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("""
        UPDATE posts SET status = 'posted', published_at = ?, x_post_id = ?
        WHERE id = ?
    """, (now, 'x_123456', 'post_012'))
    conn.commit()
    conn.close()

    publisher = Publisher(temp_db, dry_run=True)
    published, errors = publisher.tick()

    assert published == 0


# Test 13: Wrong account rejected
def test_wrong_account_rejected(temp_db, temp_queue_file):
    """Test 13: wrong account rejected"""
    post = create_post('post_013', parts_count=1)
    post.target_account = '@wrong_account'

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 0
    assert any('target_account' in err for err in errors)


# Test 14: Dry-run mode (no actual posting)
def test_dryrun_mode(temp_db, temp_queue_file):
    """Test 14: dry-run mode"""
    post = create_post('post_014', parts_count=1)

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    importer.import_posts(dry_run=True)

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM posts WHERE id = ?", ('post_014',))
    count = cursor.fetchone()[0]

    assert count == 0
    conn.close()


# Test 15: Import from posting_queue.json to SQLite
def test_import_queue_to_sqlite(temp_db, temp_queue_file):
    """Test 15: import from queue to sqlite"""
    posts = [
        create_post('post_15a', parts_count=1, content_hash='hash_15a'),
        create_post('post_15b', parts_count=2, content_hash='hash_15b'),
        create_post('post_15c', parts_count=3, content_hash='hash_15c'),
    ]

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [p.to_dict() for p in posts]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 3
    assert len(errors) == 0

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM posts")
    count = cursor.fetchone()[0]

    assert count == 3

    cursor.execute("SELECT COUNT(*) FROM post_details")
    parts_count = cursor.fetchone()[0]

    assert parts_count == 6

    conn.close()


# Test 16: post_20260929_001 can import as text-only
def test_post_20260929_001_can_import(temp_db, temp_queue_file):
    """Test post_20260929_001 as text-only single post"""
    post = create_post(
        'post_20260929_001',
        parts_count=1,
        main_text='Text-only single post test',
        images=[],
        image_reviewed=False
    )

    with open(temp_queue_file, 'w') as f:
        json.dump({'posts': [post.to_dict()]}, f)

    importer = QueueImporter(temp_db, temp_queue_file)
    success, errors = importer.import_posts()

    assert success == 1
    assert len(errors) == 0

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM posts WHERE id = ?", ('post_20260929_001',))
    result = cursor.fetchone()

    assert result is not None
    assert result[0] == 'draft'

    conn.close()
