"""
Telegram Video Conversion Bot (Powered by Pyrogram for 2GB Files)
====================================================================
- Truly parallel batch downloads and conversions.
- 2GB Large File Support out-of-the-box (MTProto).
- Easy to use messages and advanced options restored.
- NEW: Direct Convert - YouTube link থেকে সরাসরি কনভার্ট করুন।
- cookies.txt সাপোর্ট যোগ করা হয়েছে।
"""

import os
import re
import time
import asyncio
import logging
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# ── Auto-detect FFmpeg ────────────────────────────────────────────────────
def _find_ffmpeg() -> tuple[str, str]:
    system_ff = shutil.which("ffmpeg")
    system_fp = shutil.which("ffprobe")
    if system_ff and system_fp:
        return system_ff, system_fp
    try:
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
        fp = str(Path(ff).parent / "ffprobe")
        if not Path(fp).exists():
            fp = ff
        return ff, fp
    except Exception:
        pass
    raise RuntimeError("FFmpeg not found! Install it with: sudo apt install ffmpeg")

FFMPEG_BIN, FFPROBE_BIN = _find_ffmpeg()

from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Credentials (এখানে আপনার ডেটা দিন) ───────────────────────────────────
API_ID    = 25072571                          # আপনার API ID
API_HASH  = "1d8d4d849fd130618bb34aa82ea3df6f" # আপনার API HASH
BOT_TOKEN = "8632524497:AAF6StSmYfxTq-znsVBnpi_vgleNCF9b8J0"  # আপনার Bot Token

# ── Configuration ─────────────────────────────────────────────────────────
TEMP_DIR = Path.cwd() / "tg_video_bot_files"
TEMP_DIR.mkdir(parents=True, exist_ok=True)

YT_DLP_BIN       = shutil.which("yt-dlp") or "yt-dlp"   # yt-dlp পাথ
MAX_FILE_SIZE_MB  = 2000
MAX_CONCURRENT_TASKS = 2

# ── Cookies Path (bot.py এর পাশে cookies.txt রাখুন) ──────────────────────
COOKIES_FILE = Path(__file__).parent / "cookies.txt"

def _cookies_args() -> list:
    """cookies.txt থাকলে yt-dlp এর জন্য argument return করে।"""
    if COOKIES_FILE.exists():
        return ["--cookies", str(COOKIES_FILE)]
    return []

