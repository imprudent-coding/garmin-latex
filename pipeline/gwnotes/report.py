"""Raccolta di avvisi e scrittura del report di conversione."""
from __future__ import annotations

import collections
import sys


class Warnings:
    def __init__(self):
        self.items: dict[str, list[str]] = collections.defaultdict(list)

    def add(self, category: str, msg: str, quiet: bool = False):
        if msg not in self.items[category]:
            self.items[category].append(msg)
            if not quiet:
                print(f"  avviso [{category}] {msg}", file=sys.stderr)

    def count(self) -> int:
        return sum(len(v) for v in self.items.values())

    def markdown(self) -> str:
        if not self.items:
            return "Nessun avviso.\n"
        out = []
        for cat in sorted(self.items):
            msgs = self.items[cat]
            out.append(f"### {cat} ({len(msgs)})\n")
            for m in msgs[:200]:
                out.append(f"- {m}")
            if len(msgs) > 200:
                out.append(f"- … altri {len(msgs) - 200}")
            out.append("")
        return "\n".join(out) + "\n"
