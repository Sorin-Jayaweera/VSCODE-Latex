#!/usr/bin/env python3
"""Export Obsidian Latex Suite snippets for the local VS Code auto-expander."""

import json
import sys
from pathlib import Path

import port_snippets as port

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tools" / "latex-suite-auto" / "snippets.generated.json"


def clean_options(value):
    if isinstance(value, dict):
        return ""
    return (value or "").strip().strip('"').strip("'")


def main():
    data_json = Path(sys.argv[1]) if len(sys.argv) > 1 else port.DEFAULT_DATA_JSON
    if not data_json.exists():
        raise SystemExit(f"Could not find Latex Suite data.json: {data_json}")

    data = json.loads(data_json.read_text(encoding="utf-8"))
    raw = data.get("snippets", "")
    variables = port.load_snippet_variables(data.get("snippetVariables", ""))
    snippets = port.attach_sections(raw, port.Scanner(raw).read_array_of_objects())

    exported = []
    skipped = {"function": [], "visual": [], "bad": 0}
    unresolved = set()

    for index, sn in enumerate(snippets):
        trigger = sn.get("trigger")
        replacement = sn.get("replacement")
        if trigger is None or replacement is None:
            skipped["bad"] += 1
            continue
        if isinstance(replacement, dict) and "__function__" in replacement:
            skipped["function"].append(trigger.get("__regex__", "regex") if isinstance(trigger, dict) else trigger)
            continue
        if isinstance(replacement, str) and "${VISUAL}" in replacement:
            skipped["visual"].append(trigger.get("__regex__", "regex") if isinstance(trigger, dict) else trigger)
            continue

        options = clean_options(sn.get("options", ""))
        is_regex = isinstance(trigger, dict) or "r" in options
        if isinstance(trigger, dict):
            pattern = trigger["__regex__"]
            regex_flags = trigger.get("flags", "")
        else:
            pattern = trigger
            regex_flags = ""

        if is_regex:
            pattern = port.expand_variables(pattern, variables, unresolved)

        if "m" in options:
            context = "math"
        elif "t" in options or "n" in options:
            context = "text"
        elif "c" in options:
            context = "code"
        else:
            context = "any"

        try:
            priority = int(sn.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0

        exported.append({
            "index": index,
            "trigger": pattern,
            "replacement": replacement,
            "description": sn.get("description") or pattern,
            "options": options,
            "context": context,
            "regex": is_regex,
            "regexFlags": regex_flags,
            "priority": priority,
        })

    # Hand-ported function snippets from build/manual_snippets.hsnips.
    exported.extend([
        {
            "index": len(exported),
            "trigger": r"iden(\d)",
            "replacement": "",
            "description": "N x N identity matrix",
            "options": "mAr",
            "context": "math",
            "regex": True,
            "regexFlags": "",
            "priority": 0,
            "dynamic": "identity",
        },
        {
            "index": len(exported) + 1,
            "trigger": r"zeros(\d)",
            "replacement": "",
            "description": "N x N zero matrix",
            "options": "mAr",
            "context": "math",
            "regex": True,
            "regexFlags": "",
            "priority": 0,
            "dynamic": "zeros",
        },
    ])

    exported.sort(key=lambda s: (-s["priority"], s["index"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": str(data_json),
        "count": len(exported),
        "skipped": skipped,
        "unresolvedVariables": sorted(unresolved),
        "snippets": exported,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT} ({len(exported)} snippets)")
    if unresolved:
        print("WARNING unresolved variables:", ", ".join(sorted(unresolved)))


if __name__ == "__main__":
    main()
