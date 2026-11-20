"""Run I/O-bound calls (model APIs, ffmpeg) a few at a time."""

from __future__ import annotations


def parallel(fn, items, workers):
    """Yield (in completion order) fn(item) for every item, up to `workers` at a time. Results that
    finish are yielded even if another item fails; the first failure is raised after them."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    if workers <= 1:
        for item in items:
            yield fn(item)
        return
    error = None
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for fut in as_completed([pool.submit(fn, item) for item in items]):
            try:
                result = fut.result()
            except Exception as exc:  # keep saving the others, then raise
                error = error or exc
                continue
            yield result
    if error is not None:
        raise error
