#!/usr/bin/env python3
"""Check provenance in the Git index or a committed snapshot."""
import argparse
import subprocess
import sys

from provenance import inspect_provenance


def git(*args):
    return subprocess.check_output(['git', *args])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', help='Inspect a commit instead of the index')
    args = parser.parse_args()
    if args.revision:
        commit = git('rev-parse', '--verify', '--end-of-options', args.revision + '^{commit}').decode().strip()
        records = git('ls-tree', '-rz', commit).split(b'\0')
    else:
        records = git('ls-files', '--stage', '-z').split(b'\0')
    blobs = {}
    for record in filter(None, records):
        metadata, raw_path = record.split(b'\t', 1)
        fields = metadata.decode().split()
        mode = fields[0]
        oid = fields[2] if args.revision else fields[1]
        if mode not in {'100644', '100755'} or (not args.revision and fields[2] != '0'):
            print('FAIL: unsupported file mode or unresolved index')
            return 1
        blobs[raw_path.decode()] = git('cat-file', 'blob', oid)
    errors = inspect_provenance(blobs)
    for required in ('LICENSE', 'THIRD_PARTY_NOTICES.md', 'profile/README.md', 'profile/avrelun-mark.svg'):
        if not blobs.get(required, b'').strip():
            errors.append(f'missing required profile file: {required}')
    for error in errors:
        print(f'FAIL: {error}')
    print(f'Inspected {len(blobs)} files; {"FAIL" if errors else "PASS"}. Human source review remains required.')
    return int(bool(errors))


if __name__ == '__main__':
    sys.exit(main())
