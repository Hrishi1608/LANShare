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


def init_db():
    """Create the database tables if they do not already exist."""
    connection = get_db_connection()

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
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
        """
    )

    connection.commit()

    _migrate_files_table(connection)

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