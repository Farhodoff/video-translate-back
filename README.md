# 🎙️ Video Translate — AI Dubbing Backend

FastAPI va Ilg'or AI modellari (WhisperX, XTTS v2, Wav2Lip) asosida qurilgan avtomatlashtirilgan video dublyaj platformasining backend tizimi.

---

## ✨ Imkoniyatlar

- **🎧 Precise Transcription**: `WhisperX` yordamida so'zlarni vaqtiga (alignment) aniq tushirish.
- **🗣️ Voice Cloning**: `Coqui XTTS v2` yordamida foydalanuvchi ovozini 10 soniyalik namunadan klonlash.
- **👄 Lip-Sync**: `Wav2Lip` algoritmi orqali videodagi lab harakatlarini yangi audyoga moslashtirish.
- **🎵 Audio Mixing**: `Demucs` yordamida fon musiqasini ovozdan ajratib olish va qayta birlashtirish.
- **🚀 Scalable Architecture**: `Celery` + `Redis` orqali og'ir AI vazifalarni fon rejimida navbat bilan qayta ishlash.
- **📡 Real-time Progress**: `WebSockets` yordamida foydalanuvchiga videoni qayta ishlash foizini jonli ko'rsatish.

---

## 🛠 Texnologiyalar

- **Core**: FastAPI, SQLAlchemy (SQLite/PostgreSQL)
- **AI Models**: 
  - `WhisperX` (Speech-to-Text)
  - `Coqui TTS / XTTS v2` (Voice Cloning)
  - `Wav2Lip` (Lip-Syncing)
  - `Demucs` (Vocal/Music Separation)
- **Queue**: Celery, Redis
- **Media**: FFmpeg, Pydub, OpenCV

---

## 🚀 Ishga tushirish (Local)

### 1. Muhitni sozlash
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Redis-ni ishga tushiring
```bash
brew install redis # Mac uchun
redis-server
```

### 3. Celery Worker (AI JARAYONLARI UCHUN)
```bash
export PYTHONPATH=$(pwd)
celery -A backend.celery_app worker --loglevel=info
```

### 4. FastAPI Server
```bash
uvicorn backend.main:app --reload --port 8000
```

API docs: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 📋 API Xaritasi

| Method | URL | Tavsif |
|--------|-----|--------|
| `POST` | `/api/projects` | Video yuklash (URL/Fayl) va ishlovni boshlash |
| `GET` | `/api/project/{id}` | Loyiha ma'lumotlari va segmentlarni olish |
| `WS` | `/api/ws/project/{id}` | Jonli progress (WebSocket) |
| `POST` | `/api/clone-voice` | Ovozni namunadan klonlash |
| `POST` | `/api/analyze-url` | YouTube URL ma'lumotlarini olish |

---

## 👤 Muallif

[Farhodoff](https://github.com/Farhodoff)
