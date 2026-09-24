from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from thoa_screening.api.routes import router
from thoa_screening.api.schemas import ErrorResponse

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="THOA Screening API",
    description="API for the AI-assisted compliance screening system for India's THOA.",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Custom exception handler for Pydantic validation errors.
    Returns exactly which fields failed in a structured 400 Bad Request.
    """
    details = []
    for error in exc.errors():
        # format the loc tuple into a string path
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        details.append({
            "field": field,
            "message": error.get("msg", ""),
            "type": error.get("type", "")
        })
        
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "Validation failed.",
            "details": details
        }
    )

app.include_router(router)
