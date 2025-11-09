import subprocess
import tempfile
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "btrfs_care"

class TestCLILogging(unittest.TestCase):
    def run_cli(self, fmt: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        try:
            subprocess.run(
                ["python3", str(SCRIPT), "--test-debug", "--log", str(tmp_path), "--log-format", fmt],
                cwd=REPO_ROOT,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return tmp_path

    def test_text_log_contains_data(self):
        log_path = self.run_cli("text")
        try:
            data = log_path.read_text()
            self.assertIn("Starting maintenance on /", data)
            self.assertIn("Metadata profile=", data)
            self.assertIn("WARNING / (UUID", data)
        finally:
            log_path.unlink(missing_ok=True)

    def test_json_log_contains_markers(self):
        log_path = self.run_cli("json")
        try:
            data = log_path.read_text()
            self.assertIn("JSON", data)
            self.assertIn("\"level\": \"WARNING\"", data)
        finally:
            log_path.unlink(missing_ok=True)

if __name__ == "__main__":
    unittest.main()
