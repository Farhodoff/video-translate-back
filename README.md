# 🎙️ AI Dub Studio — Backend

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Redis](https://img.shields.io/badge/redis-%23DD0031.svg?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Celery](https://img.shields.io/badge/celery-%23a9cc33.svg?style=for-the-badge&logo=celery&logoColor=ddf4a4)](https://docs.celeryq.dev/)

FastAPI va sun'iy intellekt modellari asosida qurilgan avtomatlashtirilgan video dublyaj platformasining backend tizimi.

---

## ✨ Asosiy Imkoniyatlar

- **🎧 Aniq Transkripsiya**: `WhisperX` yordamida nutqni matnga vaqt belgi (timestamps) bilan aylantirish.
- **🗣️ Voice Cloning**: `XTTS v2` yordamida kishi ovozini yuqori aniqlikda klonlash.
- **👄 Lip-Sync**: `Wav2Lip` algoritmi orqali videodagi lab harakatlarini yangi audyoga sinxronlash.
- **🎵 Fon Musiqasini Saqlash**: `Demucs` yordamida original musiqani inson nutqidan ajratib olish va qayta birlashtirish.
- **🚀 Scalable Task Queue**: `Celery` + `Redis` yordamida og'ir vazifalarni samarali taqsimlash.
- **📡 WebSocket Progress**: Videoga ishlov berish bosqichlarini real-vaqtda foydalanuvchiga uzatish.

---

## 🛠 Texnologik Stack

- **Asos**: [FastAPI](https://fastapi.tiangolo.com/) + [SQLAlchemy](https://www.sqlalchemy.org/)
- **AI Modellar**: 
  - `WhisperX` (Speech-to-Text)
  - `Coqui XTTS v2` (Voice Cloning)
  - `Wav2Lip` (Visual Sync)
- **Navbat tizimi**: [Celery](https://docs.celeryq.dev/) & [Redis](https://redis.io/)
- **Media**: `FFmpeg`, `Pydub`, `OpenCV`

---

## 🚀 Ishga tushirish (Local)

### 1. Vertual muhitni sozlash
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Redis-ni yoqing
```bash
brew install redis # Mac uchun
brew services start redis
```

### 3. Celery Worker (AI JARAYONLAR UCHUN)
```bash
export PYTHONPATH=$(pwd)
celery -A backend.celery_app worker --loglevel=info
```

### 4. FastAPI Server
```bash
uvicorn backend.main:app --reload --port 8000
```

---

## 📋 API Rejasi

| Method | URL | Vazifasi |
|--------|-----|----------|
| `POST` | `/api/projects` | Loyiha yaratish (YouTube URL yoki Fayl) |
| `GET` | `/api/project/{id}` | Loyiha tafsilotlari va segmentlar |
| `WS` | `/api/ws/project/{id}` | Real-vaqt progressi (WebSocket) |
| `POST` | `/api/analyze-url` | YouTube linkidan ma'lumot olish |

---

## 👤 Muallif

**[Farhodoff](https://github.com/Farhodoff)**

---

## 📜 Litsenziya

MIT License.
