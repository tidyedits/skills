#!/usr/bin/env python3
"""Watch a video from the cloud: YouTube, Instagram, TikTok, any yt-dlp site, or a local file.
Usage: python3 -I watch.py URL_OR_FILE OUTDIR
Writes OUTDIR/info.txt, transcript.txt ([mm:ss] lines; captions, else local Whisper on the
audio), sheet-NN.jpg (4x4 grids of time-stamped frames), and when the real video is
available cuts.txt (every hard cut) and audio.txt (loudness, speech share).
YouTube usually blocks downloads from cloud servers; then frames come from storyboards."""
import sys, os, re, json, glob, subprocess, email, base64, io
url, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
YT = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--sleep-requests", "1"]
CLIENTS = ["default", "web_safari", "mweb", "tv_simply"]
def run(args): return subprocess.run(args, capture_output=True, text=True)
def yt(args):
    for c in CLIENTS:
        ex = [] if c == "default" else ["--extractor-args", f"youtube:player_client={c}"]
        r = run(YT + ex + args)
        if r.returncode == 0: return r
    return r
local = os.path.isfile(url)
# 1. info
r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", url]) if local else yt(["-f", "best/sb0/sb1", "-J", url]); info = json.loads(r.stdout) if r.returncode == 0 else {}
if local: info = {"title": os.path.basename(url), "duration": float(info.get("format", {}).get("duration", 0))}
dur = info.get("duration") or 0
open(f"{out}/info.txt", "w").write(
    f"title: {info.get('title')}\nchannel: {info.get('channel')}\nviews: {info.get('view_count')}\n"
    f"duration_s: {dur}\nupload: {info.get('upload_date')}\n\n{info.get('description','')}\n")
# 2. transcript with timestamps
import time
for attempt in range(0 if local else 3):
    yt(["--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en,en-orig,en-US", "--sub-format", "vtt", "-o", f"{out}/subs", url])
    if glob.glob(f"{out}/subs*.vtt"): break
    caps = {**info.get("automatic_captions", {}), **info.get("subtitles", {})}  # fallback: caption URLs from step 1
    u = next((t["url"] for k in ("en", "en-orig", "en-US") for t in caps.get(k, []) if t.get("ext") == "vtt"), None)
    if u and run(["curl", "-sfL", "-o", f"{out}/subs.en.vtt", u]).returncode == 0: break
    time.sleep(20)
lines, last = [], None
for f in sorted(glob.glob(f"{out}/subs*.vtt"))[:1]:
    t = None
    for l in open(f, encoding="utf-8"):
        m = re.match(r"(\d+):(\d+):(\d+)\.\d+ -->", l)
        if m: t = int(m[1])*3600 + int(m[2])*60 + int(m[3]); continue
        l = re.sub(r"<[^>]+>", "", l).strip()
        if not l or l.startswith(("WEBVTT", "Kind:", "Language:")) or l == last: continue
        last = l; t = t or 0; lines.append(f"[{t//60:02d}:{t%60:02d}] {l}")
open(f"{out}/transcript.txt", "w").write("\n".join(lines) or "(no captions)")
# 3. frames: try a small real video first, fall back to storyboard
from PIL import Image, ImageDraw
frames = []  # (seconds, PIL image)
n = 48
if local: vids = [url]
else:
    yt(["-f", "b[height<=720][ext=mp4]/bv*[height<=720]+ba/b", "-o", f"{out}/video.%(ext)s", url])
    vids = [v for v in glob.glob(f"{out}/video.*") if not v.endswith(".part")]
if vids and not dur:  # some sites (Instagram) give no duration up front
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", vids[0]])
    dur = float(r.stdout.strip() or 0)