app = Client("video_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ══════════════════════════════════════════════════════════════════════════
# Conversion Options & States
# ══════════════════════════════════════════════════════════════════════════

VIDEO_CODECS = [
    {"id": "h264_mp4",  "label": "H.264 / MP4 (Universal)",    "codec": "libx264",   "ext": "mp4",  "extra": ["-preset", "fast", "-crf", "23"]},
    {"id": "h265_mp4",  "label": "H.265 / MP4 (Smaller Size)", "codec": "libx265",   "ext": "mp4",  "extra": ["-preset", "fast", "-crf", "28"]},
    {"id": "mpeg4",     "label": "MPEG-4 (Button Phones)",      "codec": "mpeg4",     "ext": "mp4",  "extra": ["-q:v", "6"]},
    {"id": "vp9_webm",  "label": "VP9 / WebM (Web Streaming)", "codec": "libvpx-vp9","ext": "webm", "extra": ["-b:v", "0", "-crf", "30"]},
    {"id": "copy",      "label": "Copy stream (No Re-encode)",  "codec": "copy",      "ext": "mp4",  "extra": []},
]

# বাটন ফোনের সব রেজুলেশন এবং নতুন রেশিও কিপার একসাথে
RESOLUTIONS = [
    {"id": "source",    "label": "Source (যাই আছে)",    "scale": None},
    {"id": "4k_kr",     "label": "4K (Keep Ratio)",     "scale": "-2:2160", "aspect": "keep"},
    {"id": "1080p_kr",  "label": "1080p (Keep Ratio)",  "scale": "-2:1080", "aspect": "keep"},
    {"id": "1080p11",   "label": "1080x1080 (1:1)",     "scale": "1080:1080", "aspect": "force"},
    {"id": "1080p169",  "label": "1080p (16:9)",        "scale": "1920:1080", "aspect": "force"},
    {"id": "1080p43",   "label": "1080p (4:3)",         "scale": "1440:1080", "aspect": "force"},
    {"id": "720p_kr",   "label": "720p (Keep Ratio)",   "scale": "-2:720",  "aspect": "keep"},
    {"id": "720p169",   "label": "720p (16:9)",         "scale": "1280:720",  "aspect": "force"},
    {"id": "720p43",    "label": "720p (4:3)",          "scale": "960:720",   "aspect": "force"},
    {"id": "480p_kr",   "label": "480p (Keep Ratio)",   "scale": "-2:480",  "aspect": "keep"},
    {"id": "480p169",   "label": "480p (16:9)",         "scale": "854:480",   "aspect": "force"},
    {"id": "480p43",    "label": "480p (4:3)",          "scale": "640:480",   "aspect": "force"},
    {"id": "360p_kr",   "label": "360p (Keep Ratio)",   "scale": "-2:360",  "aspect": "keep"},
    {"id": "360p169",   "label": "360p (16:9)",         "scale": "640:360",   "aspect": "force"},
    {"id": "360p43",    "label": "360p (4:3)",          "scale": "480:360",   "aspect": "force"},
    {"id": "240p169",   "label": "240p (16:9)",         "scale": "426:240",   "aspect": "force"},
    {"id": "240p43",    "label": "240p (4:3)",          "scale": "320:240",   "aspect": "force"},
    {"id": "144p169",   "label": "144p (16:9)",         "scale": "256:144",   "aspect": "force"},
    {"id": "144p43",    "label": "144p (4:3)",          "scale": "192:144",   "aspect": "force"},
]

FPS_OPTIONS = [
    {"id": "source", "label": "Source FPS", "fps": None},
    {"id": "60",     "label": "60 FPS",     "fps": "60"},
    {"id": "30",     "label": "30 FPS",     "fps": "30"},
    {"id": "24",     "label": "24 FPS",     "fps": "24"},
]

AUDIO_CODECS = [
    {"id": "aac",    "label": "AAC (Standard)", "codec": "aac",       "extra": ["-b:a", "128k"]},
    {"id": "mp3",    "label": "MP3",            "codec": "libmp3lame", "extra": ["-b:a", "192k"]},
    {"id": "opus",   "label": "Opus",           "codec": "libopus",    "extra": ["-b:a", "64k"]},
    {"id": "ac3",    "label": "AC3",            "codec": "ac3",        "extra": ["-b:a", "192k"]},
    {"id": "flac",   "label": "FLAC",           "codec": "flac",       "extra": []},
    {"id": "wav",    "label": "WAV",            "codec": "pcm_s16le",  "extra": []},
    {"id": "copy_a", "label": "Copy Audio",     "codec": "copy",       "extra": []},
]

AVAILABLE_FORMATS = ["mp4", "mkv", "webm", "avi", "3gp", "mov", "flv"]

# States
STATE_NONE         = 0
STATE_ASK_BATCH    = 1
STATE_WAIT_VIDEO   = 2
STATE_WAIT_FORMAT  = 3
STATE_DC_ASK_COUNT = 10   
STATE_DC_WAIT_URLS = 11   

# Callback prefixes
CB_VCODEC   = "vc:"
CB_RES      = "res:"
CB_FPS      = "fps:"
CB_ACODEC   = "ac:"
CB_CONFIRM  = "cnf:"
CB_FORMAT   = "fmt:"
CB_DC_VC    = "dcvc:"   
CB_DC_RES   = "dcres:"
CB_DC_FPS   = "dcfps:"
CB_DC_AC    = "dcac:"
CB_DC_CONF  = "dccnf:"  

USER_DATA = {}

def get_ud(uid):
    if uid not in USER_DATA:
        USER_DATA[uid] = {"state": STATE_NONE}
    return USER_DATA[uid]

# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _lookup(cat, key, val):
    return next((e for e in cat if e[key] == val), None)

def _build_kb(options, cb_prefix, cols=2):
    btns = [InlineKeyboardButton(o["label"], callback_data=f"{cb_prefix}{o['id']}") for o in options]
    return InlineKeyboardMarkup([btns[i:i + cols] for i in range(0, len(btns), cols)])

def _main_menu_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎬 ভিডিও কনভার্ট করুন")],
            [KeyboardButton("🔄 শুধু ফরম্যাট বদলান"), KeyboardButton("ℹ️ সাহায্য")],
            [KeyboardButton("🌐 Direct Convert")],
        ],
        resize_keyboard=True
    )

def _summary(ud):
    vc_l  = _lookup(VIDEO_CODECS, "id", ud.get("video_codec"))["label"]  if ud.get("video_codec")  else "—"
    res_l = _lookup(RESOLUTIONS,  "id", ud.get("resolution"))["label"]   if ud.get("resolution")   else "—"
    fps_l = _lookup(FPS_OPTIONS,  "id", ud.get("fps"))["label"]          if ud.get("fps")           else "—"
    ac_l  = _lookup(AUDIO_CODECS, "id", ud.get("audio_codec"))["label"]  if ud.get("audio_codec")  else "—"
    return f"📹 **Video:** {vc_l}\n🖥 **Resolution:** {res_l}\n🎞 **FPS:** {fps_l}\n🔊 **Audio:** {ac_l}"

async def safe_edit(msg, text, reply_markup=None):
    try:
        await msg.edit_text(text, reply_markup=reply_markup)
    except Exception:
        pass

def _cleanup(*paths):
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

