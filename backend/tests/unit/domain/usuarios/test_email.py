from dataclasses import FrozenInstanceError

import pytest

from app.domain.usuarios.email import Email
from app.domain.usuarios.exceptions import EmailInvalido


@pytest.mark.parametrize("valor", [
    "ana@instituto.edu.ar", "ana.perez+curso@sub.instituto.edu.ar",
    "o'connor@instituto.edu.ar", "a!#$%&'*+/=?^_`{|}~-b@ejemplo.com",
    "a@mi-instituto.edu", "a" * 64 + "@ejemplo.com",
    "a@" + "b" * 63 + ".com",
    "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * 61,
])
def test_admite_emails_del_formato_documentado(valor):
    assert str(Email(valor)) == valor


def test_normaliza_y_compara_por_valor():
    email = Email("  Persona@Instituto.EDU.ar  ")
    assert email.valor == "persona@instituto.edu.ar"
    assert email == Email("persona@instituto.edu.ar")
    assert hash(email) == hash(Email("persona@instituto.edu.ar"))
    assert email != Email("otra@instituto.edu.ar")


def test_email_es_inmutable():
    email = Email("ana@ejemplo.com")
    with pytest.raises(FrozenInstanceError):
        email.valor = "otra@ejemplo.com"


@pytest.mark.parametrize("valor", [
    None, 123, True, b"ana@ejemplo.com", "", "   ", "ana", "@ejemplo.com",
    "ana@", "ana@@ejemplo.com", "ana perez@ejemplo.com", "ana@ejem plo.com",
    "ana\n@ejemplo.com", "ana@ejemplo.com\n", "\tana@ejemplo.com",
    "ana\x00@ejemplo.com", "ana\x7f@ejemplo.com", "josé@ejemplo.com",
    "ana@educación.com", "ana@localhost", "ana@.com", "ana@ejemplo.",
    "ana@ejemplo..com", "ana@-ejemplo.com", "ana@ejemplo-.com",
    "ana@mi_instituto.com", ".ana@ejemplo.com", "ana.@ejemplo.com",
    "ana..perez@ejemplo.com", '"ana"@ejemplo.com', "ana@[127.0.0.1]",
    "a" * 65 + "@ejemplo.com", "ana@" + "b" * 64 + ".com",
    "a" * 64 + "@" + "b" * 63 + "." + "c" * 63 + "." + "d" * 62,
])
def test_rechaza_emails_invalidos(valor):
    with pytest.raises(EmailInvalido):
        Email(valor)
