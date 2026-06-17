import math
import os
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

from pydub import AudioSegment
import simpleaudio as sa
import whisper
import demucs.separate


class SoundWaveApp:

    def __init__(self, root):
        self.root = root
        self.root.title("SoundWave + AI PRO")
        self.root.geometry("1150x550")
        self.root.configure(bg="#2d5ea8")

        self.current_audio = None
        self.current_file = None
        self.temp_preview_file = None
        self.play_obj = None
        self.ai_model = None

        self.build_ui()

    # =========================================================================
    # [ USER INTERFACE (UI) LAYOUT ]
    # =========================================================================

    def build_ui(self):
        """Initializes the main GUI layout, buttons, and panels."""
        self.main_frame = tk.Frame(self.root, bg="#2d5ea8")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        left_panel = tk.Frame(self.main_frame, bg="#2d5ea8")
        left_panel.pack(side="left", fill="both", expand=True)

        right_panel = tk.Frame(self.main_frame, bg="#2d5ea8")
        right_panel.pack(side="right", fill="both", padx=(20, 0))

        self.title_label = tk.Label(
            left_panel,
            text="Effects & AI Engine",
            font=("Arial", 26, "bold"),
            bg="#2d5ea8",
            fg="white",
        )
        self.title_label.pack(pady=(10, 15))

        effects_frame = tk.Frame(left_panel, bg="#2d5ea8")
        effects_frame.pack(pady=5)

        btn_style = {
            "font": ("Arial", 13, "bold"),
            "width": 11,
            "height": 2,
            "bg": "#dbeafe",
            "fg": "#0f172a",
            "activebackground": "#93c5fd",
            "activeforeground": "#0f172a",
            "bd": 2,
            "relief": "solid",
        }

        tk.Button(
            effects_frame, text="Speed Up", command=self.speedup_audio, **btn_style
        ).grid(row=0, column=0, padx=4)
        tk.Button(
            effects_frame,
            text="Speed Down",
            command=self.slowdown_audio,
            **btn_style,
        ).grid(row=0, column=1, padx=4)
        tk.Button(
            effects_frame, text="Echo", command=self.echo_audio, **btn_style
        ).grid(row=0, column=2, padx=4)
        tk.Button(
            effects_frame,
            text="Reverse",
            command=self.reverse_audio,
            **btn_style,
        ).grid(row=0, column=3, padx=4)

        player_frame = tk.Frame(left_panel, bg="#2d5ea8")
        player_frame.pack(pady=15)

        tk.Button(
            player_frame,
            text="▶ Play",
            font=("Arial", 16, "bold"),
            width=10,
            bg="#22c55e",
            fg="black",
            command=self.play_audio,
        ).grid(row=0, column=0, padx=10)
        tk.Button(
            player_frame,
            text="■ Stop",
            font=("Arial", 16, "bold"),
            width=10,
            bg="#ef4444",
            fg="black",
            command=self.stop_audio,
        ).grid(row=0, column=1, padx=10)

        bottom_frame = tk.Frame(left_panel, bg="#2d5ea8")
        bottom_frame.pack(fill="x", pady=10)

        left_buttons = tk.Frame(bottom_frame, bg="#2d5ea8")
        left_buttons.pack(side="left", padx=10)

        tk.Button(
            left_buttons,
            text="Upload file",
            font=("Arial", 12, "bold"),
            width=14,
            bg="#f8fafc",
            fg="#0f172a",
            command=self.upload,
        ).pack(pady=4)
        tk.Button(
            left_buttons,
            text="Download file",
            font=("Arial", 12, "bold"),
            width=14,
            bg="#f8fafc",
            fg="#0f172a",
            command=self.download,
        ).pack(pady=4)

        volume_frame = tk.Frame(bottom_frame, bg="#2d5ea8")
        volume_frame.pack(side="right", padx=10)

        tk.Label(
            volume_frame,
            text="Volume",
            font=("Arial", 12, "bold"),
            bg="#2d5ea8",
            fg="white",
        ).pack()
        self.volume_scale = tk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient="horizontal",
            length=160,
            bg="#2d5ea8",
            fg="white",
            highlightthickness=0,
            troughcolor="#93c5fd",
        )
        self.volume_scale.set(70)
        self.volume_scale.pack()

        self.status_label = tk.Label(
            left_panel,
            text="Upload an audio file",
            font=("Arial", 12),
            bg="#2d5ea8",
            fg="white",
        )
        self.status_label.pack(pady=(10, 0))

        tk.Label(
            right_panel,
            text="AI",
            font=("Arial", 14, "bold"),
            bg="#2d5ea8",
            fg="white",
        ).pack(pady=(0, 10))

        self.ai_btn = tk.Button(
            right_panel,
            text="AI Transcription",
            font=("Arial", 11),
            bg="#2d5ea8",
            fg="black",
            command=self.start_transcription_thread,
        )
        self.ai_btn.pack(pady=2, fill="x")

        ai_split_frame = tk.Frame(right_panel, bg="#2d5ea8")
        ai_split_frame.pack(pady=5, fill="x")

        self.vocal_btn = tk.Button(
            ai_split_frame,
            text="Extract Vocal",
            font=("Arial", 11, "bold"),
            bg="#2d5ea8",
            fg="black",
            command=lambda: self.start_split_thread("vocals"),
        )
        self.vocal_btn.pack(side="left", fill="x", expand=True, padx=(0, 2))

        self.inst_btn = tk.Button(
            ai_split_frame,
            text="Extract Music (Minus)",
            font=("Arial", 11, "bold"),
            bg="#2d5ea8",
            fg="black",
            command=lambda: self.start_split_thread("no_vocals"),
        )
        self.inst_btn.pack(side="right", fill="x", expand=True, padx=(2, 0))

        self.text_output = tk.Text(
            right_panel,
            width=42,
            height=14,
            font=("Arial", 11),
            wrap="word",
            bd=2,
            relief="solid",
        )
        self.text_output.pack(fill="both", expand=True, pady=(5, 0))

    # =========================================================================
    # [ CORE AUDIO PROCESSING ENGINE (Pydub & SimpleAudio) ]
    # =========================================================================

    def upload(self):
        """Opens a file dialog to upload an audio file and loads it via Pydub."""
        file_path = filedialog.askopenfilename(
            title="Choose audio file",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.ogg *.flac"),
                ("All files", "*.*"),
            ],
        )
        if not file_path:
            return
        try:
            self.current_audio = AudioSegment.from_file(file_path)
            self.current_file = file_path
            self.status_label.config(
                text=f"File loaded: {os.path.basename(file_path)}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file:\n{e}")

    def reverse_audio(self):
        """Reverses the playback direction of the currently loaded audio segment."""
        if self.current_audio is None:
            messagebox.showwarning("Warning", "Load audio first")
            return
        self.current_audio = self.current_audio.reverse()
        self.status_label.config(text="Reverse applied")

    def speedup_audio(self):
        """Increases the playback speed of the audio track by 1.5x."""
        if self.current_audio is None:
            messagebox.showwarning("Warning", "Load audio first")
            return
        try:
            self.current_audio = self.current_audio.speedup(playback_speed=1.5)
            self.status_label.config(text="Speed Up x1.5 applied")
        except Exception as e:
            messagebox.showerror("Error", f"Could not speed up audio:\n{e}")

    def slowdown_audio(self):
        """Decreases the audio speed by lowering the frame rate down to 75%."""
        if self.current_audio is None:
            messagebox.showwarning("Warning", "Load audio first")
            return
        try:
            new_frame_rate = int(self.current_audio.frame_rate * 0.75)
            slowed = self.current_audio._spawn(
                self.current_audio.raw_data,
                overrides={"frame_rate": new_frame_rate},
            )
            self.current_audio = slowed.set_frame_rate(
                self.current_audio.frame_rate
            )
            self.status_label.config(text="Slow Down applied")
        except Exception as e:
            messagebox.showerror("Error", f"Could not slow down audio:\n{e}")

    def echo_audio(self):
        """Creates an echo effect by overlaying a quieter version of the audio with a 250ms delay."""
        if self.current_audio is None:
            messagebox.showwarning("Warning", "Load audio first")
            return
        try:
            echo_part = self.current_audio - 8  # Decrease volume by 8 dB for the echo effect
            self.current_audio = self.current_audio.overlay(
                echo_part, position=250
            )
            self.status_label.config(text="Echo applied")
        except Exception as e:
            messagebox.showerror("Error", f"Could not add echo:\n{e}")

    def apply_volume(self, audio):
        """Calculates and applies the gain modification in dB based on the UI volume slider percentage."""
        volume_percent = self.volume_scale.get()
        if volume_percent <= 0:
            return audio - 120  # Effectively mutes the audio track
        gain_db = 20 * math.log10(volume_percent / 100)
        return audio + gain_db

    def export_temp_audio(self):
        """Applies volume settings and exports the current audio buffer into a temporary WAV file for playback."""
        if self.current_audio is None:
            return None
        if self.temp_preview_file and os.path.exists(self.temp_preview_file):
            try:
                os.remove(self.temp_preview_file)
            except:
                pass
        preview_audio = self.apply_volume(self.current_audio)
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        self.temp_preview_file = temp_file.name
        temp_file.close()
        preview_audio.export(self.temp_preview_file, format="wav")
        return self.temp_preview_file

    def play_audio(self):
        """Triggers audio playback via simpleaudio using the generated temporary preview file."""
        if self.current_audio is None:
            messagebox.showwarning("Warning", "Load audio first")
            return
        try:
            self.stop_audio()  # Ensure previous playback instance is terminated
            preview_path = self.export_temp_audio()
            wave_obj = sa.WaveObject.from_wave_file(preview_path)
            self.play_obj = wave_obj.play()
            self.status_label.config(text="Playing...")
        except Exception as e:
            messagebox.showerror("Error", f"Could not play audio:\n{e}")

    def stop_audio(self):
        """Stops the active audio playback instance if it is currently running."""
        if self.play_obj is not None:
            self.play_obj.stop()
            self.play_obj = None
            self.status_label.config(text="Playback stopped")

    def download(self):
        """Saves the modified audio track to a selected path on the computer as WAV or MP3."""
        if self.current_audio is None:
            messagebox.showwarning("Warning", "No audio to save")
            return
        save_path = filedialog.asksaveasfilename(
            title="Save file",
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav"), ("MP3 files", "*.mp3")],
        )
        if not save_path:
            return
        try:
            if save_path.endswith(".mp3"):
                self.current_audio.export(save_path, format="mp3")
            else:
                self.current_audio.export(save_path, format="wav")
            self.current_file = save_path
            self.status_label.config(text="File saved")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    # =========================================================================
    # [ AI SOURCE SEPARATION (Demucs) ]
    # =========================================================================

    def start_split_thread(self, stem_type):
        """Spawns a separate daemon thread to run the Demucs audio separation logic."""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please upload an audio file first.")
            return

        self.status_label.config(text="AI is splitting audio... (Takes a moment)")
        self.vocal_btn.config(state="disabled")
        self.inst_btn.config(state="disabled")

        threading.Thread(
            target=self.run_audio_split, args=(stem_type,), daemon=True
        ).start()

    def run_audio_split(self, stem_type):
        """Executes Demucs model to isolate vocal frequencies or instrumental tracks."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Invokes the Demucs main pipeline to isolate voice frequencies into 2 stems
                demucs.separate.main(
                    ["--two-stems", "vocals", "-o", tmpdir, self.current_file]
                )

                base_name = os.path.splitext(os.path.basename(self.current_file))[0]
                model_folder = os.listdir(tmpdir)[0]
                result_dir = os.path.join(tmpdir, model_folder, base_name)

                target_file_name = (
                    "vocals.wav" if stem_type == "vocals" else "no_vocals.wav"
                )
                target_path = os.path.join(result_dir, target_file_name)

                if os.path.exists(target_path):
                    self.current_audio = AudioSegment.from_file(target_path)

                    # Export the split result into a temporary directory cache for processing
                    out_temp = os.path.join(
                        tempfile.gettempdir(), f"split_{target_file_name}"
                    )
                    self.current_audio.export(out_temp, format="wav")
                    self.current_file = out_temp

                    msg = f"Successful! Loaded: {stem_type}"
                    self.root.after(0, self.update_ui_after_split, True, msg)
                else:
                    self.root.after(
                        0,
                        self.update_ui_after_split,
                        False,
                        "File not found",
                    )

        except Exception as e:
            self.root.after(
                0, self.update_ui_after_split, False, f"AI Error: {e}"
            )

    def update_ui_after_split(self, success, message):
        """Updates UI status labels and interaction buttons after Demucs completes execution."""
        self.status_label.config(text=message)
        self.vocal_btn.config(state="normal")
        self.inst_btn.config(state="normal")
        if success:
            messagebox.showinfo("AI Split", "Audio track is split")

    # =========================================================================
    # [ AI SPEECH-TO-TEXT TRANSCRIPTION (Whisper) ]
    # =========================================================================

    def start_transcription_thread(self):
        """Spawns a separate background thread to run Whisper speech-to-text conversion."""
        if not self.current_file:
            messagebox.showwarning("Warning", "Please upload an audio file")
            return
        self.status_label.config(text="AI is working..")
        self.ai_btn.config(state="disabled")
        threading.Thread(target=self.run_transcription, daemon=True).start()

    def run_transcription(self):
        """Loads OpenAI Whisper model dynamically and converts audio waveforms into text string."""
        try:
            if self.ai_model is None:
                self.ai_model = whisper.load_model("base")  # Uses standard multi-language base model
            result = self.ai_model.transcribe(self.current_file)
            text_result = result.get("text", "").strip()
            self.root.after(
                0, self.update_ui_with_text, text_result, "Success! Audio transcribed."
            )
        except Exception as e:
            self.root.after(
                0, self.update_ui_with_text, f"Error:\n{e}", "AI Error"
            )

    def update_ui_with_text(self, text, status_msg):
        """Inserts the transcribed text outcome received from Whisper model into the GUI display area."""
        self.text_output.delete("1.0", tk.END)
        self.text_output.insert(tk.END, text)
        self.status_label.config(text=status_msg)
        self.ai_btn.config(state="normal")


if __name__ == "__main__":
    root = tk.Tk()
    app = SoundWaveApp(root)
    root.mainloop()




