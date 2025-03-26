diff --git a/spack.yaml b/spack.yaml
index 7a0d3d8..d3e4486 100644
--- a/spack.yaml
+++ b/spack.yaml
@@ -10,6 +10,7 @@ spack:
   - py-pip
   - py-pytest
   - py-ruff
+  - py-aiohttp
   view: true
   concretizer:
     unify: true
diff --git a/src/repligit/__init__.py b/src/repligit/__init__.py
index f7bc199..3c771bd 100644
--- a/src/repligit/__init__.py
+++ b/src/repligit/__init__.py
@@ -1 +1,3 @@
-__all__ = ["repligit"]
+from repligit.client import fetch_pack, ls_remote, send_pack
+
+__all__ = ["ls_remote", "fetch_pack", "send_pack"]
diff --git a/src/repligit/asyncio/__init__.py b/src/repligit/asyncio/__init__.py
new file mode 100644
index 0000000..88bee75
--- /dev/null
+++ b/src/repligit/asyncio/__init__.py
@@ -0,0 +1,3 @@
+from repligit.asyncio.client import fetch_pack, ls_remote, send_pack
+
+__all__ = ["ls_remote", "fetch_pack", "send_pack"]
diff --git a/src/repligit/asyncio/client.py b/src/repligit/asyncio/client.py
new file mode 100644
index 0000000..8a3f220
--- /dev/null
+++ b/src/repligit/asyncio/client.py
@@ -0,0 +1,105 @@
+"""
+Asynchronous implementation of repligit operations.
+"""
+
+import ssl
+from typing import List
+
+import aiohttp
+import certifi
+
+from repligit.asyncio.parse import decode_lines, process_ls_remote
+from repligit.asyncio.util import iter_lines
+from repligit.parse import generate_fetch_pack_request, generate_send_pack_header
+from repligit.util import (
+    check_fetch_pack_resp,
+    fmt_fetch_pack_url,
+    fmt_ls_remote_url,
+    fmt_send_pack_url,
+    get_receive_pack_headers,
+    get_upload_pack_headers,
+    validate_send_pack_resp,
+    validate_service_line,
+)
+
+# TODO debug why this doesn't work
+# ssl_context = ssl.create_default_context(cafile=certifi.where())
+ssl_context = ssl._create_unverified_context()
+
+
+async def ls_remote(url: str, username: str = None, password: str = None):
+    """Get commit hash of remote master branch, return SHA-1 hex string or
+    None if no remote commits.
+    """
+
+    url = fmt_ls_remote_url(url)
+    auth = aiohttp.BasicAuth(username, password) if username or password else None
+    async with aiohttp.ClientSession(
+        auth=auth, connector=aiohttp.TCPConnector(ssl=ssl_context)
+    ) as session:
+        async with session.get(url, raise_for_status=True) as resp:
+            lines = decode_lines(iter_lines(resp, encoding="utf-8"))
+            return await process_ls_remote(lines, validate_service_line)
+
+
+async def fetch_pack(url: str, want_sha: str, have_shas: List[str], username=None, password=None):
+    """Download a packfile from a remote server."""
+    url = fmt_fetch_pack_url(url)
+    auth = aiohttp.BasicAuth(username, password) if username or password else None
+
+    request = generate_fetch_pack_request(want_sha, have_shas)
+
+    async with aiohttp.ClientSession(
+        auth=auth, connector=aiohttp.TCPConnector(ssl=ssl_context)
+    ) as session:
+        async with session.post(
+            url,
+            headers=get_upload_pack_headers(),
+            data=request,
+            raise_for_status=True,
+            timeout=None,
+        ) as resp:
+            length_bytes = await resp.content.readexactly(4)
+            line_length = int(length_bytes, 16)
+            line = await resp.content.readexactly(line_length - 4)
+
+            if check_fetch_pack_resp(line):
+                # TODO address: this is a difference in API between sync and async
+                # has to be read within this context to be used in the caller
+                return await resp.content.read()
+            else:
+                return None
+
+
+async def send_pack(
+    url: str,
+    ref: str,
+    from_sha: str,
+    to_sha: str,
+    packfile,
+    username: str = None,
+    password: str = None,
+):
+    """Send a packfile to a remote server."""
+    url = fmt_send_pack_url(url)
+    auth = aiohttp.BasicAuth(username, password) if username or password else None
+
+    header = generate_send_pack_header(ref, from_sha, to_sha)
+    # unlike in the sync version the packfile is already read into memory
+    receive_pack_request = header + packfile
+
+    async with aiohttp.ClientSession(
+        auth=auth, connector=aiohttp.TCPConnector(ssl=ssl_context)
+    ) as session:
+        async with session.post(
+            url,
+            headers=get_receive_pack_headers(),
+            data=receive_pack_request,
+            raise_for_status=True,
+        ) as resp:
+            lines = decode_lines(iter_lines(resp))
+            first_line = await anext(lines)
+            second_line = await anext(lines)
+
+            if not validate_send_pack_resp(first_line, second_line, ref):
+                raise ValueError("Invalid response from send-pack operation")
diff --git a/src/repligit/asyncio/parse.py b/src/repligit/asyncio/parse.py
new file mode 100644
index 0000000..db98b58
--- /dev/null
+++ b/src/repligit/asyncio/parse.py
@@ -0,0 +1,23 @@
+# --------- asynchronous client helpers ---------
+from typing import AsyncIterable, AsyncIterator, Callable, Dict
+
+
+async def decode_lines(line_stream: AsyncIterable) -> AsyncIterator:
+    """(async) Decode server response iterator into usable lines."""
+    async for line in line_stream:
+        line_length = int(line[:4], 16)
+        yield line[4:line_length]
+
+
+async def process_ls_remote(lines: AsyncIterator, validator: Callable) -> Dict[str, str]:
+    service_line = await anext(lines)
+    if not validator(service_line):
+        raise ValueError("Invalid service line")
+
+    # `async for` inside `dict()` not supported yet so we can't use dict comprehension
+    result = {}
+    async for line in lines:
+        if line:
+            sha, ref = line.split()
+            result[ref] = sha
+    return result
diff --git a/src/repligit/asyncio/util.py b/src/repligit/asyncio/util.py
new file mode 100644
index 0000000..60b7131
--- /dev/null
+++ b/src/repligit/asyncio/util.py
@@ -0,0 +1,27 @@
+import aiohttp
+
+
+async def iter_lines(resp: aiohttp.ClientResponse, encoding: str = None, chunk_size: int = 512):
+    """
+    Stream lines from an HTTP response. Yields raw lines as bytes by default.
+
+    If `encoding` is set, yields decoded strings using the given encoding.
+
+    This is a reimplementation of requests.models.iter_lines for async,
+    the default `chunk_size` value is inherited from that definition.
+    """
+
+    buffer = bytearray()
+
+    async for chunk in resp.content.iter_chunked(chunk_size):
+        buffer.extend(chunk)
+        while b"\n" in buffer:
+            idx = buffer.index(b"\n")
+            line = buffer[:idx].rstrip(b"\r")
+            del buffer[: idx + 1]
+            yield line.decode(encoding) if encoding else bytes(line)
+
+    # if there's anything left in the response yield it
+    if buffer:
+        line = buffer.rstrip(b"\r")
+        yield line.decode(encoding) if encoding else bytes(line)
diff --git a/src/repligit/client.py b/src/repligit/client.py
new file mode 100644
index 0000000..2cc8c8b
--- /dev/null
+++ b/src/repligit/client.py
@@ -0,0 +1,97 @@
+from typing import List
+
+import requests
+
+from repligit.parse import (
+    decode_lines,
+    generate_fetch_pack_request,
+    generate_send_pack_header,
+    process_ls_remote,
+)
+from repligit.util import (
+    check_fetch_pack_resp,
+    fmt_fetch_pack_url,
+    fmt_ls_remote_url,
+    fmt_send_pack_url,
+    get_receive_pack_headers,
+    get_upload_pack_headers,
+    validate_send_pack_resp,
+    validate_service_line,
+)
+
+
+def ls_remote(url: str, username: str = None, password: str = None):
+    """Get commit hash of remote master branch, return SHA-1 hex string or
+    None if no remote commits.
+    """
+    url = fmt_ls_remote_url(url)
+    auth = (username, password) if username or password else None
+
+    resp = requests.get(url, stream=True, auth=auth)
+    resp.raise_for_status()
+
+    if resp.encoding is None:
+        resp.encoding = "utf-8"
+
+    lines = decode_lines(resp.iter_lines(decode_unicode=True))
+
+    return process_ls_remote(lines, validate_service_line)
+
+
+def fetch_pack(url: str, want_sha: str, have_shas: List[str], username=None, password=None):
+    """Download a packfile from a remote server."""
+    url = fmt_fetch_pack_url(url)
+    auth = (username, password) if username or password else None
+
+    request = generate_fetch_pack_request(want_sha, have_shas)
+
+    resp = requests.post(
+        url,
+        headers=get_upload_pack_headers(),
+        auth=auth,
+        data=request,
+        stream=True,
+        timeout=None,
+    )
+    resp.raise_for_status()
+
+    line_length = int(resp.raw.read(4), 16)
+    line = resp.raw.read(line_length - 4)
+
+    if check_fetch_pack_resp(line):
+        return resp.raw
+    else:
+        return None
+
+
+def send_pack(
+    url: str,
+    ref: str,
+    from_sha: str,
+    to_sha: str,
+    packfile,
+    username: str = None,
+    password: str = None,
+):
+    """Send a packfile to a remote server."""
+    url = fmt_send_pack_url(url)
+    auth = (username, password) if username or password else None
+
+    header = generate_send_pack_header(ref, from_sha, to_sha)
+    receive_pack_request = header + packfile.read()
+
+    resp = requests.post(
+        url,
+        headers=get_receive_pack_headers(),
+        stream=True,
+        auth=auth,
+        data=receive_pack_request,
+    )
+    resp.raise_for_status()
+
+    lines = decode_lines(resp.iter_lines(decode_unicode=True))
+    first_line = next(lines)
+    second_line = next(lines)
+
+    if not validate_send_pack_resp(first_line, second_line, ref):
+        raise ValueError("Invalid response from send-pack operation")
diff --git a/src/repligit/parse.py b/src/repligit/parse.py
new file mode 100644
index 0000000..46780c5
--- /dev/null
+++ b/src/repligit/parse.py
@@ -0,0 +1,57 @@
+from typing import Callable, Dict, Generator, Iterator, List, Union
+
+
+def decode_lines(lines: Generator[str]) -> Generator[str]:
+    """Decode server response iterator into usable lines."""
+    for line in lines:
+        line_length = int(line[:4], 16)
+        yield line[4:line_length]
+
+
+def encode_lines(lines: List[Union[bytes, str]]) -> bytes:
+    """Build byte string from given lines to send to server."""
+    result = []
+    for line in lines:
+        if type(line) is str:
+            line = line.encode("utf-8")
+
+        result.append(f"{len(line) + 5:04x}".encode())
+        result.append(line)
+        result.append(b"\n")
+
+    return b"".join(result)
+
+
+def generate_send_pack_header(ref: str, from_sha: str, to_sha: str) -> bytes:
+    return encode_lines([f"{from_sha} {to_sha} {ref}\x00 report-status"]) + b"0000"
+
+
+def generate_fetch_pack_request(want: str, haves: List[str]) -> bytes:
+    """Generate a git-upload packfile request to retrieve a packfile from a
+    remote server based on a list of have and want commits.
+    """
+    want_cmds = encode_lines([f"want {want}".encode()])
+    have_cmds = encode_lines([f"have {sha}".encode() for sha in haves])
+
+    return want_cmds + b"0000" + have_cmds + encode_lines([b"done"])
+
+
+# --------- synchronous client helpers ---------
+
+
+def process_ls_remote(lines: Iterator, validator: Callable) -> Dict[str, str]:
+    """
+    Process ls-remote response lines.
+
+    Args:
+        lines: Iterator of response lines
+        validator: Function to validate the service line
+
+    Returns:
+        Dictionary mapping reference names to SHA values
+    """
+    service_line = next(lines)
+    if not validator(service_line):
+        raise ValueError("Invalid service line in response")
+
+    return dict(reversed(line.split()) for line in lines if line)
diff --git a/src/repligit/repligit.py b/src/repligit/repligit.py
deleted file mode 100644
index ac8fbbf..0000000
--- a/src/repligit/repligit.py
+++ /dev/null
@@ -1,122 +0,0 @@
-from typing import Generator, List, Union
-
-import requests
-
-
-def decode_lines(lines: Generator[str]) -> Generator[str]:
-    """Decode server response iterator into usable lines."""
-    for line in lines:
-        line_length = int(line[:4], 16)
-        yield line[4:line_length]
-
-
-def encode_lines(lines: List[Union[bytes, str]]) -> bytes:
-    """Build byte string from given lines to send to server."""
-    result = []
-    for line in lines:
-        if type(line) is str:
-            line = line.encode("utf-8")
-
-        result.append(f"{len(line) + 5:04x}".encode())
-        result.append(line)
-        result.append(b"\n")
-
-    return b"".join(result)
-
-
-def ls_remote(url, username=None, password=None):
-    """Get commit hash of remote master branch, return SHA-1 hex string or
-    None if no remote commits.
-    """
-    url = f"{url}/info/refs?service=git-upload-pack"
-    auth = (username, password) if username or password else None
-
-    resp = requests.get(url, stream=True, auth=auth)
-    resp.raise_for_status()
-
-    if resp.encoding is None:
-        resp.encoding = "utf-8"
-
-    lines = decode_lines(resp.iter_lines(decode_unicode=True))
-
-    service_line = next(lines)
-    assert service_line == "# service=git-upload-pack"
-
-    return dict(reversed(line.split()) for line in lines if line)
-
-
-def generate_fetch_pack_request(want: str, haves: List[str]) -> bytes:
-    """Generate a git-upload packfile request to retrieve a packfile from a
-    remote server based on a list of have and want commits.
-    """
-    want_cmds = encode_lines([f"want {want}".encode()])
-    have_cmds = encode_lines([f"have {sha}".encode() for sha in haves])
-
-    return want_cmds + b"0000" + have_cmds + encode_lines([b"done"])
-
-
-def fetch_pack(
-    url: str, want_sha: str, have_shas: List[str], username=None, password=None
-):
-    """Download a packfile from a remote server."""
-    url = f"{url}/git-upload-pack"
-    auth = (username, password) if username or password else None
-
-    request = generate_fetch_pack_request(want_sha, have_shas)
-
-    resp = requests.post(
-        url,
-        headers={
-            "Content-type": "application/x-git-upload-pack-request",
-        },
-        auth=auth,
-        data=request,
-        stream=True,
-        timeout=None,
-    )
-
-    resp.raise_for_status()
-
-    line_length = int(resp.raw.read(4), 16)
-    line = resp.raw.read(line_length - 4)
-
-    if line[:3] == b"NAK" or line[:3] == b"ACK":
-        return resp.raw
-    else:
-        return None
-
-
-def generate_send_pack_header(ref: str, from_sha: str, to_sha: str) -> bytes:
-    return encode_lines([f"{from_sha} {to_sha} {ref}\x00 report-status"]) + b"0000"
-
-
-def send_pack(
-    url: str,
-    ref: str,
-    from_sha: str,
-    to_sha: str,
-    packfile,
-    username: str = None,
-    password: str = None,
-):
-    url = f"{url}/git-receive-pack"
-    auth = (username, password) if username or password else None
-
-    header = generate_send_pack_header(ref, from_sha, to_sha)
-    recieve_pack_request = header + packfile.read()
-
-    resp = requests.post(
-        url,
-        headers={
-            "Content-type": "application/x-git-receive-pack-request",
-        },
-        stream=True,
-        auth=auth,
-        data=recieve_pack_request,
-    )
-
-    resp.raise_for_status()
-
-    lines = decode_lines(resp.iter_lines(decode_unicode=True))
-    assert next(lines) == b"unpack ok"
-    assert next(lines) == f"ok {ref}".encode()
diff --git a/src/repligit/util.py b/src/repligit/util.py
new file mode 100644
index 0000000..8fea20a
--- /dev/null
+++ b/src/repligit/util.py
@@ -0,0 +1,43 @@
+"""
+Shared utility functions for both synchronous and asynchronous repligit clients
+"""
+
+
+def fmt_ls_remote_url(url: str):
+    return f"{url}/info/refs?service=git-upload-pack"
+
+
+def fmt_fetch_pack_url(url: str):
+    return f"{url}/git-upload-pack"
+
+
+def fmt_send_pack_url(url: str):
+    return f"{url}/git-receive-pack"
+
+
+def get_upload_pack_headers():
+    return {
+        "Content-type": "application/x-git-upload-pack-request",
+    }
+
+
+def get_receive_pack_headers():
+    return {
+        "Content-type": "application/x-git-receive-pack-request",
+    }
+
+
+def validate_service_line(line: str):
+    return line == "# service=git-upload-pack"
+
+
+def validate_send_pack_resp(first_line: bytes, second_line: bytes, ref: str):
+    if first_line != b"unpack ok":
+        return False
+    if second_line != f"ok {ref}".encode():
+        return False
+    return True
+
+
+def check_fetch_pack_resp(line: bytes):
+    return line[:3] == b"NAK" or line[:3] == b"ACK"
