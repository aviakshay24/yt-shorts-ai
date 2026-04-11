import os
import shutil
import subprocess
import streamlit as st
import yt_dlp
import whisper
from collections import Counter

# ----------------------
# PAGE CONFIG
# ----------------------
st.set_page_config(layout="wide")

# ----------------------
# UI STYLE
# ----------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #020617;
    color: white;
}

.block-container {
    padding-top: 2rem;
}

.card {
    background: rgba(255,255,255,0.05);
    padding: 15px;
    border-radius: 15px;
    backdrop-filter: blur(10px);
    box-shadow: 0 0 20px rgba(0,0,0,0.3);
    margin-bottom: 15px;
}

.metric-card {
    background: rgba(255,255,255,0.06);
    padding: 15px;
    border-radius: 12px;
    text-align: center;
}

.stButton>button {
    background-color: #2563eb;
    color: white;
    border-radius: 10px;
    padding: 10px 20px;
    border: none;
}

.stDownloadButton>button {
    background-color: #16a34a;
    color: white;
    border-radius: 10px;
}

section[data-testid="stSidebar"] {
    background-color: #020617;
}
</style>
""", unsafe_allow_html=True)

# ----------------------
# FFMPEG DETECTION
# ----------------------
def find_ffmpeg():
    path = shutil.which("ffmpeg")
    if path:
        os.environ["IMAGEIO_FFMPEG_EXE"] = path
        return path
    return None

ffmpeg_bin = find_ffmpeg()

# ----------------------
# DOWNLOAD VIDEO (FIXED)
# ----------------------
def download_video(url, output="video.mp4"):
    if os.path.exists(output):
        try:
            os.remove(output)
        except:
            pass

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output,
        'quiet': True,

        # 🔥 FIXES
        'retries': 15,
        'fragment_retries': 15,
        'socket_timeout': 120,
        'source_address': '0.0.0.0',

        'http_headers': {
            'User-Agent': 'Mozilla/5.0'
        },

        'concurrent_fragment_downloads': 1
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        return os.path.abspath(output), info.get("duration", 0), info.get("title", "")

    except Exception as e:
        st.warning("⚠️ Primary download failed, trying fallback...")

        try:
            ydl_opts['format'] = 'worst'

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            return os.path.abspath(output), info.get("duration", 0), info.get("title", "")

        except Exception as e:
            st.error(f"❌ Download failed: {e}")
            return None, 0, ""

# ----------------------
# AUDIO EXTRACTION
# ----------------------
def extract_audio(video):
    audio = "audio.wav"

    cmd = [
        ffmpeg_bin, "-y", "-i", video,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1", audio
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return audio

# ----------------------
# TRANSCRIBE
# ----------------------
def transcribe(audio):
    model = whisper.load_model("base")
    result = model.transcribe(audio, fp16=False)
    return result["segments"]

# ----------------------
# KEYWORDS
# ----------------------
def extract_keywords(segments):
    words = []
    for s in segments:
        words.extend(s["text"].lower().split())

    return [w for w, _ in Counter(words).most_common(10)]

# ----------------------
# CLIP SELECTION
# ----------------------
def get_clips(segments, duration, clip_len):
    sorted_segments = sorted(
        segments,
        key=lambda x: (x['end'] - x['start']),
        reverse=True
    )

    clips = []
    used = []

    for s in sorted_segments:
        start = max(0, s['start'])
        end = min(start + clip_len, duration)

        if not any(abs(start - u) < clip_len for u in used):
            clips.append((start, end))
            used.append(start)

        if len(clips) >= 3:
            break

    return clips

# ----------------------
# CREATE CLIPS
# ----------------------
def create_clips(video, clips, segments):
    outputs = []

    for i, (start, end) in enumerate(clips):
        output = f"clip_{i}.mp4"

        text = segments[i]["text"].replace(":", "").replace("'", "")[:60]

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss", str(start),
            "-i", video,
            "-t", str(end - start),
            "-vf",
            f"scale=720:1280:force_original_aspect_ratio=increase,"
            f"crop=720:1280,"
            f"drawtext=text='{text}':fontcolor=white:fontsize=40:x=(w-text_w)/2:y=h-200",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            output
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        outputs.append(output)

    return outputs

# ----------------------
# SIDEBAR
# ----------------------
st.sidebar.markdown("## ⚙️ Settings")
clip_len = st.sidebar.slider("Clip Length", 15, 60, 30)
summary_type = st.sidebar.selectbox("Summary Type", ["Short", "Detailed"])

# ----------------------
# HEADER
# ----------------------
st.markdown("## 🎬 AI YouTube Shorts Generator (Turbo)")
st.caption("Convert long videos into viral short clips using AI")

col1, col2 = st.columns([4,1])

with col1:
    url = st.text_input("Enter YouTube Video URL")

with col2:
    generate = st.button("Generate Shorts")

# ----------------------
# MAIN LOGIC
# ----------------------
if generate:

    if not ffmpeg_bin:
        st.error("❌ FFmpeg not installed!")
    elif not url:
        st.warning("Enter a valid URL")
    else:
        with st.spinner("Processing..."):
            video, duration, title = download_video(url)

            if not video:
                st.stop()

            audio = extract_audio(video)
            segments = transcribe(audio)

            keywords = extract_keywords(segments)
            clips = get_clips(segments, duration, clip_len)
            outputs = create_clips(video, clips, segments)

        # METRICS
        c1, c2, c3 = st.columns(3)

        with c1:
            st.markdown(f'<div class="metric-card">⏱ Duration<br><b>{int(duration/60)} min</b></div>', unsafe_allow_html=True)

        with c2:
            st.markdown(f'<div class="metric-card">🎬 Clips<br><b>{len(outputs)}</b></div>', unsafe_allow_html=True)

        with c3:
            st.markdown(f'<div class="metric-card">🔑 Keywords<br><b>{len(keywords)}</b></div>', unsafe_allow_html=True)

        # TABS
        tab1, tab2, tab3 = st.tabs(["📄 Summary", "🎞 Short Clips", "💬 Captions"])

        with tab1:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            full_text = " ".join([s["text"] for s in segments])
            st.write(full_text[:500] + "...")
            st.markdown('</div>', unsafe_allow_html=True)

        with tab2:
            cols = st.columns(3)

            for i, clip in enumerate(outputs):
                with cols[i % 3]:
                    st.markdown('<div class="card">', unsafe_allow_html=True)
                    st.video(clip)

                    with open(clip, "rb") as f:
                        st.download_button(f"Download Clip {i+1}", f, file_name=clip)

                    st.markdown('</div>', unsafe_allow_html=True)

        with tab3:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            for s in segments[:15]:
                st.write(s["text"])
            st.markdown('</div>', unsafe_allow_html=True)