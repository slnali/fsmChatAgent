from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fsm_ai.api import chats, rules
from fsm_ai.config import get_settings
from fsm_ai.services import Services, build_services


def create_app(services: Services | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="fsm.ai")
    app.state.services = services or build_services(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(chats.router)
    app.include_router(rules.router)
    return app
