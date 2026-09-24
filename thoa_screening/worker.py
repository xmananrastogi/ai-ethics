import os
from celery import Celery

from thoa_screening.database import get_session
from thoa_screening.services.screening import screen_case
from thoa_screening.database.models import Case, CaseStatus

# Configuration for Celery
redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "thoa_screening",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="run_screening_task")
def run_screening_task(self, case_id: str):
    """
    Async Celery task to run the screening pipeline.
    This offloads heavy OCR and regex processing from the API server.
    """
    import uuid
    case_uuid = uuid.UUID(case_id)
    
    # get_session provides a context manager that commits on success
    # and rolls back on exception
    try:
        # We need a plain generator if it's a contextmanager-like function
        # Wait, get_session yields a session. Let's do next(get_session())
        session_gen = get_session()
        db_session = next(session_gen)
        
        # The screen_case function manages the DB transactions internally
        screen_case(case_uuid, db_session)
        
        # Close out the generator
        try:
            next(session_gen)
        except StopIteration:
            pass
            
        return {"status": "SUCCESS", "case_id": case_id}
    except Exception as e:
        session_gen = get_session()
        db_session = next(session_gen)
        # If screening catastrophically fails, we mark the case as REJECTED
        # or some error status so the frontend doesn't hang in UNDER_REVIEW forever.
        case = db_session.query(Case).filter(Case.id == case_uuid).first()
        if case:
            case.status = CaseStatus.REJECTED
            db_session.commit()
            
        # Re-raise to let Celery know it failed
        raise self.retry(exc=e, countdown=60, max_retries=3)
