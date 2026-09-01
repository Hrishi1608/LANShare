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
        """
    )

    connection.commit()
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