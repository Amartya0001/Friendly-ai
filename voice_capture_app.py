"""
Voice capture GUI — microphone se recording + voice profile (baad mein extend karne ke liye).
Run: python voice_capture_app.py
"""
from __future__ import annotations

import wave
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from datetime import datetime

import numpy as np
import sounddevice as sd

from voice_profile import VoiceProfile, DEFAULT_PATH, resolve_reference_audio_path


class VoiceCaptureApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Voice Capture")
        self.root.minsize(420, 480)
        self.profile = VoiceProfile.load()
        self._recording = False
        self._record_thread: threading.Thread | None = None
        self._audio_chunks: list[np.ndarray] = []
        self._current_rate = self.profile.sample_rate

        self._build_ui()
        self._refresh_devices()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        f_profile = ttk.LabelFrame(self.root, text="Voice profile (baad mein yahan voice add kar sakte ho)")
        f_profile.pack(fill="x", **pad)

        ttk.Label(f_profile, text="Profile name:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.var_name = tk.StringVar(value=self.profile.name)
        ttk.Entry(f_profile, textvariable=self.var_name, width=28).grid(row=0, column=1, sticky="ew", padx=4)

        ttk.Label(f_profile, text="Mic / input:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.var_device = tk.StringVar()
        self.combo_device = ttk.Combobox(f_profile, textvariable=self.var_device, width=40, state="readonly")
        self.combo_device.grid(row=1, column=1, sticky="ew", padx=4)

        ttk.Label(f_profile, text="Sample rate (Hz):").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.var_rate = tk.StringVar(value=str(self.profile.sample_rate))
        ttk.Entry(f_profile, textvariable=self.var_rate, width=12).grid(row=2, column=1, sticky="w", padx=4)

        ttk.Label(f_profile, text="Reference clip (optional, voice match / clone ke liye):").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 0)
        )
        ref_row = ttk.Frame(f_profile)
        ref_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.var_ref = tk.StringVar(value=self.profile.reference_audio_path or "")
        ttk.Entry(ref_row, textvariable=self.var_ref, width=36).pack(side="left", fill="x", expand=True)
        ttk.Button(ref_row, text="Browse…", command=self._browse_ref).pack(side="left", padx=(6, 0))
        ttk.Button(ref_row, text="Check", command=self._update_ref_status).pack(side="left", padx=(4, 0))

        self.lbl_ref_status = ttk.Label(f_profile, text="", foreground="gray", wraplength=400)
        self.lbl_ref_status.grid(row=5, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

        ttk.Label(f_profile, text="Notes:").grid(row=6, column=0, sticky="nw", padx=8, pady=4)
        self.txt_notes = tk.Text(f_profile, height=3, width=40, wrap="word")
        self.txt_notes.grid(row=6, column=1, sticky="ew", padx=4, pady=4)
        self.txt_notes.insert("1.0", self.profile.notes)
        f_profile.columnconfigure(1, weight=1)

        self.var_ref.trace_add("write", lambda *_: self._update_ref_status())
        self._update_ref_status()

        ttk.Button(f_profile, text="Profile save karo", command=self._save_profile).grid(
            row=7, column=0, columnspan=2, pady=8
        )

        f_rec = ttk.LabelFrame(self.root, text="Recording")
        f_rec.pack(fill="both", expand=True, **pad)

        self.lbl_status = ttk.Label(f_rec, text="Tayyar — Record dabao")
        self.lbl_status.pack(anchor="w", padx=8, pady=4)

        bf = ttk.Frame(f_rec)
        bf.pack(fill="x", padx=8, pady=8)
        self.btn_record = ttk.Button(bf, text="Record", command=self._toggle_record)
        self.btn_record.pack(side="left", padx=(0, 8))
        ttk.Button(bf, text="Capture save (WAV)", command=self._save_wav).pack(side="left")

        self.progress = ttk.Progressbar(f_rec, mode="indeterminate")
        self.progress.pack(fill="x", padx=8, pady=4)

        ttk.Label(
            f_rec,
            text="Tip: Profile mein jo mic / sample rate set ho, recording wahi use karti hai.",
            wraplength=400,
        ).pack(anchor="w", padx=8, pady=8)

    def _device_list(self) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                name = f"{i}: {d['name']}"
                out.append((i, name))
        return out

    def _refresh_devices(self) -> None:
        items = self._device_list()
        labels = [x[1] for x in items]
        self.combo_device["values"] = labels
        if not labels:
            self.var_device.set("")
            return
        # saved name match
        target = self.profile.input_device
        for lab in labels:
            if target and target in lab:
                self.var_device.set(lab)
                break
        else:
            self.var_device.set(labels[0])

    def _selected_device_index(self) -> int | None:
        s = self.var_device.get()
        if not s or ":" not in s:
            return None
        try:
            return int(s.split(":", 1)[0].strip())
        except ValueError:
            return None

    def _browse_ref(self) -> None:
        p = filedialog.askopenfilename(
            title="Reference audio",
            filetypes=[("Audio", "*.wav *.mp3 *.flac *.m4a"), ("All", "*.*")],
        )
        if p:
            self.var_ref.set(p)
        self._update_ref_status()

    def _update_ref_status(self) -> None:
        raw = self.var_ref.get().strip()
        if not raw:
            self.lbl_ref_status.configure(text="Reference: (koi file set nahi)", foreground="gray")
            return
        resolved = resolve_reference_audio_path(raw)
        if resolved is None:
            self.lbl_ref_status.configure(text="Reference: (invalid path)", foreground="orange")
            return
        if resolved.is_file():
            self.lbl_ref_status.configure(
                text=f"Reference OK — {resolved}",
                foreground="green",
            )
        else:
            self.lbl_ref_status.configure(
                text=f"File abhi nahi mili — yahan honi chahiye:\n{resolved}",
                foreground="orange",
            )

    def _save_profile(self) -> None:
        try:
            rate = int(self.var_rate.get().strip())
            if rate < 8000 or rate > 192000:
                raise ValueError("sample rate range")
        except ValueError:
            messagebox.showerror("Error", "Sample rate ek valid number hona chahiye (jaise 44100).")
            return

        self.profile.name = self.var_name.get().strip() or "default"
        self.profile.input_device = self.var_device.get() or None
        self.profile.sample_rate = rate
        self.profile.reference_audio_path = self.var_ref.get().strip() or None
        self.profile.notes = self.txt_notes.get("1.0", "end").strip()
        self.profile.save()
        self._current_rate = rate
        messagebox.showinfo("OK", f"Profile save ho gaya:\n{DEFAULT_PATH}")

    def _toggle_record(self) -> None:
        if not self._recording:
            self._start_record()
        else:
            self._stop_record()

    def _start_record(self) -> None:
        try:
            self._current_rate = int(self.var_rate.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Pehle valid sample rate set karo.")
            return

        dev = self._selected_device_index()
        self._audio_chunks = []
        self._recording = True
        self.btn_record.configure(text="Stop")
        self.lbl_status.configure(text="Recording…")
        self.progress.start(10)

        def loop() -> None:
            block = 1024
            try:
                with sd.InputStream(
                    device=dev,
                    channels=1,
                    samplerate=self._current_rate,
                    dtype="float32",
                    blocksize=block,
                ) as stream:
                    while self._recording:
                        data, _ = stream.read(block)
                        self._audio_chunks.append(data.copy())
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Mic error", str(e)))
                self.root.after(0, self._stop_record_ui)

        self._record_thread = threading.Thread(target=loop, daemon=True)
        self._record_thread.start()

    def _stop_record_ui(self) -> None:
        self.progress.stop()
        self.btn_record.configure(text="Record")
        self.lbl_status.configure(text="Recording band — ab Save dabao ya dubara Record")

    def _stop_record(self) -> None:
        self._recording = False
        if self._record_thread:
            self._record_thread.join(timeout=3.0)
            self._record_thread = None
        self._stop_record_ui()

    def _save_wav(self) -> None:
        if not self._audio_chunks:
            messagebox.showwarning("Kuch record nahi", "Pehle Record se audio capture karo.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV", "*.wav")],
            initialfile=f"capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav",
        )
        if not path:
            return

        audio = np.concatenate(self._audio_chunks, axis=0).flatten()
        # float32 [-1,1] -> int16
        peak = np.max(np.abs(audio)) or 1.0
        audio = np.clip(audio / peak, -1.0, 1.0)
        pcm = (audio * 32767.0).astype(np.int16)

        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self._current_rate)
            wf.writeframes(pcm.tobytes())

        messagebox.showinfo("OK", f"Save ho gaya:\n{path}")

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    VoiceCaptureApp().run()
