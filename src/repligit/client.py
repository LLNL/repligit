from typing import List

import requests

from repligit.parse import decode_lines, generate_fetch_pack_request, generate_send_pack_header
from repligit.util import (
    check_fetch_pack_resp,
    fmt_fetch_pack_url,
    fmt_ls_remote_url,
    fmt_send_pack_url,
    get_receive_pack_headers,
    get_upload_pack_headers,
    process_ls_remote,
    validate_send_pack_resp,
    validate_service_line,
)


def ls_remote(url, username=None, password=None):
    """Get commit hash of remote master branch, return SHA-1 hex string or
    None if no remote commits.
    """
    url = fmt_ls_remote_url(url)
    auth = (username, password) if username or password else None

    resp = requests.get(url, stream=True, auth=auth)
    resp.raise_for_status()

    if resp.encoding is None:
        resp.encoding = "utf-8"

    lines = decode_lines(resp.iter_lines(decode_unicode=True))

    return process_ls_remote(lines, validate_service_line)


def fetch_pack(url: str, want_sha: str, have_shas: List[str], username=None, password=None):
    """Download a packfile from a remote server."""
    url = fmt_fetch_pack_url(url)
    auth = (username, password) if username or password else None

    request = generate_fetch_pack_request(want_sha, have_shas)

    resp = requests.post(
        url,
        headers=get_upload_pack_headers(),
        auth=auth,
        data=request,
        stream=True,
        timeout=None,
    )
    resp.raise_for_status()

    # TODO check on sharing some of this..with the async or explain some of the numbers
    line_length = int(resp.raw.read(4), 16)
    line = resp.raw.read(line_length - 4)

    if check_fetch_pack_resp(line):
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
    url = fmt_send_pack_url(url)
    auth = (username, password) if username or password else None

    header = generate_send_pack_header(ref, from_sha, to_sha)
    receive_pack_request = header + packfile.read()

    resp = requests.post(
        url,
        headers=get_receive_pack_headers(),
        stream=True,
        auth=auth,
        data=receive_pack_request,
    )
    resp.raise_for_status()

    # TODO how much of this can be shared with async?
    lines = decode_lines(resp.iter_lines(decode_unicode=True))
    first_line = next(lines)
    second_line = next(lines)
    print(type(first_line), type(second_line))
    print(first_line, second_line)

    if not validate_send_pack_resp(first_line, second_line, ref):
        raise ValueError("Invalid response from send-pack operation")
