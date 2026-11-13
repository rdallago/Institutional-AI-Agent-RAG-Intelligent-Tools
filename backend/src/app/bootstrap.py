"""Punto de composición de la aplicación y sus futuras dependencias."""

from contextlib import asynccontextmanager, AsyncExitStack

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from app.application.usuarios.ports.user_repository import UserRepository


def crear_persistencia_postgresql(config=None):
    """Componer explícitamente; el llamador dispone el engine al finalizar.

    No ejecutar migraciones ni abrir conexiones al construir FastAPI.
    """
    from app.infrastructure.configuration.database import load_database_config
    from app.infrastructure.persistence.database import build_engine, build_session_factory
    from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import SQLAlchemyUserRepository

    engine = build_engine(config if config is not None else load_database_config())
    return engine, SQLAlchemyUserRepository(build_session_factory(engine))


def create_app(*, repository: UserRepository | None = None, database_config=None, auth_service=None, auth_config=None,
               administrative_provisioning_gate=None, llm_config=None, llm_runtime_factory=None,
               llm_local_context=None, llm_observe: bool = False) -> FastAPI:
    """Componer HTTP; la configuración PostgreSQL se carga solo durante lifespan.

    El repositorio inyectado pertenece al llamador y evita cargar PostgreSQL.
    """
    from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia
    from app.presentation.http.errors import register_error_handlers, persistence_error_handler
    from app.presentation.http.usuarios.router import router
    from app.presentation.http.auth.router import router as auth_router
    from app.presentation.http.ia.router import router as ia_router
    from app.presentation.http.ia.middleware import IABodyLimitMiddleware
    from app.presentation.http.ia.respuestas import router as respuestas_router
    from app.presentation.http.ia.conversaciones import router as conversaciones_router

    if repository is not None and database_config is not None:
        raise ValueError("Elegir repositorio inyectado o configuración PostgreSQL.")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = None
        try:
            from app.infrastructure.configuration.llm import LLMConfig, LLMConfigInvalida, load_llm_config
            from app.infrastructure.configuration.llm_local import require_local_runtime
            from app.infrastructure.llm.ollama import ollama_runtime
            from app.infrastructure.llm.authorization import AuthServiceNormalAccessAuthorizer
            from app.application.ia.use_cases.generar_respuesta import GenerarRespuesta
            selected_config = llm_config if llm_config is not None else (
                LLMConfig(testing=True,environment='test') if repository is not None else load_llm_config())
            if not isinstance(selected_config, LLMConfig):
                raise LLMConfigInvalida()
            require_local_runtime(selected_config, llm_local_context)
            if type(llm_observe) is not bool or (llm_observe and not selected_config.enabled):
                raise LLMConfigInvalida()
            if llm_runtime_factory is not None and not selected_config.testing:
                raise LLMConfigInvalida()
            if repository is None:
                engine, selected_repository = crear_persistencia_postgresql(database_config)
            else:
                selected_repository = repository
            if auth_service is None:
                if engine is None:
                    raise ValueError("Inyectar servicio de autenticación en aplicaciones de memoria.")
                selected_auth = crear_autenticacion_postgresql(engine, auth_config,
                    administrative_provisioning_gate=administrative_provisioning_gate)
            else:
                selected_auth = auth_service
            app.state.user_repository = selected_repository
            app.state.auth_service = selected_auth
            embedding_config = None
            if engine is not None and selected_config.enabled and not selected_config.testing:
                from app.infrastructure.configuration.embeddings import load_embedding_config
                embedding_config = load_embedding_config()
                # Arquitectura cloud operativa: rechazar configuración legacy antes
                # de crear runtime/clientes. No activar Jina ni fallback implícito.
                if selected_config.provider != 'openrouter' or embedding_config.provider != 'jina':
                    raise LLMConfigInvalida()
            async with AsyncExitStack() as stack:
                runtime_options = {'observe': True} if llm_observe else {}
                runtime_factory = ollama_runtime
                if selected_config.provider == 'openrouter' and selected_config.enabled:
                    from app.infrastructure.llm.openrouter import openrouter_runtime
                    runtime_factory = openrouter_runtime
                runtime = await stack.enter_async_context((llm_runtime_factory or runtime_factory)(selected_config, **runtime_options))
                app.state.llm_runtime = runtime
                from app.application.agent.admission import ScopedAdmission
                admission = ScopedAdmission(runtime.admission)
                from app.infrastructure.rag.models import LocalModelGate, CoordinatedDirectProvider
                from app.infrastructure.llm.work_gate import MemoryModelWorkGate
                gate=MemoryModelWorkGate() if selected_config.testing else LocalModelGate()
                direct_provider=CoordinatedDirectProvider(runtime.provider,gate)
                app.state.ia_service = GenerarRespuesta(direct_provider,AuthServiceNormalAccessAuthorizer(selected_auth),
                    admission,timeout_seconds=runtime.timeout_seconds)
                weather = planner = None
                if engine is not None and selected_config.enabled:
                    from app.infrastructure.rag.postgres import PostgresRAG
                    from app.infrastructure.rag.ollama import Embeddings, GroundedProvider
                    from app.infrastructure.rag.text import ConservativeCounter
                    from app.application.rag.use_cases import ResponderConDocumento
                    from app.application.rag.relevance import AcademicRelevance
                    # Testing nunca crea clientes reales habilitados sin MockTransport.
                    if not selected_config.testing:
                        cloud_embeddings = embedding_config.provider == 'jina'
                        if cloud_embeddings:
                            if selected_config.provider != 'openrouter':
                                raise LLMConfigInvalida()
                            from app.infrastructure.rag.jina import JinaEmbeddings
                            embeddings = JinaEmbeddings(embedding_config)
                        else:
                            embeddings=Embeddings(selected_config)
                        if selected_config.provider == 'ollama' and not cloud_embeddings:
                            direct_provider.idle=embeddings.idle
                        grounded_class = GroundedProvider
                        if selected_config.provider == 'openrouter':
                            from app.infrastructure.llm.openrouter import OpenRouterGroundedProvider
                            grounded_class = OpenRouterGroundedProvider
                        grounded=grounded_class(selected_config,observe=llm_observe)
                        stack.push_async_callback(embeddings.close)
                        stack.push_async_callback(grounded.aclose)
                        if cloud_embeddings:
                            from app.infrastructure.rag.cloud_postgres import CloudPostgresRAG
                            store = CloudPostgresRAG(engine, embedding_config)
                        else:
                            store=PostgresRAG(engine)
                        app.state.rag_documents=store
                        app.state.rag_service=ResponderConDocumento(authorizer=AuthServiceNormalAccessAuthorizer(selected_auth),
                            documents=store,vectors=store,embeddings=embeddings,provider=grounded,counter=ConservativeCounter(),
                            gate=gate,admission=admission,threshold=.60,relevance=AcademicRelevance(),
                            recovery=store.recover,continuity=store.article_context,
                            timeout_seconds=runtime.timeout_seconds,
                            diagnostic_environment=selected_config.environment)
                        from app.infrastructure.rag.weather import OpenMeteo
                        from app.infrastructure.rag.planner import JSONPlanner
                        weather=OpenMeteo()
                        planner_class = JSONPlanner
                        planner_idle = getattr(embeddings, 'idle', None)
                        if selected_config.provider == 'openrouter':
                            from app.infrastructure.llm.openrouter import OpenRouterPlanner
                            planner_class = OpenRouterPlanner
                            async def remote_idle():
                                return None
                            planner_idle = remote_idle
                        planner=planner_class(selected_config,gate,planner_idle,observe=llm_observe)
                        stack.push_async_callback(weather.close)
                        stack.push_async_callback(planner.aclose)
                from app.application.agent.agent import Agent
                from app.application.agent.skills.registry import SkillRegistry
                from app.infrastructure.rag.skills import PackagedSkillLoader
                app.state.ia_agent = Agent(authorizer=AuthServiceNormalAccessAuthorizer(selected_auth),
                    direct=app.state.ia_service, rag=getattr(app.state,'rag_service',None),
                    documents=getattr(app.state,'rag_documents',None), admission=admission,
                    skills=SkillRegistry(PackagedSkillLoader()),weather=weather,planner=planner)
                if engine is not None:
                    from app.application.agent.conversations import Conversations
                    from app.infrastructure.rag.conversations import PostgresConversations
                    app.state.conversations=Conversations(authorizer=AuthServiceNormalAccessAuthorizer(selected_auth),
                        repository=PostgresConversations(engine),agent=app.state.ia_agent)
                yield
        finally:
            for name in ('ia_service','llm_runtime','rag_documents','rag_service','ia_agent','conversations'):
                if hasattr(app.state,name):
                    delattr(app.state,name)
            if hasattr(app.state, "user_repository"):
                del app.state.user_repository
            if hasattr(app.state, "auth_service"):
                del app.state.auth_service
            if engine is not None:
                await run_in_threadpool(engine.dispose)

    app = FastAPI(
        title="API de usuarios",
        description="API de usuarios con JWT Bearer, sesiones revocables y permisos vigentes. Sprint 7.",
        version="0.1.0",
        lifespan=lifespan,
        openapi_tags=[{"name": "Usuarios", "description": "Administración de perfiles y consulta propia."},
                      {"name": "Autenticación", "description": "Login JSON, perfil propio, logout y cambio de contraseña."}],
    )
    register_error_handlers(app)
    app.add_middleware(IABodyLimitMiddleware)
    app.add_exception_handler(ErrorPersistencia, persistence_error_handler)
    app.include_router(router)
    app.include_router(auth_router)
    app.include_router(ia_router)
    app.include_router(respuestas_router)
    app.include_router(conversaciones_router)
    return app


