import threading
import json
import customtkinter as ctk
import speech_recognition as sr
import spacy
from spacy.matcher import PhraseMatcher

# For offline recognition using Vosk
try:
    from vosk import Model as VoskModel, KaldiRecognizer
except ImportError:
    VoskModel = None  # Vosk not available

# Load spaCy model (for phrase extraction)
nlp = spacy.load("en_core_web_sm")

# Global variables
vosk_model = None
is_vosk_loaded = False

def load_vosk_model():
    """Background thread function to load the Vosk model with indefinite progress bar."""
    global vosk_model, is_vosk_loaded
    if VoskModel is not None:
        try:
            app.after(0, lambda: persistent_status_label.configure(text="Loading offline voice recognition model..."))
            app.after(0, start_progress)
            
            vosk_model = VoskModel("C:\\Users\\PC\\Desktop\\Python\\Voice\\vosk-model-en-us-0.42-gigaspeech")
            is_vosk_loaded = True

            # Once loaded, update persistent status and stop progress
            app.after(0, stop_progress)
            app.after(0, lambda: persistent_status_label.configure(text="Offline loaded | Online available"))
        except Exception as e:
            app.after(0, stop_progress)
            app.after(0, lambda: persistent_status_label.configure(text=f"Error loading offline model: {e}"))
    else:
        app.after(0, lambda: persistent_status_label.configure(text="Vosk not installed."))

def start_progress():
    """Show and start indefinite progress bar."""
    progress_bar.pack(pady=(0,5), padx=10)
    progress_bar.start()

def stop_progress():
    """Stop spinning and hide the progress bar."""
    progress_bar.stop()
    progress_bar.pack_forget()

def extract_phrases(text, target_phrases):
    """Use spaCy's PhraseMatcher to extract multi-word expressions."""
    doc = nlp(text)
    matcher = PhraseMatcher(nlp.vocab)
    patterns = [nlp.make_doc(phrase.strip()) for phrase in target_phrases if phrase.strip()]
    if patterns:
        matcher.add("KEY_PHRASE", None, *patterns)
    matches = matcher(doc)
    return [doc[start:end].text for match_id, start, end in matches]

def start_listening_thread():
    """Start the listening/recognition process in a separate thread."""
    thread = threading.Thread(target=listen, daemon=True)
    thread.start()

def listen():
    """Perform speech recognition in a background thread so GUI doesn't freeze."""
    try:
        app.after(0, start_progress)

        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 1.5
        # You can remove or adjust phrase_time_limit for longer recordings
        with sr.Microphone() as source:
            #recognizer.energy_threshold = 300
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            app.after(0, lambda: ephemeral_status_label.configure(text="Listening...", fg_color="blue"))
            audio = recognizer.listen(source, phrase_time_limit=15)

        if toggle_var.get():  # Offline mode using Vosk
            if not is_vosk_loaded or vosk_model is None:
                app.after(0, lambda: ephemeral_status_label.configure(text="Offline model not loaded yet", fg_color="red"))
                return

            # Convert to 16kHz, 16-bit
            raw_audio = audio.get_raw_data(convert_rate=16000, convert_width=2)
            vosk_recognizer = KaldiRecognizer(vosk_model, 16000)
            # First check if we get a full final result
            text = ""
            if vosk_recognizer.AcceptWaveform(raw_audio):
                # If the entire utterance is recognized as a final waveform
                result_json = vosk_recognizer.Result()
                result_dict = json.loads(result_json)
                text = result_dict.get("text", "")
            else:
                # If AcceptWaveform returns False, we attempt the final result
                final_json = vosk_recognizer.FinalResult()
                final_dict = json.loads(final_json)
                text = final_dict.get("text", "")
            
        else:
            # Online recognition
            text = recognizer.recognize_google(audio)

        # Insert recognized text into transcript
        app.after(0, lambda: transcript_text.insert("end", text + "\n"))
        app.after(0, lambda: ephemeral_status_label.configure(text="Transcription successful", fg_color="green"))
        process_text(text)

    except sr.RequestError:
        app.after(0, lambda: ephemeral_status_label.configure(text="API unavailable", fg_color="red"))
    except sr.UnknownValueError:
        app.after(0, lambda: ephemeral_status_label.configure(text="Could not understand audio", fg_color="red"))
    except Exception as e:
        app.after(0, lambda: ephemeral_status_label.configure(text=f"Error: {e}", fg_color="red"))
    finally:
        app.after(0, stop_progress)

