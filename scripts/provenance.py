"""Validate asset provenance against the same Git snapshot as publication checks."""
import hashlib
import json
from pathlib import PurePosixPath

MANIFEST = 'docs/engineering/asset-provenance.json'
ASSET_SUFFIXES = {
    '.svg', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.ico',
    '.ttf', '.otf', '.woff', '.woff2', '.mp3', '.wav', '.ogg', '.mp4', '.webm',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect_provenance(blobs):
    """Return omissions/stale records, never a verdict on licensing or authorship."""
    assets = {p for p in blobs if PurePosixPath(p).suffix.lower() in ASSET_SUFFIXES}
    if MANIFEST not in blobs:
        return ['asset provenance manifest missing'] if assets else []
    try:
        manifest = json.loads(blobs[MANIFEST])
    except (ValueError, UnicodeError):
        return ['invalid asset provenance JSON']
    if not isinstance(manifest, dict) or manifest.get('version') != 1:
        return ['unsupported asset provenance schema']
    entries = manifest.get('assets')
    if not isinstance(entries, list):
        return ['asset provenance assets must be a list']
    errors = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get('path'), str):
            errors.append('invalid asset provenance entry')
            continue
        path = entry['path']
        if path in seen:
            errors.append(f'duplicate provenance entry: {path!r}')
        seen.add(path)
        if path not in assets:
            errors.append(f'provenance entry has no supported tracked asset: {path!r}')
        elif entry.get('sha256') != digest(blobs[path]):
            errors.append(f'asset changed; review provenance before updating digest: {path!r}')
        if not isinstance(entry.get('evidence'), str) or not entry['evidence'].strip():
            errors.append(f'provenance review evidence missing: {path!r}')
        sources = entry.get('sources')
        if not isinstance(sources, list) or not sources:
            errors.append(f'provenance sources missing: {path!r}')
            continue
        for source in sources:
            if not isinstance(source, dict) or any(
                not isinstance(source.get(field), str) or not source[field].strip()
                for field in ('origin', 'author', 'license', 'scope')
            ):
                errors.append(f'incomplete provenance source: {path!r}')
                continue
            if source.get('kind') not in {'project', 'third-party'}:
                errors.append(f'unknown provenance source kind: {path!r}')
            if source.get('kind') == 'third-party' and not source['origin'].startswith('https://'):
                errors.append(f'third-party source needs an HTTPS origin: {path!r}')
            notices = source.get('notices')
            if not isinstance(notices, dict) or not notices:
                errors.append(f'license/notice records missing: {path!r}')
                continue
            for notice, expected in notices.items():
                if notice not in blobs or not blobs[notice].strip():
                    errors.append(f'missing tracked notice {notice!r} for {path!r}')
                elif expected != digest(blobs[notice]):
                    errors.append(f'notice changed; recheck provenance: {notice!r} for {path!r}')
    for path in sorted(assets - seen):
        errors.append(f'asset has no provenance record: {path!r}')
    return errors
