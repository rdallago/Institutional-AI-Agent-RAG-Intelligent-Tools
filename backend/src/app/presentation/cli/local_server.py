"""Servidor local explicito. El arranque Uvicorn habitual permanece cerrado."""
import argparse
import socket
import sys

from app.infrastructure.configuration.local_provisioning import LocalProvisioningConfig, verified_local_gate


def main(argv=None):
    parser = argparse.ArgumentParser(description="Servidor local de practica con opt-in administrativo.")
    parser.add_argument("--environment", required=True, choices=["local-development", "test", "production"])
    parser.add_argument("--enable-initial-provisioning", action="store_true")
    parser.add_argument("--enable-llm", action="store_true", help="Opt-in IA solo para esta instancia local.")
    parser.add_argument("--observe-llm", action="store_true", help="Solo metadatos tecnicos de IA local.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.observe_llm and not args.enable_llm:
        parser.error("La observacion requiere --enable-llm explicito.")
    if args.environment != "local-development" or args.host != "127.0.0.1" or not 1 <= args.port <= 65535:
        parser.error("Este lanzador solo admite local-development sobre 127.0.0.1.")

    from app.bootstrap import create_app
    from app.infrastructure.configuration.database import load_database_config
    from app.infrastructure.configuration.auth import load_auth_config
    from app.infrastructure.configuration.llm import LLMConfig, load_memory_guard, load_local_model, apply_provider_settings
    from app.infrastructure.configuration.llm_local import LocalLLMContext, require_local_runtime
    from app.infrastructure.persistence.database import build_engine
    import uvicorn

    listener = None
    engine = None
    try:
        database = load_database_config()
        if (database.database, database.host, database.port) != ("usuarios_dev", "127.0.0.1", 5434):
            raise ValueError()
        auth = load_auth_config()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind((args.host, args.port))
        listener.listen(128)
        # Leer solo modelo y guarda; el opt-in sigue exclusivo de esta invocacion.
        llm = apply_provider_settings(LLMConfig(enabled=args.enable_llm,
            environment=args.environment if args.enable_llm else 'disabled',
            **({'model':load_local_model()} if args.enable_llm else {}),
            enforce_memory_guard=load_memory_guard(environment=args.environment) if args.enable_llm else True))
        context = LocalLLMContext(listener=listener, workers=1)
        require_local_runtime(llm, context)
        gate = None
        if args.enable_initial_provisioning:
            engine = build_engine(database)
            gate = verified_local_gate(LocalProvisioningConfig(args.environment, True), database, listener, engine)
            engine.dispose()
            engine = None
        app = create_app(database_config=database, auth_config=auth, administrative_provisioning_gate=gate,
            llm_config=llm, llm_local_context=context, llm_observe=args.observe_llm)
        config = uvicorn.Config(app, host=args.host, port=args.port, proxy_headers=False, access_log=False,
            workers=1, reload=False)
        print("Local server: initial provisioning " + ("ENABLED" if gate else "DISABLED"), flush=True)
        print("Local server: LLM " + ("ENABLED" if llm.enabled else "DISABLED"), flush=True)
        print('Local server: provider=' + llm.provider + ' model=' + (llm.remote_model if llm.provider == 'openrouter' else llm.model), flush=True)
        print("Local server: memory guard " + ("ENABLED" if llm.enforce_memory_guard else "DISABLED (local-development)"), flush=True)
        server = uvicorn.Server(config)
        server.run(sockets=[listener])
        return 0 if server.started else 1
    except Exception:
        # No representar excepciones de conexion/configuracion que puedan contener secretos.
        print("Inicio local rechazado o fallo del servidor; verificar destino, revision y socket.", file=sys.stderr)
        return 1
    finally:
        try:
            if engine is not None:
                engine.dispose()
        finally:
            if listener is not None:
                listener.close()


if __name__ == "__main__":
    raise SystemExit(main())
