"""
Chat + TTS: likho → friendly jawab + awaaz (Edge ya local XTTS clone).
Clone: pip install -r requirements-voice-clone.txt (+ ffmpeg). Run: streamlit run streamlit_app.py
"""
from __future__ import annotations

import importlib.util
import shutil

import streamlit as st

from friendly_voice import (
    friendly_reply,
    nana_clone_reference_path,
    reference_voice_path,
    save_uploaded_reference,
    speak_reply_bytes,
)


def _detect_lang_pref(user_text: str) -> str | None:
    low = user_text.lower()
    if "english" in low:
        return "en"
    if "hindi" in low or "हिंदी" in user_text:
        return "hi"
    return None


def _detect_lang_auto(text: str) -> str:
    return "hi" if any("\u0900" <= c <= "\u097f" for c in text) else "en"


def _edge_voice_id(lang: str) -> str:
    # Simple default voices (no UI)
    return "hi-IN-MadhurNeural" if lang == "hi" else "en-IN-PrabhatNeural"


def _tts_and_torch_installed() -> bool:
    return importlib.util.find_spec("TTS") is not None and importlib.util.find_spec("torch") is not None


def _ffmpeg_on_path() -> bool:
    return shutil.which("ffmpeg") is not None


def _clone_can_run(ref) -> bool:
    if not _tts_and_torch_installed() or ref is None or not ref.is_file():
        return False
    if ref.suffix.lower() in (".mp3", ".m4a", ".aac", ".ogg", ".flac") and not _ffmpeg_on_path():
        return False
    return True


def _inject_mobile_ui_css() -> None:
    st.markdown(
        """
<style>
  [data-testid="stSidebar"],
  [data-testid="stSidebarNavLink"],
  div[data-testid="collapsedControl"] {
    display: none !important;
  }
  .stApp {
    background: linear-gradient(180deg, #dbeafe 0%, #f1f5f9 50%, #e2e8f0 100%);
    color: #0f172a;
  }
  [data-testid="stAppViewContainer"] > .main {
    background: transparent;
  }
  .main .block-container {
    max-width: 760px !important;
    margin: 0 auto !important;
    padding: 0.75rem 0.75rem 1.25rem !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
  }
  .va-notch {
    text-align: center;
    font-size: 0.7rem;
    letter-spacing: 0.12em;
    color: #64748b;
    margin-bottom: 0.35rem;
  }
  .va-title {
    text-align: center;
    color: #0f172a;
    font-size: 1.35rem;
    font-weight: 700;
    margin: 0 0 0.15rem 0;
    letter-spacing: -0.02em;
  }
  .va-sub {
    text-align: center;
    color: #334155;
    font-size: 0.85rem;
    margin: 0 0 0.75rem 0;
  }
  .va-chat {
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid #cbd5e1;
    border-radius: 18px;
    box-shadow: 0 10px 40px rgba(15, 23, 42, 0.08);
    padding: 0.65rem 0.65rem 0.35rem;
  }
  .va-chat [data-testid="stChatMessage"] {
    padding-top: 0.25rem;
    padding-bottom: 0.25rem;
  }
  [data-testid="stChatMessage"] {
    border-radius: 16px;
    color: #0f172a !important;
  }
  [data-testid="stChatMessage"] p,
  [data-testid="stChatMessage"] li,
  [data-testid="stChatMessage"] span {
    color: #1e293b !important;
  }
  [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] {
    color: #1e293b !important;
  }
  /* Autoplay ke liye st.audio DOM mein chahiye; UI se player chhupa do */
  [data-testid="stAudio"],
  [data-testid="stAudio"] > div {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: hidden !important;
    clip: rect(0, 0, 0, 0) !important;
    clip-path: inset(50%) !important;
    opacity: 0 !important;
    pointer-events: none !important;
  }
  .main audio {
    position: fixed !important;
    left: -9999px !important;
    width: 2px !important;
    height: 2px !important;
    opacity: 0 !important;
  }
</style>
        """,
        unsafe_allow_html=True,
    )

def _append_assistant(text: str, with_voice: bool) -> None:
    ref_path = reference_voice_path()
    mode = "clone" if st.session_state.get("voice_mode") == "clone" else "edge"
    lang = st.session_state.get("chat_lang", "auto")
    lang_eff = _detect_lang_auto(text) if lang == "auto" else lang
    ev = _edge_voice_id(lang_eff)
    msg: dict = {"role": "assistant", "text": text}
    if not with_voice:
        st.session_state.messages.append(msg)
        return

    audio: bytes | None = None
    mime = ""

    if mode == "clone" and (not ref_path or not ref_path.is_file()):
        audio, mime, _ = speak_reply_bytes(text, "edge", ref_path, edge_voice=ev)
    elif mode == "clone":
        with st.spinner("Tumhari reference se awaaz clone ho rahi hai (pehli baar model bhi download ho sakta hai)…"):
            audio, mime, _ = speak_reply_bytes(text, "clone", ref_path)
        if audio is None:
            audio, mime, _ = speak_reply_bytes(text, "edge", ref_path, edge_voice=ev)
    else:
        audio, mime, _ = speak_reply_bytes(text, "edge", ref_path, edge_voice=ev)

    if audio:
        msg["audio"] = audio
        msg["audio_mime"] = mime or "audio/mpeg"
    # Fallback par bhi seedha jawab dikhao — clone/ffmpeg errors chat mein nahi

    st.session_state.messages.append(msg)
    if msg.get("audio"):
        st.session_state._voice_autoplay_idx = len(st.session_state.messages) - 1
        st.session_state._last_audio = msg["audio"]
        st.session_state._last_audio_mime = msg.get("audio_mime", "audio/mpeg")


