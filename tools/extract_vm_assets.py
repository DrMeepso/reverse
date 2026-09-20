#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import re
from pathlib import Path


OPCODE_TABLE_RE = re.compile(r"\[60343\]=\{(.*?)\},\[3450\]=\{\}", re.S)
OPCODE_TRIPLET_RE = re.compile(r"\{(\d+),(\d+),(true|false)\}")
PAYLOAD_RE = re.compile(r"Gb\(Fe['\"]([A-Za-z0-9+/=]{1000,})['\"]")


def extract_opcode_table(source: str):
    match = OPCODE_TABLE_RE.search(source)
    if not match:
        raise ValueError("Could not locate [60343] opcode table block")

    triplets = OPCODE_TRIPLET_RE.findall(match.group(1))
    if len(triplets) != 256:
        raise ValueError(f"Expected 256 opcode descriptors, found {len(triplets)}")

    return [
        {
            "opcode_byte": i,
            "class": int(a),
            "arg": int(b),
            "flag": c == "true",
        }
        for i, (a, b, c) in enumerate(triplets)
    ]


def extract_payload_bytes(source: str):
    match = PAYLOAD_RE.search(source)
    if not match:
        raise ValueError("Could not locate encoded payload passed to Gb(Fe'...')")

    payload_b64 = match.group(1)
    payload = base64.b64decode(payload_b64, validate=True)
    return payload_b64, payload


def main():
    parser = argparse.ArgumentParser(
        description="Extract VM assets from partially deobfuscated Lua source"
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to partially_deobfuscated.lua (output of deobfuscate_stage1.py)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("./vm_assets_out"),
        help="Directory for extracted artifacts",
    )
    args = parser.parse_args()

    source = args.input.read_text(encoding="latin-1")
    opcode_table = extract_opcode_table(source)
    payload_b64, payload = extract_payload_bytes(source)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    payload_path = args.output_dir / "payload.bin"
    opcode_path = args.output_dir / "opcode_table.json"
    manifest_path = args.output_dir / "vm_assets.json"

    payload_path.write_bytes(payload)
    opcode_path.write_text(json.dumps(opcode_table, indent=2), encoding="utf-8")

    manifest = {
        "opcode_table_entries": len(opcode_table),
        "payload_b64_length": len(payload_b64),
        "payload_size": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "files": {
            "payload_bin": str(payload_path),
            "opcode_table_json": str(opcode_path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Extracted opcode entries: {len(opcode_table)}")
    print(f"Extracted payload bytes: {len(payload)}")
    print(f"Wrote: {payload_path}")
    print(f"Wrote: {opcode_path}")
    print(f"Wrote: {manifest_path}")


if __name__ == "__main__":
    main()
