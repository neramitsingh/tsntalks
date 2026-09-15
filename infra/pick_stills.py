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
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

import cv2
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "site" / "img" / "episodes"
FACES = ROOT / "site" / "img" / "faces"
STILL_W = 1600
FACE_W, FACE_H = 800, 1000

_front = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_prof = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")


def faces_in(gray):
    boxes = _front.detectMultiScale(gray, 1.1, 5, minSize=(110, 110))
    if len(boxes) == 0:
        boxes = _prof.detectMultiScale(gray, 1.1, 4, minSize=(110, 110))
    return [tuple(int(v) for v in b) for b in boxes]


def score(path: Path):
    im = cv2.imread(str(path))
    if im is None:
        return None
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    boxes = faces_in(g)
    sharp = cv2.Laplacian(g, cv2.CV_64F).var()
    face = max(boxes, key=lambda b: b[2] * b[3]) if boxes else None
    # a face is worth more than any amount of sharpness; among faces, bigger then sharper
    key = ((face[2] if face else 0), sharp)
    return key, face, im.shape[1], im.shape[0]


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


def main(frames_dir: Path) -> int:
    groups: dict[str, list[Path]] = defaultdict(list)
    for p in sorted(frames_dir.glob("*.jpg")):
        m = re.fullmatch(r"([A-Za-z0-9_-]{11})-(\d+)", p.stem)
        if m:
            groups[m.group(1)].append(p)
    if not groups:
        print(f"no <id>-<n>.jpg frames in {frames_dir}")
        return 1
    for vid, paths in groups.items():
        scored = [(s, p) for p in paths if (s := score(p))]
        if not scored:
            print(f"{vid}: unreadable"); continue
        (key, face, w, h), best = max(scored, key=lambda t: t[0][0])
        save_still(best, EPISODES / f"{vid}.jpg")
        if face:
            save_face(best, face, FACES / f"{vid}.jpg")
        print(f"{vid}: {best.name}  face={'yes' if face else 'no'}  sharp={key[1]:.0f}  {w}x{h}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    raise SystemExit(main(Path(sys.argv[1])))