def _build_cmd(inp, out, vc, res, fps, ac):
    cmd = [FFMPEG_BIN, "-y", "-i", inp]
    if vc["codec"] == "copy":
        cmd += ["-c:v", "copy"]
    else:
        cmd += ["-c:v", vc["codec"]] + vc["extra"]
    
    vf = []
    if res["scale"]:
        if res.get("aspect") == "keep":
            vf.append(f"scale={res['scale']}:flags=lanczos")
        else:
            vf.append(f"scale={res['scale']}:flags=lanczos:force_original_aspect_ratio=disable")
    
    if fps["fps"]:
        vf.append(f"fps={fps['fps']}")
    if vf and vc["codec"] != "copy":
        cmd += ["-vf", ",".join(vf)]
    if ac["codec"] == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += ["-c:a", ac["codec"]] + ac["extra"]
    cmd += ["-progress", "pipe:2", "-nostats", out]
    return cmd

def _probe_duration(inp):
    for cmd in [
        [FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", inp],
        [FFPROBE_BIN, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", inp],
    ]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.stdout.strip() and r.stdout.strip().lower() != "n/a":
                return float(r.stdout.strip())
        except Exception:
            pass
    return None

async def animate_progress(proc, smsg, dur, v_idx, v_total):
    pat = re.compile(r"out_time_ms=(\d+)")
    last_up = asyncio.get_event_loop().time()
    curr_pct, step = 0, 0
    spin = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]

    while True:
        try:
            line = await proc.stderr.readline()
            if not line:
                break
            m = pat.search(line.decode("utf-8", errors="ignore").strip())
            if m and dur:
                curr_pct = max(0, min(int((int(m.group(1)) / 1_000_000) / dur * 100), 99))

            now = asyncio.get_event_loop().time()
            if now - last_up >= 3.5:
                last_up = now
                step += 1
                s = spin[step % len(spin)]
                bar = "█" * (curr_pct // 10) + "░" * (10 - curr_pct // 10)
                txt = f"{s} **ভিডিও কনভার্ট হচ্ছে {v_idx}/{v_total}...**\n\n`[{bar}]` {curr_pct}%"
                asyncio.create_task(safe_edit(smsg, txt))
        except Exception:
            break

# ══════════════════════════════════════════════════════════════════════════
# YouTube Download Helper (yt-dlp)
# ══════════════════════════════════════════════════════════════════════════

YOUTUBE_RE = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|m\.youtube\.com/watch\?v=)[\w\-]+"
)

def is_valid_youtube_url(url: str) -> bool:
    return bool(YOUTUBE_RE.match(url.strip()))

async def ytdlp_download_video(url: str, quality_height: int, out_path: str) -> str:
    """yt-dlp দিয়ে YouTube ভিডিও ডাউনলোড করে। Python Warning ও Bot bypass arg ফিক্স করা হয়েছে।"""
    fmt = f"bestvideo[height<={quality_height}]+bestaudio/best[height<={quality_height}]/best"
    base_path = out_path.rsplit(".", 1)[0]
    
    cmd = [
        YT_DLP_BIN,
        "-f", fmt,
        "--merge-output-format", "mkv",
        "--no-warnings",
        "--no-playlist",
        "--no-progress",
        "--extractor-args", "youtube:player_client=tv,web_embedded;player_skip=webpage", # Ultimate Bot Bypass
        "--print", "after_move:filepath"
    ] + _cookies_args() + [
        "-o", f"{base_path}.%(ext)s",
        url,
    ]
    
    # Suppress Python 3.9 deprecation warnings generated by yt-dlp
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "ignore"
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    stdout, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_text = stderr.decode("utf-8", errors="ignore")
        if "Sign in to confirm you're not a bot" in err_text:
            raise RuntimeError("⚠️ YouTube Bot Protection Error!\nদয়া করে আপনার ব্রাউজার থেকে একদম ফ্রেশ একটি 'cookies.txt' এক্সপোর্ট করে বটের ডিরেক্টরিতে আপলোড/রিপ্লেস করুন।")
        raise RuntimeError(err_text[:300])
        
    output_text = stdout.decode("utf-8").strip()
    final_file = output_text.split("\n")[-1].strip()
    
    if final_file and Path(final_file).exists():
        return final_file
        
    for ext in ["mp4", "mkv", "webm", "avi"]:
        candidate = f"{base_path}.{ext}"
        if Path(candidate).exists():
            return candidate
            
    raise RuntimeError("yt-dlp আউটপুট ফাইল খুঁজে পাওয়া যায়নি।")

async def ytdlp_get_info(url: str) -> dict:
    """ভিডিওর তথ্য JSON হিসেবে নিয়ে আসে।"""
    cmd = [
        YT_DLP_BIN,
        "--dump-json",
        "--no-warnings",
        "--no-playlist",
        "--extractor-args", "youtube:player_client=tv,web_embedded;player_skip=webpage", # Ultimate Bot Bypass
    ] + _cookies_args() + [
        url,
    ]
    
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "ignore"
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_text = stderr.decode("utf-8", errors="ignore")
        if "Sign in to confirm you're not a bot" in err_text:
            raise RuntimeError("⚠️ YouTube Bot Protection Error!\nদয়া করে একটি ফ্রেশ 'cookies.txt' ফাইল ব্যবহার করুন।")
        raise RuntimeError(err_text[:300])
    import json
    return json.loads(stdout.decode("utf-8"))

