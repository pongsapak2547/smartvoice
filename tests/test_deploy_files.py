"""deploy/aws-ec2 — the single-EC2 pilot files keep their safety properties."""

import re
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parent.parent / "deploy" / "aws-ec2"
FILES = sorted(p for p in DEPLOY.iterdir() if p.is_file())


def _text(name: str) -> str:
    return (DEPLOY / name).read_text(encoding="utf-8")


def _code(name: str) -> str:
    """The file without its comment lines (comments may name what is forbidden)."""
    return "\n".join(
        line for line in _text(name).splitlines() if not line.lstrip().startswith("#")
    )


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_deploy_files_use_lf_line_endings(path):
    """bash and systemd reject CRLF; a Windows checkout must not break them."""
    assert b"\r\n" not in path.read_bytes()


def test_app_listens_on_loopback_only():
    unit = _text("smartvoice.service")
    assert "--server.address 127.0.0.1" in unit
    assert "streamlit run Home.py" in unit
    assert "User=smartvoice" in unit
    assert "--browser.gatherUsageStats false" in unit


def test_app_can_write_only_its_data_and_env():
    unit = _text("smartvoice.service")
    assert "ProtectSystem=strict" in unit
    paths = re.search(r"^ReadWritePaths=(.+)$", unit, re.M).group(1).split()
    assert paths == ["/opt/smartvoice/app/data", "/opt/smartvoice/app/.env"]


def test_caddy_proxies_to_the_app_over_https_only():
    caddy = _text("Caddyfile.template")
    assert "reverse_proxy 127.0.0.1:8501" in caddy
    assert "__DOMAIN__ {" in caddy
    assert "Strict-Transport-Security" in caddy
    assert "http://" not in caddy


def test_installer_never_uses_the_published_password():
    install = _code("install.sh")
    assert "admin1234" not in install
    assert "SMARTVOICE_BOOTSTRAP_PASSWORD" in install
    assert "secrets.token_urlsafe" in install
    # The first-install branch only runs when there is no .env yet.
    assert 'if [[ ! -f "$APP/.env" ]]' in install
    assert "chmod 0600" in install


def test_installer_keeps_data_and_env_on_update():
    install = _text("install.sh")
    rsync = install[install.index("rsync -a --delete"):]
    rsync = rsync[: rsync.index('"$SRC_DIR/" "$APP/"')]
    for protected in ("'/data/'", "'/.env'", "'/.git/'"):
        assert f"--exclude {protected}" in rsync
    # rsync uses the first matching rule: the include must precede '/.env.*'.
    assert rsync.index("--include '/.env.example'") < rsync.index("--exclude '/.env.*'")
    assert "--delete-excluded" not in rsync


def test_installer_validates_its_arguments():
    install = _text("install.sh")
    assert "set -euo pipefail" in install
    assert '[[ ! "$DOMAIN" =~ ^[A-Za-z0-9.-]+$ ]]' in install
    assert "EUID" in install


def test_backup_uses_the_checked_snapshot_and_encrypts_uploads():
    backup = _code("backup.sh")
    assert "scripts/backup_db.py" in backup
    assert backup.count("--sse AES256") == 2
    assert "--delete" not in backup


def test_backup_timer_catches_up_after_a_stopped_instance():
    timer = _text("smartvoice-backup.timer")
    assert "Persistent=true" in timer
    assert "OnCalendar=" in timer