def process_text(text):
    """Extract key phrases from the text using user-defined phrases."""
    user_input = phrase_entry.get()
    if user_input.strip():
        target_phrases = [p.strip() for p in user_input.split(",")]
    else:
        target_phrases = ["safety reset"]
    phrases = extract_phrases(text, target_phrases)
    if phrases:
        app.after(0, lambda: key_phrase_text.insert("end", "Key Phrases: " + ", ".join(phrases) + "\n"))
    else:
        app.after(0, lambda: key_phrase_text.insert("end", "No key phrases detected.\n"))

# ------------------- GUI SETUP -------------------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry("700x700")
app.title("Voice Recognition & Command via Phrase - by Shaun Harris")

# ------------------- Top Frame for Status -------------------
top_frame = ctk.CTkFrame(master=app)
top_frame.pack(pady=10, padx=10, fill="x")

# Persistent status label (e.g., "Offline loaded | Online available")
persistent_status_label = ctk.CTkLabel(master=top_frame, text="Initializing...", width=400)
persistent_status_label.pack(pady=5, padx=10)

# Ephemeral status label (e.g., "Listening...", "Transcription successful")
ephemeral_status_label = ctk.CTkLabel(master=top_frame, text="", width=400)
ephemeral_status_label.pack(pady=(0,5), padx=10)

# Progress Bar (initially hidden)
progress_bar = ctk.CTkProgressBar(master=top_frame, orientation="horizontal", mode="indeterminate", width=400)

# ------------------- Frame for Input Phrases -------------------
input_frame = ctk.CTkFrame(master=app)
input_frame.pack(pady=5, padx=10, fill="x")

phrase_label = ctk.CTkLabel(master=input_frame, text="Enter phrases to detect (comma-separated):")
phrase_label.pack(pady=5, padx=10, anchor="w")

phrase_entry = ctk.CTkEntry(master=input_frame, width=500)
phrase_entry.insert(0, "safety, start, stop, data")
phrase_entry.pack(pady=(0,5), padx=10)

# ------------------- Frame for Transcript Output -------------------
transcript_frame = ctk.CTkFrame(master=app)
transcript_frame.pack(pady=5, padx=10, fill="both", expand=True)

transcript_label = ctk.CTkLabel(master=transcript_frame, text="Transcript:")
transcript_label.pack(pady=(0,5), padx=10, anchor="w")

transcript_text = ctk.CTkTextbox(master=transcript_frame, width=600, height=200)
transcript_text.pack(pady=5, padx=10, fill="both", expand=True)

# ------------------- Frame for Key Phrases Output -------------------
phrase_output_frame = ctk.CTkFrame(master=app)
phrase_output_frame.pack(pady=5, padx=10, fill="both", expand=True)

phrase_output_label = ctk.CTkLabel(master=phrase_output_frame, text="Detected Key Phrases:")
phrase_output_label.pack(pady=(0,5), padx=10, anchor="w")

key_phrase_text = ctk.CTkTextbox(master=phrase_output_frame, width=600, height=120)
key_phrase_text.pack(pady=5, padx=10, fill="both", expand=True)

# ------------------- Bottom Frame for Controls -------------------
bottom_frame = ctk.CTkFrame(master=app)
bottom_frame.pack(pady=10, padx=10, fill="x")

listen_button = ctk.CTkButton(master=bottom_frame, text="Start Listening", command=start_listening_thread)
listen_button.pack(side="left", padx=(0,20))

toggle_var = ctk.BooleanVar(value=False)
toggle_switch = ctk.CTkSwitch(
    master=bottom_frame, 
    text="Use Offline Recognition", 
    variable=toggle_var
)
toggle_switch.pack(side="left")

def load_model_in_thread():
    """Start the background thread to load the Vosk model after GUI is ready."""
    model_thread = threading.Thread(target=load_vosk_model, daemon=True)
    model_thread.start()

# After the GUI is fully created, load the model
app.after(100, load_model_in_thread)

app.mainloop()
