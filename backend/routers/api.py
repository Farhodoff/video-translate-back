from fastapi import APIRouter, Form, UploadFile, File, WebSocket, WebSocketDisconnect, Depends, BackgroundTasks
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
from backend.services import video_service, transcription_service, translation_service, tts_service, dubbing_service, notes_service
from backend.utils.text_normalizer import normalize_text
from backend.models.schemas import TranslationRequest, ProjectUpdateRequest

router = APIRouter(prefix="/api")
UPLOAD_DIR = "uploads"


# ─── Background task ─────────────────────────────────────────────────────────

async def process_project_video(project_id: int, db: Session, url: Optional[str] = None, file_path: Optional[str] = None):
    try:
        project = db.query(models.Project).filter(models.Project.id == project_id).first()
        if not project:
            return

        output_path = file_path
        if url:
            info = video_service.analyze_youtube_url(url)
            project.thumbnail = info.get("thumbnail")
            project.title = info.get("video_title") if not project.title else project.title
            db.commit()

            filename = f"{project_id}_{int(time.time())}.mp4"
            output_path = video_service.download_video(url, UPLOAD_DIR, filename)

        if not output_path:
            return

        transcript = transcription_service.transcribe_video(str(output_path), quality=project.quality)
        project.transcript = transcript

        project.status = "Translating"
        db.commit()

        translated_segments = translation_service.translate_segments(transcript, target_lang='uz')
        project.translated_transcript = translated_segments

        project.status = "Dubbing"
        db.commit()

        output_dir = os.path.dirname(str(output_path))
        audio_path = await dubbing_service.create_dubbing(project_id, translated_segments, output_dir)
        project.dubbed_audio_url = f"/uploads/{os.path.basename(audio_path)}"

        final_video_filename = f"final_{project_id}.mp4"
        final_video_path = os.path.join(output_dir, final_video_filename)
        dubbing_service.merge_video_audio(str(output_path), audio_path, final_video_path)
        project.final_video_url = f"/uploads/{final_video_filename}"

        project.status = "Ready"
        db.commit()
    except Exception as e:
        print(f"Error processing project {project_id}: {e}")
        project.status = "Error"
        project.error_message = str(e)
        db.commit()


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
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(process_project_video, new_project.id, db, url=youtube_url, file_path=file_path)

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


# ─── Project CRUD ─────────────────────────────────────────────────────────────

@router.get("/project/{project_id}")
async def get_project(project_id: int, db: Session = Depends(database.get_db)):
    project = db.query(models.Project).filter(models.Project.id == project_id).first()
    if not project:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Loyiha topilmadi"})

    segments = []
    if project.transcript:
        raw = project.transcript.get('segments', []) if isinstance(project.transcript, dict) else project.transcript
    elif project.translated_transcript:
        raw = project.translated_transcript
    else:
        raw = []

    segments = [{"start": s['start'], "end": s['end'], "text": s['text'], "translated": s.get('translated_text') or s.get('translated')} for s in raw]

    return JSONResponse(content={
        "status": "success",
        "data": {
            "project_id": project.id,
            "video_url": project.video_url,
            "segments": segments,
            "status": project.status,
            "title": project.title
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