def main() -> None:
    st.set_page_config(
        page_title="Talk to Talk",
        layout="centered",
        initial_sidebar_state="collapsed",
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "voice_mode" not in st.session_state:
        # Pehli baar: clone tabhi default jab nana .wav/.mp3 + XTTS (+ mp3 ke liye ffmpeg) theek ho
        _n0 = nana_clone_reference_path()
        st.session_state.voice_mode = "clone" if _clone_can_run(_n0) else "edge"
    if "chat_lang" not in st.session_state:
        st.session_state.chat_lang = "auto"
    _inject_mobile_ui_css()

    st.markdown('<p class="va-notch">TALK · TO · TALK</p>', unsafe_allow_html=True)
    st.markdown('<p class="va-title">Baat se baat</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="va-sub">Neeche likho — assistant usi language mein reply karega. '
        'Agar tum likho: <strong>"English mein baat karo"</strong> ya <strong>"Hindi mein baat karo"</strong>, '
        "to woh preference set ho जाएगी.</p>",
        unsafe_allow_html=True,
    )

    nana_ref = nana_clone_reference_path()
    if not nana_ref:
        st.warning(
            "Voice clone **`nana_patekar.wav`** (behtar, ffmpeg kam zaroori) ya **`nana_patekar.mp3`** se — "
            "**project folder** mein rakho. Upload se bhi save kar sakte ho."
        )
        up = st.file_uploader("Upload (mp3 / wav / m4a)", type=["mp3", "wav", "m4a"], key="ref_up")
        if up is not None and st.button("Project mein save karo", type="primary"):
            save_uploaded_reference(up.getvalue(), up.name)
            st.rerun()

    # Engine UI hata diya. Defaults:
    # - voice_mode: clone if possible else edge
    # - chat_lang: auto, user message se detect
    ref = reference_voice_path()

    st.markdown('<div class="va-chat">', unsafe_allow_html=True)

    if not st.session_state.messages:
        st.session_state.messages = [
            {
                "role": "assistant",
                "text": "Namaste! Neeche likho — jawab ki awaaz **khud chalne** ki koshish hogi (player UI band hai).",
            }
        ]

    # Fallback: autoplay block ho to user click se play (player UI nahi)
    if st.session_state.get("_last_audio"):
        c1, c2 = st.columns([1, 2], vertical_alignment="center")
        with c1:
            if st.button("Play last reply", type="primary", use_container_width=True):
                st.session_state._force_play_last = True
        with c2:
            st.caption("Agar browser autoplay block kare to yahan se awaaz chala lo.")

    autoplay_i = st.session_state.pop("_voice_autoplay_idx", None)

    chat_box = st.container(height=520, border=False)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                if msg.get("text"):
                    st.markdown(msg["text"])

    # Sirf naye jawab ke liye ek chhupa hua audio (chat bubble mein player nahi)
    if (
        autoplay_i is not None
        and 0 <= autoplay_i < len(st.session_state.messages)
        and st.session_state.messages[autoplay_i].get("audio")
    ):
        m = st.session_state.messages[autoplay_i]
        fmt = m.get("audio_mime", "audio/mpeg")
        try:
            st.audio(m["audio"], format=fmt, autoplay=True)
        except TypeError:
            st.audio(m["audio"], format=fmt)
    elif st.session_state.pop("_force_play_last", False):
        # Button click counts as a user gesture; render a hidden st.audio with autoplay.
        la = st.session_state.get("_last_audio")
        if la:
            fmt = st.session_state.get("_last_audio_mime", "audio/mpeg")
            try:
                st.audio(la, format=fmt, autoplay=True)
            except TypeError:
                st.audio(la, format=fmt)

    st.markdown("</div>", unsafe_allow_html=True)

    prompt = st.chat_input("Ya yahan type karke bhejo…")
    if prompt:
        pref = _detect_lang_pref(prompt)
        if pref:
            st.session_state.chat_lang = pref
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "text": ("ठीक है — अब से हिंदी में।" if pref == "hi" else "Okay — English from now on."),
                }
            )
            st.rerun()
        # Auto switch language per message if user hasn't locked preference
        if st.session_state.get("chat_lang") == "auto":
            st.session_state.chat_lang = _detect_lang_auto(prompt)
        st.session_state.messages.append({"role": "user", "text": prompt})
        reply = friendly_reply(prompt, lang=st.session_state.get("chat_lang", "auto"))
        _append_assistant(reply, True)
        st.rerun()


if __name__ == "__main__":
    main()
