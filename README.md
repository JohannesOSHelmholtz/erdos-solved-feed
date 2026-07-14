# Erdős Problems — Open → Solved feed

An RSS/Atom feed that gets a new entry every time an Erdős problem changes
from **open** to **solved** on [erdosproblems.com](https://www.erdosproblems.com).
Runs entirely on free GitHub Actions — no server, no cost.

Subscribe to the generated `feed.xml` in any feed reader that supports push
notifications (Feedly, Inoreader, NetNewsWire, Miniflux, FreshRSS, …).

## How it works

erdosproblems.com does **not** publish its own feed. But the site's data lives
in a public, actively-synced community database:
[`teorth/erdosproblems`](https://github.com/teorth/erdosproblems) →
`data/problems.yaml`. Each problem has a `status.state` field (`open`,
`proved`, `disproved`, `solved`, …).

Every 6 hours a GitHub Action:

1. downloads `problems.yaml` from the upstream repo,
2. compares each problem's status against the previously seen state
   (`data/state.json`),
3. writes an Atom entry for every problem that just went from *not solved*
   to *solved*, and
4. commits the updated `feed.xml` back to this repo.

**"Solved"** is defined exactly like the project's own statistics: `status.state`
(ignoring a trailing ` (Lean)`) equal to `proved`, `disproved`, or `solved`.
States like `verifiable`/`falsifiable`/`independent` are *not* counted as solved.
You can change this in `SOLVED_BASE_STATES` at the top of
`scripts/check_solved.py`.

## Setup (about 5 minutes)

1. Create a **new empty GitHub repository** (public is simplest) and copy these
   files into it, keeping the folder layout:
   ```
   .github/workflows/erdos-solved-feed.yml
   scripts/check_solved.py
   data/state.json      # pre-seeded with the current status of all problems
   data/events.json     # [] to start
   feed.xml             # empty feed to start
   README.md
   ```
2. In the repo: **Settings → Actions → General → Workflow permissions** →
   select **Read and write permissions** → Save.
   (The workflow also requests this via its `permissions:` block, but the repo
   setting must allow it.)
3. Go to the **Actions** tab, enable workflows if prompted, open
   *"Erdős Open → Solved feed"*, and click **Run workflow** once to arm it.
4. Subscribe your feed reader to:
   ```
   https://raw.githubusercontent.com/<your-user>/<your-repo>/main/feed.xml
   ```

That's it. From now on you get one feed entry per newly solved problem, each
linking to `https://www.erdosproblems.com/<number>`.

### Optional: a nicer feed URL via GitHub Pages
`raw.githubusercontent.com` serves the file as `text/plain`, which almost every
reader accepts. If you want a proper `application/xml` URL instead, enable
**Settings → Pages → Deploy from branch → main → / (root)**; the feed is then at
`https://<your-user>.github.io/<your-repo>/feed.xml`.

## Behaviour notes (so nothing surprises you)

- **No backlog flood.** The shipped `data/state.json` is already seeded with the
  current status of every problem, so you only get transitions that happen
  *after* you set this up — not the ~550 problems already solved.
- **Backfilled old solutions are skipped by default.** If a problem is added to
  the database already-solved, it is not emitted. Set
  `EMIT_BACKFILLED_ALREADY_SOLVED = True` in the script to include those.
- **Latency.** The upstream database syncs roughly daily; the Action runs every
  6 hours. So expect notifications within about a day of a status change, not
  instantly.
- **To re-seed from scratch**, delete `data/state.json` and run the workflow;
  the next run will re-snapshot silently without emitting a flood.
- **GitHub caveat:** scheduled Actions on a repo with *no commits for 60 days*
  get auto-disabled by GitHub. This feed commits whenever something changes, and
  you can always re-enable or hit *Run workflow* manually.

## Data credit

Problem data © the [`teorth/erdosproblems`](https://github.com/teorth/erdosproblems)
community database and [erdosproblems.com](https://www.erdosproblems.com)
(T. F. Bloom). This project only reads that data and reformats status changes
as a feed.