# ══════════════════════════════════════════════════════════════════════════
# Pyrogram Message Handlers
# ══════════════════════════════════════════════════════════════════════════

@app.on_message(filters.private & filters.text)
async def handle_text(client, message):
    uid = message.from_user.id
    ud  = get_ud(uid)
    text = message.text.strip()

    if text in ["/start", "/cancel"]:
        USER_DATA.pop(uid, None)
        await message.reply(
            "👋 **ভিডিও কনভার্টার বটে স্বাগতম!**\n\n"
            "আপনি চাইলে একসাথে অনেকগুলো ভিডিও কনভার্ট করতে পারবেন। "
            "নিচের বাটনগুলো থেকে অপশন বেছে নিন:",
            reply_markup=_main_menu_kb()
        )
        return

    if text == "ℹ️ সাহায্য":
        cookies_status = "✅ cookies.txt পাওয়া গেছে" if COOKIES_FILE.exists() else "❌ cookies.txt নেই (age-restricted ভিডিও কাজ নাও করতে পারে)"
        await message.reply(
            "ℹ️ **নিয়মকানুন:**\n"
            "১. 'ভিডিও কনভার্ট করুন' — টেলিগ্রামে ভিডিও পাঠিয়ে কনভার্ট করুন।\n"
            "২. '🔄 শুধু ফরম্যাট বদলান' — ফরম্যাট পরিবর্তন করুন।\n"
            "৩. '🌐 Direct Convert' — YouTube লিংক থেকে সরাসরি ডাউনলোড + কনভার্ট করুন।\n\n"
            "**Direct Convert এর নিয়ম:**\n"
            "• কতটি লিংক দেবেন সেই সংখ্যা লিখুন\n"
            "• একে একে সেই কয়টি YouTube URL পাঠান\n"
            "• কনফিগারেশন সিলেক্ট করুন\n"
            "• বাকি কাজ আমি করব!\n\n"
            f"**Cookies Status:** {cookies_status}",
            reply_markup=_main_menu_kb()
        )
        return

    if text == "🎬 ভিডিও কনভার্ট করুন":
        ud["state"] = STATE_ASK_BATCH
        await message.reply("🎬 **কয়টি ভিডিও কনভার্ট করতে চান?**\n(১ থেকে ৫০ এর মধ্যে একটি সংখ্যা লিখুন):")
        return

    if text == "🔄 শুধু ফরম্যাট বদলান":
        ud["state"] = STATE_WAIT_FORMAT
        await message.reply("🔄 **ফরম্যাট পরিবর্তন**\n\nদয়া করে ভিডিও ফাইলটি পাঠান:")
        return

    if text == "🌐 Direct Convert":
        USER_DATA[uid] = {"state": STATE_DC_ASK_COUNT}
        await message.reply(
            "🌐 **Direct Convert**\n\n"
            "YouTube লিংক থেকে সরাসরি ডাউনলোড করে কনভার্ট করা হবে।\n\n"
            "কতটি YouTube লিংক দিতে চান? (১ থেকে ২০)"
        )
        return

    if ud["state"] == STATE_ASK_BATCH:
        try:
            c = int(text)
            if not (1 <= c <= 50):
                raise ValueError
            ud["batch_total"]    = c
            ud["batch_done"]     = 0
            ud["batch_messages"] = []
            ud["state"]          = STATE_WAIT_VIDEO
            await message.reply(f"✅ ঠিক আছে, আমি **{c}টি** ভিডিও নেব। এবার ১ নম্বর ভিডিওটি পাঠান:")
        except ValueError:
            await message.reply("⚠️ দয়া করে ১ থেকে ৫০ এর মধ্যে একটি সঠিক সংখ্যা দিন।")
        return

    if ud["state"] == STATE_DC_ASK_COUNT:
        try:
            c = int(text)
            if not (1 <= c <= 20):
                raise ValueError
            ud["dc_total"] = c
            ud["dc_urls"]  = []
            ud["state"]    = STATE_DC_WAIT_URLS
            await message.reply(
                f"✅ ঠিক আছে! এবার **{c}টি** YouTube লিংক পাঠান।\n\n"
                f"**১ নম্বর লিংক পাঠান:**"
            )
        except ValueError:
            await message.reply("⚠️ দয়া করে ১ থেকে ২০ এর মধ্যে একটি সঠিক সংখ্যা দিন।")
        return

    if ud["state"] == STATE_DC_WAIT_URLS:
        url = text.strip()
        if not is_valid_youtube_url(url):
            await message.reply(
                "❌ এটি সঠিক YouTube লিংক নয়।\n"
                "সঠিক লিংক উদাহরণ:\n"
                "`https://www.youtube.com/watch?v=...`\n"
                "`https://youtu.be/...`"
            )
            return

        ud["dc_urls"].append(url)
        done  = len(ud["dc_urls"])
        total = ud["dc_total"]

        if done < total:
            await message.reply(f"✅ লিংক {done}/{total} পেয়েছি।\n\n**{done + 1} নম্বর লিংক পাঠান:**")
        else:
            ud["state"] = STATE_NONE
            await message.reply(
                f"✅ সবগুলো ({total}টি) লিংক পেয়েছি!\n\n"
                "এবার কনভার্টের অপশন সিলেক্ট করুন:\n\n"
                "1️⃣ **ভিডিও কোডেক বেছে নিন:**",
                reply_markup=_build_kb(VIDEO_CODECS, CB_DC_VC, 1)
            )
        return

