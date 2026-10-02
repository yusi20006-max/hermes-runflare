from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bale_plugin_has_no_telegram_allowlist_fallback():
    source = (ROOT / "bale-plugin" / "adapter.py").read_text()
    assert "TELEGRAM_ALLOWED_USERS" not in source
    assert "BALE_ALLOWED_USERS" in source
    assert "BALE_CHAT_ID" in source


def test_bale_disables_telegram_fallback_transport():
    source = (ROOT / "bale-plugin" / "adapter.py").read_text()
    assert "def _telegram_fallback_transport_allowed" in source
    assert "return False" in source
    assert "def _fallback_ips" in source


def test_docker_applies_platform_isolation_patch():
    patch = (ROOT / "patches" / "hermes-bale.patch").read_text()
    assert "_telegram_fallback_transport_allowed" in patch
    assert "discover_fallback_ips" not in patch


def test_entrypoint_enables_bale_without_touching_secrets():
    source = (ROOT / "docker-entrypoint.sh").read_text()
    assert "BALE_BOT_TOKEN" not in source
    assert '"bale-platform"' in source
    assert 'bale["enabled"] = True' in source
