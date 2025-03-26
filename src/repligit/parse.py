# --------- shared client helpers ---------
from typing import Generator, List, Union


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


def generate_send_pack_header(ref: str, from_sha: str, to_sha: str) -> bytes:
    return encode_lines([f"{from_sha} {to_sha} {ref}\x00 report-status"]) + b"0000"


def generate_fetch_pack_request(want: str, haves: List[str]) -> bytes:
    """Generate a git-upload packfile request to retrieve a packfile from a
    remote server based on a list of have and want commits.
    """
    want_cmds = encode_lines([f"want {want}".encode()])
    have_cmds = encode_lines([f"have {sha}".encode() for sha in haves])

    return want_cmds + b"0000" + have_cmds + encode_lines([b"done"])
