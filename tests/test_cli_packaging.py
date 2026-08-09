import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mvd_edge import __version__
from mvd_edge.app import main
from mvd_edge.config import EdgeConfig
from mvd_edge.storage.queue import EventQueue


def write_config(path: Path, **overrides) -> None:
    values = {
        "RFID_API_URL": "https://api.example.test/api/v1/rfid/events",
        "RFID_INGEST_API_KEY": "super-secret-test-key",
        "DEVICE_ID": "EXP-CENTER-EDGE-01",
        "READER_ID": "LAB-RFID-01",
        "SERIAL_PORT": "AUTO",
        "EDGE_DATA_DIR": str(path.parent / "data"),
    }
    values.update(overrides)
    path.write_text(
        "\n".join(
            f"{key}={value}"
            for key, value in values.items()
        )
    )


class CliPackagingTests(unittest.TestCase):
    def run_cli(self, args, env):
        output = io.StringIO()

        with patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
            code = main(args)

        return code, output.getvalue()

    def test_version_prints_authoritative_version(self):
        code, output = self.run_cli(["--version"], {})

        self.assertEqual(code, 0)
        self.assertIn(f"MVD Insights Edge Agent {__version__}", output)
        self.assertIn("Python:", output)

    def test_check_config_succeeds_with_valid_config_and_hides_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "edge.env"
            write_config(config_path)

            code, output = self.run_cli(
                ["--check-config"],
                {"MVD_EDGE_CONFIG": str(config_path)},
            )

        self.assertEqual(code, 0)
        self.assertIn("VALID", output)
        self.assertIn("API Key: configured", output)
        self.assertNotIn("super-secret-test-key", output)

    def test_check_config_rejects_missing_required_config(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "edge.env"
            write_config(config_path, RFID_API_URL="")

            code, output = self.run_cli(
                ["--check-config"],
                {"MVD_EDGE_CONFIG": str(config_path)},
            )

        self.assertEqual(code, 1)
        self.assertIn("INVALID", output)

    def test_mvd_edge_config_path_is_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "custom.env"
            write_config(config_path, DEVICE_ID="CUSTOM-EDGE-01")

            config = EdgeConfig.from_env(env_file=config_path)

        self.assertEqual(config.device_id, "CUSTOM-EDGE-01")

    def test_check_config_works_outside_project_root(self):
        original_cwd = Path.cwd()

        with tempfile.TemporaryDirectory() as directory:
            workdir = Path(directory) / "elsewhere"
            workdir.mkdir()
            config_path = Path(directory) / "edge.env"
            write_config(config_path)

            try:
                os.chdir(workdir)
                code, output = self.run_cli(
                    ["--check-config"],
                    {"MVD_EDGE_CONFIG": str(config_path)},
                )
            finally:
                os.chdir(original_cwd)

        self.assertEqual(code, 0)
        self.assertIn("VALID", output)

    def test_external_edge_data_dir_initializes_sqlite_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory) / "external-data"
            config_path = Path(directory) / "edge.env"
            write_config(config_path, EDGE_DATA_DIR=str(data_dir))
            config = EdgeConfig.from_env(env_file=config_path)
            queue = EventQueue(config.edge_data_dir / "events.sqlite3")

            try:
                self.assertTrue((data_dir / "events.sqlite3").exists())
                self.assertEqual(queue.pending_count(), 0)
            finally:
                queue.close()

    def test_no_developer_absolute_path_in_runtime_defaults(self):
        source_files = [
            Path("src/mvd_edge/config.py"),
            Path(".env.example"),
            Path("packaging/config/edge-agent.env.example"),
            Path("packaging/linux/config/edge.env.example"),
            Path("packaging/linux/systemd/mvd-edge.service"),
            Path("packaging/windows/service/MVDInsightsEdgeAgent.xml"),
        ]

        for source_file in source_files:
            self.assertNotIn(
                "/Users/manishpareek",
                source_file.read_text(),
                source_file,
            )


if __name__ == "__main__":
    unittest.main()
