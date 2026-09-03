import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BASE_DIR / "instance"
DATABASE_PATH = INSTANCE_DIR / "lanshare.db"


def get_db_connection():
    """Create and return a connection to the LANShare database."""
    INSTANCE_DIR.mkdir(exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def _column_exists(connection, table, column):
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _migrate_files_table(connection):
    """Add the sha256 column to files if it doesn't exist yet (safe on existing DBs)."""
    if not _column_exists(connection, "files", "sha256"):
        connection.execute("ALTER TABLE files ADD COLUMN sha256 TEXT")
        connection.commit()


def _migrate_users_table(connection):
    """Add the role column to users if it doesn't exist yet (safe on existing DBs).

    Existing users are backfilled: the earliest-created account becomes 'admin'
    so there's always at least one admin after upgrading; everyone else becomes
    'user'. On a fresh database this backfill is a no-op (no rows yet).
    """
    if not _column_exists(connection, "users", "role"):
        connection.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )
        connection.commit()

        first_user = connection.execute(
            "SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1"
        ).fetchone()

        if first_user:
            connection.execute(
                "UPDATE users SET role = 'admin' WHERE id = ?",
                (first_user["id"],),
            )
            connection.commit()


def init_db():
    """Create the database tables if they do not already exist."""
    connection = get_db_connection()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            size INTEGER NOT NULL,
            uploaded_by INTEGER,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sha256 TEXT,
            FOREIGN KEY (uploaded_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER,
            transfer_type TEXT NOT NULL,
            status TEXT NOT NULL,
            size INTEGER,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT NOT NULL,
            target TEXT,
            ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS shares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            expires_at TIMESTAMP,
            max_downloads INTEGER,
            download_count INTEGER NOT NULL DEFAULT 0,
            revoked INTEGER NOT NULL DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_id) REFERENCES files(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        );
        """
    )

    connection.commit()

    _migrate_files_table(connection)
    _migrate_users_table(connection)

    # Fresh database, no admin yet (e.g. right after first-ever init, before
    # any user has registered): nothing to backfill here, register() handles
    # making the very first registrant an admin. See app/auth.py.

    connection.close()


def log_transfer(
    file_id,
    transfer_type,
    status,
    size=None,
):
    """Store a file transfer event in the transfer history."""
    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO transfers (
            file_id,
            transfer_type,
            status,
            size,
            completed_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (
            file_id,
            transfer_type,
            status,
            size,
        ),
    )

    connection.commit()
    connection.close()


def log_action(user_id, username, action, target=None, ip_address=None):
    """Record a security/audit event (login, logout, upload, download, delete, etc.)."""
    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO audit_log (user_id, username, action, target, ip_address)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, username, action, target, ip_address),
    )

    connection.commit()
    connection.close()


def count_users():
    """Return the total number of registered users (used to decide if the
    next registration should become the first admin)."""
    connection = get_db_connection()

    row = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()

    connection.close()

    return row["n"]


def get_all_users():
    """Return all users, most recently created first, for the admin panel."""
    connection = get_db_connection()

    users = connection.execute(
        """
        SELECT id, username, role, created_at
        FROM users
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()

    connection.close()

    return users


def get_user_by_id(user_id):
    connection = get_db_connection()

    user = connection.execute(
        "SELECT id, username, role, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    connection.close()

    return user


def set_user_role(user_id, role):
    """Update a user's role. Caller is responsible for validating `role`
    (must be 'admin' or 'user') and for preventing self-demotion/last-admin
    lockout — see app/routes.py admin_users_update."""
    connection = get_db_connection()

    connection.execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (role, user_id),
    )

    connection.commit()
    connection.close()


def count_admins():
    connection = get_db_connection()

    row = connection.execute(
        "SELECT COUNT(*) AS n FROM users WHERE role = 'admin'"
    ).fetchone()

    connection.close()

    return row["n"]


def get_file_by_id(file_id):
    connection = get_db_connection()

    file_row = connection.execute(
        """
        SELECT files.id, files.filename, files.filepath, files.size, files.uploaded_by,
               users.username AS uploader
        FROM files
        LEFT JOIN users ON files.uploaded_by = users.id
        WHERE files.id = ?
        """,
        (file_id,),
    ).fetchone()

    connection.close()

    return file_row


def create_share(file_id, token, password_hash, expires_at, max_downloads, created_by):
    connection = get_db_connection()

    connection.execute(
        """
        INSERT INTO shares (file_id, token, password_hash, expires_at, max_downloads, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (file_id, token, password_hash, expires_at, max_downloads, created_by),
    )

    connection.commit()
    connection.close()


def get_share_by_token(token):
    connection = get_db_connection()

    share = connection.execute(
        """
        SELECT
            shares.id,
            shares.file_id,
            shares.token,
            shares.password_hash,
            shares.expires_at,
            shares.max_downloads,
            shares.download_count,
            shares.revoked,
            shares.created_by,
            shares.created_at,
            files.filename,
            files.filepath,
            files.size
        FROM shares
        LEFT JOIN files ON shares.file_id = files.id
        WHERE shares.token = ?
        """,
        (token,),
    ).fetchone()

    connection.close()

    return share


def increment_share_downloads(token):
    connection = get_db_connection()

    connection.execute(
        "UPDATE shares SET download_count = download_count + 1 WHERE token = ?",
        (token,),
    )

    connection.commit()
    connection.close()


def revoke_share(share_id):
    connection = get_db_connection()

    connection.execute(
        "UPDATE shares SET revoked = 1 WHERE id = ?",
        (share_id,),
    )

    connection.commit()
    connection.close()


def get_shares_for_user(user_id, include_all=False):
    """Return active-and-past shares. Regular users see only shares they
    created; admins (include_all=True) see everyone's."""
    connection = get_db_connection()

    if include_all:
        shares = connection.execute(
            """
            SELECT
                shares.id, shares.token, shares.expires_at, shares.max_downloads,
                shares.download_count, shares.revoked, shares.created_at,
                shares.password_hash,
                files.filename,
                users.username AS created_by_username
            FROM shares
            LEFT JOIN files ON shares.file_id = files.id
            LEFT JOIN users ON shares.created_by = users.id
            ORDER BY shares.id DESC
            """
        ).fetchall()
    else:
        shares = connection.execute(
            """
            SELECT
                shares.id, shares.token, shares.expires_at, shares.max_downloads,
                shares.download_count, shares.revoked, shares.created_at,
                shares.password_hash,
                files.filename,
                users.username AS created_by_username
            FROM shares
            LEFT JOIN files ON shares.file_id = files.id
            LEFT JOIN users ON shares.created_by = users.id
            WHERE shares.created_by = ?
            ORDER BY shares.id DESC
            """,
            (user_id,),
        ).fetchall()

    connection.close()

    return shares


def get_share_by_id(share_id):
    connection = get_db_connection()

    share = connection.execute(
        "SELECT id, created_by FROM shares WHERE id = ?",
        (share_id,),
    ).fetchone()

    connection.close()

    return share