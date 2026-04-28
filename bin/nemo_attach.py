#!/usr/bin/env python3
"""
nemo-attach — drop NEMO memory rules into any project so the AI working
there is forced to use NEMO as persistent memory.

Designed to be run via the official NEMO Docker image:

    docker run --rm -v "$PWD":/workdir nemo:local nemo-attach

…but also works as a plain Python script if you prefer a host-local install:

    python bin/nemo_attach.py --target /path/to/project

What it does:
  * Validates NEMO is reachable at http://localhost:8765/health (non-blocking).
  * Writes per-client rules files (CLAUDE.md, .cursor/rules/nemo.mdc,
    .windsurfrules, .clinerules, .github/copilot-instructions.md, AGENTS.md)
    each derived from the canonical templates/nemo-rules.md.
  * Idempotent: BEGIN/END markers let you re-run to upgrade in place without
    duplicating content or stomping on user-authored sections.
  * Optional --with-hooks edits ~/.claude/settings.json (with .bak backup) to
    install SessionStart + Stop hooks that auto-call NEMO every session.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

VERSION = "1"
MARKER_BEGIN = f"<!-- BEGIN NEMO RULES v{VERSION} -->"
MARKER_END = "<!-- END NEMO RULES -->"
MARKER_RE = re.compile(
    rf"{re.escape(MARKER_BEGIN[:25])}.*?{re.escape(MARKER_END)}",
    re.DOTALL,
)

DEFAULT_NEMO_URL = os.environ.get("NEMO_URL", "http://localhost:8765")


def health_check_url(display_url: str) -> str:
    """Translate a host-relative URL into one reachable from inside a container.

    ``display_url`` is what the *user* sees in printed instructions — they're
    on the host, so `localhost` is right for them. But this script may itself
    be running inside a sibling container where `localhost` doesn't resolve
    to NEMO. In that case rewrite to `host.docker.internal`, which Docker
    Desktop maps automatically on Mac/Windows, and on Linux resolves once the
    user passes `--add-host=host.docker.internal:host-gateway`.
    """
    if Path("/.dockerenv").exists():
        return display_url.replace("//localhost", "//host.docker.internal", 1)
    return display_url


# ── Per-client target descriptors ────────────────────────────────────────────
@dataclass
class Target:
    key: str                       # CLI selector
    path: str                      # relative to project root
    formatter: Callable[[str], str]  # canonical → file payload
    description: str               # for the summary table


def _plain(body: str) -> str:
    """Return the canonical block wrapped in NEMO markers, unmodified."""
    return f"{MARKER_BEGIN}\n{body.rstrip()}\n{MARKER_END}\n"


def _cursor_mdc(body: str) -> str:
    """Cursor expects YAML frontmatter so the rules attach to every request."""
    front = (
        "---\n"
        "description: NEMO persistent memory rules — required reading every turn.\n"
        "alwaysApply: true\n"
        "---\n\n"
    )
    return front + _plain(body)


def _copilot_md(body: str) -> str:
    """GitHub Copilot picks up .github/copilot-instructions.md verbatim."""
    return _plain(body)


TARGETS: list[Target] = [
    Target("claude", "CLAUDE.md", _plain, "Claude Code / Claude Desktop project rules"),
    Target("cursor", ".cursor/rules/nemo.mdc", _cursor_mdc, "Cursor always-on rule"),
    Target("windsurf", ".windsurfrules", _plain, "Windsurf project rules"),
    Target("cline", ".clinerules", _plain, "Cline project rules"),
    Target("copilot", ".github/copilot-instructions.md", _copilot_md, "VS Code Copilot instructions"),
    Target("agents", "AGENTS.md", _plain, "Generic AGENTS.md (Codex, Aider, generic agents)"),
]


# ── Template loading ─────────────────────────────────────────────────────────
def find_template() -> Path:
    """Locate templates/nemo-rules.md relative to this script."""
    candidates = [
        Path(__file__).resolve().parent.parent / "templates" / "nemo-rules.md",
        Path("/app/templates/nemo-rules.md"),  # Docker default
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(
        "Could not locate templates/nemo-rules.md. Looked at:\n  "
        + "\n  ".join(str(c) for c in candidates)
    )


# ── Health check ─────────────────────────────────────────────────────────────
def health_check(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=timeout) as resp:
            data = json.loads(resp.read())
            return data.get("status") == "ok", data.get("status", "unknown")
    except urllib.error.URLError as exc:
        return False, f"unreachable ({exc.reason})"
    except Exception as exc:
        return False, f"error ({type(exc).__name__}: {exc})"


# ── Per-target write logic ───────────────────────────────────────────────────
def apply_target(target: Target, root: Path, body: str, dry_run: bool) -> str:
    """Return one of: 'created' | 'updated' | 'appended' | 'unchanged' | 'skipped' | 'dry-run'."""
    payload = target.formatter(body)
    dest = root / target.path
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not dest.exists():
        if dry_run:
            return "dry-run (would create)"
        dest.write_text(payload, encoding="utf-8")
        return "created"

    existing = dest.read_text(encoding="utf-8")

    # Already managed — replace just our BEGIN/END block; leave any per-client
    # header (e.g. Cursor's YAML frontmatter) untouched so we don't duplicate it.
    if MARKER_BEGIN[:25] in existing and MARKER_END in existing:
        m = MARKER_RE.search(payload)
        block_only = m.group(0) if m else payload.strip()
        new = MARKER_RE.sub(block_only, existing, count=1)
        if new == existing:
            return "unchanged"
        if dry_run:
            return "dry-run (would update)"
        dest.write_text(new, encoding="utf-8")
        return "updated"

    # User-authored file with no NEMO block — append ours at the end.
    appended = existing.rstrip() + "\n\n" + payload
    if dry_run:
        return "dry-run (would append)"
    dest.write_text(appended, encoding="utf-8")
    return "appended"


# ── Optional Claude Code hooks installer ─────────────────────────────────────
def install_hooks(nemo_url: str, dry_run: bool) -> str:
    """Add SessionStart + Stop hooks to ~/.claude/settings.json with a .bak backup."""
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return f"skipped (cannot parse existing {settings_path})"
        if not dry_run:
            shutil.copy2(settings_path, settings_path.with_suffix(".json.bak"))
    else:
        current = {}

    hooks = current.setdefault("hooks", {})

    nemo_session_start = {
        "type": "command",
        "command": f"curl -s -X POST {nemo_url}/api/tools/prime_context -H 'Content-Type: application/json' -d '{{\"arguments\": {{}}}}'",
    }
    nemo_stop = {
        "type": "command",
        "command": f"curl -s -X POST {nemo_url}/api/tools/store_conversation -H 'Content-Type: application/json' -d '{{\"arguments\": {{\"content\": \"session ended\", \"role\": \"assistant\"}}}}' >/dev/null",
    }

    def _ensure(event: str, hook: dict) -> None:
        existing = hooks.setdefault(event, [])
        for entry in existing:
            for h in entry.get("hooks", []):
                if h.get("command") == hook["command"]:
                    return  # already present
        existing.append({"matcher": "*", "hooks": [hook]})

    _ensure("SessionStart", nemo_session_start)
    _ensure("Stop", nemo_stop)

    if dry_run:
        return f"dry-run (would update {settings_path})"
    settings_path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    return f"updated {settings_path} (backup at {settings_path.with_suffix('.json.bak')})"


# ── CLI ──────────────────────────────────────────────────────────────────────
def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="nemo-attach",
        description="Drop NEMO memory rules into any project so AI clients are forced to use it.",
    )
    parser.add_argument(
        "--target",
        default=None,
        help="Project directory. Defaults to /workdir inside the Docker image, $PWD otherwise.",
    )
    parser.add_argument(
        "--clients",
        default="all",
        help="Comma-separated subset of clients to set up. Default: all. "
             f"Available: {','.join(t.key for t in TARGETS)}.",
    )
    parser.add_argument(
        "--with-hooks",
        action="store_true",
        help="Also install SessionStart + Stop hooks in ~/.claude/settings.json (Claude Code only).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without touching anything.",
    )
    parser.add_argument(
        "--nemo-url",
        default=DEFAULT_NEMO_URL,
        help=f"NEMO base URL for the health check + hook commands. Default: {DEFAULT_NEMO_URL}",
    )
    return parser.parse_args(argv)


def resolve_target_dir(arg: str | None) -> Path:
    """Pick the project directory we should write into.

    Preference order:
      1. --target if explicitly passed.
      2. /workdir if it exists (Docker bind-mount convention).
      3. The current working directory.

    We deliberately do NOT pre-check writability for /workdir: if it exists we
    trust the user's bind-mount intent and let any later permission error
    surface naturally (with a clear hint about --user).
    """
    if arg:
        return Path(arg).expanduser().resolve()
    workdir = Path("/workdir")
    if workdir.is_dir():
        return workdir
    return Path.cwd().resolve()


def filter_targets(spec: str) -> list[Target]:
    if spec.strip().lower() == "all":
        return TARGETS
    keys = {k.strip() for k in spec.split(",") if k.strip()}
    bad = keys - {t.key for t in TARGETS}
    if bad:
        raise SystemExit(f"Unknown client(s): {', '.join(sorted(bad))}. "
                         f"Available: {', '.join(t.key for t in TARGETS)}.")
    return [t for t in TARGETS if t.key in keys]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    project = resolve_target_dir(args.target)
    selected = filter_targets(args.clients)
    template = find_template()
    body = template.read_text(encoding="utf-8")

    print(f"nemo-attach v{VERSION}")
    print(f"  project   : {project}")
    print(f"  template  : {template}")
    print(f"  clients   : {', '.join(t.key for t in selected)}")
    print(f"  dry-run   : {args.dry_run}")
    print()

    probe_url = health_check_url(args.nemo_url)
    ok, status = health_check(probe_url)
    badge = "[OK]  " if ok else "[WARN]"
    print(f"{badge} NEMO @ {args.nemo_url} — {status}")
    if not ok:
        print("        Rules will be installed anyway. Start NEMO with:")
        print("          docker compose up -d   (from the NEMO repo root)")
    print()

    counts: dict[str, int] = {}
    for t in selected:
        outcome = apply_target(t, project, body, args.dry_run)
        counts[outcome.split(" ", 1)[0]] = counts.get(outcome.split(" ", 1)[0], 0) + 1
        print(f"  {outcome:<24}  {t.path:<40}  {t.description}")

    print()
    summary = " · ".join(f"{k}: {v}" for k, v in sorted(counts.items()))
    print(f"Summary  →  {summary}")

    if args.with_hooks:
        print()
        print("Hooks:")
        print(f"  {install_hooks(args.nemo_url, args.dry_run)}")
    else:
        print()
        print("Tip: pass --with-hooks to also wire SessionStart + Stop into ~/.claude/settings.json")

    print()
    print("─ Connect your AI client (one-time per client) ─────────────────────")
    print(f"  Claude Code     →  claude mcp add nemo {args.nemo_url}/mcp/sse --transport sse")
    print(f"  Claude Desktop  →  paste {args.nemo_url}/mcp/sse into claude_desktop_config.json")
    print(f"  Cursor / Cline  →  Settings → MCP → Add → {args.nemo_url}/mcp/sse")
    print(f"  Windsurf        →  Settings → MCP → {args.nemo_url}/mcp/sse")
    print(f"  VS Code Copilot →  ~/.config/Code/User/mcp.json (URL: {args.nemo_url}/mcp/sse)")
    print(f"  ChatGPT GPT     →  Builder → Actions → Import {args.nemo_url}/openapi.json")
    print(f"  Anything else   →  REST: {args.nemo_url}/api/...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
