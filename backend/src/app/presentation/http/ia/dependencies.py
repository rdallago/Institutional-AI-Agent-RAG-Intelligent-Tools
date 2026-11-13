from fastapi import Request

from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta


def get_ia_service(request: Request) -> GenerarRespuesta:
    return request.app.state.ia_service
