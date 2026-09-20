#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

SIMPLE_ESCAPES = {
    'a': 7,
    'b': 8,
    'f': 12,
    'n': 10,
    'r': 13,
    't': 9,
    'v': 11,
    '\\': 92,
    '"': 34,
    "'": 39,
}


def parse_lua_string(src: str, i: int):
    quote = src[i]
    if quote not in ('"', "'"):
        raise ValueError('expected quote')
    i += 1
    out = bytearray()

    while i < len(src):
        ch = src[i]
        if ch == quote:
            return bytes(out), i + 1

        if ch != '\\':
            out.append(ord(ch))
            i += 1
            continue

        i += 1
        if i >= len(src):
            raise ValueError('truncated escape')
        esc = src[i]

        if esc in SIMPLE_ESCAPES:
            out.append(SIMPLE_ESCAPES[esc])
            i += 1
            continue

        if esc == 'z':
            i += 1
            while i < len(src) and src[i].isspace():
                i += 1
            continue

        if esc == 'x' and i + 2 < len(src):
            hex_part = src[i + 1 : i + 3]
            try:
                out.append(int(hex_part, 16))
                i += 3
                continue
            except ValueError:
                pass

        if esc.isdigit():
            j = i
            while j < len(src) and src[j].isdigit() and j - i < 3:
                j += 1
            out.append(int(src[i:j], 10) % 256)
            i = j
            continue

        out.append(ord(esc))
        i += 1

    raise ValueError('unterminated string')


def skip_ws(src: str, i: int):
    while i < len(src) and src[i].isspace():
        i += 1
    return i


def find_sf_calls(src: str):
    i = 0
    calls = []
    while i < len(src):
        idx = src.find('sf(', i)
        if idx == -1:
            break
        if idx > 0 and (src[idx - 1].isalnum() or src[idx - 1] == '_'):
            i = idx + 3
            continue

        pos = idx + 3
        try:
            pos = skip_ws(src, pos)
            if src[pos] not in ('"', "'"):
                i = idx + 3
                continue
            arg1, pos = parse_lua_string(src, pos)
            pos = skip_ws(src, pos)
            if src[pos] != ',':
                i = idx + 3
                continue
            pos += 1
            pos = skip_ws(src, pos)
            if src[pos] not in ('"', "'"):
                i = idx + 3
                continue
            arg2, pos = parse_lua_string(src, pos)
            pos = skip_ws(src, pos)
            if src[pos] != ')':
                i = idx + 3
                continue
            pos += 1
        except (IndexError, ValueError):
            i = idx + 3
            continue

        calls.append((idx, pos, arg1, arg2))
        i = pos

    return calls


def xor_decode(data: bytes, key: bytes):
    if not key:
        return data
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def lua_escape(data: bytes):
    out = []
    for b in data:
        if 32 <= b <= 126 and b not in (34, 92):
            out.append(chr(b))
        elif b == 34:
            out.append('\\"')
        elif b == 92:
            out.append('\\\\')
        elif b == 10:
            out.append('\\n')
        elif b == 13:
            out.append('\\r')
        elif b == 9:
            out.append('\\t')
        else:
            out.append(f'\\x{b:02x}')
    return '"' + ''.join(out) + '"'


def main():
    p = argparse.ArgumentParser(description='Stage-1 static deobfuscation for sf(...) calls')
    p.add_argument('input', type=Path, help='Path to obfuscated Lua file')
    p.add_argument('--output-dir', type=Path, default=Path('./deobf_out'), help='Output directory')
    args = p.parse_args()

    src = args.input.read_text(encoding='latin-1')
    calls = find_sf_calls(src)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    mappings = []
    rewritten = []
    cursor = 0
    for idx, (start, end, arg1, arg2) in enumerate(calls):
        decoded = xor_decode(arg1, arg2)
        mappings.append({
            'index': idx,
            'start': start,
            'end': end,
            'encoded_length': len(arg1),
            'key_length': len(arg2),
            'decoded_hex': decoded.hex(),
            'decoded_text': decoded.decode('latin-1', errors='replace'),
        })

        rewritten.append(src[cursor:start])
        rewritten.append(lua_escape(decoded))
        cursor = end

    rewritten.append(src[cursor:])

    (args.output_dir / 'sf_mappings.json').write_text(
        json.dumps(mappings, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    (args.output_dir / 'partially_deobfuscated.lua').write_text(
        ''.join(rewritten),
        encoding='latin-1',
    )

    print(f'Found {len(calls)} sf(...) calls')
    print(f'Wrote: {args.output_dir / "sf_mappings.json"}')
    print(f'Wrote: {args.output_dir / "partially_deobfuscated.lua"}')


if __name__ == '__main__':
    main()
