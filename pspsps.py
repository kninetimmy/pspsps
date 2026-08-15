#!/usr/bin/env python3
"""pspsps - the kitty detector. M2: 5-minute loop, once-per-visit alert, Drive copy."""

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAME = HERE / "frame.jpg"                  # local scratch: latest frame only
WEIGHTS = HERE / "yolov8n.pt"               # script-relative: another cwd, same weights
PENDING = HERE / "pending"                  # where frames land when Drive is missing
DRIVE = Path("G:/My Drive/kitty")
# fixture: Wikimedia Commons "Cat August 2010-4.jpg" by Alvesgaspar, CC BY-SA 3.0
FIXTURE = HERE / "tests" / "fixture-cat.jpg"

FFMPEG = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
DEVICE = "video=1080P Pro Stream"
LIFT = "eq=gamma=2.4:saturation=1.2"        # gamma-only; brightness= grays the blacks

CAT_CLASS = 15                              # COCO 'cat'
SURE = 0.60                                 # >= this: it's the cat
BORDERLINE = 0.25                           # >= this but < SURE: M3 will ask Claude

INTERVAL = 300                              # seconds between passes
LEAVE_AFTER = 2                             # misses before she's gone (1 = behind a cushion)
AWAY, PRESENT = "away", "present"
DEVICES = ("ipad165", "iphone182")          # Taildrop targets, first one online wins

_model = None                               # loaded on first detect, reused every pass


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def capture(dest: Path) -> None:
    """Grab one gamma-lifted 1080p frame from the couch cam. Raises on failure."""
    cmd = [
        str(FFMPEG), "-hide_banner", "-y",
        "-f", "dshow",
        "-vcodec", "mjpeg",                 # or the shutter drags and blows out white
        "-framerate", "30",
        "-video_size", "1920x1080",         # or dshow defaults to blurry 640x480
        "-rtbufsize", "256M",
        "-i", DEVICE,
        "-ss", "3",                         # let auto-exposure settle
        "-frames:v", "1",
        "-vf", LIFT,
        str(dest),
    ]
    dest.unlink(missing_ok=True)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise RuntimeError(f"ffmpeg not found at {FFMPEG}")
    except subprocess.TimeoutExpired:
        raise RuntimeError("ffmpeg timed out after 60s grabbing a frame")
    if p.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
        tail = (p.stderr or "").strip().splitlines()[-3:]
        raise RuntimeError(
            f"ffmpeg exit {p.returncode} on device {DEVICE!r} "
            "(camera absent or held by another process): " + " | ".join(tail)
        )


def detect(image: Path) -> tuple:
    """(highest 'cat' confidence, YOLO result) for image. Confidence 0.0 if no cat."""
    global _model
    if not image.exists():
        raise RuntimeError(f"no such image: {image}")
    if _model is None:
        from ultralytics import YOLO       # deferred: torch is slow, and the state
        _model = YOLO(WEIGHTS)             # test has no business importing it
    result = _model(str(image), classes=[CAT_CLASS], verbose=False)[0]
    return max((float(b.conf) for b in result.boxes), default=0.0), result


def verdict(conf: float) -> bool:
    """Print the verdict, return True if that's the cat."""
    if conf >= SURE:
        print(f"CAT (cat {conf:.2f} >= {SURE:.2f})")
        return True
    if conf >= BORDERLINE:
        print(f"NO CAT - BORDERLINE (cat {conf:.2f}, in {BORDERLINE:.2f}-{SURE:.2f}; "
              "M3 will ask Claude about these)")
        return False
    print(f"NO CAT (cat {conf:.2f} < {BORDERLINE:.2f})")
    return False


def step(state: str, misses: int, detected: bool) -> tuple:
    """One tick of the once-per-visit machine -> (state, misses, alert)."""
    if detected:
        return PRESENT, 0, state == AWAY
    if state == PRESENT and misses + 1 < LEAVE_AFTER:
        return PRESENT, misses + 1, False
    return AWAY, 0, False


def pick_device(status: str) -> str | None:
    """First DEVICES entry `tailscale status` shows as online, None if all are down."""
    up = {
        fields[1]
        for fields in (line.split(maxsplit=4) for line in status.splitlines())
        if len(fields) == 5 and not fields[4].startswith("offline")
    }
    return next((d for d in DEVICES if d in up), None)


def archive(frame: Path) -> Path:
    """Copy the frame to Drive as kitty-<stamp>.jpg, or to pending/ if Drive is gone."""
    dest_dir = DRIVE
    if not DRIVE.parent.is_dir():
        dest_dir = PENDING
        log(f"{DRIVE.parent} not mounted (Drive app not running?) - saving to {PENDING}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"kitty-{datetime.now():%Y%m%d-%H%M%S}.jpg"
    shutil.copyfile(frame, dest)
    return dest


def taildrop(frame: Path) -> None:
    """Send the frame to the first online device. Both offline: log it and move on."""
    try:
        p = subprocess.run(["tailscale", "status"], capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        raise RuntimeError("tailscale not found on PATH")
    except subprocess.TimeoutExpired:
        raise RuntimeError("tailscale status timed out after 30s")
    device = pick_device(p.stdout)
    if device is None:
        log(f"none of {', '.join(DEVICES)} online - no Taildrop, the Drive copy stands")
        return
    cmd = ["tailscale", "file", "cp", str(frame), f"{device}:"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"tailscale file cp to {device} timed out after 120s")
    if p.returncode != 0:
        raise RuntimeError(f"tailscale file cp to {device} exit {p.returncode}: "
                           + (p.stderr or "").strip())
    log(f"taildropped to {device}")


def watch() -> int:
    """Capture + detect every INTERVAL until Ctrl+C, alerting once per visit."""
    state, misses = AWAY, 0
    log(f"watching every {INTERVAL // 60} min - Ctrl+C to stop")
    try:
        while True:
            try:
                capture(FRAME)
                conf, result = detect(FRAME)
                found = verdict(conf)
                state, misses, alert = step(state, misses, found)
                if found:
                    result.save(filename=str(FRAME))    # YOLO's box, over the scratch frame
                    log(f"saved {archive(FRAME)}")
                    if alert:
                        taildrop(FRAME)
            except RuntimeError as e:
                # a bad pass is not evidence she left: log it, leave the state alone
                log(f"pass failed, retrying next tick: {e}")
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        log("stopped")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="capture one frame and print the verdict")
    ap.add_argument("--selftest", nargs="?", const=FIXTURE, type=Path, metavar="IMAGE",
                    help=f"detect on IMAGE (default {FIXTURE.name}); nonzero if no cat")
    args = ap.parse_args()

    if args.selftest:
        found = verdict(detect(args.selftest)[0])
        if not found:
            print(f"selftest FAILED: no cat in {args.selftest}", file=sys.stderr)
        return 0 if found else 1

    if args.once:
        try:
            capture(FRAME)
        except RuntimeError as e:
            print(f"capture failed: {e}", file=sys.stderr)
            return 1
        verdict(detect(FRAME)[0])
        return 0

    return watch()


if __name__ == "__main__":
    sys.exit(main())
