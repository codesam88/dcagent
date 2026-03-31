#!/usr/bin/env python3
"""
Generate docs/deltachat-rpc-api.md from `deltachat-rpc-server --openrpc`.

Usage:
    python scripts/gen_rpc_ref.py
    python scripts/gen_rpc_ref.py --out docs/deltachat-rpc-api.md
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_MISC_GROUP = "misc"

# Map from a keyword that appears anywhere in the method name → group key.
# First match wins (order matters).
_KEYWORD_GROUPS: list[tuple[str, str]] = [
    ("account", "account"),
    ("contact", "contact"),
    ("chat", "chat"),
    ("message", "message"),
    ("msg", "message"),
    ("transport", "transport"),
    ("backup", "backup"),
    ("import", "backup"),
    ("export", "backup"),
    ("webxdc", "webxdc"),
    ("reaction", "message"),
    ("location", "location"),
    ("provider", "provider"),
    ("vcard", "contact"),
    ("qr", "contact"),
    ("sticker", "message"),
    ("io", "io"),
    ("call", "io"),
    ("realtime", "io"),
    ("event", "events"),
    ("config", "config"),
    ("network", "io"),
]

_GROUP_DISPLAY: dict[str, str] = {
    "account": "Accounts",
    "chat": "Chats",
    "contact": "Contacts",
    "message": "Messages",
    "config": "Configuration",
    "transport": "Transport",
    "backup": "Backup & import/export",
    "webxdc": "Webxdc",
    "location": "Locations",
    "provider": "Provider info",
    "io": "IO & network",
    "events": "Events",
    _MISC_GROUP: "Miscellaneous",
}

_GROUP_ORDER = [
    "account",
    "chat",
    "contact",
    "message",
    "config",
    "transport",
    "backup",
    "webxdc",
    "location",
    "provider",
    "io",
    "events",
    _MISC_GROUP,
]


def _fetch_spec() -> dict:
    result = subprocess.run(
        ["deltachat-rpc-server", "--openrpc"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: deltachat-rpc-server --openrpc failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def _schema_to_str(schema: dict) -> str:
    """Render a JSON Schema fragment as a compact type string."""
    if not schema:
        return "any"
    t = schema.get("type")
    if isinstance(t, list):
        parts = [s for s in t if s != "null"]
        base = parts[0] if parts else "any"
        return f"{base} | null" if "null" in t else base
    if t == "array":
        items = schema.get("items", {})
        if isinstance(items, list):
            return f"tuple[{', '.join(_schema_to_str(i) for i in items)}]"
        return f"list[{_schema_to_str(items)}]"
    if t == "object":
        ref = schema.get("$ref", "")
        if ref:
            return ref.split("/")[-1]
        props = schema.get("properties", {})
        if props:
            inner = ", ".join(f"{k}: {_schema_to_str(v)}" for k, v in list(props.items())[:4])
            suffix = ", …" if len(props) > 4 else ""
            return "{" + inner + suffix + "}"
        additional = schema.get("additionalProperties")
        if additional:
            return f"dict[str, {_schema_to_str(additional)}]"
        return "object"
    if t == "null":
        return "None"
    if t in ("integer", "number"):
        fmt = schema.get("format", "")
        return fmt if fmt else t
    if t == "boolean":
        return "bool"
    if t == "string":
        if "enum" in schema:
            return " | ".join(f'"{v}"' for v in schema["enum"][:6])
        return "str"
    ref = schema.get("$ref", "")
    if ref:
        return ref.split("/")[-1]
    one_of = schema.get("oneOf") or schema.get("anyOf") or schema.get("allOf")
    if one_of:
        return " | ".join(_schema_to_str(s) for s in one_of[:3])
    return "any"


def _method_group(name: str) -> str:
    """Return the group key for a method name."""
    parts = set(name.split("_"))
    for keyword, group in _KEYWORD_GROUPS:
        if keyword in parts or any(keyword in p for p in parts):
            return group
    return _MISC_GROUP


def _render(spec: dict) -> str:
    version = spec.get("info", {}).get("version", "unknown")
    methods = spec.get("methods", [])

    # Group methods
    groups: dict[str, list] = {}
    for m in methods:
        g = _method_group(m["name"])
        groups.setdefault(g, []).append(m)

    # Sort groups: follow _GROUP_ORDER, then any extras, then misc
    ordered_keys = [k for k in _GROUP_ORDER if k in groups and k != _MISC_GROUP]
    extra = [k for k in groups if k not in _GROUP_ORDER and k != _MISC_GROUP]
    ordered_keys += sorted(extra)
    if _MISC_GROUP in groups:
        ordered_keys.append(_MISC_GROUP)

    lines = [
        "# Delta Chat JSON-RPC API",
        "",
        f"> Generated from `deltachat-rpc-server --openrpc` · core version **{version}**",
        "> Re-run `make docs` after `uv sync` to update.",
        "",
        "The RPC methods below are called via `rpc.<method_name>(...)` using the",
        "`deltachat2.Rpc` dynamic dispatcher (snake_case args map to camelCase JSON).",
        "",
        "## Table of contents",
        "",
    ]

    for key in ordered_keys:
        display = _GROUP_DISPLAY.get(key, key.replace("_", " ").title())
        anchor = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-")
        lines.append(f"- [{display}](#{anchor})")

    lines.append("")

    for key in ordered_keys:
        display = _GROUP_DISPLAY.get(key, key.replace("_", " ").title())
        lines += [f"## {display}", ""]

        for m in sorted(groups[key], key=lambda x: x["name"]):
            name = m["name"]
            params = m.get("params", [])
            result = m.get("result", {})
            desc = (m.get("description") or "").strip()

            # Signature line
            param_strs = []
            for p in params:
                pname = re.sub(r"([A-Z])", r"_\1", p["name"]).lower().lstrip("_")
                ptype = _schema_to_str(p.get("schema", {}))
                param_strs.append(f"{pname}: {ptype}")

            ret_schema = result.get("schema", {}) if isinstance(result, dict) else {}
            ret_type = _schema_to_str(ret_schema)

            sig = f"rpc.{name}({', '.join(param_strs)}) → {ret_type}"
            lines.append(f"### `{name}`")
            lines.append("")
            lines.append(f"```\n{sig}\n```")
            lines.append("")
            if desc:
                lines.append(desc)
                lines.append("")

            if params:
                lines.append("| Param | Type | Required |")
                lines.append("|-------|------|----------|")
                for p in params:
                    pname = p["name"]
                    ptype = _schema_to_str(p.get("schema", {}))
                    req = "✓" if p.get("required") else ""
                    lines.append(f"| `{pname}` | `{ptype}` | {req} |")
                lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="docs/deltachat-rpc-api.md", help="output path")
    args = ap.parse_args()

    spec = _fetch_spec()
    md = _render(spec)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md)
    methods_count = len(spec.get("methods", []))
    print(f"Written {out} ({methods_count} methods, core {spec.get('info', {}).get('version', '?')})")


if __name__ == "__main__":
    main()
