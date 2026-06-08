from .knowledge_base import router as kb_router
from .documents import router as doc_router
from .chat import router as chat_router
from .admin import router as admin_router
from .knowledge_graph import router as graph_router

__all__ = ["kb_router", "doc_router", "chat_router", "admin_router", "graph_router"]
