"""
Asynchronous implementation of repligit operations.
"""

import ssl
from typing import List

import aiohttp
import certifi

from repligit.asyncio.parse import decode_lines, process_ls_remote
from repligit.asyncio.util import iter_lines
from repligit.parse import generate_fetch_pack_request, generate_send_pack_header
from repligit.util import (
    check_fetch_pack_resp,
    fmt_fetch_pack_url,
    fmt_ls_remote_url,
    fmt_send_pack_url,
    get_receive_pack_headers,
    get_upload_pack_headers,
    validate_send_pack_resp,
    validate_service_line,
)

# TODO debug why this doesn't work
# ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context = ssl._create_unverified_context()


async def ls_remote(url: str, username: str = None, password: str = None):
    """Get commit hash of remote master branch, return SHA-1 hex string or
    None if no remote commits.
    """

    url = fmt_ls_remote_url(url)
    auth = aiohttp.BasicAuth(username, password) if username or password else None
    async with aiohttp.ClientSession(
        auth=auth, connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        async with session.get(url, raise_for_status=True) as resp:
            lines = decode_lines(iter_lines(resp, encoding="utf-8"))
            return await process_ls_remote(lines, validate_service_line)


async def fetch_pack(url: str, want_sha: str, have_shas: List[str], username=None, password=None):
    """Download a packfile from a remote server."""
    url = fmt_fetch_pack_url(url)
    auth = aiohttp.BasicAuth(username, password) if username or password else None

    request = generate_fetch_pack_request(want_sha, have_shas)

    async with aiohttp.ClientSession(
        auth=auth, connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        async with session.post(
            url,
            headers=get_upload_pack_headers(),
            data=request,
            raise_for_status=True,
            timeout=None,
        ) as resp:
            length_bytes = await resp.content.readexactly(4)
            line_length = int(length_bytes, 16)
            line = await resp.content.readexactly(line_length - 4)

            if check_fetch_pack_resp(line):
                # TODO address: this is a difference in API between sync and async
                # has to be read within this context to be used in the caller
                return await resp.content.read()
            else:
                return None


async def send_pack(
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
    auth = aiohttp.BasicAuth(username, password) if username or password else None

    header = generate_send_pack_header(ref, from_sha, to_sha)
    # unlike in the sync version the packfile is already read into memory
    receive_pack_request = header + packfile

    async with aiohttp.ClientSession(
        auth=auth, connector=aiohttp.TCPConnector(ssl=ssl_context)
    ) as session:
        async with session.post(
            url,
            headers=get_receive_pack_headers(),
            data=receive_pack_request,
            raise_for_status=True,
        ) as resp:
            lines = decode_lines(iter_lines(resp))
            first_line = await anext(lines)
            second_line = await anext(lines)

            if not validate_send_pack_resp(first_line, second_line, ref):
                raise ValueError("Invalid response from send-pack operation")
