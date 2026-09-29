"""Database schema for NOK Social posting pipeline."""

POSTS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    target_account TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',

    main_text TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,

    parts_count INTEGER NOT NULL,

    approved BOOLEAN NOT NULL DEFAULT 0,
    approved_at TEXT,
    approved_by TEXT,

    images_json TEXT,
    image_reviewed BOOLEAN DEFAULT 0,

    publishing_status TEXT,
    published_at TEXT,
    x_post_id TEXT UNIQUE,
    response_metadata_json TEXT,

    error_code TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    last_attempt_at TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    CONSTRAINT valid_status CHECK (status IN ('draft', 'approved', 'scheduled', 'publishing', 'posted', 'failed')),
    CONSTRAINT valid_parts_count CHECK (parts_count >= 1 AND parts_count <= 3),
    CONSTRAINT valid_retry_count CHECK (retry_count >= 0 AND retry_count <= 3)
)
"""

POSTS_DETAILS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS post_details (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    part_number INTEGER NOT NULL,
    text TEXT NOT NULL,
    x_post_id TEXT UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    UNIQUE (post_id, part_number)
)
"""

POSTING_LIMITS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS posting_limits (
    id TEXT PRIMARY KEY,
    post_date TEXT NOT NULL UNIQUE,
    count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    CONSTRAINT valid_daily_limit CHECK (count >= 0 AND count <= 10)
)
"""

POSTING_INTERVALS_TABLE_SCHEMA = """
CREATE TABLE IF NOT EXISTS posting_intervals (
    id TEXT PRIMARY KEY,
    last_post_id TEXT NOT NULL,
    last_posted_at TEXT NOT NULL,
    FOREIGN KEY (last_post_id) REFERENCES posts(id) ON DELETE SET NULL
)
"""

def init_db(conn):
    """Initialize database schema."""
    cursor = conn.cursor()
    cursor.execute(POSTS_TABLE_SCHEMA)
    cursor.execute(POSTS_DETAILS_TABLE_SCHEMA)
    cursor.execute(POSTING_LIMITS_TABLE_SCHEMA)
    cursor.execute(POSTING_INTERVALS_TABLE_SCHEMA)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_posts_scheduled_at ON posts(scheduled_at)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_posts_target_account ON posts(target_account)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_post_details_post_id ON post_details(post_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_posting_limits_date ON posting_limits(post_date)
    """)

    conn.commit()
