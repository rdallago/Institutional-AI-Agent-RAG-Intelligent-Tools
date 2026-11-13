"""Opt-in local validado contra conexion y socket efectivos; sin variables globales."""
from dataclasses import dataclass
import socket

from sqlalchemy import text

from app.application.auth.exceptions import AprovisionamientoNoHabilitado
from app.infrastructure.configuration.database import DatabaseConfig


@dataclass(frozen=True, slots=True)
class LocalProvisioningConfig:
    environment: str
    enabled: bool = False

    def require_allowed(self, database: DatabaseConfig) -> None:
        if (self.environment != "local-development" or self.enabled is not True
                or (database.database, database.host, database.port)
                != ("usuarios_dev", "127.0.0.1", 5434)):
            raise AprovisionamientoNoHabilitado()


def verified_local_gate(config: LocalProvisioningConfig, database: DatabaseConfig,
                        listener: socket.socket, engine):
    """Validar antes de servir. No recibe host declarado por HTTP o por un cliente."""
    config.require_allowed(database)

    def require_listener():
        config.require_allowed(database)
        try:
            valid = (listener.family == socket.AF_INET
                and listener.getsockname()[0] == "127.0.0.1"
                and listener.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 1)
        except OSError:
            valid = False
        if not valid:
            raise AprovisionamientoNoHabilitado()

    require_listener()
    # La misma configuracion inmutable se entrega luego a create_app.
    # Lectura forzada; no migrar ni escribir durante el preflight del lanzador.
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        identity = tuple(connection.execute(text("SELECT current_database(), current_user")).one())
        revisions = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
        # 0004_rag y 0005_agent_memory son aditivas: conservan el contrato de
        # usuarios, credenciales y sesiones de 0003. Rechazar heads desconocidos.
        if (identity != (database.database, database.username)
                or len(revisions) != 1
                or revisions[0] not in {"0003", "0004_rag", "0005_agent_memory"}):
            raise AprovisionamientoNoHabilitado()
    return require_listener
