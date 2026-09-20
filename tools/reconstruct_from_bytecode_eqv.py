#!/usr/bin/env python3
import argparse
import json
from collections import Counter
from pathlib import Path


def load_opcode_table(path: Path):
    table = json.loads(path.read_text(encoding="utf-8"))
    if len(table) != 256:
        raise ValueError(f"Expected 256 opcode descriptors, found {len(table)}")
    return table


def main():
    parser = argparse.ArgumentParser(
        description="Build a bytecode-equivalent IR from extracted payload and opcode table"
    )
    parser.add_argument("payload", type=Path, help="Path to payload.bin")
    parser.add_argument("opcode_table", type=Path, help="Path to opcode_table.json")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("./bytecode_eqv_out"), help="Output directory"
    )
    args = parser.parse_args()

    payload = args.payload.read_bytes()
    opcode_table = load_opcode_table(args.opcode_table)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    ir_path = args.output_dir / "bytecode_eqv.jsonl"
    listing_path = args.output_dir / "reconstructed_eqv.lua"
    summary_path = args.output_dir / "ir_summary.json"

    class_counts = Counter()
    flag_counts = Counter()
    opcode_freq = Counter(payload)

    with ir_path.open("w", encoding="utf-8") as jf, listing_path.open(
        "w", encoding="utf-8"
    ) as lf:
        lf.write("-- Reconstructed bytecode-equivalent listing\n")
        lf.write("-- Each entry is one payload byte mapped through the VM opcode descriptor table.\n\n")

        for offset, op_byte in enumerate(payload):
            meta = opcode_table[op_byte]
            class_counts[meta["class"]] += 1
            flag_counts[meta["flag"]] += 1

            rec = {
                "offset": offset,
                "opcode_byte": op_byte,
                "class": meta["class"],
                "arg": meta["arg"],
                "flag": meta["flag"],
            }
            jf.write(json.dumps(rec) + "\n")
            lf.write(
                f"-- [{offset:06d}] op=0x{op_byte:02X} class={meta['class']} arg={meta['arg']} flag={str(meta['flag']).lower()}\n"
            )

    summary = {
        "payload_size": len(payload),
        "distinct_opcode_bytes": len(opcode_freq),
        "top_16_opcodes": [
            {"opcode_byte": op, "count": count} for op, count in opcode_freq.most_common(16)
        ],
        "class_counts": {str(k): v for k, v in sorted(class_counts.items())},
        "flag_counts": {"true": flag_counts[True], "false": flag_counts[False]},
        "files": {
            "bytecode_eqv_jsonl": str(ir_path),
            "reconstructed_listing_lua": str(listing_path),
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Processed payload bytes: {len(payload)}")
    print(f"Wrote: {ir_path}")
    print(f"Wrote: {listing_path}")
    print(f"Wrote: {summary_path}")


if __name__ == "__main__":
    main()
