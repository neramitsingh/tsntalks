"""Choose one clean still per episode from a folder of candidate frames.

    python infra/pick_stills.py <frames_dir>

`<frames_dir>` holds `<video_id>-<n>.jpg` candidates (frames pulled from the
episode itself, never the YouTube thumbnail — the thumbnail has the headline and
the guest's name baked in, and the site sets those in its own type).

For each video id this writes:

    site/img/episodes/<id>.jpg   the frame, 1600px wide — the hero and any wide use
    site/img/faces/<id>.jpg      a 4:5 crop around the guest's face — the strip

The pick prefers a frame with a detected face, largest face first, then the
sharpest. A video with no detectable face in any candidate still gets an
episode still (the sharpest frame) but no face crop; the strip falls back to the
thumbnail for that one. Both folders are manifested by the Pages workflow, so
committing the files is the whole change.

**Hand picks.** The detector cannot tell the guest from the host, and a group
photograph in the b-roll has the most faces of all. `infra/still_picks.json`
overrides it per video: `{"frame": 3}` pins the candidate, `{"face": "right"}`
takes the rightmost face in a two-shot (the guest sits on the right in the
FORM studio episodes), `"left"` the leftmost, `"upper"` ignores anything found
below the middle of the frame (hands on a table read as a face once), and an
explicit `[x, y, w, h]` box in frame pixels skips detection altogether. When a
side is asked for, frames showing at least two faces win over single shots, so
a host monologue never becomes the guest's tile.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "site" / "img" / "episodes"
FACES = ROOT / "site" / "img" / "faces"
PICKS = ROOT / "infra" / "still_picks.json"
STILL_W = 1600
FACE_W, FACE_H = 800, 1000

_front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


def faces_in(gray):
    boxes = _front.detectMultiScale(gray, 1.1, 5, minSize=(110, 110))
    if len(boxes) == 0:
        boxes = _prof.detectMultiScale(gray, 1.1, 4, minSize=(110, 110))
    return [tuple(int(v) for v in b) for b in boxes]


def area(b):
    return b[2] * b[3]


def choose_face(boxes, hint, height):
    """Which detected face is the guest, given the hint from still_picks.json."""
    if not boxes:
        return None
    if hint == "left":
        return min(boxes, key=lambda b: b[0] + b[2] / 2)
    if hint == "right":
        return max(boxes, key=lambda b: b[0] + b[2] / 2)
    if hint == "upper":
        upper = [b for b in boxes if b[1] + b[3] / 2 < height * 0.6]
        return max(upper, key=area) if upper else None
    return max(boxes, key=area)


def score(path: Path, hint):
    im = cv2.imread(str(path))
    if im is None:
        return None
    h, w = im.shape[:2]
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    sharp = cv2.Laplacian(g, cv2.CV_64F).var()
    if isinstance(hint, list):
        face = tuple(int(v) for v in hint)
        return (face[2], 1, sharp), face, w, h
    boxes = faces_in(g)
    face = choose_face(boxes, hint, h)
    # a face is worth more than any amount of sharpness; among faces, bigger then
    # sharper. With a side hint, a two-shot (two faces found) outranks a single
    # shot, which is how a host monologue loses to the frame with the guest in it.
    two = 1 if (hint in ("left", "right") and len(boxes) >= 2) else 0
    key = ((face[2] if face else 0), two, sharp)
    return key, face, w, h


def save_still(src: Path, dst: Path):
    im = Image.open(src).convert("RGB")
    # The show burns its logo into the top-right of every frame; it stays. A crop
    # deep enough to remove it would take the guest's head with it, and an
    # inpaint smears the shelf behind it, so the page dims it with a top vignette
    # instead of the still pretending it was never there.
    if im.width > STILL_W:
        im = im.resize((STILL_W, round(im.height * STILL_W / im.width)), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=82, optimize=True, progressive=True)


def save_face(src: Path, face, dst: Path):
    x, y, w, h = face
    im = Image.open(src).convert("RGB")
    W, H = im.size
    # the crop is 4:5 with the face in the upper third, shoulders in frame
    ch = min(H, int(h * 3.2))
    cw = int(ch * FACE_W / FACE_H)
    if cw > W:
        cw = W; ch = int(cw * FACE_H / FACE_W)
    cx = x + w / 2
    top = max(0, min(H - ch, int(y - h * 0.75)))
    left = max(0, min(W - cw, int(cx - cw / 2)))
    crop = im.crop((left, top, left + cw, top + ch)).resize((FACE_W, FACE_H), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dst, "JPEG", quality=84, optimize=True, progressive=True)


def load_picks() -> dict:
    if not PICKS.exists():
        return {}
    data = json.loads(PICKS.read_text(encoding="utf-8"))
    return {k: v for k, v in data.items() if not k.startswith("_")}


def main(frames_dir: Path) -> int:
    picks = load_picks()
    groups: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(frames_dir.glob("*.jpg")):
        m = re.fullmatch(r"([A-Za-z0-9_-]{11})-(\d+)", p.stem)
        if m:
            groups[m.group(1)].append(p)
    if not groups:
        print(f"no <id>-<n>.jpg frames in {frames_dir}")
        return 1
    for vid, paths in groups.items():
        pick = picks.get(vid, {})
        if "frame" in pick:
            want = f"{vid}-{pick['frame']}"
            pinned = [p for p in paths if p.stem == want]
            if not pinned:
                print(f"{vid}: still_picks.json pins {want}.jpg but it is not in {frames_dir}; skipped")
                continue
            paths = pinned
        hint = pick.get("face", "largest")
        scored = [(s, p) for p in paths if (s := score(p, hint))]
        if not scored:
            print(f"{vid}: unreadable"); continue
        (key, face, w, h), best = max(scored, key=lambda t: t[0][0])
        save_still(best, EPISODES / f"{vid}.jpg")
        if face:
            save_face(best, face, FACES / f"{vid}.jpg")
        else:
            (FACES / f"{vid}.jpg").unlink(missing_ok=True)
        how = f"pinned frame {pick['frame']}" if "frame" in pick else "auto"
        print(f"{vid}: {best.name}  face={'yes' if face else 'no'} ({hint})  sharp={key[2]:.0f}  {w}x{h}  [{how}]")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    raise SystemExit(main(Path(sys.argv[1])))
