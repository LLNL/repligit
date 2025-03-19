from typing import Generator, List, Union

import requests


def decode_lines(lines: Generator[str]) -> Generator[str]:
    """Decode server response iterator into usable lines."""
    for line in lines:
        line_length = int(line[:4], 16)
        yield line[4:line_length]


def encode_lines(lines: List[Union[bytes, str]]) -> bytes:
    """Build byte string from given lines to send to server."""
    result = []
    for line in lines:
        if type(line) is str:
            line = line.encode("utf-8")

        result.append(f"{len(line) + 5:04x}".encode())
        result.append(line)
        result.append(b"\n")

    return b"".join(result)


def ls_remote(url, username=None, password=None):
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


def generate_fetch_pack_request(want: str, haves: List[str]) -> bytes:
    """Generate a git-upload packfile request to retrieve a packfile from a
    remote server based on a list of have and want commits.
    """
    want_cmds = encode_lines([f"want {want}".encode()])
    have_cmds = encode_lines([f"have {sha}".encode() for sha in haves])

    return want_cmds + b"0000" + have_cmds + encode_lines([b"done"])


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


def generate_send_pack_header(ref: str, from_sha: str, to_sha: str) -> bytes:
    return encode_lines([f"{from_sha} {to_sha} {ref}\x00 report-status"]) + b"0000"


def send_pack(
    url: str,
    ref: str,
    from_sha: str,
    to_sha: str,
    packfile,
    username: str = None,
    password: str = None,
):
    url = f"{url}/git-receive-pack"
    auth = (username, password) if username or password else None

    header = generate_send_pack_header(ref, from_sha, to_sha)
    recieve_pack_request = header + packfile.read()

    resp = requests.post(
        url,
        headers={
            "Content-type": "application/x-git-receive-pack-request",
        },
        stream=True,
        auth=auth,
        data=recieve_pack_request,
    )

    resp.raise_for_status()

    lines = decode_lines(resp.iter_lines(decode_unicode=True))
    assert next(lines) == b"unpack ok"
    assert next(lines) == f"ok {ref}".encode()
