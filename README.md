# reverse

## Static reverse-engineering notes: `Jailbird/Main.lua`

Target analyzed: `https://github.com/Benmuhammed7/Hexiron/blob/main/Jailbird/Main.lua`

### What the script is doing (high confidence)
- Uses a custom XOR string decoder (`bit32.bxor`) to hide API names/strings.
- Includes a custom Base64 decode stage.
- Resolves globals dynamically through `getfenv()` lookups.
- Implements a flattened VM/interpreter-style execution flow to run hidden payload bytecode.
- Carries a large embedded encoded payload blob that is decoded/executed at runtime.

### Why this matters for anti-cheat
This is a staged obfuscated loader designed to prevent static signatures and expose behavior only at runtime.

### Practical anti-cheat detections to add
- Flag scripts that combine:
  - heavy `bit32` usage for string decoding,
  - dynamic global lookup via `getfenv()[...]`,
  - custom Base64 decode routines,
  - VM-like dispatch loops/state machines.
- Add telemetry/signatures for watermark or marker text seen in this sample:
  - `Theil.cc`
- Treat large inline encoded blobs plus runtime decode+execute behavior as high risk.

### Confidence
- High confidence on architecture (decoder + loader + VM wrapper).
- Medium confidence on final payload actions (hidden by VM layer).

## Begin proper deobfuscation (stage 1)

Added static tooling:
- `/home/runner/work/reverse/reverse/tools/deobfuscate_stage1.py`

What it does:
- Parses and decodes `sf(<encoded>, <key>)` calls from the obfuscated Lua source.
- Produces:
  - `sf_mappings.json` (decoded string mapping data)
  - `partially_deobfuscated.lua` (same source with `sf(...)` replaced by decoded string literals)

Example:

```bash
python /home/runner/work/reverse/reverse/tools/deobfuscate_stage1.py \
  /tmp/Jailbird_Main.lua \
  --output-dir /tmp/deobf_stage1
```

Next stage after this output:
- Resolve dynamic `de[...]` global lookups using decoded strings.
- Name VM fields/tables and split state-machine blocks into logical opcode handlers.

## Stage 2: extract VM assets (opcode table + payload)

Added static extractor:
- `/home/runner/work/reverse/reverse/tools/extract_vm_assets.py`

It reads `partially_deobfuscated.lua` and emits:
- `opcode_table.json` (256 opcode descriptor entries from `[60343]`)
- `payload.bin` (decoded bytes from `Gb(Fe'...')`)
- `vm_assets.json` (manifest + payload hash/stats)

Example:

```bash
python /home/runner/work/reverse/reverse/tools/extract_vm_assets.py \
  /tmp/deobf_stage1/partially_deobfuscated.lua \
  --output-dir /tmp/vm_assets
```

## Stage 3: bytecode-equivalent reconstruction

Added reconstruction tool:
- `/home/runner/work/reverse/reverse/tools/reconstruct_from_bytecode_eqv.py`

It maps every payload byte through the 256-entry VM opcode descriptor table and outputs a
bytecode-equivalent IR/listing:
- `bytecode_eqv.jsonl`
- `reconstructed_eqv.lua`
- `ir_summary.json`

Example:

```bash
python /home/runner/work/reverse/reverse/tools/reconstruct_from_bytecode_eqv.py \
  /tmp/vm_assets/payload.bin \
  /tmp/vm_assets/opcode_table.json \
  --output-dir /tmp/bytecode_eqv
```