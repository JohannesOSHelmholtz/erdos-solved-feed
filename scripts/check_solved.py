#!/usr/bin/env python3
"""
Erdos Problems: Open -> Solved feed generator.

Reads the community database (data/problems.yaml in teorth/erdosproblems),
compares each problem's status against the last seen state, and emits an
Atom feed entry whenever a problem transitions from "not solved" to "solved".

"Solved" is defined the same way the project's own statistics are computed:
status.state (ignoring a trailing " (Lean)") is one of proved / disproved / solved.

Files it maintains (all committed back to the repo by the GitHub Action):
  data/state.json   -> {problem_number: last_seen_state}
  data/events.json  -> list of detected transitions (newest first, capped)
  feed.xml          -> Atom feed regenerated from events.json

Design choices (documented so behaviour is predictable):
  * FIRST RUN only seeds state.json and writes an empty feed. It does NOT
    dump the ~550 already-solved problems into the feed.
  * A problem that appears in the DB for the first time already-solved
    (a backfilled old solution) is NOT emitted by default. Flip
    EMIT_BACKFILLED_ALREADY_SOLVED to True if you want those too.
"""

import json
import os
import sys
import datetime
import urllib.request
import xml.sax.saxutils as sax

import yaml

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SOURCE_URL = "https://raw.githubusercontent.com/teorth/erdosproblems/main/data/problems.yaml"

SOLVED_BASE_STATES = {"proved", "disproved", "solved"}

# If True, also emit a problem that shows up in the DB for the first time
# already in a solved state (i.e. an old solution newly added to the site).
EMIT_BACKFILLED_ALREADY_SOLVED = False

MAX_EVENTS = 300          # how many entries to keep in the feed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "state.json")
EVENTS_PATH = os.path.join(ROOT, "data", "events.json")
FEED_PATH = os.path.join(ROOT, "feed.xml")

SITE = "https://www.erdosproblems.com"
FEED_SELF_ID = "urn:erdos-open-to-solved-feed"
FEED_TITLE = "Erdős Problems — Open → Solved"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def normalise(state: str) -> str:
    """Base state, lowercased, without a trailing ' (Lean)' marker."""
    if state is None:
        return ""
    return state.replace(" (Lean)", "").strip().lower()


def is_solved(state: str) -> bool:
    return normalise(state) in SOLVED_BASE_STATES


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def fetch_problems():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "erdos-solved-feed"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    data = yaml.safe_load(raw)
    current = {}
    for item in data:
        num = str(item.get("number", "")).strip()
        status = item.get("status") or {}
        state = status.get("state")
        last_update = status.get("last_update")
        if num:
            current[num] = {"state": state, "last_update": last_update}
    return current


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()


# ---------------------------------------------------------------------------
# Feed generation
# ---------------------------------------------------------------------------
def build_feed(events):
    updated = events[0]["detected_at"] if events else now_iso()
    parts = []
    parts.append('<?xml version="1.0" encoding="utf-8"?>')
    parts.append('<feed xmlns="http://www.w3.org/2005/Atom">')
    parts.append(f"  <title>{sax.escape(FEED_TITLE)}</title>")
    parts.append(f'  <id>{FEED_SELF_ID}</id>')
    parts.append(f"  <updated>{updated}</updated>")
    parts.append(f'  <link href="{SITE}/" />')
    parts.append('  <link rel="self" href="feed.xml" />')
    parts.append('  <author><name>erdos-solved-feed (community data)</name></author>')
    parts.append(
        "  <subtitle>Notifies when an Erdős problem changes from open to "
        "solved (proved / disproved / solved), based on the teorth/erdosproblems "
        "community database.</subtitle>"
    )
    for ev in events:
        num = ev["number"]
        to_state = ev["to"]
        from_state = ev["from"]
        detected = ev["detected_at"]
        last_update = ev.get("last_update") or ""
        url = f"{SITE}/{num}"
        entry_id = f"tag:erdos-solved:problem-{num}:{normalise(to_state)}:{ev.get('event_date','')}"
        title = f"Problem {num} solved ({to_state})"
        summary = (
            f"Erdős Problem #{num} changed status from "
            f"“{from_state or 'unknown'}” to “{to_state}”."
        )
        if last_update:
            summary += f" (database last_update: {last_update})"
        parts.append("  <entry>")
        parts.append(f"    <title>{sax.escape(title)}</title>")
        parts.append(f"    <id>{sax.escape(entry_id)}</id>")
        parts.append(f'    <link href="{url}" />')
        parts.append(f"    <updated>{detected}</updated>")
        parts.append(f"    <summary>{sax.escape(summary)}</summary>")
        parts.append("  </entry>")
    parts.append("</feed>")
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    previous = load_json(STATE_PATH, None)
    events = load_json(EVENTS_PATH, [])

    current = fetch_problems()
    first_run = previous is None
    previous = previous or {}

    new_events = []
    if not first_run:
        for num, info in current.items():
            new_state = info["state"]
            old = previous.get(num)  # old is a bare state string or None

            if old is None:
                # Problem new to the DB since last run.
                if is_solved(new_state) and EMIT_BACKFILLED_ALREADY_SOLVED:
                    new_events.append(make_event(num, None, new_state, info))
                continue

            if not is_solved(old) and is_solved(new_state):
                new_events.append(make_event(num, old, new_state, info))

    # Update stored state to the current bare states.
    new_state_map = {num: info["state"] for num, info in current.items()}

    if new_events:
        # newest first
        events = new_events + events
        events = events[:MAX_EVENTS]

    # Write everything.
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(new_state_map, fh, indent=0, sort_keys=True)
    with open(EVENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(events, fh, indent=2)
    with open(FEED_PATH, "w", encoding="utf-8") as fh:
        fh.write(build_feed(events))

    if first_run:
        print(f"First run: seeded {len(new_state_map)} problems. No events emitted.")
    else:
        print(f"Checked {len(current)} problems. New solved transitions: {len(new_events)}.")
        for ev in new_events:
            print(f"  #{ev['number']}: {ev['from']} -> {ev['to']}")


def make_event(num, from_state, to_state, info):
    return {
        "number": num,
        "from": from_state,
        "to": to_state,
        "event_date": info.get("last_update"),
        "last_update": info.get("last_update"),
        "detected_at": now_iso(),
    }


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
