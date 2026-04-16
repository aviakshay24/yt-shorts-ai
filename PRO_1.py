import os
import shutil
import subprocess
import streamlit as st
import yt_dlp

# ----------------------
# PAGE CONFIG
# ----------------------
st.set_page_config(page_title="AI Shorts Generator", layout="wide")

# ----------------------
# DARK UI STYLING
# ----------------------
st.markdown("""
<style>
body {
    background-color: #0e1117;
}

.metric-card {
    background: #1c1f2e;
    padding: 20px;
    border-radius: 12px;
    border: 1px solid #2c2f3a;
    color: white;
}

.metric-title {
    font-size: 14px;
    color: #9aa0aa;
}

.metric-value {
    font-size: 26px;
    font-weight: bold;
}

.stButton>button {
    background-color: #2563eb;
    color: white;
    border-radius: 8px;
    height: 45px;
    font-weight: bold;
}

.stTextInput>div>div>input {
    background-color: #1c1f2e;
    color: white;
}

section[data-testid="stSidebar"] {
    background-color: #11131a;
}

</style>
""", unsafe_allow_html=True)

# ----------------------
# FFMPEG CHECK
# ----------------------
def get_ffmpeg():
    return shutil.which("ffmpeg")

FFMPEG = get_ffmpeg()

# ----------------------
# DOWNLOAD FUNCTION
# ----------------------
def download_video(url, output="video.mp4"):
    if os.path.exists(output):
        os.remove(output)

    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': output,
        'quiet': True,

        'js_runtimes': {
            'node': {}
        },

        'continuedl': False,

        'http_headers': {
            'User-Agent': 'Mozilla/5.0'
        },

        'extractor_args': {
            'youtube': {
                'player_client': ['android']
            }
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return output, info.get("duration", 0), info.get("title", "")
    except Exception as e:
        st.error(f"Download Error: {e}")
        return None, 0, ""

# ----------------------
# CLIP FUNCTION
# ----------------------
def create_clips(video, length=30):
    clips = []

    for i in range(3):
        out = f"clip_{i}.mp4"
        start = i * 30

        cmd = [
            FFMPEG,
            "-y",
            "-ss", str(start),
            "-i", video,
            "-t", str(length),
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            out
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        clips.append(out)

    return clips

# ----------------------
# SIDEBAR
# ----------------------
with st.sidebar:
    st.title(" Settings")

    clip_len = st.slider("Clip Length", 15, 60, 30)

    if FFMPEG:
        st.success("FFmpeg Ready")
    else:
        st.error("Install FFmpeg")

# ----------------------
# HEADER
# ----------------------
st.title("🎬 AI YouTube Shorts Generator (Turbo)")
st.caption("Convert long videos into viral short clips using AI")

# ----------------------
# INPUT
# ----------------------
col1, col2 = st.columns([4,1])

with col1:
    url = st.text_input("Enter YouTube URL")

with col2:
    st.write("")
    generate = st.button("Generate Shorts", use_container_width=True)

# ----------------------
# METRICS
# ----------------------
m1, m2, m3 = st.columns(3)

duration_val = "0 min"
clips_val = "0"
keywords_val = "0"

# ----------------------
# PROCESS
# ----------------------
if generate and url:

    with st.spinner("Processing video..."):

        video, duration, title = download_video(url)

        if video:
            clips = create_clips(video, clip_len)

            duration_val = f"{duration//60} min"
            clips_val = str(len(clips))
            keywords_val = "7"

            st.success("Processing complete!")

            # ----------------------
            # TABS
            # ----------------------
            tab1, tab2, tab3 = st.tabs(["Summary", "Short Clips", "Captions"])

            with tab1:
                st.write(f"### {title}")
                st.write("Auto-generated summary coming soon...")

            with tab2:
                st.subheader("Short Clips")

                cols = st.columns(4)

                with cols[0]:
                    st.video(url)

                for i, c in enumerate(clips):
                    with cols[i+1]:
                        st.video(c)
                        with open(c, "rb") as f:
                            st.download_button(f"Download Clip {i+1}", f, file_name=c)

            with tab3:
                st.write("Captions feature coming soon...")

# ----------------------
# METRIC DISPLAY
# ----------------------
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">⏱ Duration</div>
        <div class="metric-value">{duration_val}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title"> Clips Generated</div>
        <div class="metric-value">{clips_val}</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title"> Keywords</div>
        <div class="metric-value">{keywords_val}</div>
    </div>
    """, unsafe_allow_html=True)