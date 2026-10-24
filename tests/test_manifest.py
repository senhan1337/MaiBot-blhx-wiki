import json
from pathlib import Path

MANIFEST = json.loads((Path(__file__).resolve().parent.parent / "_manifest.json").read_text(encoding="utf-8"))

REQUIRED_FIELDS = (
    "manifest_version", "id", "version", "name", "description", "author",
    "license", "urls", "host_application", "sdk", "capabilities", "i18n",
)


def test_manifest_required_fields() -> None:
    for field in REQUIRED_FIELDS:
        assert field in MANIFEST, f"missing required field: {field}"


def test_manifest_dependencies_use_version_spec() -> None:
    for dep in MANIFEST["dependencies"]:
        assert "version_spec" in dep, f"dependency missing version_spec: {dep}"
        assert "version" not in dep, f"dependency uses legacy 'version' field: {dep}"


def test_manifest_declares_send_text_capability() -> None:
    assert "send.text" in MANIFEST["capabilities"]


def test_manifest_repository_url_is_http() -> None:
    assert MANIFEST["urls"]["repository"].startswith(("http://", "https://"))
