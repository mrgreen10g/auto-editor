"""Persist completion independently of the number of requested inserts."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path


def search_key(block, matches, use_manual):
    sources = []
    by_id = {m.id: m for m in matches}
    for ident in block.match_ids:
        source = by_id.get(ident)
        if source is None:
            sources.append([ident, None])
            continue
        path = Path(source.path)
        try:
            stat = path.stat()
            stamp = [stat.st_size, stat.st_mtime_ns]
        except OSError:
            stamp = None
        sources.append([asdict(source), stamp])
    data = ['event-search-v1', block.title, block.script, block.language,
            block.sport, sources, use_manual,
            [asdict(c) for c in block.clips] if use_manual else []]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def needs_search(block, matches, use_manual):
    if not block.match_ids or block.events or (use_manual and block.clips):
        return False
    return block.event_search_key != search_key(block, matches, use_manual)


def record_completion(block, matches, use_manual, scans):
    from .event_rules import requests_for
    # Errors must not masquerade as a successful scan with no candidates.
    complete = not requests_for(block, matches, use_manual) or all(
        ident in scans for ident in block.match_ids)
    block.event_search_key = search_key(block, matches, use_manual) if complete else ''


EMPTY_SEARCH_NOTE = ('В сценарии не найдены фразы для автоматических игровых вставок. '
                     'Можно определить тайминги и оставить ведущего или добавить фразу вручную.')
