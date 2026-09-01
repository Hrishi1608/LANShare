import socket


def get_local_ip():
    """Return the local IP address used by the current machine."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    try:
        # No data is actually sent to this address.
        # The connection is used to determine the preferred
        # local network interface.
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]

    except OSError:
        return "127.0.0.1"

    finally:
        sock.close()


def get_hostname():
    """Return the current machine hostname."""
    return socket.gethostname()