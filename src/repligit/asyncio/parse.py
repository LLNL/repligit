# --------- asynchronous client helpers ---------
from typing import AsyncIterable, AsyncIterator, Callable, Dict


async def decode_lines(line_stream: AsyncIterable) -> AsyncIterator:
    """(async) Decode server response iterator into usable lines."""
    async for line in line_stream:
        line_length = int(line[:4], 16)
        yield line[4:line_length]


async def process_ls_remote(lines: AsyncIterator, validator: Callable) -> Dict[str, str]:
    service_line = await anext(lines)
    if not validator(service_line):
        raise ValueError("Invalid service line")

    # `async for` inside `dict()` not supported yet so we can't use dict comprehension
    result = {}
    async for line in lines:
        if line:
            sha, ref = line.split()
            result[ref] = sha
    return result
