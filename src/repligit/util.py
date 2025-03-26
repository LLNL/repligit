"""
Shared utility functions for both synchronous and asynchronous repligit clients
"""

from typing import Callable, Dict, Iterator


def fmt_ls_remote_url(url):
    return f"{url}/info/refs?service=git-upload-pack"


def fmt_fetch_pack_url(url):
    return f"{url}/git-upload-pack"


def fmt_send_pack_url(url):
    return f"{url}/git-receive-pack"


def get_upload_pack_headers():
    return {
        "Content-type": "application/x-git-upload-pack-request",
    }


def get_receive_pack_headers():
    return {
        "Content-type": "application/x-git-receive-pack-request",
    }


def validate_service_line(line):
    return line == "# service=git-upload-pack"


def validate_send_pack_resp(first_line, second_line, ref):
    if first_line != b"unpack ok":
        return False
    if second_line != f"ok {ref}".encode():
        return False
    return True


def check_fetch_pack_resp(line):
    return line[:3] == b"NAK" or line[:3] == b"ACK"


def process_ls_remote(lines: Iterator, validator: Callable) -> Dict[str, str]:
    """
    Process ls-remote response lines.

    Args:
        lines: Iterator of response lines
        validator: Function to validate the service line

    Returns:
        Dictionary mapping reference names to SHA values
    """
    service_line = next(lines)
    if not validator(service_line):
        raise ValueError("Invalid service line in response")

    return dict(reversed(line.split()) for line in lines if line)
