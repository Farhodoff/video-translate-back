import os
import time
import asyncio
from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import models
from backend.services import video_service, transcription_service, translation_service, dubbing_service, lipsync_service
from backend.utils.progress import publish_progress

@celery_app.task(bind=True, name="backend.tasks.process_project_video_task")
def process_project_video_task(self, project_id: int, url: str = None, file_path: str = None):
    db = SessionLocal()
    try:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            return "Project not found"

        UPLOAD_DIR = "uploads"
        output_path = file_path
        
        # 1. Download Video
        if url:
            publish_progress(project_id, "Processing", 10)
            info = video_service.analyze_youtube_url(url)
            project.thumbnail = info.get("thumbnail")
            project.title = info.get("video_title") if not project.title else project.title
            db.commit()

            filename = f"{project_id}_{int(time.time())}.mp4"
            output_path = video_service.download_video(url, UPLOAD_DIR, filename)

        if not output_path:
            publish_progress(project_id, "Error", 0)
            project.error_message = "Failed to obtain video file"
            db.commit()
            return "No output_path"

        # 2. Transcribe
        publish_progress(project_id, "Transcribing", 20)
        transcript = transcription_service.transcribe_video(str(output_path), quality=project.quality)
        project.transcript = transcript
        db.commit()

        # 3. Translate
        publish_progress(project_id, "Translating", 40)
        translated_segments = translation_service.translate_segments(transcript, target_lang='uz')
        project.translated_transcript = translated_segments
        db.commit()

        # 4. Dubbing
        publish_progress(project_id, "Dubbing", 60)
        output_dir = os.path.dirname(str(output_path))
        
        # Dubbing service uses async, so we wrap it in a synchronous event loop execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            audio_path = loop.run_until_complete(
                dubbing_service.create_dubbing(project_id, translated_segments, output_dir, video_path=str(output_path))
            )
        finally:
            loop.close()

        project.dubbed_audio_url = f"/uploads/{os.path.basename(audio_path)}"

        # 5. Lip-Sync (Wav2Lip)
        publish_progress(project_id, "Lip-Syncing", 96)
        sync_video_filename = f"sync_{project_id}.mp4"
        sync_video_path = os.path.join(output_dir, sync_video_filename)
        
        # Apply lip sync using original downloaded video + dubbed audio
        lipsync_success = lipsync_service.apply_lipsync(
            video_path=str(output_path),
            audio_path=audio_path,
            output_path=sync_video_path
        )
        
        final_target_video = sync_video_path if lipsync_success else str(output_path)

        # 6. Merge Background audio (if Demucs wasn't fully mixed, or just ensure proper format)
        publish_progress(project_id, "Merging", 98)
        final_video_filename = f"final_{project_id}.mp4"
        final_video_path = os.path.join(output_dir, final_video_filename)
        dubbing_service.merge_video_audio(final_target_video, audio_path, final_video_path)
        project.final_video_url = f"/uploads/{final_video_filename}"

        publish_progress(project_id, "Ready", 100)
        db.commit()
        return "Task Completed Successfully"

    except Exception as e:
        print(f"Error processing project {project_id} in Celery task: {e}")
        publish_progress(project_id, "Error")
        # Attempt to save error message if DB is still available
        try:
            project.error_message = str(e)
            db.commit()
        except:
            pass
        return f"Error: {str(e)}"
    finally:
        db.close()
