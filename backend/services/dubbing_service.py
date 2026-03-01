import edge_tts
import asyncio
import os
import subprocess
from pydub import AudioSegment

VOICE = "uz-UZ-MadinaNeural" # High quality Uzbek voice

def merge_video_audio(video_path: str, audio_path: str, output_path: str):
    """
    Merges video and audio using ffmpeg.
    Replaces original audio with the new audio track.
    """
    cmd = [
        "ffmpeg",
        "-y", # Overwrite output
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy", # Copy video stream (no re-encoding)
        "-c:a", "aac", # Encode audio to AAC
        "-map", "0:v:0", # Use video from first input
        "-map", "1:a:0", # Use audio from second input
        "-shortest", # Finish when the shorter stream ends
        output_path
    ]
    
    print(f"Running merge command: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    return output_path

async def generate_segment_audio(text: str, output_file: str) -> bool:
    """
    Generates audio for a single segment using edge-tts.
    """
    try:
        if not text or not text.strip():
            return False
            
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"Error generating audio for '{text}': {e}")
        return False

async def create_dubbing(project_id: int, translated_segments: list, output_dir: str) -> str:
    """
    Generates audio for all segments and merges them.
    Returns the path to the final audio file.
    """
    print(f"Starting dubbing for project {project_id}...")
    
    # Create temp dir for segments
    temp_dir = os.path.join(output_dir, f"temp_{project_id}")
    os.makedirs(temp_dir, exist_ok=True)
    
    final_audio = AudioSegment.silent(duration=0)
    last_end_time = 0
    
    try:
        for i, segment in enumerate(translated_segments):
            text = segment.get('translated_text', '')
            start_time_ms = int(segment['start'] * 1000)
            end_time_ms = int(segment['end'] * 1000)
            
            if not text.strip():
                continue
                
            # Generate audio for this segment
            segment_file = os.path.join(temp_dir, f"seg_{i}.mp3")
            success = await generate_segment_audio(text, segment_file)
            
            if success and os.path.exists(segment_file):
                audio_segment = AudioSegment.from_mp3(segment_file)
                
                # Calculate silence padding
                # Ensure we don't overlap or go back in time
                silence_duration = max(0, start_time_ms - len(final_audio))
                if silence_duration > 0:
                    final_audio += AudioSegment.silent(duration=silence_duration)
                
                # Append audio
                final_audio += audio_segment
                
                # Update duration tracking
                # Note: We rely on the natural length of the TTS audio. 
                # If it's longer than the video segment, it will push the next segments.
                # Advanced logic would involve speed adjustment, but for MVP we append.
                
        # Export final
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
