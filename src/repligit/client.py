from typing import List

import requests

from repligit.parse import (
    decode_lines,
    generate_fetch_pack_request,
    generate_send_pack_header,
)


def ls_remote(url: str, username: str = None, password: str = None):
    """Get commit hash of remote master branch, return SHA-1 hex string or
    None if no remote commits.
    """
    url = f"{url}/info/refs?service=git-upload-pack"
    auth = (username, password) if username or password else None

    resp = requests.get(url, stream=True, auth=auth)
    resp.raise_for_status()

    if resp.encoding is None:
        resp.encoding = "utf-8"

    lines = decode_lines(resp.iter_lines(decode_unicode=True))
    service_line = next(lines)
    assert service_line == "# service=git-upload-pack"

    return dict(reversed(line.split()) for line in lines if line)


def fetch_pack(
    url: str, want_sha: str, have_shas: List[str], username=None, password=None
):
    """Download a packfile from a remote server."""
    url = f"{url}/git-upload-pack"
    auth = (username, password) if username or password else None

    request = generate_fetch_pack_request(want_sha, have_shas)

    resp = requests.post(
        url,
        headers={
            "Content-type": "application/x-git-upload-pack-request",
        },
        auth=auth,
        data=request,
        stream=True,
        timeout=None,
    )
    resp.raise_for_status()

    line_length = int(resp.raw.read(4), 16)
    line = resp.raw.read(line_length - 4)

    if line[:3] == b"NAK" or line[:3] == b"ACK":
        return resp.raw
    else:
        return None


def send_pack(
    url: str,
    ref: str,
    from_sha: str,
    to_sha: str,
    packfile,
    username: str = None,
    password: str = None,
):
    """Send a packfile to a remote server."""
    url = f"{url}/git-receive-pack"
    auth = (username, password) if username or password else None

    header = generate_send_pack_header(ref, from_sha, to_sha)
    receive_pack_request = header + packfile.read()

    resp = requests.post(
        url,
        headers={
            "Content-type": "application/x-git-receive-pack-request",
        },
        stream=True,
        auth=auth,
        data=receive_pack_request,
    )
    resp.raise_for_status()

    if resp.encoding is None:
        resp.encoding = "utf-8"

    lines = decode_lines(resp.iter_lines(decode_unicode=True))
    assert next(lines) == "unpack ok"
    assert next(lines) == f"ok {ref}"