if vids and dur:
    v = vids[0]
    # hard cuts (scene change > 0.3) with their times
    r = run(["ffmpeg", "-i", v, "-vf", "select='gt(scene,0.3)',showinfo", "-f", "null", "-"])
    cuts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    open(f"{out}/cuts.txt", "w").write(f"cuts: {len(cuts)} in {dur:.0f}s (avg shot {dur/(len(cuts)+1):.1f}s)\n" +
        "\n".join(f"{int(c)//60:02d}:{c%60:04.1f}" for c in cuts))
    # frames: one just after each cut plus an even grid, deduped by second
    times = sorted({int(t) for t in [i*dur/n for i in range(n)] + [c + 0.3 for c in cuts] if t < dur})
    for t in times:
        p = f"{out}/f_{t:05d}.jpg"
        run(["ffmpeg", "-loglevel", "error", "-ss", str(t), "-i", v, "-frames:v", "1", "-vf", "scale=320:-2", p, "-y"])
        if os.path.exists(p): frames.append((t, Image.open(p).convert("RGB")))
    # audio: loudness, and speech via local Whisper when there were no captions
    a = f"{out}/audio.wav"
    if run(["ffmpeg", "-loglevel", "error", "-i", v, "-vn", "-ac", "1", "-ar", "16000", a, "-y"]).returncode == 0:
        vol = " ".join(re.findall(r"(mean_volume: \S+ dB|max_volume: \S+ dB)", run(["ffmpeg", "-i", a, "-af", "volumedetect", "-f", "null", "-"]).stderr))
        speech = 0.0
        try:
            import wave, numpy as np
            from faster_whisper import WhisperModel
            w = wave.open(a); pcm = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            segs, _ = WhisperModel("small", device="cpu", compute_type="int8").transcribe(pcm, vad_filter=True)
            segs = list(segs); speech = sum(x.end - x.start for x in segs)
            if not lines:
                lines = [f"[{int(x.start)//60:02d}:{int(x.start)%60:02d}] {x.text.strip()}" for x in segs]
                open(f"{out}/transcript.txt", "w").write("\n".join(lines) or "(no speech)")
        except Exception as e:
            vol += f" (whisper unavailable: {e.__class__.__name__})"
        open(f"{out}/audio.txt", "w").write(f"{vol}\nspeech: {speech:.0f}s of {dur:.0f}s ({100*speech/dur:.0f}%); the rest is music, sound or silence\n")
    src = "video"
else:
    yt(["-f", "sb0/sb1", "-o", f"{out}/sb.%(ext)s", url])
    fmt = next((x for x in info.get("formats", []) if x.get("format_id") == "sb0"), None) or {}
    rows, cols = fmt.get("rows", 5), fmt.get("columns", 5)
    fw, fh, fps = fmt.get("width"), fmt.get("height"), fmt.get("fps")
    tiles = []
    if not glob.glob(f"{out}/sb.*"):  # fallback: fetch storyboard images straight from the step 1 URLs
        for i, fr in enumerate(fmt.get("fragments", [])):
            u = fr.get("url") or (fmt.get("fragment_base_url", "") + fr.get("path", ""))
            if run(["curl", "-sfL", "-o", f"{out}/sbf_{i:03d}.jpg", u]).returncode == 0:
                tiles.append(Image.open(f"{out}/sbf_{i:03d}.jpg").convert("RGB"))
    for p in glob.glob(f"{out}/sb.*"):
        msg = email.message_from_bytes(open(p, "rb").read())
        for part in msg.walk():
            if part.get_content_maintype() == "image":
                tiles.append(Image.open(io.BytesIO(part.get_payload(decode=True))).convert("RGB"))
    cells = []
    for im in tiles:
        w, h = (fw or im.width // cols), (fh or im.height // rows)
        for y in range(rows):
            for x in range(cols):
                c = im.crop((x*w, y*h, x*w+w, y*h+h))
                if x*w < im.width and y*h < im.height and c.convert("L").getextrema()[1] > 10: cells.append(c)
    per = (1 / fps) if fps else (dur / len(cells) if cells and dur else 0)
    frames = [(int(i*per), c) for i, c in enumerate(cells)]
    src = "storyboard"
if len(frames) > n:  # keep about n evenly spaced frames
    frames = [frames[round(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
# 4. contact sheets, 4x4 per sheet, time label on each frame
for s in range(0, len(frames), 16):
    chunk = frames[s:s+16]; w, h = chunk[0][1].size
    sheet = Image.new("RGB", (w*4, h*4), "white"); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(chunk):
        x, y = (i % 4)*w, (i//4)*h; sheet.paste(im.resize((w, h)), (x, y))
        d.rectangle((x, y, x+44, y+14), fill="black"); d.text((x+3, y+2), f"{t//60:02d}:{t%60:02d}", fill="white")
    sheet.save(f"{out}/sheet-{s//16+1:02d}.jpg", quality=85)
print(f"source={src} frames={len(frames)} sheets={(len(frames)+15)//16} transcript_lines={len(lines)} out={out}")