def create_test_database_app() -> FastAPI:
    """Fábrica para pruebas manuales; solo usuarios_test en el puerto de DB 5435."""
    from app.infrastructure.configuration.database import load_database_config

    config = load_database_config(testing=True)
    from app.infrastructure.configuration.auth import load_auth_config
    from app.infrastructure.configuration.llm import load_llm_config
    return create_app(database_config=config, auth_config=load_auth_config(testing=True),
        llm_config=load_llm_config(testing=True))


def crear_autenticacion_postgresql(engine, auth_config=None, *, administrative_provisioning_gate=None):
    from app.application.auth.service import AuthService
    from app.infrastructure.configuration.auth import load_auth_config
    from app.infrastructure.persistence.database import build_session_factory
    from app.infrastructure.security.postgres import PostgresSecurityUnitOfWork
    from app.infrastructure.security.crypto import Argon2Hasher, JWTService
    from app.infrastructure.security.limiter import LoginLimiter

    config = auth_config if auth_config is not None else load_auth_config()
    sessions = build_session_factory(engine)
    factory = lambda: PostgresSecurityUnitOfWork(sessions)
    return AuthService(factory, Argon2Hasher(), JWTService(config), LoginLimiter(factory, config.limiter_key),
        administrative_provisioning_gate=administrative_provisioning_gate)
