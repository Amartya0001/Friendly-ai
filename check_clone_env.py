"""
Voice clone environment checks — plan verification checklist.
Run: python check_clone_env.py
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from friendly_voice import NANA_REFERENCE_FILENAMES, reference_voice_path
def get_clone_environment_status() -> list[tuple[str, bool, str]]:
    """(label, ok, detail) rows for UI or printing."""
    rows: list[tuple[str, bool, str]] = []

    v = sys.version_info
    py_ok = v.major == 3 and 9 <= v.minor <= 11
    rows.append(
        (
            "Python 3.9–3.11 (Coqui TTS ke liye)",
            py_ok,
            f"Current: {sys.version.split()[0]}" + ("" if py_ok else " — 3.12+ par TTS wheel nahi milta"),
        )
    )

    ref = reference_voice_path()
    ref_ok = ref is not None and ref.is_file()
    nana_names = {n.lower() for n in NANA_REFERENCE_FILENAMES}
    if ref_ok:
        ref_detail = f"`{ref.name}` @ `{ref.parent}`"
        if ref.name.lower() in nana_names:
            ref_detail += " (nana default WAV/MP3)"
    else:
        ref_detail = (
            "Missing — project mein `nana_patekar.wav` (pehle) ya `nana_patekar.mp3` rakho ya profile path theek karo"
        )
    rows.append(("Reference audio (profile + nana wav/mp3 fallback)", ref_ok, ref_detail))

    torch_ok = importlib.util.find_spec("torch") is not None
    rows.append(("torch installed", torch_ok, "OK" if torch_ok else "pip install torch"))

    tts_ok = importlib.util.find_spec("TTS") is not None
    rows.append(("Coqui TTS installed", tts_ok, "OK" if tts_ok else "pip install -r requirements-voice-clone.txt"))

    ffmpeg_ok = False
    ffmpeg_detail = ""
    try:
        r = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=10,
            check=False,
        )
        ffmpeg_ok = r.returncode == 0
        ffmpeg_detail = "PATH par ffmpeg mil gaya" if ffmpeg_ok else "ffmpeg ne error di"
    except FileNotFoundError:
        ffmpeg_detail = "ffmpeg PATH mein nahi — MP3 reference convert nahi hoga"
    except subprocess.TimeoutExpired:
        ffmpeg_detail = "ffmpeg timeout"
    rows.append(("ffmpeg (MP3 → WAV)", ffmpeg_ok, ffmpeg_detail))

    st_ok = importlib.util.find_spec("streamlit") is not None
    rows.append(("streamlit (app chalane ke liye)", st_ok, "OK" if st_ok else "pip install streamlit"))

    return rows


def main() -> int:
    print("=== Voice clone environment ===\n")
    all_ok = True
    for label, ok, detail in get_clone_environment_status():
        mark = "PASS" if ok else "FAIL"
        if not ok:
            all_ok = False
        # Windows default console encoding can choke on unicode arrows/dashes.
        safe_label = label.encode("ascii", "replace").decode("ascii")
        safe_detail = detail.encode("ascii", "replace").decode("ascii")
        print(f"[{mark}] {safe_label}")
        print(f"       {safe_detail}\n")
    print("Streamlit isi Python se chalao jahan TTS install ho (e.g. .venv-tts).")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
