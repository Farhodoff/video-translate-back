from fastapi import APIRouter, Form, UploadFile, File, WebSocket, WebSocketDisconnect, Depends
from typing import Optional
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import timedelta
from backend import database
from backend.models import models
from backend.services import auth, video_service
import os
import shutil
import uuid
import json
import time
import traceback
import asyncio
import redis
from backend.services import video_service, transcription_service, translation_service, tts_service, dubbing_service, notes_service
from backend.utils.text_normalizer import normalize_text
from backend.models.schemas import TranslationRequest, ProjectUpdateRequest

router = APIRouter(prefix="/api")
UPLOAD_DIR = "uploads"


from backend.tasks import process_project_video_task


# ─── Auth endpoints ───────────────────────────────────────────────────────────

@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.email == username).first()
    if not user or not auth.verify_password(password, user.hashed_password):
        raise JSONResponse(
            status_code=401,
            content={"status": "error", "message": "Email yoki parol noto'g'ri"}
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return JSONResponse(content={
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "full_name": user.full_name}
    })


@router.post("/register")
async def register(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(None),
    confirm_password: str = Form(None),
    db: Session = Depends(database.get_db)
):
    if db.query(models.User).filter(models.User.email == username).first():
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Bu email allaqachon ro'yxatdan o'tgan"}
        )
    hashed_password = auth.get_password_hash(password)
    new_user = models.User(email=username, hashed_password=hashed_password, full_name=full_name)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return JSONResponse(content={
        "status": "success",
        "message": "Ro'yxatdan o'tish muvaffaqiyatli"
    })


@router.post("/logout")
async def logout():
    return JSONResponse(content={"status": "success", "message": "Chiqish muvaffaqiyatli"})


@router.get("/me")
async def get_me(user: models.User = Depends(auth.get_current_user)):
    return JSONResponse(content={
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name
    })


# ─── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    return {"status": "ok"}


# ─── Projects ─────────────────────────────────────────────────────────────────

