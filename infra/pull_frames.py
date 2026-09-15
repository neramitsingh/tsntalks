"""Pull candidate stills from every TSN Talks episode.

    python infra/pull_frames.py <frames_dir> [video_id ...]
    python infra/pick_stills.py <frames_dir>

Five short sections per video, one representative frame each, newest episode
first, into <frames_dir>/<video_id>-<n>.jpg. pick_stills.py then chooses one
per episode and writes site/img/episodes and site/img/faces.

Needs yt-dlp >= 2026.08 with yt-dlp-ejs (pip install -U "yt-dlp[default]"),
Node on PATH as the JS runtime, and ffmpeg. HLS through yt-dlp's native
downloader is the path YouTube does not throttle: the ffmpeg range path hung on
every episode but the newest.

Windows note: the section download is a child process tree. With captured
pipes, a timeout kills yt-dlp but an orphaned ffmpeg keeps the pipe open and
subprocess.run() blocks forever. So: no pipes, and taskkill /T on timeout.
"""
import json, subprocess, sys, pathlib, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
FRACS = [0.12, 0.30, 0.48, 0.66, 0.84]
only = set(sys.argv[2:])
SECTION_TIMEOUT = 70
FMT = "bv*[height<=1080][protocol^=m3u8]/b[height<=1080][protocol^=m3u8]/bv*[height<=1080][ext=mp4][protocol=https]"
YT = ["yt-dlp", "--js-runtimes", "node", "--no-update", "--no-playlist"]
KILL = ["taskkill", "/F", "/T", "/PID"] if sys.platform == "win32" else None

eps = json.load(open(ROOT / "data/live.json", encoding="utf-8"))["episodes"]
eps.sort(key=lambda e: e["published_at"], reverse=True)
log = open(OUT / "frames.log", "a", encoding="utf-8")

def note(msg):
    log.write(msg + "\n"); log.flush(); print(msg, flush=True)

def probe_duration(url):
    try:
        r = subprocess.run(YT + ["--print", "%(duration)s", "--skip-download", url],
                           capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
        return float(r.stdout.strip().splitlines()[-1])
    except Exception:
        return None

def fetch_section(url, t, seg):
    cmd = YT + ["--downloader", "dash,m3u8:native", "-f", FMT, "--download-sections", f"*{t}-{t + 3}",
                "--force-overwrites", "--no-part", "-q", "-o", str(seg), url]
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        p.wait(timeout=SECTION_TIMEOUT)
    except subprocess.TimeoutExpired:
        if KILL:
            subprocess.run(KILL + [str(p.pid)], capture_output=True)
        else:
            p.kill()
        return "timeout"
    return "ok" if seg.exists() else f"exit {p.returncode}"

for e in eps:
    vid = e["youtube_video_id"]
    if only and vid not in only:
        continue
    if all((OUT / f"{vid}-{k}.jpg").exists() for k in range(len(FRACS))):
        continue
    url = f"https://www.youtube.com/watch?v={vid}"
    dur = probe_duration(url)
    if not dur:
        note(f"{vid} duration probe failed  S{e['season']}E{e['number']} {e['guest']}"); continue
    for k, f in enumerate(FRACS):
        jpg = OUT / f"{vid}-{k}.jpg"
        if jpg.exists():
            continue
        t = int(dur * f)
        seg = OUT / f"_{vid}-{k}.mp4"
        t0 = time.time()
        status = fetch_section(url, t, seg)
        if status != "ok":
            note(f"{vid}-{k} section {status} after {time.time()-t0:.0f}s  S{e['season']}E{e['number']} {e['guest']}  -> skipping this video")
            seg.unlink(missing_ok=True)
            break
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(seg),
                            "-vf", "thumbnail=60", "-frames:v", "1", "-q:v", "2", str(jpg)],
                           capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
        seg.unlink(missing_ok=True)
        note(f"{vid}-{k} {'ok' if jpg.exists() else 'ffmpeg failed: ' + r.stderr[-200:]} t={t}s of {int(dur)}s "
             f"S{e['season']}E{e['number']} {e['guest']}  ({time.time()-t0:.0f}s)")

note("DONE"); log.close()
