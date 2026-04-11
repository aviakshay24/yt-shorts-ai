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

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #020617;
    color: white;
}

.metric-card {
    background: rgba(255,255,255,0.06);
    padding: 15px;
    border-radius: 12px;
    text-align: center;
    border: 1px solid rgba(255,255,255,0.1);
}

.stButton>button {
    background-color: #2563eb;
    color: white;
    width: 100%;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)

# ----------------------
# OPTIMIZED MODEL LOADING
# ----------------------
@st.cache_resource
def load_whisper_model():
    """Caches the model in memory to prevent crashes on cloud servers."""
    return whisper.load_model("base")

# ----------------------
# FFMPEG DETECTION
# ----------------------
def find_ffmpeg():
    # On Streamlit Cloud, ffmpeg is usually in the PATH after adding to packages.txt
    path = shutil.which("ffmpeg")
    if path:
        return path
    return None

ffmpeg_bin = find_ffmpeg()

# ----------------------
# VIDEO PROCESSING FUNCTIONS
# ----------------------
def download_video(url, output="video.mp4"):
    if os.path.exists(output):
        try: os.remove(output)
        except: pass

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {'User-Agent': 'Mozilla/5.0'}
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        return os.path.abspath(output), info.get("duration", 0), info.get("title", "")
    except Exception as e:
        st.error(f"Download Error: {e}")
        return None, 0, ""

def extract_audio(video):
    audio = "audio.wav"
    if os.path.exists(audio): os.remove(audio)
    
    cmd = [
        ffmpeg_bin, "-y", "-i", video,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1", audio
    ]
    subprocess.run(cmd, capture_output=True)
    return audio

def transcribe_audio(audio):
    model = load_whisper_model()
    result = model.transcribe(audio, fp16=False)
    return result["segments"]

def get_clips_metadata(segments, duration, clip_len):
    # Sort by longest segments to find interesting parts
    sorted_segments = sorted(segments, key=lambda x: (x['end'] - x['start']), reverse=True)
    clips = []
    used_starts = []

    for s in sorted_segments:
        start = max(0, s['start'])
        if not any(abs(start - u) < clip_len for u in used_starts):
            end = min(start + clip_len, duration)
            clips.append((start, end))
            used_starts.append(start)
        if len(clips) >= 3: break
    return clips

def create_video_clips(video, clips, segments):
    outputs = []
    for i, (start, end) in enumerate(clips):
        output = f"clip_{i}.mp4"
        # Clean text for FFmpeg drawtext filter
        raw_text = segments[i]["text"] if i < len(segments) else "Viral Clip"
        clean_text = raw_text.replace(":", "").replace("'", "").replace('"', "")[:50]

        cmd = [
            ffmpeg_bin, "-y", "-ss", str(start), "-i", video, "-t", str(end - start),
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,"
                   f"drawtext=text='{clean_text}':fontcolor=white:fontsize=40:x=(w-text_w)/2:y=h-200",
            "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", output
        ]
        subprocess.run(cmd, capture_output=True)
        outputs.append(output)
    return outputs

# ----------------------
# MAIN INTERFACE
# ----------------------
st.sidebar.title("⚙️ Configuration")
clip_len = st.sidebar.slider("Clip Duration (sec)", 15, 60, 30)

st.title("🎬 AI YouTube Shorts Generator")
st.markdown("Transform long-form content into vertical shorts using AI transcription and smart cropping.")

url = st.text_input("Paste YouTube URL here:", placeholder="https://www.youtube.com/watch?v=...")
generate_btn = st.button("🚀 Generate Viral Clips")

if generate_btn:
    if not url:
        st.warning("Please provide a URL.")
    elif not ffmpeg_bin:
        st.error("FFmpeg not found. Ensure 'ffmpeg' is in your packages.txt.")
    else:
        with st.spinner("1/4: Downloading video..."):
            video_path, duration, title = download_video(url)
        
        if video_path:
            with st.spinner("2/4: Transcribing audio (this takes a minute)..."):
                audio_path = extract_audio(video_path)
                segments = transcribe_audio(audio_path)
            
            with st.spinner("3/4: Identifying best moments..."):
                clip_ranges = get_clips_metadata(segments, duration, clip_len)
            
            with st.spinner("4/4: Rendering vertical clips..."):
                video_files = create_video_clips(video_path, clip_ranges, segments)

            # Display Results
            st.success(f"Successfully processed: {title}")
            
            m1, m2, m3 = st.columns(3)
            m1.markdown(f'<div class="metric-card">⏱ Length<br><b>{int(duration/60)} min</b></div>', unsafe_allow_html=True)
            m2.markdown(f'<div class="metric-card">🎞 Generated<br><b>{len(video_files)} Clips</b></div>', unsafe_allow_html=True)
            m3.markdown(f'<div class="metric-card">🧠 AI Model<br><b>Whisper Base</b></div>', unsafe_allow_html=True)

            st.divider()
            
            cols = st.columns(len(video_files))
            for idx, clip in enumerate(video_files):
                with cols[idx]:
                    st.video(clip)
                    with open(clip, "rb") as f:
                        st.download_button(f"Download #{idx+1}", f, file_name=f"short_{idx}.mp4")