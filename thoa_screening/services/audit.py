import inspect
import functools
import traceback
import uuid
from typing import Callable, Any, Optional

from sqlalchemy.orm import Session
from fastapi import Request

from thoa_screening.database.models import AuditLog, AuditAction

def audit_log(action_name: AuditAction) -> Callable:
    """
    Decorator to wrap key functions and log them in the immutable AuditLog.
    It inspects the wrapped function's signature to dynamically extract:
    - case_id: If the function takes a case_id (UUID).
    - db: The SQLAlchemy Session.
    - request: The FastAPI Request object to extract IP address.
    
    If the function throws an exception, the failure is logged in the details JSON.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return _execute_and_log(func, action_name, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            return await _execute_async_and_log(func, action_name, *args, **kwargs)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator

def _extract_context(func: Callable, *args: Any, **kwargs: Any) -> tuple[Optional[Session], Optional[uuid.UUID], str, Optional[uuid.UUID]]:
    """Extracts db, case_id, ip_address, and user_id from arguments."""
    sig = inspect.signature(func)
    bound_args = sig.bind(*args, **kwargs)
    bound_args.apply_defaults()
    
    db: Optional[Session] = None
    case_id: Optional[uuid.UUID] = None
    ip_address: str = "unknown"
    user_id: Optional[uuid.UUID] = None

    for name, value in bound_args.arguments.items():
        if isinstance(value, Session):
            db = value
        elif name == "case_id" and isinstance(value, uuid.UUID):
            case_id = value
        elif name == "request" and isinstance(value, Request):
            if getattr(value, "client", None) and hasattr(value.client, "host"):
                ip_address = value.client.host
        # user_id extraction depends on how auth is handled, using a dummy system user for now.
        # Real system would extract from Depends(get_current_user)
        
    return db, case_id, ip_address, user_id

from thoa_screening.database.models import User, UserRole

def _create_log(
    db: Session, 
    action_name: AuditAction, 
    case_id: Optional[uuid.UUID], 
    ip_address: str, 
    user_id: Optional[uuid.UUID], 
    details: dict
):
    if not db:
        return # Can't log without DB
        
    # We use a dummy fallback user UUID if none provided, since it's nullable=False in schema
    # In a real system, user_id comes from auth context.
    dummy_uuid = uuid.UUID("00000000-0000-0000-0000-000000000000")
    if not user_id:
        user_id = dummy_uuid
        # Ensure dummy user exists to satisfy FK constraint
        if not db.query(User).filter_by(id=dummy_uuid).first():
            dummy_user = User(
                id=dummy_uuid, 
                email="system@thoa.local", 
                full_name="System", 
                role=UserRole.ADMIN, 
                password_hash="none"
            )
            db.add(dummy_user)
            db.commit()
    
    log_entry = AuditLog(
        case_id=case_id,
        user_id=user_id,
        action=action_name,
        detail=details,
        ip_address=ip_address,
        user_agent="System Automated" # Simplified
    )
    db.add(log_entry)
    db.commit()

def _execute_and_log(func: Callable, action_name: AuditAction, *args: Any, **kwargs: Any) -> Any:
    db, case_id, ip, user_id = _extract_context(func, *args, **kwargs)
    
    try:
        result = func(*args, **kwargs)
        if db:
            _create_log(db, action_name, case_id, ip, user_id, {"status": "SUCCESS"})
        return result
    except Exception as e:
        if db:
            _create_log(db, action_name, case_id, ip, user_id, {
                "status": "FAILED", 
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        raise e

async def _execute_async_and_log(func: Callable, action_name: AuditAction, *args: Any, **kwargs: Any) -> Any:
    db, case_id, ip, user_id = _extract_context(func, *args, **kwargs)
    
    try:
        result = await func(*args, **kwargs)
        if db:
            _create_log(db, action_name, case_id, ip, user_id, {"status": "SUCCESS"})
        return result
    except Exception as e:
        if db:
            _create_log(db, action_name, case_id, ip, user_id, {
                "status": "FAILED", 
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        raise e
