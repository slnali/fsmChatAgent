from fastapi import Request

from fsm_ai.services import Services


def get_services(request: Request) -> Services:
    return request.app.state.services
