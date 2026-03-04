import os
import torch
import torch.serialization
import shutil
import subprocess

# Auto-agree to Coqui TOS so the server doesn't hang
os.environ["COQUI_TOS_AGREED"] = "1"

# PyTorch 2.6+ security fix
_orig_load = torch.load
def _patched_load(*args, **kwargs):
    kwargs['weights_only'] = False
    return _orig_load(*args, **kwargs)

torch.load = _patched_load
torch.serialization.load = _patched_load

# Define the XTTS v2 model name
XTTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
_tts_model = None

from backend.utils.device_manager import get_xtts_device

def get_device():
    """Determine the best available device for synthesis."""
    return get_xtts_device()

def get_tts_model():
    """Load and cache the XTTS v2 model."""
    global _tts_model
    if _tts_model is None:
        from TTS.api import TTS
        print("Loading XTTS v2 model...")
        device = get_device()
        _tts_model = TTS(XTTS_MODEL_NAME).to(device)
        print("XTTS v2 model loaded successfully!")
    return _tts_model

def extract_speaker_sample(video_path: str, output_wav_path: str, duration: int = 10):
    """
    Extract a short audio snippet from the video to use as the speaker prompt.
    Extracts the first `duration` seconds.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Source video not found: {video_path}")
        
    print(f"Extracting {duration}s speaker sample from {video_path}...")
    
    # We use ffmpeg to accurately extract the first few seconds 
    # and convert to a mono 16kHz wav file which is ideal for XTTS
    command = [
        "ffmpeg",
        "-y", # Overwrite output file
        "-i", video_path,
        "-t", str(duration), # Extract this many seconds
        "-ac", "1", # Mono
        "-ar", "22050", # Assuming 22050 is good for TTS, XTTS usually needs 22.05k or 24k
        "-acodec", "pcm_s16le", # 16-bit PCM
        output_wav_path
    ]
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Speaker sample extracted to {output_wav_path}")
        return output_wav_path
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg extraction failed: {e.stderr.decode()}")
        raise RuntimeError("Failed to extract audio sample.")

def clone_voice(text: str, speaker_wav: str, language_code: str, output_path: str):
    """
    Synthesize speech using XTTS v2, cloning the voice from `speaker_wav`.
    """
    if not os.path.exists(speaker_wav):
        raise FileNotFoundError(f"Speaker sample not found: {speaker_wav}")
        
    # Mapping our generic language codes to XTTS expected language codes
    # XTTS supports: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, hu, ko, ja, hi
    # uz (Uzbek) is NOT supported by standard XTTS natively. 
    # Usually, for unsupported languages, people fallback to a similar sounding language or 'tr' (Turkish) 
    # or general 'en' if multi-lingual adaptation is okay, but accent might be off.
    
    xtts_lang_map = {
        "ru": "ru",
        "en": "en",
        "uz": "tr", # Fallback to Turkish for Uzbek as it's the closest supported in XTTS v2
        "tr": "tr",
        "ar": "ar",
        "zh-cn": "zh-cn"
    }
    
    lang = xtts_lang_map.get(language_code.lower().split('-')[0], "en")
    print(f"Synthesizing voice in '{lang}' (mapped from {language_code})...")
    
    model = get_tts_model()
    
    try:
        model.tts_to_file(
            text=text,
            speaker_wav=speaker_wav,
            language=lang,
            file_path=output_path
        )
        print(f"Cloned audio saved to {output_path}")
        return True
    except Exception as e:
        print(f"Voice cloning failed: {e}")
        return False
