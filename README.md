# SPRV Merge Tool

A Tkinter-based GUI for merging two `server_privilege.sprv` files using hash-based deduplication.

## What it does

SPRV files contain JSON with two sections — **roles** (platform ID + role mappings) and **bans** (ban records). This tool loads two SPRV files, hashes every entry with SHA-256, and uses set operations to categorize each entry as:

- **Common** — identical entry exists in both files
- **Only A** — entry unique to File A
- **Only B** — entry unique to File B

The merged output is the deduplicated union of both files.

## Features

- **Hash-based diff** — SHA-256 on canonical JSON for O(1) duplicate detection
- **Color-coded table** — green rows for Only-B entries, red for Only-A, neutral for Common
- **Roles / Bans tabs** — switch between sections
- **Filter buttons** — show All, Common, Only A, or Only B entries
- **Search** — real-time substring search across all columns and full hashes
- **Column sorting** — click any heading to sort ascending/descending; numeric columns sort numerically
- **Detail panel** — click a row to see its full syntax-highlighted JSON, origin, and SHA-256 hash
- **Apply Merge & Save** — write the deduplicated merged file
- **Export Diff Report** — save a plain-text summary of all differences

## Usage

### From source

```
python merge_sprv.py
```

### As a standalone exe

```
build_exe.bat
```

This runs PyInstaller and produces `dist/SPRV_MergeTool.exe` (~10 MB). The exe bundles Python and tkinter so it runs on any Windows machine without Python installed.

### File selection

Use the **Browse A / Browse B** buttons or **File > Load File A / Load File B** to pick your two `.sprv` files.

## Requirements

- Python 3.10+ (for `X | Y` union type syntax)
- No external dependencies (stdlib only: `tkinter`, `json`, `hashlib`, `pathlib`, `dataclasses`)
- [PyInstaller](https://pyinstaller.org/) (only needed for building the exe)

## File structure

```
merge_sprv.py              # Main application
build_exe.bat              # One-click exe builder
README.md                  # This file
```
