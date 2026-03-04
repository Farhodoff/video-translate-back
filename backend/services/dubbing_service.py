import asyncio
import edge_tts
import os
import subprocess
from typing import Optional
from pydub import AudioSegment
from backend.services import audio_processing_service
from backend.utils.progress import publish_progress

EDGE_TTS_VOICE = "uz-UZ-MadinaNeural"  # Fallback voice if XTTS fails


def merge_video_audio(video_path: str, audio_path: str, output_path: str):
    """
    Merges video and audio using ffmpeg.
    Replaces original audio with the new audio track.
    """
    cmd = [
        "ffmpeg",
        "-y",       # Overwrite output
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",     # Copy video stream (no re-encoding)
        "-c:a", "aac",      # Encode audio to AAC
        "-map", "0:v:0",    # Video from first input
        "-map", "1:a:0",    # Audio from second input
        "-shortest",
        output_path
    ]
    print(f"Running merge command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return output_path


def _generate_segment_xtts(text: str, speaker_wav: Optional[str], output_file: str, lang: str = "uz") -> bool:
    """
    Synthesize one segment via XTTS v2 voice cloning (synchronous).
    Returns True on success.
    """
    if not speaker_wav:
        return False
    try:
        from backend.services import voice_cloning_service
        return voice_cloning_service.clone_voice(text, speaker_wav, lang, output_file)
    except Exception as e:
        print(f"XTTS failed for segment: {e}")
        return False


async def _generate_segment_edge_tts(text: str, output_file: str) -> bool:
    """
    Fallback: generate single segment audio via Edge-TTS (async).
    """
    try:
        if not text or not text.strip():
            return False
        communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"Edge-TTS failed: {e}")
        return False


async def create_dubbing(
    project_id: int,
    translated_segments: list,
    output_dir: str,
    video_path: Optional[str] = None,
    use_voice_cloning: bool = True
) -> Optional[str]:
    """
    Generates audio for all translated segments.
    Strategy:
      1. Extract speaker sample from source video.
      2. Try XTTS v2 voice cloning for each segment (preserves speaker identity).
      3. If XTTS is unavailable / fails, fall back to Edge-TTS.
    Returns path to the final mixed audio file.
    """
    print(f"Starting dubbing for project {project_id} (use_voice_cloning={use_voice_cloning})...")

    temp_dir = os.path.join(output_dir, f"temp_{project_id}")
    os.makedirs(temp_dir, exist_ok=True)

    # ── Step A: Separate background music (Demucs) ──────────────────────────────
    no_vocals_path = None
    if video_path and os.path.exists(video_path):
        try:
            _, no_vocals_path = audio_processing_service.separate_audio(video_path, temp_dir)
        except Exception as e:
            print(f"Warning: Demucs separation failed, continuing without background mix: {e}")

    # ── Step B: Extract speaker sample for voice cloning ─────────────────────────
    speaker_wav = None
    if use_voice_cloning and video_path and os.path.exists(video_path):
        try:
            from backend.services import voice_cloning_service
            speaker_wav_path = os.path.join(temp_dir, "speaker_sample.wav")
            voice_cloning_service.extract_speaker_sample(video_path, speaker_wav_path, duration=12)
            speaker_wav = speaker_wav_path
            print(f"Speaker sample ready: {speaker_wav}")
        except Exception as e:
            print(f"Warning: Speaker sample extraction failed, will use Edge-TTS: {e}")

    # ── Step C: Generate audio per segment ───────────────────────────────────────
    final_vocals = AudioSegment.silent(duration=0)
    total_segments = len(translated_segments)

    try:
        for i, segment in enumerate(translated_segments):
            # Real-time progress between 60% and 95%
            if total_segments > 0:
                current_progress = 60 + int((i / total_segments) * 35)
                publish_progress(project_id, "Dubbing", current_progress)

            text = segment.get('translated_text', '')
            start_time_ms = int(segment['start'] * 1000)
            end_time_ms = int(segment['end'] * 1000)

            if not text.strip():
                continue

            segment_file = os.path.join(temp_dir, f"seg_{i}.wav")
            success = False

            # Prefer XTTS voice cloning if speaker sample is available
            if use_voice_cloning:
                success = _generate_segment_xtts(text, speaker_wav, segment_file, lang="uz")

            # Fallback to Edge-TTS
            if not success:
                segment_file = os.path.join(temp_dir, f"seg_{i}.mp3")
                success = await _generate_segment_edge_tts(text, segment_file)

            if success and os.path.exists(segment_file):
                target_duration_ms = end_time_ms - start_time_ms
                adjusted_file = os.path.join(temp_dir, f"adj_seg_{i}.wav")

                try:
                    audio_processing_service.adjust_audio_speed(segment_file, target_duration_ms, adjusted_file)
                    audio_segment = AudioSegment.from_file(adjusted_file)
                except Exception as e:
                    print(f"Speed adjustment failed for segment {i}: {e}")
                    audio_segment = AudioSegment.from_file(segment_file)

                silence_duration = max(0, start_time_ms - len(final_vocals))
                if silence_duration > 0:
                    final_vocals += AudioSegment.silent(duration=silence_duration)

                final_vocals += audio_segment

        # ── Step D: Mix with background music ─────────────────────────────────────
        no_vocals_str: Optional[str] = no_vocals_path
        if no_vocals_str is not None and os.path.exists(no_vocals_str):
            try:
                background_audio = AudioSegment.from_file(no_vocals_path)
                final_audio = background_audio.overlay(final_vocals)
                print("Successfully mixed with background music.")
            except Exception as e:
                print(f"Mixing failed: {e}")
                final_audio = final_vocals
        else:
            final_audio = final_vocals

        # ── Step E: Export ────────────────────────────────────────────────────────
        output_filename = f"dubbed_{project_id}.mp3"
        output_path = os.path.join(output_dir, output_filename)
        final_audio.export(output_path, format="mp3")
        print(f"Dubbing completed: {output_path}")
        return output_path

    except Exception as e:
        print(f"Dubbing failed: {e}")
        raise e
    finally:
        # Cleanup temp files
        try:
            for f in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, f))
            os.rmdir(temp_dir)
        except Exception as cleanup_error:
            print(f"Cleanup warning: {cleanup_error}")
