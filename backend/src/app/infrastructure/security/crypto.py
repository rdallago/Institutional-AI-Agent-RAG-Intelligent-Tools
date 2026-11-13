from datetime import UTC, datetime
from uuid import UUID

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.application.auth.exceptions import AutenticacionRequerida


class Argon2Hasher:
    def __init__(self, *, memory_cost=65536, time_cost=3, parallelism=1):
        self._hasher = PasswordHasher(type=Type.ID, memory_cost=memory_cost, time_cost=time_cost,
            parallelism=parallelism, hash_len=32, salt_len=16)

    def hash(self, password):
        return self._hasher.hash(password)

    def verify(self, encoded, password):
        try:
            return self._hasher.verify(encoded, password)
        except VerifyMismatchError:
            return False
        except (VerificationError, InvalidHashError, UnicodeError):
            # Un hash almacenado inválido es un fallo técnico, no una contraseña errónea.
            from app.infrastructure.persistence.repositories.sqlalchemy_user_repository import ErrorPersistencia
            raise ErrorPersistencia("Credencial almacenada inválida.") from None

    def needs_rehash(self, encoded):
        return self._hasher.check_needs_rehash(encoded)


class JWTService:
    def __init__(self, config, *, clock=lambda: datetime.now(UTC)):
        self.config, self.clock = config, clock

    def issue(self, session):
        return jwt.encode({"sub": str(session.usuario_id), "jti": str(session.id),
            "iat": int(session.creada_at.timestamp()), "exp": int(session.expira_at.timestamp()),
            "iss": self.config.issuer, "aud": self.config.audience, "token_use": "access"},
            self.config.keys[self.config.active_kid], algorithm="HS256",
            headers={"kid": self.config.active_kid, "typ": "at+jwt"})

    def verify(self, token):
        try:
            if not isinstance(token, str) or len(token) > 8192:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if set(header) - {"alg", "typ", "kid"} or header.get("alg") != "HS256" or header.get("typ") != "at+jwt":
                raise ValueError()
            kid = header.get("kid")
            if not isinstance(kid, str) or kid not in self.config.keys:
                raise ValueError()
            claims = jwt.decode(token, self.config.keys[kid], algorithms=["HS256"],
                issuer=self.config.issuer, audience=self.config.audience,
                options={"require": ["sub", "jti", "iat", "exp", "iss", "aud", "token_use"],
                         "verify_exp": False, "verify_iat": False, "strict_aud": True})
            now = self.clock().timestamp()
            if (type(claims["iat"]) is not int or type(claims["exp"]) is not int
                or claims["token_use"] != "access" or claims["iat"] > now + 30
                or claims["exp"] <= now - 30 or not 0 < claims["exp"] - claims["iat"] <= 900):
                raise ValueError()
            return UUID(claims["sub"]), UUID(claims["jti"])
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise AutenticacionRequerida() from None
