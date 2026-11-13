from inspect import iscoroutinefunction


def test_seven_operations_and_documented_errors_match_http(client, http_app):
    schema = client.get("/openapi.json").json()
    paths = {path: value for path, value in schema["paths"].items() if path.startswith("/api/v1/usuarios")}
    assert set(paths) == {"/api/v1/usuarios", "/api/v1/usuarios/{id}", "/api/v1/usuarios/{id}/reactivar", "/api/v1/usuarios/{id}/credencial-inicial"}
    operations = [(method, path, op) for path, methods in paths.items() for method, op in methods.items()]
    assert len(operations) == 7
    assert len({op["operationId"] for _, _, op in operations}) == 7
    for method, path, operation in operations:
        assert operation["tags"] == ["Usuarios"]
        for status in ("422", "500"):
            assert operation["responses"][status]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorRespuesta")
    assert "content" not in paths["/api/v1/usuarios/{id}"]["delete"]["responses"]["204"]
    assert "Location" in paths["/api/v1/usuarios"]["post"]["responses"]["201"]["headers"]
    schemas = schema["components"]["schemas"]
    assert schemas["CrearUsuarioSolicitud"]["additionalProperties"] is False
    assert schemas["ModificarUsuarioSolicitud"]["additionalProperties"] is False
    assert set(schemas["ModificarUsuarioSolicitud"]["required"]) == {"nombre", "apellido", "email"}
    assert schemas["CrearUsuarioSolicitud"]["examples"]
    for route in http_app.routes:
        if getattr(route, "path", "").startswith("/api/v1/usuarios"):
            assert not iscoroutinefunction(route.endpoint)


def test_query_defaults_and_limits_are_documented(client):
    parameters = client.get("/openapi.json").json()["paths"]["/api/v1/usuarios"]["get"]["parameters"]
    by_name = {item["name"]: item["schema"] for item in parameters}
    assert by_name["estado"]["default"] == "activos"
    assert by_name["limite"]["default"] == 20
    assert by_name["limite"]["minimum"] == 1 and by_name["limite"]["maximum"] == 100
    assert by_name["desplazamiento"]["minimum"] == 0
