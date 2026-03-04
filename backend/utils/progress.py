import json
import redis
import os
from backend.database import SessionLocal
from backend.models.models import Project

# Configure synchronous redis client
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL)

def publish_progress(project_id: int, status: str, progress: int = None):
    """
    Updates the project status and progress in the DB, 
    and publishes the event to Redis for WebSockets to pickup.
    """
    # 1. Update Database
    db = SessionLocal()
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            if status:
                project.status = status
            if progress is not None:
                # Ensure it stays within 0-100 bounds
                project.progress = max(0, min(100, progress))
            db.commit()
            
            # Use updated values from DB in case only one was passed
            final_status = project.status
            final_progress = project.progress
        else:
            final_status = status
            final_progress = progress or 0
    finally:
        db.close()
        
    # 2. Publish to Redis channel `project_{id}_progress`
    channel_name = f"project_{project_id}_progress"
    message = json.dumps({
        "status": final_status,
        "progress": final_progress
    })
    
    try:
        redis_client.publish(channel_name, message)
    except Exception as e:
        print(f"Failed to publish progress to Redis: {e}")
