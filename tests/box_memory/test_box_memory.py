"""Read-only capacity script: fake commands only, no Docker daemon or host probe."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "ops/box-memory.sh"

FREE = r'''#!/bin/bash
printf 'free %s\n' "$*" >> "$CALLS"
[[ "${FAIL_FREE:-}" != yes ]] || exit 7
printf '              total used free shared buff/cache available\n'
[[ "${BAD_FREE:-}" != yes ]] || exit 0
printf 'Mem:          10000 4000 1000 0 5000 6000\n'
printf 'Swap:         0 0 0\n'
'''

DOCKER = r'''#!/bin/bash
printf 'docker' >> "$CALLS"
printf ' %q' "$@" >> "$CALLS"
printf '\n' >> "$CALLS"
case "$1" in
  stats)
    [[ "$*" == 'stats --all --no-stream --format {{.ID}} {{.Name}} {{.MemUsage}}' ]] || exit 99
    [[ "${FAIL_STATS:-}" != yes ]] || exit 8
    [[ "${EMPTY_CONTAINERS:-}" != yes ]] || exit 0
    printf 'placeholder-a placeholder-running-a 512B / 2KiB\n'
    printf 'placeholder-b placeholder-stopped-b 0B / 4KiB\n'
    printf 'placeholder-c placeholder-running-c 1KiB / 0B\n'
    ;;
  inspect)
    [[ "$2" == --format && "$3" == '{{.State.Running}} {{.HostConfig.Memory}}' ]] || exit 99
    [[ "${FAIL_INSPECT:-}" != yes ]] || exit 9
    [[ "${BAD_LIMIT:-}" != yes ]] || { printf 'true placeholder-invalid\n'; exit 0; }
    case "$4" in
      placeholder-a) printf 'true 2048\n' ;;
      placeholder-b) printf 'false 4096\n' ;;
      placeholder-c) printf 'true 0\n' ;;
      *) exit 99 ;;
    esac
    ;;
  *) exit 99 ;;
esac
'''


class BoxMemoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="placeholder-box-memory-")
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)
        self.calls = self.path / "calls.txt"
        for name, text in (("free", FREE), ("docker", DOCKER)):
            target = self.path / name
            target.write_text(text)
            target.chmod(0o755)

    def report(self, **options):
        environment = {"PATH": str(self.path), "CALLS": str(self.calls), "LANG": "C", **options}
        result = subprocess.run([shutil.which("bash"), str(SCRIPT)], env=environment,
                                capture_output=True, text=True, timeout=10)
        calls = [shlex.split(line) for line in self.calls.read_text().splitlines()]
        return result, calls

    def test_host_bytes_running_usage_and_all_container_limit_sum(self):
        result, _ = self.report()
        self.assertEqual(result.returncode, 0, result.stderr)
        for line in ("host_memory_total_bytes=10000", "host_memory_used_bytes=4000",
                     "host_memory_available_bytes=6000", "container_count=3",
                     "running_container_count=2", "container_mem_limit_sum_bytes=6144",
                     "running_container_mem_limit_sum_bytes=2048", "unlimited_container_count=1",
                     "running_container=placeholder-running-a memory_usage=512B / 2KiB mem_limit_bytes=2048",
                     "running_container=placeholder-running-c memory_usage=1KiB / 0B mem_limit_bytes=0"):
            self.assertIn(line, result.stdout.splitlines())
        self.assertNotIn("placeholder-stopped-b", result.stdout)

    def test_no_other_external_or_docker_command_and_no_environment_inspection(self):
        result, calls = self.report()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(calls, [
            ["free", "-b"],
            ["docker", "stats", "--all", "--no-stream", "--format", "{{.ID}} {{.Name}} {{.MemUsage}}"],
            *[["docker", "inspect", "--format", "{{.State.Running}} {{.HostConfig.Memory}}", identity]
              for identity in ("placeholder-a", "placeholder-b", "placeholder-c")],
        ])
        self.assertNotIn("Env", result.stdout + repr(calls))

    def test_empty_docker_host_reports_zero_limits(self):
        result, calls = self.report(EMPTY_CONTAINERS="yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("container_mem_limit_sum_bytes=0\n", result.stdout)
        self.assertIn("running_container_count=0\n", result.stdout)
        self.assertIn("unlimited_container_count=0\n", result.stdout)
        self.assertEqual(len(calls), 2)

    def test_failed_free_stops_before_docker(self):
        result, calls = self.report(FAIL_FREE="yes")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(calls, [["free", "-b"]])

    def test_missing_mem_row_stops_before_docker(self):
        result, calls = self.report(BAD_FREE="yes")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(calls, [["free", "-b"]])

    def test_failed_stats_is_not_reported_as_an_empty_host(self):
        result, _ = self.report(FAIL_STATS="yes")
        self.assertEqual(result.returncode, 8)
        self.assertNotIn("container_mem_limit_sum_bytes", result.stdout)

    def test_failed_inspect_is_not_reported_as_zero_limit(self):
        result, _ = self.report(FAIL_INSPECT="yes")
        self.assertEqual(result.returncode, 9)
        self.assertNotIn("container_mem_limit_sum_bytes", result.stdout)

    def test_invalid_limit_is_refused(self):
        result, _ = self.report(BAD_LIMIT="yes")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("container_mem_limit_sum_bytes", result.stdout)


if __name__ == "__main__":
    unittest.main()
