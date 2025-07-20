from .auth import router as auth_router
from .customer import router as customer_router
from .shop import router as shop_router
from .recommend import router as recommend_router
from .mylist import router as mylist_router
from .completed import router as completed_router
from .manager import router as manager_router
from .websocket import router as websocket_router

__all__ = [
    "auth_router", "customer_router", "shop_router", 
    "recommend_router", "mylist_router", "completed_router", 
    "manager_router", "websocket_router"
] 