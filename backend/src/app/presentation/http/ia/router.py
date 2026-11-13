from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.auth.service import Principal
from app.application.ia.dto import ConsultaDatos
from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta
from app.presentation.http.auth.dependencies import get_current_user
from app.presentation.http.errors import documented_errors
from app.presentation.http.ia.dependencies import get_ia_service
from app.presentation.http.ia.schemas import ConsultaSolicitud, ConsultaRespuesta


router = APIRouter(prefix='/api/v1/ia', tags=['IA'])
ia_errors = documented_errors(401,403,413,422,429,502,503,504,500)
ia_errors[429]['content']['application/json'] = {'examples': {
    'cuota': {'value': {'error': {'codigo': 'IA_LIMITE_INTENTOS', 'mensaje': 'Limite temporal de consultas IA.'}}},
    'ocupacion': {'value': {'error': {'codigo': 'IA_OCUPADA', 'mensaje': 'El servicio IA esta ocupado temporalmente.'}}},
}}


@router.post('/consultas', response_model=ConsultaRespuesta, operation_id='consultar_ia',
    summary='Generar una respuesta informativa',
    description='Solo sesiones normales. Cuerpo JSON de hasta 16 KiB; prompt acotado. IA deshabilitada por defecto.',
    responses=ia_errors)
async def consultar(body: ConsultaSolicitud,
    principal: Annotated[Principal, Depends(get_current_user)],
    service: Annotated[GenerarRespuesta, Depends(get_ia_service)]) -> ConsultaRespuesta:
    result = await service.ejecutar(principal, ConsultaDatos(prompt=body.prompt.get_secret_value()))
    return ConsultaRespuesta(respuesta=result.respuesta, finalizacion=result.finalizacion)
