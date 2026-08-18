import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    match = re.search(
        r'^version\s*=\s*"([^"]+)"',
        (ROOT / "pyproject.toml").read_text(),
        re.MULTILINE,
    )

    if not match:
        raise AssertionError("pyproject.toml version not found")

    return match.group(1)


class InstallerFoundationTests(unittest.TestCase):
    def run_script(self, script: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
        merged_env = os.environ.copy()
        merged_env.update(env)

        return subprocess.run(
            ["sh", str(script)],
            cwd=ROOT,
            env=merged_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def create_dummy_agent(self, directory: Path, body: Optional[str] = None) -> Path:
        agent = directory / "mvd-edge-agent"
        agent.write_text(body or "#!/usr/bin/env sh\nprintf 'dummy agent\\n'\n")
        agent.chmod(agent.stat().st_mode | stat.S_IXUSR)
        return agent

    def create_dummy_runtime(self, directory: Path, body: Optional[str] = None) -> Path:
        runtime = directory / "runtime"
        internal = runtime / "_internal"
        internal.mkdir(parents=True)
        self.create_dummy_agent(runtime, body=body)
        (internal / "support.dat").write_text("pyinstaller runtime support")
        return runtime

    def test_linux_staged_install_creates_expected_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            destdir = temp_dir / "stage"
            runtime = self.create_dummy_runtime(temp_dir)

            result = self.run_script(
                ROOT / "packaging/linux/install.sh",
                {
                    "DESTDIR": str(destdir),
                    "AGENT_RUNTIME_DIR": str(runtime),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((destdir / "opt/mvd-edge/mvd-edge-agent").is_file())
            self.assertTrue((destdir / "opt/mvd-edge/_internal/support.dat").is_file())
            self.assertTrue((destdir / "opt/mvd-edge/docs/LINUX_SERVICE.md").is_file())
            self.assertTrue((destdir / "etc/mvd-edge/edge.env").is_file())
            self.assertTrue((destdir / "var/lib/mvd-edge").is_dir())
            self.assertTrue((destdir / "var/log/mvd-edge").is_dir())
            self.assertTrue((destdir / "etc/systemd/system/mvd-edge.service").is_file())

    def test_linux_staged_reinstall_preserves_existing_config_and_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            destdir = temp_dir / "stage"
            runtime = self.create_dummy_runtime(temp_dir)
            env = {
                "DESTDIR": str(destdir),
                "AGENT_RUNTIME_DIR": str(runtime),
                "RUN_PREFLIGHT": "0",
            }

            first = self.run_script(ROOT / "packaging/linux/install.sh", env)
            self.assertEqual(first.returncode, 0, first.stderr)

            config = destdir / "etc/mvd-edge/edge.env"
            data_marker = destdir / "var/lib/mvd-edge/events.sqlite3"
            config.write_text(
                "DEVICE_ID=CUSTOMER-DEVICE\n"
                "READER_ID=CUSTOMER-READER\n"
                "SITE_ID=CUSTOMER-SITE\n"
                "LOCATION_ID=CUSTOMER-LOCATION\n"
                "ZONE_ID=CUSTOMER-ZONE\n"
                "RFID_API_URL=https://api.example.test\n"
                "RFID_INGEST_API_KEY=customer-secret\n"
            )
            data_marker.write_text("customer runtime data")
            stale_runtime_file = destdir / "opt/mvd-edge/old-runtime-file"
            stale_runtime_file.write_text("old")
            (runtime / "_internal/support.dat").write_text("replacement runtime")

            second = self.run_script(ROOT / "packaging/linux/install.sh", env)

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertIn("CUSTOMER-DEVICE", config.read_text())
            self.assertEqual(data_marker.read_text(), "customer runtime data")
            self.assertFalse(stale_runtime_file.exists())
            self.assertEqual(
                (destdir / "opt/mvd-edge/_internal/support.dat").read_text(),
                "replacement runtime",
            )

    def test_linux_staged_uninstall_preserves_config_data_and_logs_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            destdir = temp_dir / "stage"
            runtime = self.create_dummy_runtime(temp_dir)
            install_env = {
                "DESTDIR": str(destdir),
                "AGENT_RUNTIME_DIR": str(runtime),
                "RUN_PREFLIGHT": "0",
            }

            install = self.run_script(ROOT / "packaging/linux/install.sh", install_env)
            self.assertEqual(install.returncode, 0, install.stderr)

            config = destdir / "etc/mvd-edge/edge.env"
            data_marker = destdir / "var/lib/mvd-edge/events.sqlite3"
            log_marker = destdir / "var/log/mvd-edge/agent.log"
            data_marker.write_text("queued")
            log_marker.write_text("log")

            uninstall = self.run_script(
                ROOT / "packaging/linux/uninstall.sh",
                {"DESTDIR": str(destdir)},
            )

            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertFalse((destdir / "opt/mvd-edge/mvd-edge-agent").exists())
            self.assertFalse((destdir / "opt/mvd-edge/_internal").exists())
            self.assertFalse((destdir / "etc/systemd/system/mvd-edge.service").exists())
            self.assertTrue(config.exists())
            self.assertEqual(data_marker.read_text(), "queued")
            self.assertEqual(log_marker.read_text(), "log")

    def test_linux_first_install_allows_blank_commissioning_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            destdir = temp_dir / "stage"
            runtime = self.create_dummy_runtime(temp_dir)

            result = self.run_script(
                ROOT / "packaging/linux/install.sh",
                {
                    "DESTDIR": str(destdir),
                    "AGENT_RUNTIME_DIR": str(runtime),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            config_text = (destdir / "etc/mvd-edge/edge.env").read_text()
            self.assertIn("RFID_API_URL=", config_text)
            self.assertIn("RFID_INGEST_API_KEY=", config_text)

    def test_linux_preflight_passes_with_valid_dummy_agent_and_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            config = temp_dir / "edge.env"
            data_dir = temp_dir / "data"
            log_dir = temp_dir / "logs"
            data_dir.mkdir()
            log_dir.mkdir()
            agent = self.create_dummy_agent(
                temp_dir,
                "#!/usr/bin/env sh\n"
                "if [ \"$1\" = \"--check-config\" ]; then printf 'VALID\\n'; exit 0; fi\n"
                "exit 1\n",
            )
            config.write_text(
                "SERIAL_PORT=/run/iotdin-imx8p/gateway/access/industrial_io/ttyRS485\n"
                "DEVICE_ID=EDGE-01\n"
                "READER_ID=READER-01\n"
                "SITE_ID=SITE-01\n"
                "LOCATION_ID=LOCATION-01\n"
                "ZONE_ID=ZONE-01\n"
                "RFID_API_URL=https://api.example.test/api/v1/rfid/events\n"
                "RFID_INGEST_API_KEY=secret-value\n"
            )

            result = self.run_script(
                ROOT / "packaging/linux/preflight.sh",
                {
                    "AGENT_BIN": str(agent),
                    "MVD_EDGE_CONFIG": str(config),
                    "EDGE_DATA_DIR": str(data_dir),
                    "EDGE_LOG_DIR": str(log_dir),
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Preflight passed.", result.stdout)
            self.assertNotIn("secret-value", result.stdout)
            self.assertNotIn("secret-value", result.stderr)

    def test_assemble_release_creates_self_contained_linux_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            runtime = self.create_dummy_runtime(temp_dir)
            output_dir = temp_dir / "release"

            result = self.run_script(
                ROOT / "packaging/linux/assemble-release.sh",
                {
                    "RUNTIME_DIR": str(runtime),
                    "OUTPUT_DIR": str(output_dir),
                    "ARCH": "aarch64",
                },
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            bundle = output_dir / f"mvd-edge-agent-{project_version()}-linux-aarch64"
            self.assertTrue((bundle / "executable/mvd-edge-agent").is_file())
            self.assertTrue((bundle / "executable/_internal/support.dat").is_file())
            self.assertTrue((bundle / "install.sh").is_file())
            self.assertTrue((bundle / "uninstall.sh").is_file())
            self.assertTrue((bundle / "preflight.sh").is_file())
            self.assertTrue((bundle / "config/edge.env.example").is_file())
            self.assertTrue((bundle / "systemd/mvd-edge.service").is_file())
            self.assertTrue((bundle / "docs/LINUX_SERVICE.md").is_file())
            self.assertTrue((bundle / "INSTALL.md").is_file())
            self.assertFalse((bundle / ".git").exists())
            self.assertFalse((bundle / ".env").exists())

            destdir = temp_dir / "bundle-stage"
            install = self.run_script(
                bundle / "install.sh",
                {"DESTDIR": str(destdir)},
            )

            self.assertEqual(install.returncode, 0, install.stderr)
            self.assertTrue((destdir / "opt/mvd-edge/mvd-edge-agent").is_file())
            self.assertTrue((destdir / "opt/mvd-edge/_internal/support.dat").is_file())
            self.assertTrue((destdir / "opt/mvd-edge/docs/LINUX_SERVICE.md").is_file())
            self.assertTrue((destdir / "etc/mvd-edge/edge.env").is_file())

    def test_templates_contain_no_production_secrets_or_fake_binaries(self):
        packaging_dir = ROOT / "packaging"
        forbidden = [
            "supabase_service_role",
            "RFID_INGEST_API_KEY=sk_",
            "RFID_INGEST_API_KEY=ey",
        ]

        for path in packaging_dir.rglob("*"):
            if not path.is_file():
                continue

            text = path.read_text(errors="ignore")
            for value in forbidden:
                self.assertNotIn(value, text, path)

        binary_like_files = [
            ROOT / "packaging/windows/service/MVDInsightsEdgeAgent.exe",
            ROOT / "packaging/usb/LINUX-X64/mvd-edge-agent",
            ROOT / "packaging/usb/LINUX-ARM64/mvd-edge-agent",
        ]
        for path in binary_like_files:
            self.assertFalse(path.exists(), path)

    def test_windows_scripts_reference_expected_locations_and_preserve_config(self):
        install_script = ROOT / "packaging/windows/scripts/install-service.ps1"
        uninstall_script = ROOT / "packaging/windows/scripts/uninstall-service.ps1"

        install_text = install_script.read_text()
        uninstall_text = uninstall_script.read_text()

        self.assertIn("$env:ProgramFiles", install_text)
        self.assertIn("$env:ProgramData", install_text)
        self.assertIn("MVD Insights\\Edge Agent", install_text)
        self.assertIn("Preserved existing config", install_text)
        self.assertIn("mvd-edge-agent.exe", install_text)
        self.assertIn("MVDInsightsEdgeAgent.exe", install_text)
        self.assertIn("--check-config", install_text)

        self.assertIn("$env:ProgramData", uninstall_text)
        self.assertIn("Preserved config/data/logs by default", uninstall_text)
        self.assertIn("Remove-Item -LiteralPath", uninstall_text)
        self.assertIn("[switch]$Purge", uninstall_text)

    def test_no_developer_machine_paths_in_installer_foundation(self):
        paths = [
            ROOT / "packaging",
            ROOT / "docs/COMMISSIONING_CHECKLIST.md",
        ]

        for base in paths:
            files = [base] if base.is_file() else list(base.rglob("*"))
            for path in files:
                if path.is_file():
                    self.assertNotIn("/Users/manishpareek", path.read_text(errors="ignore"), path)


if __name__ == "__main__":
    unittest.main()
