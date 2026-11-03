"""Probe behavior for non-HTTP workers, without broker or production state."""
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]


def services(path):
    return yaml.safe_load((ROOT / path).read_text())["services"]


class WorkerHealthTests(unittest.TestCase):
    def run_probe(self, test, argv):
        self.assertEqual(test[:2], ["CMD", "python"])
        with patch.object(Path, "read_bytes", return_value=b"\0".join(argv)):
            with self.assertRaises(SystemExit) as result:
                exec(test[3], {})
        return result.exception.code

    def test_beat_accepts_both_celery_entrypoints_and_rejects_other_processes(self):
        test = services("ops/trigger-crm/docker-compose.yml")["celery-beat"]["healthcheck"]["test"]
        for args in ([b"/usr/local/bin/celery", b"-A", b"crm", b"beat"],
                     [b"/usr/local/bin/python", b"/usr/local/bin/celery", b"-A", b"crm", b"beat"]):
            self.assertEqual(self.run_probe(test, args), 0)
        for args in ([b"python", b"other.py"], [b"celery", b"worker"], [b"notcelery", b"beat"]):
            self.assertEqual(self.run_probe(test, args), 1)

    def test_worker_ping_is_local_and_time_bounded(self):
        probe = services("ops/trigger-crm/docker-compose.yml")["celery-worker"]["healthcheck"]
        command = probe["test"][1]
        self.assertIn('--destination "celery@$$HOSTNAME"', command)
        self.assertIn("--timeout 5", command)
        self.assertGreater(int(probe["timeout"].removesuffix("s")), 5)


if __name__ == "__main__":
    unittest.main()