# ══════════════════════════════════════════════════════════════════════════
# Media Handler
# ══════════════════════════════════════════════════════════════════════════

@app.on_message(filters.private & (filters.video | filters.document))
async def handle_media(client, message):
    uid   = message.from_user.id
    ud    = get_ud(uid)
    state = ud.get("state", STATE_NONE)

    if state not in [STATE_WAIT_VIDEO, STATE_WAIT_FORMAT]:
        await message.reply("⚠️ দয়া করে আগে মেনু থেকে একটি অপশন সিলেক্ট করুন।")
        return

    f_obj = message.video or message.document
    if message.document and not (f_obj.mime_type and f_obj.mime_type.startswith("video/")):
        await message.reply("❌ এটি ভিডিও ফাইল নয়।")
        return

    size_mb = f_obj.file_size / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        await message.reply(f"❌ সাইজ অনেক বড় ({size_mb:.1f} MB)। সর্বোচ্চ সীমা 2GB।")
        return

    if state == STATE_WAIT_VIDEO:
        ud.setdefault("batch_messages", []).append(message)
        ud["batch_done"] += 1
        b_tot, b_done = ud["batch_total"], ud["batch_done"]

        if b_done < b_tot:
            await message.reply(f"✅ ভিডিও {b_done}/{b_tot} পেয়েছি। পরেরটি দিন:")
        else:
            ud["state"] = STATE_NONE
            await message.reply(
                f"✅ আপনার সবগুলো ({b_tot}টি) ভিডিও পেয়েছি!\n"
                "এবার কনভার্ট করার অপশনগুলো সিলেক্ট করুন:"
            )
            await message.reply("1️⃣ **ভিডিও কোডেক বেছে নিন:**", reply_markup=_build_kb(VIDEO_CODECS, CB_VCODEC, 1))

    elif state == STATE_WAIT_FORMAT:
        ud["format_message"] = message
        ext = (
            f_obj.file_name.rsplit(".", 1)[-1].lower()
            if f_obj.file_name and "." in f_obj.file_name
            else "mp4"
        )
        ud["current_ext"] = ext
        avail = [f for f in AVAILABLE_FORMATS if f != ext]
        btns  = [InlineKeyboardButton(f".{x.upper()}", callback_data=f"{CB_FORMAT}{x}") for x in avail]
        ud["state"] = STATE_NONE
        await message.reply(
            f"✅ **ফাইল পেয়েছি! বর্তমান ফরম্যাট:** `.{ext.upper()}`\n\nকোন ফরম্যাটে কনভার্ট করবেন?",
            reply_markup=InlineKeyboardMarkup([btns[i:i + 3] for i in range(0, len(btns), 3)])
        )

# ══════════════════════════════════════════════════════════════════════════
# Callback Queries
# ══════════════════════════════════════════════════════════════════════════

