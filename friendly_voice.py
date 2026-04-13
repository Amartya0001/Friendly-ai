"""Friendly text + optional TTS: tumhari reference file se XTTS clone (local)."""
from __future__ import annotations

import io
import os
import random
import re
import subprocess
import tempfile
import time
from pathlib import Path

import numpy as np

from voice_profile import PROJECT_ROOT, VoiceProfile, resolve_reference_audio_path

# Project root par default speaker files — pehle WAV (ffmpeg optional), phir MP3
NANA_REFERENCE_FILENAMES = ("nana_patekar.wav", "nana_patekar.mp3")

# Coqui XTTS — lazy load
_xtts_model = None


def default_nana_reference_path() -> Path | None:
    """`nana_patekar.wav` pehle (clone ke liye behtar, ffmpeg kam zaroori), phir `.mp3`."""
    for name in NANA_REFERENCE_FILENAMES:
        p = (PROJECT_ROOT / name).resolve()
        if p.is_file():
            return p
    return None


def nana_clone_reference_path() -> Path | None:
    """XTTS clone: project root par nana WAV ya MP3 — WAV ko priority."""
    return default_nana_reference_path()


def reference_voice_path() -> Path | None:
    """Pehle profile path agar file maujood; warna project root par nana `.wav` / `.mp3`."""
    p = VoiceProfile.load()
    resolved = resolve_reference_audio_path(p.reference_audio_path)
    if resolved is not None and resolved.is_file():
        return resolved
    fb = default_nana_reference_path()
    if fb is not None:
        return fb
    if resolved is not None:
        return resolved
    return None


def save_uploaded_reference(data: bytes, filename: str = "nana_patekar.mp3") -> Path:
    name = Path(filename).name
    if not name.lower().endswith((".mp3", ".wav", ".m4a")):
        name = "nana_patekar.wav"
    dest = (PROJECT_ROOT / name).resolve()
    dest.write_bytes(data)
    prof = VoiceProfile.load()
    prof.reference_audio_path = name
    prof.startup_voice_path = prof.startup_voice_path or name
    prof.save()
    return dest


def friendly_reply(user_text: str, *, lang: str = "auto") -> str:
    """Dosti wala tone. `lang`: auto|hi|en (user ke hisaab se)."""
    t = user_text.strip()
    if not t:
        return "मैं सुन रहा हूँ… कुछ लिखो, दिल से।" if lang == "hi" else "I’m listening… say something."

    low = t.lower()
    if lang == "auto":
        # Devanagari => Hindi; otherwise English-ish (includes Hinglish)
        lang = "hi" if any("\u0900" <= c <= "\u097f" for c in t) else "en"

    if re.search(r"\b(hi|hello|hey|namaste|namaskar)\b", low):
        if lang == "hi":
            return random.choice(
                [
                    "नमस्ते! आज मूड कैसा है? आराम से बात करते हैं।",
                    "हैलो! बताओ क्या चल रहा है?",
                ]
            )
        return random.choice(
            [
                "Hello! How’s your mood today?",
                "Hey! Tell me what’s going on.",
            ]
        )
    if "kaise" in low or "kaisa" in low or "how are you" in low:
        return "मैं बढ़िया हूँ! तुम बताओ—तुम्हारी तरफ सब ठीक?" if lang == "hi" else "I’m good! How are you?"
    if any(x in low for x in ("khush", "happy", "accha", "acha", "good")):
        return "वाह! सुनकर अच्छा लगा। ऐसे ही मुस्कुराते रहो।" if lang == "hi" else "Nice! Glad to hear that."
    if any(x in low for x in ("dukhi", "sad", "tension", "stress", "pareshan")):
        return (
            "ऐसा हो जाता है। एक बार सांस लो—मैं सुन रहा हूँ। चाहो तो थोड़ा और बताओ।"
            if lang == "hi"
            else "That happens. Take a breath—I’m here to listen. Tell me more if you want."
        )
    if any(x in low for x in ("thank", "dhanyavad", "shukriya")):
        return "कोई बात नहीं! 😊" if lang == "hi" else "No worries!"
    if any(x in low for x in ("bye", "alvida", "good night", "goodnight")):
        return "ठीक है, फिर मिलते हैं। अपना ध्यान रखना।" if lang == "hi" else "Alright, talk later. Take care!"

    return random.choice(
        [
            "समझ गया। थोड़ा और detail में बताओ।" if lang == "hi" else "Got it. Tell me a bit more.",
            "ठीक है—आगे बोलो।" if lang == "hi" else "Okay—go on.",
            "दिल की बात करो, समय है।" if lang == "hi" else "Speak your mind—I’m here.",
        ]
    )


def _xtts_language(text: str) -> str:
    """XTTS text language — galat language = weak clone."""
    if any("\u0900" <= c <= "\u097f" for c in text):
        return "hi"
    return "en"


