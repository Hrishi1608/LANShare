import io

import qrcode


def generate_qr_png(data):
    """Return an in-memory PNG (BytesIO) of a QR code encoding `data`."""
    img = qrcode.make(data, box_size=8, border=2)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return buffer