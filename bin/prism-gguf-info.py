#!/usr/bin/env python3
"""Read bounded GGUF metadata, without loading tensor data or importing gguf."""
import json
import struct
import sys


def inspect(path):
    with open(path, 'rb') as stream:
        def read(size):
            if size > 16 * 1024 * 1024 or stream.tell() + size > 64 * 1024 * 1024:
                raise ValueError('metadata inspection limit exceeded')
            value = stream.read(size)
            if len(value) != size:
                raise ValueError('truncated GGUF')
            return value

        def number(fmt):
            return struct.unpack('<' + fmt, read(struct.calcsize(fmt)))[0]

        def string():
            return read(number('Q')).decode('utf-8')

        def value(kind, depth=0):
            if depth > 2:
                raise ValueError('nested metadata limit exceeded')
            formats = {0: 'B', 1: 'b', 2: 'H', 3: 'h', 4: 'I', 5: 'i',
                       6: 'f', 7: '?', 10: 'Q', 11: 'q', 12: 'd'}
            if kind in formats:
                return number(formats[kind])
            if kind == 8:
                return string()
            if kind == 9:
                subtype, count = number('I'), number('Q')
                if count > 1_000_000:
                    raise ValueError('array limit exceeded')
                for _ in range(count):
                    value(subtype, depth + 1)
                return None
            raise ValueError('unknown metadata type')

        if read(4) != b'GGUF' or number('I') not in (2, 3):
            raise ValueError('unsupported GGUF header')
        number('Q')  # tensor count: tensor payloads are never read
        count = number('Q')
        if count > 100_000:
            raise ValueError('metadata entry limit exceeded')
        metadata = {}
        for _ in range(count):
            key = string()
            item = value(number('I'))
            if key in ('general.file_type', 'general.name', 'general.architecture'):
                metadata[key] = item
        return metadata


if __name__ == '__main__':
    try:
        print(json.dumps(inspect(sys.argv[1])))
    except (OSError, ValueError, UnicodeError, struct.error, IndexError) as exc:
        print(f'GGUF metadata unavailable: {exc}', file=sys.stderr)
        sys.exit(1)
