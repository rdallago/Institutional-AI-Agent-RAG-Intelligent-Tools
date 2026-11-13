"""Solo usuarios_dev. Inspeccion por defecto; escritura con doble confirmacion."""
import argparse
import getpass
import sys
import warnings
from uuid import UUID

from sqlalchemy import text

from app.domain.usuarios.email import Email


class SafeParser(argparse.ArgumentParser):
    def error(self,message):
        self.exit(2,'Argumentos invalidos; usar --help. Nunca pasar passwords por argumentos.\n')


def inspect_target(engine,email):
    with engine.connect() as conn:
        conn.exec_driver_sql('SET TRANSACTION READ ONLY')
        conn.exec_driver_sql("SET LOCAL statement_timeout='3s'")
        if conn.exec_driver_sql('SELECT current_database()').scalar_one()!='usuarios_dev':
            raise ValueError('Destino no permitido.')
        count=conn.execute(text("SELECT count(*) FROM public.usuarios WHERE rol='ADMIN'")).scalar_one()
        rows=conn.execute(text("""SELECT u.id,u.email,u.activo,u.rol,
          EXISTS(SELECT 1 FROM public.usuario_credenciales c WHERE c.usuario_id=u.id) AS has_credential
          FROM public.usuarios u WHERE u.email=:email"""),{'email':email}).mappings().all()
        conn.rollback()
    if len(rows)!=1 or rows[0]['rol']!='ADMIN' or not rows[0]['activo'] or not rows[0]['has_credential']:
        raise ValueError('Cuenta no apta para recuperacion.')
    return count,rows[0]


def hidden_password():
    # getpass puede caer a entrada visible si no controla el eco: se prohibe.
    with warnings.catch_warnings():
        warnings.simplefilter('error',getpass.GetPassWarning)
        password=getpass.getpass('Nueva contraseña (oculta): ')
        confirmation=getpass.getpass('Repetir contraseña (oculta): ')
    if password!=confirmation:
        raise ValueError('Las contraseñas no coinciden.')
    return password


def main(argv=None):
    parser=SafeParser(description='Recuperar ADMIN existente exclusivamente en usuarios_dev. Solo lectura por defecto.')
    parser.add_argument('--email',required=True)
    parser.add_argument('--usuario-id',type=UUID)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--allow-development',action='store_true')
    args=parser.parse_args(argv)
    if args.apply and (not args.allow_development or args.usuario_id is None):
        parser.error('Falta autorizacion o seleccion de cuenta.')
    if args.apply and not sys.stdin.isatty():
        parser.exit(2,'Se requiere terminal interactiva con entrada oculta.\n')
    engine=None
    try:
        from app.infrastructure.configuration.database import load_database_config
        from app.infrastructure.persistence.database import build_engine,build_session_factory
        from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
        from app.infrastructure.security.crypto import Argon2Hasher
        from app.application.auth.recovery import LocalAdminRecovery
        email=str(Email(args.email))
        config=load_database_config()
        if (config.host,config.port,config.database)!=('127.0.0.1',5434,'usuarios_dev'):
            raise ValueError('Destino no permitido.')
        engine=build_engine(config)
        count,target=inspect_target(engine,email)
        if args.usuario_id is not None and args.usuario_id!=target['id']:
            raise ValueError('Identidad no coincidente.')
        print(f"Cuenta: {email} | ID: {target['id']} | ADMIN activo | administradores: {count}")
        if not args.apply:
            print('SOLO LECTURA: no se modificaron credenciales o sesiones.')
            return 0
        # UUID obligatorio selecciona una cuenta concreta incluso con varios ADMIN.
        expected=f"RESTABLECER {email}"
        if input(f'Para autorizar esta cuenta escribí exactamente: {expected}\n')!=expected:
            print('Cancelado; sin cambios.')
            return 2
        password=hidden_password()
        sessions=build_session_factory(engine)
        service=LocalAdminRecovery(lambda:PostgresSecurityUnitOfWork(sessions),Argon2Hasher())
        try:service.reset(target['id'],email,password)
        finally:password=None
        print('Contraseña restablecida y sesiones de esta cuenta revocadas. Ingresá nuevamente desde React.')
        return 0
    except (KeyboardInterrupt,EOFError):
        print('Cancelado; sin cambios.',file=sys.stderr)
        return 2
    except Exception:
        print('Recuperacion rechazada. No se confirmaron cambios parciales. Revisá cuenta, política y disponibilidad.',file=sys.stderr)
        return 1
    finally:
        if engine is not None:engine.dispose()


if __name__=='__main__':
    raise SystemExit(main())
