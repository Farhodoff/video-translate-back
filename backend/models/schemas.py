from pydantic import BaseModel
from typing import List, Optional

class TranslationRequest(BaseModel):
    segments: list
    target_lang: str = "uz"

class VideoMetadata(BaseModel):
    video_title: str
    duration: str
    thumbnail: str
    original_url: str

class Segment(BaseModel):
    start: float
    end: float
    text: str
    original: Optional[str] = None
    translated: Optional[str] = None

class ProjectUpdateRequest(BaseModel):
    segments: List[Segment]