@app.on_callback_query()
async def handle_callback(client, query):
    d   = query.data
    uid = query.from_user.id
    ud  = get_ud(uid)

    if d.startswith(CB_VCODEC):
        ud["video_codec"] = d[len(CB_VCODEC):]
        await safe_edit(query.message, "✅ ভিডিও কোডেক সেভ।\n\n2️⃣ **রেজুলেশন সিলেক্ট করুন:**", _build_kb(RESOLUTIONS, CB_RES, 2))

    elif d.startswith(CB_RES):
        ud["resolution"] = d[len(CB_RES):]
        await safe_edit(query.message, "✅ রেজুলেশন সেভ।\n\n3️⃣ **FPS সিলেক্ট করুন:**", _build_kb(FPS_OPTIONS, CB_FPS, 2))

    elif d.startswith(CB_FPS):
        ud["fps"] = d[len(CB_FPS):]
        await safe_edit(query.message, "✅ FPS সেভ।\n\n4️⃣ **অডিও কোডেক সিলেক্ট করুন:**", _build_kb(AUDIO_CODECS, CB_ACODEC, 1))

    elif d.startswith(CB_ACODEC):
        ud["audio_codec"] = d[len(CB_ACODEC):]
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ শুরু করুন",   callback_data=f"{CB_CONFIRM}yes"),
            InlineKeyboardButton("❌ বাতিল করুন", callback_data=f"{CB_CONFIRM}no"),
        ]])
        await safe_edit(query.message, f"✅ সব সেটিংস সেভ!\n\n{_summary(ud)}\n\nকনভার্ট শুরু করবেন?", kb)

    elif d.startswith(CB_CONFIRM):
        if d.endswith("no"):
            await safe_edit(query.message, "❌ প্রক্রিয়াটি বাতিল করা হয়েছে।")
            USER_DATA.pop(uid, None)
            return
        await query.answer()
        await safe_edit(query.message, "🚀 কনভার্ট শুরু হচ্ছে...")
        await execute_batch(client, query.message, ud, uid)

    elif d.startswith(CB_FORMAT):
        await query.answer()
        await execute_format(client, query.message, ud, d[len(CB_FORMAT):], uid)

    elif d.startswith(CB_DC_VC):
        ud["dc_video_codec"] = d[len(CB_DC_VC):]
        await safe_edit(query.message, "✅ ভিডিও কোডেক সেভ।\n\n2️⃣ **রেজুলেশন সিলেক্ট করুন:**", _build_kb(RESOLUTIONS, CB_DC_RES, 2))

    elif d.startswith(CB_DC_RES):
        ud["dc_resolution"] = d[len(CB_DC_RES):]
        await safe_edit(query.message, "✅ রেজুলেশন সেভ।\n\n3️⃣ **FPS সিলেক্ট করুন:**", _build_kb(FPS_OPTIONS, CB_DC_FPS, 2))

    elif d.startswith(CB_DC_FPS):
        ud["dc_fps"] = d[len(CB_DC_FPS):]
        await safe_edit(query.message, "✅ FPS সেভ।\n\n4️⃣ **অডিও কোডেক সিলেক্ট করুন:**", _build_kb(AUDIO_CODECS, CB_DC_AC, 1))

    elif d.startswith(CB_DC_AC):
        ud["dc_audio_codec"] = d[len(CB_DC_AC):]
        vc_l  = _lookup(VIDEO_CODECS, "id", ud["dc_video_codec"])["label"]
        res_l = _lookup(RESOLUTIONS,  "id", ud["dc_resolution"])["label"]
        fps_l = _lookup(FPS_OPTIONS,  "id", ud["dc_fps"])["label"]
        ac_l  = _lookup(AUDIO_CODECS, "id", ud["dc_audio_codec"])["label"]
        summary = (
            f"📹 **Video:** {vc_l}\n"
            f"🖥 **Resolution:** {res_l}\n"
            f"🎞 **FPS:** {fps_l}\n"
            f"🔊 **Audio:** {ac_l}"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ শুরু করুন",   callback_data=f"{CB_DC_CONF}yes"),
            InlineKeyboardButton("❌ বাতিল করুন", callback_data=f"{CB_DC_CONF}no"),
        ]])
        await safe_edit(
            query.message,
            f"✅ সব সেটিংস সেভ!\n\n{summary}\n\n"
            f"**{len(ud.get('dc_urls', []))}টি** লিংক কনভার্ট হবে।\n\n"
            "শুরু করবেন?",
            kb
        )

    elif d.startswith(CB_DC_CONF):
        if d.endswith("no"):
            await safe_edit(query.message, "❌ প্রক্রিয়াটি বাতিল করা হয়েছে।")
            USER_DATA.pop(uid, None)
            return
        await query.answer()
        await safe_edit(query.message, "🚀 Direct Convert শুরু হচ্ছে...")
        await execute_direct_convert(client, query.message, ud, uid)

# ══════════════════════════════════════════════════════════════════════════
# Execute: Normal Batch Convert
# ══════════════════════════════════════════════════════════════════════════

