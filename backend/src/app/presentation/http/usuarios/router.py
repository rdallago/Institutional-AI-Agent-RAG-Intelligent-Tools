from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query, Request, Response

from app.application.usuarios.dto import EstadoUsuarios, ListarUsuariosDatos
from app.presentation.http import dependencies as deps
from app.presentation.http.errors import documented_errors
from app.presentation.http.usuarios.mappers import crear_datos, modificar_datos, usuario_respuesta
from app.presentation.http.usuarios.schemas import (
    CrearUsuarioSolicitud, ModificarUsuarioSolicitud, OperacionEstadoSolicitud, UsuarioRespuesta,
    CredencialInicialSolicitud,
)


router = APIRouter(prefix="/api/v1/usuarios", tags=["Usuarios"])

create_errors = documented_errors(401, 403, 409, 422, 500)
create_errors[409]["content"]["application/json"] = {"examples": {
    "activo": {"value": {"error": {"codigo": "USUARIO_ACTIVO_EXISTENTE", "mensaje": "Ya existe un usuario activo con ese email."}}},
    "inactivo": {"value": {"error": {"codigo": "USUARIO_INACTIVO_REACTIVABLE", "mensaje": "El usuario está dado de baja y puede reactivarse explícitamente.", "usuario_id": "550e8400-e29b-41d4-a716-446655440000"}}},
}}


@router.post("", status_code=201, response_model=UsuarioRespuesta, operation_id="crear_usuario",
    summary="Crear usuario", description="Perfil y credencial inicial atómicos, password_inicial obligatoria y cambio posterior requerido. Aprovisionamiento operativo deshabilitado. Un email inactivo produce conflicto; nunca reactiva automáticamente.",
    responses={**create_errors, 201: {"headers": {"Location": {"description": "URL del usuario creado", "schema": {"type": "string"}}}}})
def crear_usuario(body: CrearUsuarioSolicitud, request: Request, response: Response,
    case: Annotated[deps.AuthorizedCase, Depends(deps.get_crear_usuario)]) -> UsuarioRespuesta:
    result = case.ejecutar(crear_datos(body), body.password_inicial.get_secret_value())
    response.headers["Location"] = str(request.url_for("obtener_usuario", id=str(result.id)))
    return usuario_respuesta(result)


@router.post("/{id}/credencial-inicial", status_code=204, response_class=Response,
    response_model=None, operation_id="asignar_credencial_inicial",
    description="Solo ADMIN normal; perfil activo sin credencial. No reemplaza ni restablece contraseñas. Aprovisionamiento operativo deshabilitado.",
    responses=documented_errors(401, 403, 404, 409, 422, 500))
def asignar_credencial_inicial(id: UUID, body: CredencialInicialSolicitud,
    principal: deps.Current, service: deps.Service) -> Response:
    service.assign_initial_admin(principal, id, body.password_inicial.get_secret_value())
    return Response(status_code=204)


@router.get("", response_model=list[UsuarioRespuesta], operation_id="listar_usuarios",
    summary="Listar usuarios", description="Filtra antes de paginar. Orden ascendente por fecha de creación y UUID. No incluye un total.",
    responses=documented_errors(401, 403, 422, 500))
def listar_usuarios(case: Annotated[deps.AuthorizedCase, Depends(deps.get_listar_usuarios)],
    estado: Annotated[EstadoUsuarios, Query(description="activos (predeterminado), inactivos o todos")] = EstadoUsuarios.ACTIVOS,
    limite: Annotated[int, Query(description="Entre 1 y 100; validado por Application", json_schema_extra={"minimum": 1, "maximum": 100})] = 20,
    desplazamiento: Annotated[int, Query(description="Entero no negativo", json_schema_extra={"minimum": 0})] = 0,
) -> list[UsuarioRespuesta]:
    results = case.ejecutar(ListarUsuariosDatos(estado=estado, limite=limite, desplazamiento=desplazamiento))
    return [usuario_respuesta(result) for result in results]


@router.get("/{id}", response_model=UsuarioRespuesta, name="obtener_usuario", operation_id="obtener_usuario",
    summary="Obtener usuario", description="Consulta por UUID, tanto para usuarios activos como inactivos.",
    responses=documented_errors(401, 403, 404, 422, 500))
def obtener_usuario(id: UUID, case: Annotated[deps.AuthorizedCase, Depends(deps.get_obtener_usuario)]) -> UsuarioRespuesta:
    return usuario_respuesta(case.ejecutar(id))


@router.put("/{id}", response_model=UsuarioRespuesta, operation_id="modificar_usuario",
    summary="Modificar datos del usuario", description="Reemplaza nombre, apellido y email. Conserva identidad, fecha, rol y estado. Admite usuarios inactivos.",
    responses=documented_errors(401, 403, 404, 409, 422, 500))
def modificar_usuario(id: UUID, body: ModificarUsuarioSolicitud,
    case: Annotated[deps.AuthorizedCase, Depends(deps.get_modificar_usuario)]) -> UsuarioRespuesta:
    return usuario_respuesta(case.ejecutar(id, modificar_datos(body)))


@router.delete("/{id}", status_code=204, response_class=Response, response_model=None, operation_id="dar_de_baja_usuario",
    summary="Dar de baja lógica", description="Solo cambia activo a false. Repetir la baja devuelve 204 sin cuerpo. No elimina físicamente.",
    responses=documented_errors(401, 403, 404, 422, 500))
def dar_de_baja_usuario(id: UUID, case: Annotated[deps.AuthorizedCase, Depends(deps.get_dar_de_baja_usuario)],
    body: Annotated[OperacionEstadoSolicitud | None, Body(description="Sin cuerpo o un objeto vacío; no admite campos.")] = None,
) -> Response:
    case.ejecutar(id)
    return Response(status_code=204)


@router.patch("/{id}/reactivar", response_model=UsuarioRespuesta, operation_id="reactivar_usuario",
    summary="Reactivar usuario", description="Reactivación explícita e idempotente. Conserva UUID, fecha y demás atributos.",
    responses=documented_errors(401, 403, 404, 422, 500))
def reactivar_usuario(id: UUID, case: Annotated[deps.AuthorizedCase, Depends(deps.get_reactivar_usuario)],
    body: Annotated[OperacionEstadoSolicitud | None, Body(description="Sin cuerpo o un objeto vacío; no admite campos.")] = None,
) -> UsuarioRespuesta:
    return usuario_respuesta(case.ejecutar(id))
