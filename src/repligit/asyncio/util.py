async def iter_lines(resp, encoding=None, chunk_size=512):
    """
    Stream lines from an HTTP response. Yields raw lines as bytes by default.

    If `encoding` is set, yields decoded strings using the given encoding.

    This is a reimplementation of requests.models.iter_lines for async,
    the default chunk_size value is inherited from that definition.
    """

    buffer = bytearray()

    async for chunk in resp.content.iter_chunked(chunk_size):
        buffer.extend(chunk)
        while b"\n" in buffer:
            idx = buffer.index(b"\n")
            line = buffer[:idx].rstrip(b"\r")
            del buffer[: idx + 1]
            yield line.decode(encoding) if encoding else bytes(line)

    # if there's anything left in the response yield it
    if buffer:
        line = buffer.rstrip(b"\r")
        yield line.decode(encoding) if encoding else bytes(line)
