# pspsps

The kitty detector: watches the couch webcam, detects the cat with a local
YOLOv8n model, alerts once per visit via Taildrop + Google Drive copy.
Design is locked in `PLAN.md` — read it before changing anything.

## Session Continuity

memhub is the source of truth at `.memhub/project.sqlite`.
The rendered files under `.memhub/rendered/` are the local
human-readable view. They are generated from the DB and ignored by
Git by default. Re-render after `/wrap-up` with `memhub render`.

## Stack

Python 3.x, venv in project dir. Only pip dep: `ultralytics`.
ffmpeg and tailscale are invoked as subprocesses. Claude runs headless via
`claude -p` (subscription — never the pay-per-token API).

## Build / test / run

- Run once (debug): `python pspsps.py --once`
- Self-test: `python pspsps.py --selftest` (asserts a cat in `tests/fixture-cat.jpg`)
- Normal run: `python pspsps.py` — loops every 5 min until Ctrl+C