def test_units_point_at_installed_paths():
    assert "ExecStart=/opt/smartvoice/app/deploy/aws-ec2/backup.sh" in _text("smartvoice-backup.service")
    assert "WorkingDirectory=/opt/smartvoice/app" in _text("smartvoice.service")


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("script", ["install.sh", "backup.sh"])
def test_shell_scripts_parse(script):
    result = subprocess.run(["bash", "-n", str(DEPLOY / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_gitattributes_pins_lf_for_deploy_files():
    attributes = (DEPLOY.parent.parent / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
    assert "deploy/** text eol=lf" in attributes


def test_update_preserves_ownership_of_excluded_runtime_files():
    install = _code("install.sh")
    assert not re.search(r'chown\s+-R\s+\S+\s+"\$APP"', install)
    rsync = install[install.index("rsync -a --delete"):]
    rsync = rsync[:rsync.index('"$SRC_DIR/" "$APP/"')]
    assert "--chown=root:root" in rsync
    assert "--exclude '/data/'" in rsync
    assert "--exclude '/.env'" in rsync


def test_release_is_prepared_before_services_stop_and_live_copy():
    install = _code("install.sh")
    assert install.index("flock -n 9") < install.index("apt-get update")
    assert install.index("caddy validate --config") < install.index("activate_release\n")
    assert install.index("database_backend.check_schema()") < install.index("activate_release\n")
    assert 'python3 -m venv "$VENV"' in install
    assert 'PREVIOUS="$RELEASE/previous"' in install
    assert 'trap finish_install EXIT' in install


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("outcome", ["installed", "missing", "apt_failed"])
def test_prerequisites_on_host_without_rsync(tmp_path, outcome):
    source = _text("install.sh")
    start = source.index("for tool in ")
    preflight = source[start:source.index("\ndone", start) + len("\ndone")]
    packages = source[source.index('echo "==> packages"'):source.index("if ! command -v caddy")]
    script = r'''
set -euo pipefail
installed=0
command() {
    if [[ "$1" == -v && ( "$2" == rsync || "$2" == python3 ) ]]; then
        printf '%s:%s\n' "$2" "$installed" >> checks
        [[ "$installed" == 1 && ( "$2" != rsync || "$OUTCOME" != missing ) ]]
    else
        builtin command "$@" >/dev/null 2>&1 || [[ "$1" == -v ]]
    fi
}
apt-get() {
    printf '%s\n' "$*" >> packages
    if [[ "$1" == install ]]; then
        [[ " $* " == *" rsync "* ]] || return 90
        [[ "$OUTCOME" != apt_failed ]] || return 91
        installed=1
    fi
}
'''
    result = subprocess.run(["bash", "-c", script + preflight + "\n" + packages],
                            cwd=tmp_path, env=dict(os.environ, OUTCOME=outcome),
                            capture_output=True, text=True)
    assert (tmp_path / "packages").is_file(), result.stderr
    assert (result.returncode == 0) == (outcome == "installed"), result.stderr
    if outcome != "apt_failed":
        assert (tmp_path / "checks").read_text().splitlines() == ["python3:1", "rsync:1"]
    if outcome == "apt_failed":
        assert not (tmp_path / "checks").exists()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
@pytest.mark.parametrize("failure", ["none", "prepare", "copy", "start", "health"])
def test_release_activation_and_rollback(tmp_path, failure):
    source = _text("install.sh")
    functions = source[source.index("stop_services() {"):source.index('echo "==> packages"')]
    script = r'''
set -euo pipefail
BASE="$PWD/live"
APP="$BASE/app"
RELEASE="$PWD/release"
PREVIOUS="$RELEASE/previous"
CANDIDATE="$RELEASE/app"
VENV="$RELEASE/venv"
CONFIG_ROOT="$PWD/config"
mkdir -p "$APP/data" "$BASE/venv" "$CANDIDATE" "$VENV" "$PREVIOUS/app" "$CONFIG_ROOT/caddy" "$PREVIOUS/config/caddy"
printf old > "$APP/version"
printf old > "$BASE/venv/version"
printf secret > "$APP/.env"
printf customer > "$APP/data/record"
printf new > "$CANDIDATE/version"
printf new > "$VENV/version"
cp "$APP/version" "$PREVIOUS/app/version"
printf old > "$CONFIG_ROOT/caddy/Caddyfile"
cp "$CONFIG_ROOT/caddy/Caddyfile" "$PREVIOUS/config/caddy/Caddyfile"
ACTIVATING=0
VENV_SAVED=0
systemctl() {
    printf '%s\n' "$*" >> "$PWD/events"
    if [[ "$1" == stop ]]; then touch "$PWD/stopped"; fi
    if [[ "$1" == start && "$FAILURE" == start ]]; then return 1; fi
}
rsync() {
    [[ -f "$PWD/stopped" ]] || return 81
    local args=("$@")
    local src="${args[${#args[@]}-2]}" dst="${args[${#args[@]}-1]}"
    cp "$src/version" "$dst/version"
    if [[ "$src" == "$CANDIDATE/" && "$FAILURE" == copy ]]; then return 82; fi
}
'''
    if os.name == "nt":
        script += r'''
ln() {
    "$TEST_PYTHON" -c 'import subprocess, sys; sys.exit(subprocess.call(["cmd", "/c", "mklink", "/J", sys.argv[2], sys.argv[1]], stdout=subprocess.DEVNULL))' "$(cygpath -w "$2")" "$(cygpath -w "$3")"
}
'''
    script += functions[:functions.index('trap finish_install EXIT')] + r'''
trap finish_install EXIT
[[ "$FAILURE" != prepare ]] || exit 83
activate_release
printf new > "$CONFIG_ROOT/caddy/Caddyfile"
[[ "$FAILURE" != health ]] || exit 84
ACTIVATING=0
'''
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path,
                            env=dict(os.environ, FAILURE=failure, TEST_PYTHON=sys.executable.replace("\\", "/")), capture_output=True, text=True)
    assert (result.returncode == 0) == (failure == "none"), result.stderr
    assert (tmp_path / "live/app/.env").read_text() == "secret"
    assert (tmp_path / "live/app/data/record").read_text() == "customer"
    expected = "new" if failure == "none" else "old"
    assert (tmp_path / "live/app/version").read_text() == expected
    assert (tmp_path / "live/venv/version").read_text() == expected
    assert (tmp_path / "config/caddy/Caddyfile").read_text() == expected
    if failure == "prepare":
        assert not (tmp_path / "events").exists()


@pytest.mark.parametrize("setting, valid", [
    (None, False),
    ("", False),
    ("   ", False),
    ("admin1234", False),
    ("short", False),
    ("synthetic-bootstrap-password", True),
])
def test_installer_validates_existing_env_before_starting_services(tmp_path, setting, valid):
    install = _text("install.sh")
    match = re.search(r"<<'PY'\n(.*?)\nPY", install, re.S)
    assert match is not None, "installer must validate the existing bootstrap configuration"
    assert match.end() < install.index("systemctl enable --now smartvoice.service")
    env_path = tmp_path / ".env"
    contents = "TYPHOON_API_KEY=synthetic-secret\n"
    if setting is not None:
        contents += f"SMARTVOICE_BOOTSTRAP_PASSWORD='{setting}'\n"
    env_path.write_text(contents, encoding="utf-8")
    environment = dict(os.environ, PYTHON_DOTENV_DISABLED="1", PYTHONPATH=str(DEPLOY.parent.parent))
    environment["SMARTVOICE_BOOTSTRAP_PASSWORD"] = "inherited-password-must-not-mask-file"
    result = subprocess.run(
        [sys.executable, "-", str(env_path)], input=match.group(1),
        capture_output=True, text=True, cwd=tmp_path, env=environment,
    )
    assert (result.returncode == 0) is valid, result.stderr
    assert env_path.read_text(encoding="utf-8") == contents
    assert "synthetic-secret" not in result.stdout + result.stderr
    assert "synthetic-bootstrap-password" not in result.stdout + result.stderr
