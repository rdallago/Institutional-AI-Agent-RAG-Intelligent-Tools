import argparse
import getpass
import sys
from uuid import UUID


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "Argumentos inválidos; consultar --help. Nunca pasar contraseñas por argumentos.\n")


def main(argv=None, *, service=None):
    parser = SafeParser(description="Aprovisionamiento local. Por defecto solo usuarios_test.")
    parser.add_argument("--target", choices=["test", "development"], default="test")
    parser.add_argument("--allow-development", action="store_true")
    actions = parser.add_subparsers(dest="action", required=True, parser_class=SafeParser)
    bootstrap = actions.add_parser("bootstrap-admin")
    bootstrap.add_argument("--nombre", required=True)
    bootstrap.add_argument("--apellido", required=True)
    bootstrap.add_argument("--email", required=True)
    initial = actions.add_parser("asignar-credencial-inicial")
    initial.add_argument("--usuario-id", type=UUID, required=True)
    actions.add_parser("limpiar-intentos")
    args = parser.parse_args(argv)
    if args.target == "development" and not args.allow_development:
        parser.error("Desarrollo requiere autorización explícita")
    engine = None
    try:
        if args.action != "limpiar-intentos":
            from app.application.auth.provisioning import require_initial_provisioning_enabled
            require_initial_provisioning_enabled()
        if service is None:
            from app.bootstrap import crear_autenticacion_postgresql
            from app.infrastructure.configuration.auth import load_auth_config
            from app.infrastructure.configuration.database import load_database_config
            from app.infrastructure.persistence.database import build_engine

            testing = args.target == "test"
            config = load_database_config(testing=testing)
            if testing:
                config.require_test_database()
            elif (config.database, config.host, config.port) != ("usuarios_dev", "127.0.0.1", 5434):
                raise ValueError()
            engine = build_engine(config)
            service = crear_autenticacion_postgresql(engine, load_auth_config(testing=testing))
        if args.action == "limpiar-intentos":
            count = service.limiter.cleanup(service.clock())
            print(f"Registros vencidos retirados: {count}")
            return 0
        if not sys.stdin.isatty():
            parser.exit(2, "Se requiere una terminal interactiva para la entrada oculta.\n")
        password = getpass.getpass("Contraseña (entrada oculta): ")
        confirmation = getpass.getpass("Confirmación: ")
        if password != confirmation:
            parser.exit(2, "Las contraseñas no coinciden.\n")
        if args.action == "bootstrap-admin":
            user_id = service.bootstrap(args.nombre, args.apellido, args.email, password)
            print(f"Administrador inicial creado: {user_id}")
        else:
            service.assign_initial(args.usuario_id, password)
            print("Credencial inicial asignada; no se modificó el estado del perfil.")
        return 0
    except Exception:
        print("Operación rechazada o no disponible. No se realizaron cambios parciales.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
