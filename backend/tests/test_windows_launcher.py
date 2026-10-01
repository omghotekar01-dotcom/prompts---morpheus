from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT / "START-MORPHEUS.ps1"


def test_fresh_windows_launcher_does_not_probe_missing_package_via_pip_show() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "pip show uvicorn" not in text
    assert "importlib.util.find_spec('uvicorn')" in text


def test_windows_launcher_verifies_installs_and_uses_venv_python_directly() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")
    assert 'Assert-NativeSuccess "Installing backend dependencies"' in text
    assert 'Assert-NativeSuccess "Installing frontend dependencies"' in text
    assert "$VenvPythonLiteral = ConvertTo-PsLiteral $VenvPython" in text
    assert "& $VenvPythonLiteral -m uvicorn app.server:app" in text
