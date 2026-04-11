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
st.set_page_config(page_title="AI Shorts Generator", layout="wide")

# ----------------------
# UI STYLE
# ----------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background-color: #020617; color: white; }
.metric-card { background: rgba(255,255,255,0.06); padding: 15px; border-radius: 12px; text-align: center; border: 1px solid rgba(255,255,255,0.1); }
.stButton>button { background-color: #2563eb; color: white; width: 100%; border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# ----------------------
# OPTIMIZED MODEL LOADING
# ----------------------
@st.cache_resource
def load_whisper_model():
    return whisper.load_model("base")

# ----------------------
# FFMPEG DETECTION
# ----------------------
def find_ffmpeg():
    path = shutil.which("ffmpeg")
    return path if path else None

ffmpeg_bin = find_ffmpeg()

# ----------------------
# DOWNLOAD VIDEO (FIXED FOR 403 FORBIDDEN)
# ----------------------
def download_video(url, output="video.mp4"):
    if os.path.exists(output):
        try: os.remove(output)
        except: pass

    # Latest 2026 403 Bypass Arguments
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output,
        'quiet': True,
        'no_warnings': True,
        # Impersonate a standard browser client
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        },
        # Force specific clients that are less likely to trigger PO Token blocks
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls'] 
            }
        },
        'nocheckcertificate': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        return os.path.abspath(output), info.get("duration", 0), info.get("title", "")
    except Exception as e:
        # Fallback to 'best' combined format if separate streams are blocked
        st.info("🔄 Applying secondary bypass...")
        try:
            ydl_opts['format'] = 'best'
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
            return os.path.abspath(output), info.get("duration", 0), info.get("title", "")
        except Exception as fallback_e:
            st.error(f"❌ YouTube blocked the connection: {fallback_e}")
            return None, 0, ""

# ----------------------
# CORE LOGIC
# ----------------------
def extract_audio(video):
    audio = "audio.wav"
    if os.path.exists(audio): os.remove(audio)
    cmd = [ffmpeg_bin, "-y", "-i", video, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio]
    subprocess.run(cmd, capture_output=True)
    return audio

def transcribe_audio(audio):
    model = load_whisper_model()
    return model.transcribe(audio, fp16=False)["segments"]

def create_video_clips(video, segments, duration, clip_len):
    # Select top 3 interesting segments based on length
    sorted_segments = sorted(segments, key=lambda x: (x['end'] - x['start']), reverse=True)[:3]
    outputs = []
    
    for i, s in enumerate(sorted_segments):
        output = f"clip_{i}.mp4"
        start = max(0, s['start'])
        clean_text = s["text"].replace(":", "").replace("'", "")[:50]

        cmd = [
            ffmpeg_bin, "-y", "-ss", str(start), "-i", video, "-t", str(clip_len),
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,"
                   f"drawtext=text='{clean_text}':fontcolor=white:fontsize=40:x=(w-text_w)/2:y=h-200",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", output
        ]
        subprocess.run(cmd, capture_output=True)
        outputs.append(output)
    return outputs

# ----------------------
# MAIN UI
# ----------------------
st.title("🎬 AI Shorts Generator")
url = st.text_input("YouTube URL")
clip_len = st.sidebar.slider("Clip Length (sec)", 15, 60, 30)

if st.button("Generate"):
    if not url:
        st.warning("Please enter a URL")
    elif not ffmpeg_bin:
        st.error("FFmpeg missing! Add 'ffmpeg' to packages.txt")
    else:
        with st.spinner("Processing..."):
            video_path, duration, title = download_video(url)
            if video_path:
                audio_path = extract_audio(video_path)
                segments = transcribe_audio(audio_path)
                video_files = create_video_clips(video_path, segments, duration, clip_len)

                st.success(f"Generated {len(video_files)} clips for: {title}")
                cols = st.columns(len(video_files))
                for idx, clip in enumerate(video_files):
                    with cols[idx]:
                        st.video(clip)
                        with open(clip, "rb") as f:
                            st.download_button(f"Download #{idx+1}", f, file_name=clip)
