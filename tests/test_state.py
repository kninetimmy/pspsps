#!/usr/bin/env python3
"""The once-per-visit logic, checked without a camera: python tests/test_state.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pspsps import AWAY, PRESENT, pick_device, step


def run(detections: list) -> list:
    """Feed a run of passes through the machine, collect (state, alert) for each."""
    state, misses, out = AWAY, 0, []
    for detected in detections:
        state, misses, alert = step(state, misses, detected)
        out.append((state, alert))
    return out


def status(ipad: bool, iphone: bool) -> str:
    """A `tailscale status` listing with each Taildrop target up or down."""
    up = "active; direct 172.58.245.47:52135, tx 41125752 rx 13772304"
    down = "offline, last seen 2d ago"
    return (
        "100.102.188.1   desktop-lcj0f6h  kninetimmy@  windows  -\n"
        f"100.108.176.96  ipad165          kninetimmy@  iOS      {up if ipad else down}\n"
        f"100.74.57.83    iphone182        kninetimmy@  iOS      {up if iphone else down}\n"
    )


# one visit: the first sighting alerts, every repeat stays quiet
assert run([True]) == [(PRESENT, True)]
assert run([True, True, True]) == [(PRESENT, True), (PRESENT, False), (PRESENT, False)]

# a single miss is her behind a cushion, not a departure - and no re-alert after it
assert run([True, False, True]) == [(PRESENT, True), (PRESENT, False), (PRESENT, False)]

# two consecutive misses end the visit
assert run([True, False, False]) == [(PRESENT, True), (PRESENT, False), (AWAY, False)]

# ...and the next sighting is a new visit, so it alerts again
assert run([True, False, False, True])[-1] == (PRESENT, True)

# the miss counter resets on a sighting: miss, see, miss must not add up to a departure
assert run([True, False, True, False])[-1] == (PRESENT, False)

# an empty couch never alerts, however long we stare at it
assert run([False] * 5) == [(AWAY, False)] * 5

# Taildrop target: the iPad wins when it is up, the iPhone is the fallback
assert pick_device(status(True, True)) == "ipad165"
assert pick_device(status(True, False)) == "ipad165"
assert pick_device(status(False, True)) == "iphone182"

# both down (or tailscale itself down) -> no target: skip the send, keep the Drive copy
assert pick_device(status(False, False)) is None
assert pick_device("") is None

# an idle-but-reachable peer reports "-", not "offline": still a valid target
assert pick_device("100.108.176.96  ipad165  kninetimmy@  iOS  -") == "ipad165"

print("test_state OK")
