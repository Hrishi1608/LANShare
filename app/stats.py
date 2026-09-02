import shutil
import time

from app.database import get_db_connection


_START_TIME = time.time()


def get_uptime_seconds():
    """Seconds since this Flask process started."""
    return int(time.time() - _START_TIME)


def format_uptime(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")

    return " ".join(parts)


def format_bytes(num_bytes):
    """Human-readable byte size, e.g. 1536 -> '1.5 KB'."""
    value = float(num_bytes)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024


def get_file_stats():
    """Total number of files and total bytes stored by LANShare."""
    db = get_db_connection()

    row = db.execute(
        """
        SELECT
            COUNT(*) AS file_count,
            COALESCE(SUM(size), 0) AS total_size
        FROM files
        """
    ).fetchone()

    db.close()

    return {
        "file_count": row["file_count"],
        "total_size": row["total_size"],
    }


def get_disk_stats(path):
    """Disk usage of the volume that holds the upload folder."""
    usage = shutil.disk_usage(path)

    percent_used = round((usage.used / usage.total) * 100, 1) if usage.total else 0

    return {
        "total": usage.total,
        "used": usage.used,
        "free": usage.free,
        "percent_used": percent_used,
    }


def get_dashboard_stats(upload_folder):
    """Everything the dashboard's stats cards need, pre-formatted."""
    file_stats = get_file_stats()
    disk_stats = get_disk_stats(upload_folder)

    return {
        "file_count": file_stats["file_count"],
        "total_size_display": format_bytes(file_stats["total_size"]),
        "disk_used_display": format_bytes(disk_stats["used"]),
        "disk_total_display": format_bytes(disk_stats["total"]),
        "disk_free_display": format_bytes(disk_stats["free"]),
        "disk_percent_used": disk_stats["percent_used"],
        "uptime_display": format_uptime(get_uptime_seconds()),
    }