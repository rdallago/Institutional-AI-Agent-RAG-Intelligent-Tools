import pytest

from auth_support import PASSWORD
from app.presentation.cli.security import main


def test_cli_uses_hidden_confirmed_input_and_cannot_repeat_bootstrap(security, monkeypatch, capsys, initial_provisioning_test_gate):
    from auth_support import memory_auth
    _, service, _ = memory_auth()
    monkeypatch.setattr("sys.stdin.isatty",lambda: True)
    monkeypatch.setattr("getpass.getpass",lambda prompt: PASSWORD)
    args=["bootstrap-admin","--nombre","Test","--apellido","Admin","--email","cli@example.com"]
    assert main(args,service=service)==0
    assert main(args,service=service)==1
    captured=capsys.readouterr()
    assert PASSWORD not in captured.out+captured.err and "$argon2" not in captured.out+captured.err


def test_cli_rejects_password_argument_without_echo(capsys):
    with pytest.raises(SystemExit):
        main(["bootstrap-admin","--nombre","A","--apellido","B","--email","a@example.com","--password","do-not-echo-this"])
    assert "do-not-echo-this" not in capsys.readouterr().err


def test_cli_rejects_development_without_explicit_flag():
    with pytest.raises(SystemExit): main(["--target","development","limpiar-intentos"])
