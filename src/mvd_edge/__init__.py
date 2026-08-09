"""MVD Insights Edge Agent."""

from importlib import metadata
from pathlib import Path
import re


def _version_from_pyproject() -> str:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"

    if pyproject.exists():
        match = re.search(
            r'^version\s*=\s*"([^"]+)"',
            pyproject.read_text(),
            re.MULTILINE,
        )

        if match:
            return match.group(1)

    return "0+unknown"


try:
    __version__ = metadata.version("mvd-insights-edge-agent")
except metadata.PackageNotFoundError:
    __version__ = _version_from_pyproject()
