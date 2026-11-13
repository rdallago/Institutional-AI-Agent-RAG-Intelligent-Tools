from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator, StrictStr

from app.application.auth.service import Principal
from app.application.ia.exceptions import IANoDisponible
from app.presentation.http.auth.dependencies import get_current_user
from app.presentation.http.ia.schemas import ConsultaSolicitud
from app.presentation.http.ia.router import ia_errors


router=APIRouter(prefix='/api/v1/ia',tags=['IA'])


class RespuestaSolicitud(ConsultaSolicitud):
    modo: Literal['LLM_DIRECTO','RAG','AUTO'] = 'AUTO'
    documento_id: UUID | None = None

    @model_validator(mode='after')
    def mode_document(self):
        if ((self.modo == 'RAG' and self.documento_id is None)
                or (self.modo == 'LLM_DIRECTO' and self.documento_id is not None)):
            raise ValueError('Seleccion de documento invalida.')
        return self


class Referencia(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id: StrictStr
    pagina: int = Field(ge=1)


class Respuesta(BaseModel):
    model_config=ConfigDict(extra='forbid')
    respuesta: StrictStr=Field(repr=False)
    finalizacion: Literal['completa','limite'] | None
    estado: Literal['GENERADA','FUNDAMENTADA','SIN_EVIDENCIA','HERRAMIENTA','ACLARACION']
    estrategia: Literal['LLM_DIRECTO','RAG','TOOL']
    fuentes: list[Referencia]


class PublicacionSolicitud(BaseModel):
    model_config=ConfigDict(extra='forbid')
    version_id: UUID


async def change_publication(request,principal,document,version,publish):
    store=getattr(request.app.state,'rag_documents',None)
    if store is None or not hasattr(store,'set_institutional_publication'):
        raise IANoDisponible()
    await store.set_institutional_publication(principal,document,version,publish=publish)
    return {'documento_id':str(document),'version_id':str(version),
            'publicacion':'PUBLICADA' if publish else 'REVOCADA'}


@router.post('/documentos/{document}/publicacion',responses=ia_errors)
async def publicar(document:UUID,body:PublicacionSolicitud,request:Request,
                   principal:Annotated[Principal,Depends(get_current_user)]):
    return await change_publication(request,principal,document,body.version_id,True)


@router.delete('/documentos/{document}/publicacion',responses=ia_errors)
async def revocar_publicacion(document:UUID,body:PublicacionSolicitud,request:Request,
                             principal:Annotated[Principal,Depends(get_current_user)]):
    return await change_publication(request,principal,document,body.version_id,False)


@router.get('/documentos')
async def documentos(request:Request,principal:Annotated[Principal,Depends(get_current_user)]):
    store=getattr(request.app.state,'rag_documents',None)
    if store is None:raise IANoDisponible()
    return await store.list_documents(principal)


@router.post('/respuestas',response_model=Respuesta,responses=ia_errors)
async def responder(body:RespuestaSolicitud,request:Request,
                    principal:Annotated[Principal,Depends(get_current_user)]):
    question=body.prompt.get_secret_value()
    service=getattr(request.app.state,'ia_agent',None)
    if service is None:raise IANoDisponible()
    result=await service.execute(principal,question,mode=body.modo,document_id=body.documento_id)
    return Respuesta(respuesta=result.answer,finalizacion=result.finalization,estado=result.status,
        estrategia=result.strategy,fuentes=[Referencia(id=e.citation,pagina=e.chunk.page) for e in result.citations])