@router.post("/projects")
async def create_project(
    youtube_url: str = Form(None),
    file: UploadFile = File(None),
    title: str = Form(None),
    quality: str = Form("standard"),
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    if not youtube_url and not file:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Video havolasi yoki fayl yuklang"})

    new_project = models.Project(
        user_id=user.id,
        title=title or ("Video Project" if not file else file.filename),
        status="Processing",
        quality=quality,
        video_url=None,
        thumbnail=None
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    file_path = None
    if file:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        file_path = os.path.join(UPLOAD_DIR, f"{new_project.id}_{file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

    # Delay the task via Celery Queue asynchronously
    process_project_video_task.delay(new_project.id, url=youtube_url, file_path=file_path)

    return JSONResponse(content={
        "status": "success",
        "data": {"id": new_project.id, "title": new_project.title, "status": new_project.status}
    })


@router.get("/projects")
async def list_projects(
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    projects = db.query(models.Project).filter(models.Project.user_id == user.id).all()
    return JSONResponse(content={
        "status": "success",
        "data": [
            {
                "id": p.id,
                "title": p.title,
                "status": p.status,
                "thumbnail": p.thumbnail,
                "video_url": p.video_url,
                "final_video_url": p.final_video_url,
                "dubbed_audio_url": p.dubbed_audio_url,
                "quality": p.quality,
                "created_at": str(p.created_at),
                "error_message": p.error_message,
            }
            for p in projects
        ]
    })




@router.websocket("/ws/project/{project_id}")
async def websocket_project_status(websocket: WebSocket, project_id: int, db: Session = Depends(database.get_db)):
    await websocket.accept()
    
    # 1. Send immediate current status from DB
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if project:
        await websocket.send_json({
            "status": project.status,
            "progress": project.progress
        })
    else:
        await websocket.send_json({"error": "Project not found"})
        await websocket.close()
        return

    # 2. Subscribe to Redis for real-time updates
    REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    try:
        redis_client = redis.from_url(REDIS_URL)
        pubsub = redis_client.pubsub()
        channel_name = f"project_{project_id}_progress"
        pubsub.subscribe(channel_name)
        
        # We need to listen to Redis messages in a non-blocking way
        while True:
            # get_message() is synchronous, but we can put it in a loop with asyncio.sleep
            message = pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                data = json.loads(message["data"])
                await websocket.send_json(data)
                
                # If finished or error, we could optionally disconnect, but let's stay open
                # so the frontend can handle the closure
            
            # Prevent blocking the async event loop
            await asyncio.sleep(0.5)
            
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for project {project_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if 'pubsub' in locals():
            pubsub.unsubscribe(channel_name)
            pubsub.close()
        if 'redis_client' in locals():
            redis_client.close()


# ─── Video Processing ─────────────────────────────────────────────────────────

@router.post("/analyze-url")
async def analyze_url(url: str = Form(...)):
    try:
        data = video_service.analyze_youtube_url(url)
        return JSONResponse(content={"status": "success", "data": data})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=400)


@router.post("/process-video")
async def process_video(url: str = Form(...), original_title: str = Form(...)):
    try:
        clean_title = "".join([c for c in original_title if c.isalnum() or c in (' ', '-', '_')]).strip()
        filename = f"{clean_title}.mp4"
        video_path = video_service.download_video(url, UPLOAD_DIR, filename)
        json_filename = f"{clean_title}.json"
        json_path = os.path.join(UPLOAD_DIR, json_filename)
        segments = transcription_service.transcribe_file(video_path, json_path)
        formatted_segments = [{"start": s['start'], "end": s['end'], "text": s['text']} for s in segments]
        return JSONResponse(content={
            "status": "success",
            "data": {"audio_path": video_path, "segments": formatted_segments}
        })
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


@router.post("/upload-video")
async def upload_video(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        clean_title = os.path.splitext(file.filename)[0]
        json_path = os.path.join(UPLOAD_DIR, f"{clean_title}.json")
        segments = transcription_service.transcribe_file(file_path, json_path)
        formatted_segments = [{"start": s['start'], "end": s['end'], "text": s['text']} for s in segments]
        return JSONResponse(content={"status": "success", "data": {"segments": formatted_segments}})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


@router.post("/translate")
async def translate_text(request: TranslationRequest):
    try:
        translated = translation_service.translate_segments(request.segments, request.target_lang)
        return JSONResponse(content={"status": "success", "data": {"segments": translated}})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


# ─── Generate Audio ───────────────────────────────────────────────────────────

@router.post("/generate-audio")
async def generate_audio(
    text: str = Form(...),
    voice: str = Form("uz-UZ-MadinaNeural"),
    rate: str = Form("+0%"),
    pitch: str = Form("+0Hz")
):
    try:
        filename = f"tts_{uuid.uuid4()}.mp3"
        output_path = os.path.join(UPLOAD_DIR, filename)
        normalized_text = normalize_text(text)
        success = await tts_service.generate_speech(normalized_text, output_path, voice, rate, pitch)
        if success:
            return JSONResponse(content={"status": "success", "audio_url": f"/uploads/{filename}"})
        return JSONResponse(content={"status": "error", "message": "TTS failed"}, status_code=500)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


from backend.services import voice_cloning_service

@router.post("/clone-voice")
async def clone_voice_endpoint(
    text: str = Form(...),
    video_file: UploadFile = File(...),
    language: str = Form("en")
):
    try:
        # Save video temporarily to extract audio
        video_filename = f"temp_video_{uuid.uuid4()}{os.path.splitext(video_file.filename)[1]}"
        video_path = os.path.join(UPLOAD_DIR, video_filename)
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)
            
        # Extract speaker sample
        speaker_wav_path = os.path.join(UPLOAD_DIR, f"speaker_{uuid.uuid4()}.wav")
        voice_cloning_service.extract_speaker_sample(video_path, speaker_wav_path, duration=10)
        
        # Clone voice
        output_filename = f"cloned_{uuid.uuid4()}.wav"
        output_path = os.path.join(UPLOAD_DIR, output_filename)
        
        success = voice_cloning_service.clone_voice(text, speaker_wav_path, language, output_path)
        
        # Cleanup temp video and speaker sample
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(speaker_wav_path):
            os.remove(speaker_wav_path)
            
        if success:
            return JSONResponse(content={"status": "success", "audio_url": f"/uploads/{output_filename}"})
        return JSONResponse(content={"status": "error", "message": "Voice cloning failed"}, status_code=500)
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# ─── Project CRUD ─────────────────────────────────────────────────────────────

@router.get("/project/{project_id}")
async def get_project(
    project_id: int, 
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.user_id == user.id
    ).first()
    if not project:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Loyiha topilmadi"})

    # Extract segments logic
    raw_segments = []
    if project.transcript:
        if isinstance(project.transcript, dict) and 'segments' in project.transcript:
            raw_segments = project.transcript['segments']
        elif isinstance(project.transcript, list):
            raw_segments = project.transcript
    elif project.translated_transcript:
        raw_segments = project.translated_transcript

    # Format segments for frontend
    segments = []
    for s in raw_segments:
        segments.append({
            "start": s.get('start', 0),
            "end": s.get('end', 0),
            "text": s.get('text', ''),
            "translated": s.get('translated_text') or s.get('translated') or ''
        })

    return JSONResponse(content={
        "status": "success",
        "data": {
            "id": project.id,
            "project_id": project.id, # legacy support
            "title": project.title,
            "status": project.status,
            "progress": project.progress,
            "thumbnail": project.thumbnail,
            "video_url": project.video_url,
            "final_video_url": project.final_video_url,
            "dubbed_audio_url": project.dubbed_audio_url,
            "quality": project.quality,
            "created_at": str(project.created_at),
            "segments": segments,
            "error_message": project.error_message
        }
    })


@router.put("/project/{project_id}")
async def update_project(project_id: int, request: ProjectUpdateRequest, db: Session = Depends(database.get_db)):
    try:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Loyiha topilmadi"})
        
        # Save to database
        project.transcript = {"segments": [s.dict() for s in request.segments]}
        db.commit()
        
        return JSONResponse(content={"status": "success", "message": "Project yangilandi"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


@router.delete("/project/{project_id}")
async def delete_project(project_id: int, db: Session = Depends(database.get_db)):
    try:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Loyiha topilmadi"})
        
        db.delete(project)
        db.commit()
        return JSONResponse(content={"status": "success", "message": "Project o'chirildi"})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


# ─── Meeting Notes ────────────────────────────────────────────────────────────

@router.post("/project/{project_id}/notes")
async def generate_notes(project_id: int):
    try:
        json_path = os.path.join(UPLOAD_DIR, f"{project_id}.json")
        if not os.path.exists(json_path):
            return JSONResponse(content={"status": "error", "message": "Transcript topilmadi"}, status_code=404)
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            segments = data.get('segments', []) if isinstance(data, dict) else data
        full_text = " ".join([s.get('text', '') for s in segments])
        if not full_text.strip():
            return JSONResponse(content={"status": "error", "message": "Transcript bo'sh"}, status_code=400)
        notes = notes_service.generate_meeting_notes(full_text, language="uz")
        if notes.get('error'):
            return JSONResponse(content={"status": "error", "message": notes['message']}, status_code=400)
        notes_path = os.path.join(UPLOAD_DIR, f"notes_{project_id}.json")
        with open(notes_path, "w", encoding='utf-8') as f:
            json.dump(notes, f, ensure_ascii=False, indent=4)
        return JSONResponse(content={"status": "success", "data": notes})
    except Exception as e:
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)


@router.get("/project/{project_id}/notes")
async def get_notes(project_id: int):
    notes_path = os.path.join(UPLOAD_DIR, f"notes_{project_id}.json")
    if os.path.exists(notes_path):
        with open(notes_path, "r", encoding='utf-8') as f:
            notes = json.load(f)
        return JSONResponse(content={"status": "success", "data": notes})
    return JSONResponse(content={"status": "success", "data": None})


# ─── WebSocket Export ─────────────────────────────────────────────────────────

@router.websocket("/ws/export/{project_id}")
async def export_websocket(websocket: WebSocket, project_id: int):
    await websocket.accept()
    try:
        video_filename = None
        for ext in ['.mp4', '.mov', '.avi', '.webm']:
            if os.path.exists(os.path.join(UPLOAD_DIR, str(project_id) + ext)):
                video_filename = str(project_id) + ext
                break
        if not video_filename:
            await websocket.send_json({"status": "error", "message": "Video topilmadi"})
            await websocket.close()
            return
        
        video_path = os.path.join(UPLOAD_DIR, str(video_filename))
        json_path = os.path.join(UPLOAD_DIR, f"{project_id}.json")
        if not os.path.exists(json_path):
            await websocket.send_json({"status": "error", "message": "Transcript topilmadi"})
            await websocket.close()
            return
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            segments = data.get('segments', []) if isinstance(data, dict) else data

        async def send_progress(percent):
            await websocket.send_json({"status": "progress", "percent": percent})

        result = await dubbing_service.generate_dubbed_video(
            project_id, segments, video_path, UPLOAD_DIR, progress_callback=send_progress
        )
        await websocket.send_json({"status": "complete", "data": result})
        await websocket.close()
    except Exception as e:
        traceback.print_exc()
        await websocket.send_json({"status": "error", "message": str(e)})
        try:
            await websocket.close()
        except:
            pass
