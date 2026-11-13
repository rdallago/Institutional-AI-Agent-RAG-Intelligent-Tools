from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from app.application.auth.service import Principal
from app.application.ia.exceptions import IANoDisponible
from app.presentation.http.auth.dependencies import get_current_user
from app.presentation.http.ia.respuestas import RespuestaSolicitud, Respuesta

router = APIRouter(prefix='/api/v1/ia/conversaciones', tags=['IA'])


class Turn(RespuestaSolicitud):
    solicitud_id: UUID


class NewConversation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    conversacion_id: UUID | None = None


def service(request):
    result = getattr(request.app.state,'conversations',None)
    if result is None: raise IANoDisponible()
    return result


@router.post('')
async def create(body:NewConversation,request:Request, principal:Annotated[Principal,Depends(get_current_user)]):
    return await service(request).create(principal,body.conversacion_id)


@router.get('')
async def conversations(request:Request, principal:Annotated[Principal,Depends(get_current_user)]):
    return await service(request).list(principal)


@router.get('/{conversation}/mensajes')
async def messages(conversation:UUID,request:Request,principal:Annotated[Principal,Depends(get_current_user)]):
    rows=await service(request).history(principal,conversation)
    return [{'id':r['id'],'rol':r['role'],'contenido':r['content'],'estrategia':r['strategy'],
             'estado':r['status'],'herramienta':r['tool'],'creado_at':r['creado_at'],
             'fuentes':[{'id':f['id'],'pagina':f['pagina']} for f in r['references']]} for r in rows]


@router.post('/{conversation}/mensajes')
async def turn(conversation:UUID, body:Turn,request:Request,principal:Annotated[Principal,Depends(get_current_user)]):
    result=await service(request).turn(principal,conversation,body.solicitud_id,
        body.prompt.get_secret_value(),body.modo,body.documento_id)
    Respuesta.model_validate(result['resultado'])
    return result
