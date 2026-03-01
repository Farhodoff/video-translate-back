# Video Translate — Backend API

FastAPI asosida qurilgan AI dublyaj platformasining backend REST API si.

## 🛠 Texnologiyalar

- **FastAPI** — REST API framework
- **SQLAlchemy** — ORM (SQLite)
- **OpenAI Whisper** — Transkripsiya
- **deep-translator** — Google Translate
- **Edge TTS** — O'zbek tili TTS
- **JWT (Bearer Token)** — Autentifikatsiya

## 🚀 Ishga tushirish

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export PYTHONPATH=$PYTHONPATH:$(pwd)
python3 backend/main.py
```

API docs: **http://127.0.0.1:8000/docs**

## 🌐 CORS

Frontend URL larini `backend/main.py` dagi `origins` ga yoki `.env` dagi `FRONTEND_URL` ga qo'shing.

## 🔐 Autentifikatsiya

Bearer Token (JWT):
```
Authorization: Bearer <token>
```

## 📋 Asosiy Endpointlar

| Method | URL | Tavsif |
|--------|-----|--------|
| POST | `/api/login` | Kirish — token qaytaradi |
| POST | `/api/register` | Ro'yxatdan o'tish |
| GET | `/api/me` | Joriy foydalanuvchi |
| GET | `/api/projects` | Barcha loyihalar |
| POST | `/api/projects` | Yangi loyiha yaratish |
| POST | `/api/analyze-url` | YouTube URL tahlil |
| POST | `/api/process-video` | Video yuklab transkripsiya |
| POST | `/api/upload-video` | Fayl yuklash |
| POST | `/api/translate` | Tarjima |
| POST | `/api/generate-audio` | TTS audio |
| GET | `/api/health` | Server holati |

## 🐳 Docker

```bash
docker build -t video-translate-back .
docker run -p 8000:8000 video-translate-back
```

## 👤 Muallif

[Farhodoff](https://github.com/Farhodoff)
