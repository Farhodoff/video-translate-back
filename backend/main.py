from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend import database
from backend.models import models
from backend.routers import api
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Video Translate API", version="1.0.0")

# CORS — frontend domenlarini ruxsat berish
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:3000",
    "https://video-translate-front.vercel.app",
    os.getenv("FRONTEND_URL", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in origins if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create Tables
models.Base.metadata.create_all(bind=database.engine)

# Uploads static files (video/audio fayllar uchun)
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include Router
app.include_router(api.router)


@app.get("/")
async def root():
    return {"message": "Video Translate API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", 8000))
    print(f"Server ishga tushmoqda: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
