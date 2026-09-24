from typing import Generator
from sqlalchemy.orm import Session
from thoa_screening.database import get_session_factory, get_engine

# Initialize a global session factory bound to the engine
engine = get_engine()
SessionFactory = get_session_factory(engine)

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy session.
    Automatically closes the session after the request is finished.
    """
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()
