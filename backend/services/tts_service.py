import edge_tts
import os

async def generate_speech(text: str, output_path: str, voice: str = "uz-UZ-MadinaNeural", rate: str = "+0%", pitch: str = "+0Hz"):
    """
    Generate speech from text using Microsoft Edge's online TTS service.
    
    Args:
        text (str): The text to synthesize.
        output_path (str): The path to save the output audio file (e.g., .mp3).
        voice (str): The voice to use. Defaults to "uz-UZ-MadinaNeural".
        rate (str): Speaking rate adjustment (e.g., "+10%", "-5%").
        pitch (str): Pitch adjustment (e.g., "+5Hz", "-2Hz").
    """
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"Error checking TTS: {e}")
        return False