async def execute_batch(client, message, ud, uid):
    msgs = ud.get("batch_messages", [])
    tot  = len(msgs)
    await message.reply(f"🚀 **একসাথে {tot}টি ভিডিওর ডাউনলোড ও কনভার্ট শুরু হচ্ছে...**")

    vc  = _lookup(VIDEO_CODECS, "id", ud["video_codec"])
    res = _lookup(RESOLUTIONS,  "id", ud["resolution"])
    fps = _lookup(FPS_OPTIONS,  "id", ud["fps"])
    ac  = _lookup(AUDIO_CODECS, "id", ud["audio_codec"])
    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def proc_single(idx, msg):
        await asyncio.sleep((idx - 1) * 1.5)
        async with sem:
            smsg = await message.reply(f"📥 **ভিডিও {idx}/{tot} ডাউনলোড শুরু হচ্ছে...**")
            last_up = [0]

            async def dl_prog(curr, t):
                now = time.time()
                if now - last_up[0] > 3:
                    last_up[0] = now
                    pct = int(curr * 100 / t) if t else 0
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    await safe_edit(smsg, f"📥 **ডাউনলোড হচ্ছে {idx}/{tot}...**\n\n`[{bar}]` {pct}%")

            try:
                inp = await client.download_media(msg, file_name=TEMP_DIR.as_posix() + "/", progress=dl_prog)
            except Exception as e:
                await safe_edit(smsg, f"❌ ভিডিও {idx} ডাউনলোড ব্যর্থ: {e}")
                return

            out = str(TEMP_DIR / f"out_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{idx}.{vc['ext']}")
            cmd = _build_cmd(inp, out, vc, res, fps, ac)

            p   = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            tsk = asyncio.create_task(animate_progress(p, smsg, _probe_duration(inp), idx, tot))
            await p.wait()
            tsk.cancel()

            if p.returncode != 0:
                await safe_edit(smsg, f"❌ **ভিডিও {idx}/{tot} কনভার্ট ব্যর্থ।**")
                _cleanup(inp, out)
                return

            await safe_edit(smsg, f"✅ **ভিডিও {idx}/{tot} কনভার্ট শেষ! আপলোড হচ্ছে…**")
            sz  = Path(out).stat().st_size / (1024 * 1024)
            cap = f"🎬 **Converted {idx}/{tot}**\n\n{_summary(ud)}\n\n📦 Size: {sz:.1f} MB"

            last_up[0] = 0

            async def up_prog(curr, t):
                now = time.time()
                if now - last_up[0] > 3:
                    last_up[0] = now
                    pct = int(curr * 100 / t) if t else 0
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    await safe_edit(smsg, f"📤 **আপলোড হচ্ছে {idx}/{tot}...**\n\n`[{bar}]` {pct}%")

            try:
                await client.send_document(msg.chat.id, out, caption=cap, progress=up_prog)
                await smsg.delete()
            except Exception as e:
                await message.reply(f"❌ ভিডিও {idx} আপলোড ব্যর্থ: {e}")
            finally:
                _cleanup(inp, out)

    await asyncio.gather(*[proc_single(i, m) for i, m in enumerate(msgs, 1)])
    USER_DATA.pop(uid, None)
    await message.reply("🎉 **আপনার সবগুলো ভিডিও সফলভাবে কনভার্ট সম্পন্ন হয়েছে!**", reply_markup=_main_menu_kb())

# ══════════════════════════════════════════════════════════════════════════
# Execute: Format Only
# ══════════════════════════════════════════════════════════════════════════

async def execute_format(client, message, ud, ext, uid):
    msg = ud.get("format_message")
    if not msg:
        return await safe_edit(message, "❌ ফাইলটি খুঁজে পাওয়া যায়নি।")

    smsg = await message.reply(f"🚀 **.{ext.upper()} তে কনভার্টের জন্য ডাউনলোড হচ্ছে...**")
    last_up = [0]

    async def dl_prog(curr, t):
        now = time.time()
        if now - last_up[0] > 3:
            last_up[0] = now
            pct = int(curr * 100 / t) if t else 0
            bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
            await safe_edit(smsg, f"📥 **ডাউনলোড হচ্ছে...**\n\n`[{bar}]` {pct}%")

    try:
        inp = await client.download_media(msg, file_name=TEMP_DIR.as_posix() + "/", progress=dl_prog)
    except Exception as e:
        return await safe_edit(smsg, f"❌ ডাউনলোড ব্যর্থ: {e}")

    out = str(TEMP_DIR / f"fmt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}")
    await safe_edit(smsg, f"🚀 **Converting to .{ext.upper()}...**")

    cmd = [FFMPEG_BIN, "-y", "-i", inp, "-preset", "fast", "-progress", "pipe:2", "-nostats", out]
    p   = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    tsk = asyncio.create_task(animate_progress(p, smsg, _probe_duration(inp), 1, 1))
    await p.wait()
    tsk.cancel()

    if p.returncode == 0:
        sz      = Path(out).stat().st_size / (1024 * 1024)
        last_up[0] = 0

        async def up_prog(curr, t):
            now = time.time()
            if now - last_up[0] > 3:
                last_up[0] = now
                pct = int(curr * 100 / t) if t else 0
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                await safe_edit(smsg, f"📤 **আপলোড হচ্ছে...**\n\n`[{bar}]` {pct}%")

        try:
            await client.send_document(
                msg.chat.id, out,
                caption=f"🔄 Format: `{ext.upper()}`\n📦 Size: {sz:.1f} MB",
                progress=up_prog
            )
            await safe_edit(smsg, "✅ **সফলভাবে সম্পন্ন হয়েছে!**")
        except Exception as e:
            await safe_edit(smsg, f"❌ Upload Error: {e}")
    else:
        await safe_edit(smsg, "❌ Conversion Error!")

    _cleanup(inp, out)
    USER_DATA.pop(uid, None)

# ══════════════════════════════════════════════════════════════════════════
# Execute: Direct Convert 
# ══════════════════════════════════════════════════════════════════════════

