from .health import router as health_router
from .subjects import router as subjects_router
from .documents import router as documents_router
from .upload import router as upload_router
from .pages import router as pages_router
from .chat import router as chat_router
from .notes import router as notes_router
from .quizzes import router as quizzes_router
from .planner import router as planner_router
from .profile import router as profile_router

__all__ = ["health_router", "subjects_router", "documents_router", "upload_router", "pages_router", "chat_router", "notes_router", "quizzes_router", "planner_router", "profile_router"]
