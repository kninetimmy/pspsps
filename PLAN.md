# pspsps — the kitty detector

Watches the couch webcam, detects the cat with a local YOLO model, and tells
you when she shows up. Named after the universal cat-summoning sound.

## Decisions (grilled and locked, 2026-08-14)

| Decision | Choice |
|---|---|
| Detection | Stage 1: local YOLO11m at 960px (`ultralytics`). Stage 2: Claude via `claude -p` headless — uses the Claude Code subscription, **never** the pay-per-token API |
| Runtime | Manual start: run `pspsps`, loops until Ctrl+C. No scheduler, no service |
| Cadence | Snap + detect every 5 minutes |
| Alerting | Once per visit: first detection alerts, repeats stay quiet until she's been gone 2 consecutive checks |
| Alert action | Taildrop annotated frame to iPad/iPhone (whichever is online) + copy frame to `G:\My Drive\kitty\` |
| Claude's jobs | (1) verify borderline YOLO detections, (2) write a funny one-line caption sent with the alert |
| Stack | Python 3.x, venv in project dir, `ultralytics` (only pip dep), ffmpeg + tailscale as subprocesses |
| Repo | Private GitHub repo `pspsps`, feature-branch + PR workflow |

## How it works (one loop pass, every 5 min)

1. **Capture** — ffmpeg one-shot frame, using the proven couch-cam recipe:
   - binary: `%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe`
   - device: dshow `1080P Pro Stream`
   - flags: `-vcodec mjpeg -framerate 30 -video_size 1920x1080 -rtbufsize 256M -ss 3 -frames:v 1`
     (mjpeg@30 forced or the shutter drags and blows out white; 1080p forced or it
     defaults to blurry 640x480; `-ss 3` lets auto-exposure settle)
   - post: `eq=gamma=2.4:saturation=1.2` — gamma-only shadow lift for the dark room.
     Never add `brightness=`; it grays the blacks and looks washed out.
     Run detection on the *lifted* frame (YOLO sees the dark original poorly too).
2. **Detect** — YOLO11m at 960px, COCO class `cat`:
   - confidence ≥ 0.60 → cat, no question
   - 0.25–0.60 → borderline → ask Claude: `claude -p "Is there a real cat in this
     image? Answer only yes or no." <frame>` — yes counts as cat
   - < 0.25 → no cat
   - Claude CLI errors on a borderline frame → treat as no-cat, log a warning,
     still save the frame to Drive so nothing is lost. (Fail toward quiet, not spam.)
3. **State machine** (the once-per-visit logic):
   - `AWAY` + detection → `PRESENT`, fire the alert
   - `PRESENT` + detection → stay `PRESENT`, save frame to Drive, no alert
   - `PRESENT` + 2 consecutive misses → `AWAY` (1 miss could be her behind a cushion)
4. **Alert** (on the AWAY→PRESENT edge only):
   - draw YOLO's box on the frame
   - caption via `claude -p` ("one funny line about what this cat is doing"); caption
     failure is non-fatal — alert goes out captionless
   - `tailscale file cp <frame> <device>:` — try `ipad165:` then `iphone182:`,
     first online device wins (check `tailscale status`)
   - copy to `G:\My Drive\kitty\` (verified mounted on this machine)
5. **Every** detection (alert or not) saves to Drive as `kitty-YYYYMMDD-HHMMSS.jpg`.
   Non-detections save nothing. Local scratch keeps only the latest frame.

## Files

```
pspsps/
  PLAN.md            this file
  CLAUDE.md          repo instructions (stack, run/test commands)
  pspsps.py          the whole thing — single script, ~150 lines
  requirements.txt   ultralytics
  .gitignore         .venv/, *.jpg, *.mkv, yolo11m.pt
  tests/fixture-cat.jpg   one known-cat frame for the self-test
```

`pspsps.py --once` does a single pass and prints the verdict (debug loop).
`pspsps.py --selftest` runs detection on `tests/fixture-cat.jpg` and asserts a cat
is found — the one runnable check that fails if the pipeline breaks.

## Milestones (one PR each)

1. **M1 — see the cat:** capture + YOLO verdict printed to console. `--once` and
   `--selftest` work. No alerts yet.
2. **M2 — tell the human:** 5-min loop, state machine, Taildrop + Drive copy,
   annotated frame.
3. **M3 — Claude:** borderline verification + funny caption via `claude -p`.

## Known edges (accepted, not blockers)

- Webcam is single-client: if Claude Code (or anything) grabs the camera during a
  pass, that pass fails → log and retry next tick, don't crash.
- Both Tailscale devices offline → skip Taildrop, Drive copy still happens, log it.
- Google Drive `G:` not mounted (Drive app not running) → save to a local
  `pending/` folder and log; no sync-retry logic in v1.
- First run downloads `yolo11m.pt` (40,684,120 bytes, ~40.7MB) and torch CPU wheels (~2GB one-time).