def reference_to_wav_mono(ref: Path, max_seconds: float = 25.0) -> Path | None:
    """
    XTTS ke liye stable reference: mono 24kHz s16 WAV, pehle ~25s tak.
    Lamba / noisy reference clone bigaad sakta hai; stereo 48kHz WAV bhi ffmpeg se normalize hota hai.
    """
    if not ref.is_file():
        return None
    out_dir = Path(tempfile.mkdtemp(prefix="xtts_ref_"))
    out = out_dir / "speaker.wav"
    cmd = [
        "ffmpeg",
        "-nostdin",
        "-y",
        "-i",
        str(ref),
        "-t",
        str(max_seconds),
        "-ac",
        "1",
        "-ar",
        "24000",
        "-sample_fmt",
        "s16",
        str(out),
    ]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            timeout=180,
            check=False,
        )
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    except OSError:
        pass
    if ref.suffix.lower() == ".wav" and ref.is_file():
        return ref
    return None


def _float_wav_to_bytes(wav: np.ndarray, sample_rate: int) -> bytes:
    w = np.asarray(wav, dtype=np.float32).flatten()
    w = np.clip(w, -1.0, 1.0)
    pcm = (w * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    import wave

    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def get_xtts():
    global _xtts_model
    if _xtts_model is None:
        # Coqui XTTS v2 is under CPML (non-commercial unless you have a commercial license).
        # Setting this env var avoids the interactive license prompt.
        os.environ.setdefault("COQUI_TOS_AGREED", "1")
        # PyTorch 2.6+ defaults `torch.load(weights_only=True)` which can break XTTS checkpoints.
        # This forces legacy behavior (only do this if you trust the checkpoint source).
        os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
        import torch
        from TTS.api import TTS

        gpu = torch.cuda.is_available()
        _xtts_model = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", gpu=gpu)
    return _xtts_model


def _xtts_tts_call(tts, text: str, wav_ref: Path, lang: str):
    """Coqui API: list `speaker_wav` + split_sentences + optional inference kwargs (**kwargs)."""
    import inspect

    sig = inspect.signature(tts.tts)
    p = set(sig.parameters)
    has_varkw = any(x.kind == inspect.Parameter.VAR_KEYWORD for x in sig.parameters.values())
    kw: dict = {}
    if "split_sentences" in p:
        kw["split_sentences"] = True
    tuning = {
        "temperature": 0.65,
        "repetition_penalty": 5.0,
        "length_penalty": 1.0,
    }
    for k, v in tuning.items():
        if k in p or has_varkw:
            kw[k] = v

    def _call(sw):
        return tts.tts(text=text, speaker_wav=sw, language=lang, **kw)

    try:
        return _call([str(wav_ref)])
    except TypeError:
        return _call(str(wav_ref))


def xtts_clone_wav_bytes(text: str, ref_file: Path | None) -> tuple[bytes | None, str]:
    """
    Tumhari di hui reference clip se clone (Coqui XTTS v2).
    Returns (wav_bytes_or_None, error_message) — error_message khali on success.
    """
    if not text.strip():
        return None, "Khali text — kuch likh kar bhejo."
    if ref_file is None:
        return None, "Reference file path set nahi."
    if not ref_file.is_file():
        return None, f"Reference file nahi mili: {ref_file}"
    text = text.strip()[:800]
    wav_ref = reference_to_wav_mono(ref_file)
    if wav_ref is None:
        return (
            None,
            "MP3/M4A se WAV nahi bana — `ffmpeg` PATH mein hona chahiye, ya `.wav` reference use karo.",
        )
    last_err: str | None = None
    for attempt in range(2):
        try:
            tts = get_xtts()
            lang = _xtts_language(text)
            out = _xtts_tts_call(tts, text, wav_ref, lang)
            sr = 24000
            if isinstance(out, (list, tuple)) and len(out) == 2:
                wav_part, sr = out[0], int(out[1])
                arr = np.asarray(wav_part, dtype=np.float32)
            else:
                arr = np.asarray(out, dtype=np.float32)
                syn = getattr(tts, "synthesizer", None)
                if syn is not None and getattr(syn, "output_sample_rate", None):
                    sr = int(syn.output_sample_rate)
            return _float_wav_to_bytes(arr, sr), ""
        except Exception as e:
            msg = str(e).strip() or type(e).__name__
            if len(msg) > 280:
                msg = msg[:277] + "..."
            last_err = f"XTTS error: {msg}"
            if attempt == 0:
                time.sleep(1.0)
                continue
    return None, last_err or "XTTS error"


def speak_reply_bytes(
    text: str,
    ref: Path | None,
) -> tuple[bytes | None, str, str]:
    """
    Returns (audio_bytes, mime, clone_error) — clone_error sirf clone mode mein meaningful.
    mime = audio/wav
    """
    if not text.strip():
        return None, "", ""

    nana = nana_clone_reference_path()
    ref = nana if nana is not None else ref
    b, err = xtts_clone_wav_bytes(text, ref)
    if b:
        return b, "audio/wav", ""
    return None, "", err or "Clone output nahi bana."
