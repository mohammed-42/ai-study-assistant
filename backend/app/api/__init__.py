from .health import router as health_router
from .subjects import router as subjects_router
from .documents import router as documents_router
from .upload import router as upload_router
from .pages import router as pages_router

__all__ = ["health_router", "subjects_router", "documents_router", "upload_router", "pages_router"]
