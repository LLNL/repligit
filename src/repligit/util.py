"""
Shared utility functions for both synchronous and asynchronous repligit clients
"""


def fmt_ls_remote_url(url: str):
    return f"{url}/info/refs?service=git-upload-pack"


def fmt_fetch_pack_url(url: str):
    return f"{url}/git-upload-pack"


def fmt_send_pack_url(url: str):
    return f"{url}/git-receive-pack"


def get_upload_pack_headers():
    return {
        "Content-type": "application/x-git-upload-pack-request",
    }


def get_receive_pack_headers():
    return {
        "Content-type": "application/x-git-receive-pack-request",
    }


def validate_service_line(line: str):
    return line == "# service=git-upload-pack"


def validate_send_pack_resp(first_line: bytes, second_line: bytes, ref: str):
    if first_line != b"unpack ok":
        return False
    if second_line != f"ok {ref}".encode():
        return False
    return True


def check_fetch_pack_resp(line: bytes):
    return line[:3] == b"NAK" or line[:3] == b"ACK"
