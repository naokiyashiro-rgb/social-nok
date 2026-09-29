"""Command-line interface for posting pipeline."""

import sys
import argparse
import sqlite3
from pathlib import Path
from .schema import init_db
from .importer import QueueImporter
from .publisher import Publisher


def init_db_cmd(args):
    """Initialize database."""
    db_path = args.db
    print(f"Initializing database at {db_path}...")

    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    print("✓ Database initialized")


def import_queue_cmd(args):
    """Import queue from JSON."""
    db_path = args.db
    queue_path = args.queue

    print(f"Importing from {queue_path} to {db_path}...")

    # Ensure database exists
    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    importer = QueueImporter(db_path, queue_path)
    success_count, errors = importer.import_posts(dry_run=args.dry_run)

    print(f"✓ Imported {success_count} posts")

    if errors:
        print(f"\n⚠️  {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")

    if args.dry_run:
        print("\n(dry-run mode: no changes committed)")


def publisher_tick_cmd(args):
    """Run publisher tick."""
    db_path = args.db

    conn = sqlite3.connect(db_path)
    init_db(conn)
    conn.close()

    from .xclient import XClient

    # Initialize X client
    try:
        xclient = XClient(dry_run=args.dry_run)
    except Exception as e:
        print(f"❌ XClient initialization failed: {str(e)}")
        return 1

    publisher = Publisher(db_path, xclient=xclient, dry_run=args.dry_run)

    if args.live and not args.dry_run:
        print("🔴 LIVE MODE - Posts will be sent to X API")
    else:
        print("🟢 DRY-RUN MODE - No actual posts sent")

    published_count, errors = publisher.tick()

    print(f"✓ Published {published_count} posts")

    if errors:
        print(f"\n⚠️  {len(errors)} errors/warnings:")
        for err in errors:
            print(f"  - {err}")


def status_cmd(args):
    """Show posting status."""
    db_path = args.db

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Count by status
    statuses = ['draft', 'approved', 'scheduled', 'publishing', 'posted', 'failed']

    print("📊 Posting Status:")
    print()

    for status in statuses:
        cursor.execute("SELECT COUNT(*) FROM posts WHERE status = ?", (status,))
        count = cursor.fetchone()[0]
        print(f"  {status:12} : {count:3} posts")

    print()

    # Show next scheduled post
    cursor.execute("""
        SELECT id, scheduled_at, main_text
        FROM posts
        WHERE status IN ('approved', 'scheduled')
        ORDER BY scheduled_at ASC
        LIMIT 1
    """)

    result = cursor.fetchone()
    if result:
        post_id, scheduled_at, text = result
        text_preview = (text[:50] + '...') if len(text) > 50 else text
        print(f"📌 Next: {post_id} at {scheduled_at}")
        print(f"   {text_preview}")

    conn.close()


def auth_cmd(args):
    """Check X API credentials."""
    from .xclient import XClient

    try:
        xclient = XClient(dry_run=False)
    except Exception as e:
        print(f"❌ XClient initialization failed: {str(e)}")
        print(f"   Make sure X_API_BEARER_TOKEN is set in .env")
        return 1

    db_path = args.db
    publisher = Publisher(db_path, xclient=xclient, dry_run=False)

    print("🔐 Verifying X API credentials...")
    print()

    success, message = publisher.verify_credentials()

    if success:
        print(f"✅ {message}")
        user = xclient.get_authenticated_user()
        print(f"   User ID: {user.get('id')}")
        print(f"   Username: @{user.get('username')}")
        print(f"   Name: {user.get('name', 'N/A')}")
        return 0
    else:
        print(f"❌ {message}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='NOK Social Posting Pipeline')

    parser.add_argument('--db', default='data/publisher.sqlite3', help='Database path')
    parser.add_argument('--queue', default='handoff/posting_queue.json', help='Queue JSON path')

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # init-db command
    init_parser = subparsers.add_parser('init-db', help='Initialize database')
    init_parser.set_defaults(func=init_db_cmd)

    # import-queue command
    import_parser = subparsers.add_parser('import-queue', help='Import queue from JSON')
    import_parser.add_argument('--dry-run', action='store_true', help='Dry run mode')
    import_parser.set_defaults(func=import_queue_cmd)

    # publisher tick command
    pub_parser = subparsers.add_parser('publisher', help='Publisher operations')
    pub_subparsers = pub_parser.add_subparsers(dest='pub_command')

    tick_parser = pub_subparsers.add_parser('tick', help='Run one tick of publishing')
    tick_parser.add_argument('--live', action='store_true', help='Live mode (actually post to X)')
    tick_parser.add_argument('--dry-run', action='store_true', dest='dry_run', help='Dry run mode')
    tick_parser.set_defaults(func=publisher_tick_cmd)

    # status command
    status_parser = subparsers.add_parser('status', help='Show posting status')
    status_parser.set_defaults(func=status_cmd)

    # auth command
    auth_parser = subparsers.add_parser('auth', help='Check X API credentials')
    auth_parser.set_defaults(func=auth_cmd)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    try:
        result = args.func(args)
        if result is None:
            result = 0
        sys.exit(result)
    except Exception as e:
        print(f"❌ Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
