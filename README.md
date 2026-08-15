# pspsps

Named after the universal cat-summoning sound. It watches the couch through a
webcam, runs a local YOLO11m model at 960px on each frame, and sends the picture to my
iPad when the cat turns up — once per visit, not once every five minutes.

The whole thing is one script (`pspsps.py`), one pip dependency
(`ultralytics`), and two subprocesses (`ffmpeg`, `tailscale`). Detection runs
entirely on the machine — no frame is uploaded anywhere to decide whether it has
a cat in it.

## This is a one-machine project

It is written for one couch, one webcam, and one Windows PC — mine. The camera
is hardcoded as the DirectShow device `1080P Pro Stream`, ffmpeg is expected at
the path WinGet puts it, the Taildrop targets are named `ipad165` and
`iphone182`, and the archive folder is `G:\My Drive\kitty\`. The script also
reads `%LOCALAPPDATA%` at import time, so it will not even start on Linux or
macOS.

None of that is configurable yet. Read it as a recipe to adapt rather than
something to install: the constants all live at the top of `pspsps.py`, and the
capture flags in particular were tuned against a real dark living room (see
`PLAN.md` for why each one is there).

## What one pass does

1. **Capture** — ffmpeg grabs a single 1080p MJPEG frame from the webcam, waits
   3 seconds first so auto-exposure settles, and applies a gamma lift
   (`eq=gamma=2.4:saturation=1.2`) because the room is dark. The lifted frame is
   what gets detected on.
2. **Detect** — YOLO11m at 960px, restricted to the COCO `cat` class. Confidence `>= 0.60`
   is the cat. Anything below counts as no cat, though the 0.25–0.60 band is
   reported separately as borderline, because that is what M3 will hand to
   Claude.
3. **Decide** — a two-state machine. The first sighting after an absence is an
   alert; further sightings are quiet. One miss does not end a visit (she gets
   behind a cushion); two consecutive misses do, and the next sighting after
   that alerts again.
4. **Save** — every detection, alert or not, is archived to
   `G:\My Drive\kitty\kitty-YYYYMMDD-HHMMSS.jpg` via Google Drive for Desktop.
   If `G:\My Drive` is not mounted, the frame goes to a local `pending\` folder
   instead and the run says so. Archived frames are the annotated ones, with
   YOLO's box drawn on — the box is the evidence.
5. **Alert** — on the away-to-present edge only, the annotated frame is
   Taildropped to the first device that `tailscale status` shows online, trying
   `ipad165` before `iphone182`. If both are offline it logs that and moves on;
   the Drive copy is the backstop.

A failed pass is not evidence the cat left. If the camera is busy — it is
single-client, so anything else holding it wins — the pass logs the error, the
state is left alone, and the next tick tries again.

## Requirements

- **Windows** with a webcam that ffmpeg can see as a DirectShow device.
- **Python 3** with `venv`.
- **ffmpeg** at `%LOCALAPPDATA%\Microsoft\WinGet\Links\ffmpeg.exe`, which is
  where `winget install ffmpeg` puts it.
- **Tailscale** on `PATH`, with Taildrop working to the devices you want the
  alert on.
- **Google Drive for Desktop**, mounted at `G:`, for the archive. Optional in
  practice — without it every frame lands in `pending\`.

## Setup

```
py -3 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

Then activate it — `.venv\Scripts\Activate.ps1` in PowerShell,
`.venv\Scripts\activate.bat` in cmd — so that `python` below means the venv's
python.

Two downloads happen once and are not small: `ultralytics` pulls in the CPU
build of torch (~2GB), and the first detection fetches the `yolo11m.pt` weights
(40,684,120 bytes, ~40.7MB) into the repo root. Both are cached afterwards, and neither is committed.

## Running

```
python pspsps.py --selftest
```

Runs detection on `tests/fixture-cat.jpg`, a picture that definitely contains a
cat, and exits nonzero if the model disagrees. This is the check that the whole
capture-free half of the pipeline still works; run it first, since it needs no
camera. Pass a path — `python pspsps.py --selftest some-frame.jpg` — to point it
at any other image.

```
python pspsps.py --once
```

Captures one frame from the webcam and prints the verdict. No alert, no archive,
nothing sent — this is the loop for aiming the camera and arguing with the
lighting.

```
python pspsps.py
```

The real thing: capture, detect, decide, save, alert — every 5 minutes until
Ctrl+C. Each pass prints its verdict, and anything worth a timestamp — a save, a
Taildrop, a pass that failed — gets one.

There is also `python tests/test_state.py`, which exercises the once-per-visit
logic and the Taildrop device choice with no camera and no torch import. It
prints `test_state OK` and takes about a second.

## Roadmap

M3 is Claude: verifying the borderline detections that currently count as
no-cat, and writing a one-line caption to send with the alert. Neither exists
yet. `PLAN.md` has the design.

## Credits

`tests/fixture-cat.jpg` is
[Cat August 2010-4.jpg](https://commons.wikimedia.org/wiki/File:Cat_August_2010-4.jpg)
by Alvesgaspar, from Wikimedia Commons, used under
[CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).

Detection is [Ultralytics](https://github.com/ultralytics/ultralytics) YOLO11m at 960px.
