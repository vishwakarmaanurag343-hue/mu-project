"""Process-isolated PDF parser with strict execution timeout and memory limits."""

import contextlib
import io
import multiprocessing as mp
import sys

import pypdf
from fastapi import HTTPException, status

# 512 MB virtual memory ceiling per worker process
MAX_PARSER_MEMORY_BYTES = 512 * 1024 * 1024


def _worker_parse_pdf(
    content: bytes,
    max_pages: int,
    result_queue: "mp.Queue[tuple[bool, int | str]]",
) -> None:
    """Worker process function: enforces Linux memory limit and counts PDF pages."""
    # Apply resource limit on POSIX/Linux platforms.
    # Note: RLIMIT_AS is enforced on Linux only (production target) and is a no-op on macOS/Windows.
    if sys.platform != "win32":
        with contextlib.suppress(Exception):
            import resource  # type: ignore[import-not-found]

            resource.setrlimit(
                resource.RLIMIT_AS,
                (MAX_PARSER_MEMORY_BYTES, MAX_PARSER_MEMORY_BYTES),
            )

    try:
        reader = pypdf.PdfReader(io.BytesIO(content))
        page_count = len(reader.pages)
        if page_count > max_pages:
            result_queue.put(
                (
                    False,
                    f"Document exceeds maximum page limit of {max_pages} pages (found {page_count})",
                )
            )
            return
        result_queue.put((True, page_count))
    except Exception as exc:
        result_queue.put((False, f"Corrupted or invalid PDF document: {exc!s}"))


def parse_pdf_safe(
    content: bytes,
    max_pages: int = 100,
    timeout_seconds: float = 10.0,
) -> int:
    """Parse PDF document in a dedicated subprocess with timeout and memory limits.

    Raises HTTPException(422) on timeout or parser crash.
    """
    # Use multiprocessing.get_context("spawn") instead of the default fork start method.
    # Fork inside multi-threaded Uvicorn can deadlock; spawn ensures a clean, isolated worker process.
    ctx = mp.get_context("spawn")
    queue: mp.Queue[tuple[bool, int | str]] = ctx.Queue()

    process = ctx.Process(
        target=_worker_parse_pdf,
        args=(content, max_pages, queue),
    )
    process.start()
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        process.terminate()
        process.join(timeout=1.0)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"PDF parsing timed out after {timeout_seconds} seconds",
        )

    if process.exitcode != 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF parsing worker process crashed or ran out of memory",
        )

    if queue.empty():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="PDF parsing process exited without returning page count",
        )

    success, payload = queue.get()
    if not success:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(payload),
        )

    return int(payload)