async def execute_direct_convert(client, message, ud, uid):
    urls  = ud.get("dc_urls", [])
    total = len(urls)

    vc  = _lookup(VIDEO_CODECS, "id", ud["dc_video_codec"])
    res = _lookup(RESOLUTIONS,  "id", ud["dc_resolution"])
    fps = _lookup(FPS_OPTIONS,  "id", ud["dc_fps"])
    ac  = _lookup(AUDIO_CODECS, "id", ud["dc_audio_codec"])

    # yt-dlp এর জন্য height নির্ধারণ 
    if res["scale"]:
        try:
            if "2160" in res["scale"]: dl_height = 2160
            elif "1080" in res["scale"]: dl_height = 1080
            elif "720" in res["scale"]: dl_height = 720
            elif "480" in res["scale"]: dl_height = 480
            elif "360" in res["scale"]: dl_height = 360
            elif "240" in res["scale"]: dl_height = 240
            elif "144" in res["scale"]: dl_height = 144
            else: dl_height = 1080
        except Exception:
            dl_height = 1080
    else:
        dl_height = 9999  # Source / best

    summary_text = (
        f"📹 **Video:** {vc['label']}\n"
        f"🖥 **Resolution:** {res['label']}\n"
        f"🎞 **FPS:** {fps['label']}\n"
        f"🔊 **Audio:** {ac['label']}"
    )

    await message.reply(f"🚀 **{total}টি YouTube ভিডিও Direct Convert শুরু হচ্ছে...**\n\n{summary_text}")

    sem = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    async def proc_url(idx, url):
        await asyncio.sleep((idx - 1) * 2.0)
        async with sem:
            smsg = await message.reply(f"🔍 **ভিডিও {idx}/{total}:** তথ্য নেওয়া হচ্ছে...")

            try:
                info = await ytdlp_get_info(url)
                title    = info.get("title", f"Video_{idx}")
                duration = info.get("duration", 0)
                mins, secs = divmod(int(duration), 60)
                await safe_edit(smsg,
                    f"📥 **ভিডিও {idx}/{total} ডাউনলোড হচ্ছে...**\n"
                    f"🎬 {title}\n⏱ {mins}:{secs:02d}"
                )
            except Exception as e:
                await safe_edit(smsg, f"❌ ভিডিও {idx} তথ্য পাওয়া যায়নি:\n`{str(e)[:200]}`")
                return

            ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_path = str(TEMP_DIR / f"dc_raw_{uid}_{idx}_{ts}.mp4")
            out_path = str(TEMP_DIR / f"dc_out_{uid}_{idx}_{ts}.{vc['ext']}")

            try:
                actual_raw = await ytdlp_download_video(url, dl_height, raw_path)
                await safe_edit(smsg,
                    f"⚙️ **ভিডিও {idx}/{total} কনভার্ট হচ্ছে...**\n"
                    f"🎬 {title}"
                )
            except Exception as e:
                await safe_edit(smsg, f"❌ ভিডিও {idx} ডাউনলোড ব্যর্থ:\n`{str(e)[:200]}`")
                return

            cmd = _build_cmd(actual_raw, out_path, vc, res, fps, ac)
            p   = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            dur = _probe_duration(actual_raw)
            tsk = asyncio.create_task(animate_progress(p, smsg, dur, idx, total))
            await p.wait()
            tsk.cancel()

            if p.returncode != 0:
                await safe_edit(smsg, f"❌ ভিডিও {idx}/{total} কনভার্ট ব্যর্থ।")
                _cleanup(actual_raw, out_path)
                return

            if not Path(out_path).exists():
                await safe_edit(smsg, f"❌ ভিডিও {idx}/{total} আউটপুট ফাইল পাওয়া যায়নি।")
                _cleanup(actual_raw)
                return

            sz  = Path(out_path).stat().st_size / (1024 * 1024)
            cap = (
                f"🌐 **Direct Convert {idx}/{total}**\n"
                f"🎬 {title}\n\n"
                f"{summary_text}\n\n"
                f"📦 Size: {sz:.1f} MB"
            )

            await safe_edit(smsg, f"📤 **ভিডিও {idx}/{total} আপলোড হচ্ছে...**\n🎬 {title}")

            last_up = [0]

            async def up_prog(curr, t):
                now = time.time()
                if now - last_up[0] > 3:
                    last_up[0] = now
                    pct = int(curr * 100 / t) if t else 0
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    await safe_edit(smsg, f"📤 **আপলোড হচ্ছে {idx}/{total}...**\n\n`[{bar}]` {pct}%")

            try:
                await client.send_document(
                    message.chat.id,
                    out_path,
                    caption=cap,
                    progress=up_prog
                )
                await smsg.delete()
            except Exception as e:
                await message.reply(f"❌ ভিডিও {idx} আপলোড ব্যর্থ: {e}")
            finally:
                _cleanup(actual_raw, out_path)

    await asyncio.gather(*[proc_url(i, u) for i, u in enumerate(urls, 1)])
    USER_DATA.pop(uid, None)
    await message.reply(
        "🎉 **সবগুলো Direct Convert সম্পন্ন হয়েছে!**",
        reply_markup=_main_menu_kb()
    )

# ══════════════════════════════════════════════════════════════════════════
# Run
# ══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("Bot is running. Press Ctrl+C to stop.")
    if COOKIES_FILE.exists():
        logger.info(f"✅ cookies.txt found at: {COOKIES_FILE}")
    else:
        logger.warning(f"⚠️ cookies.txt not found at: {COOKIES_FILE} (age-restricted videos may fail)")
    try:
        app.run()
    except Exception as e:
        logger.error(f"Bot crashed: {e}")