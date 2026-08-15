#!/usr/bin/env python3
"""pspsps - the kitty detector. M1: capture a frame, print a YOLO cat verdict."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ultralytics import YOLO

HERE = Path(__file__).resolve().parent
FRAME = HERE / "frame.jpg"                  # local scratch: latest frame only
# fixture: Wikimedia Commons "Cat August 2010-4.jpg" by Alvesgaspar, CC BY-SA 3.0
FIXTURE = HERE / "tests" / "fixture-cat.jpg"

FFMPEG = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
DEVICE = "video=1080P Pro Stream"
LIFT = "eq=gamma=2.4:saturation=1.2"        # gamma-only; brightness= grays the blacks

CAT_CLASS = 15                              # COCO 'cat'
SURE = 0.60                                 # >= this: it's the cat
BORDERLINE = 0.25                           # >= this but < SURE: M3 will ask Claude


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


def top_cat(image: Path) -> float:
    """Highest 'cat' confidence YOLOv8n finds in image, 0.0 if none."""
    if not image.exists():
        raise RuntimeError(f"no such image: {image}")
    result = YOLO("yolov8n.pt")(str(image), classes=[CAT_CLASS], verbose=False)[0]
    return max((float(b.conf) for b in result.boxes), default=0.0)


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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true",
                    help="capture one frame and print the verdict")
    ap.add_argument("--selftest", nargs="?", const=FIXTURE, type=Path, metavar="IMAGE",
                    help=f"detect on IMAGE (default {FIXTURE.name}); nonzero if no cat")
    args = ap.parse_args()

    if args.selftest:
        found = verdict(top_cat(args.selftest))
        if not found:
            print(f"selftest FAILED: no cat in {args.selftest}", file=sys.stderr)
        return 0 if found else 1

    if args.once:
        try:
            capture(FRAME)
        except RuntimeError as e:
            print(f"capture failed: {e}", file=sys.stderr)
            return 1
        verdict(top_cat(FRAME))
        return 0

    ap.error("M1 is --once or --selftest; the 5-minute loop lands in M2")


if __name__ == "__main__":
    sys.exit(main())
