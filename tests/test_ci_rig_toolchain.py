"""The real-conversion shard prepares locked tools; other shards do no setup."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("offline_rig_setup", ROOT / ".github/scripts/offline_suite.py")
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)


class RigToolchainSetupTests(unittest.TestCase):
    def test_other_shards_do_not_download_tools(self):
        with patch.dict(os.environ, {"CI_PREPARE_RIG_TOOLS": "1"}), patch.object(suite.subprocess, "run") as run:
            env = {"PATH": "/usr/bin"}
            suite.prepare_rig_tools(["tests/test_tiger.py"], env)
            run.assert_not_called()
            self.assertEqual(env["PATH"], "/usr/bin")

    def test_conversion_shard_uses_production_installer_and_locked_npm(self):
        with patch.dict(os.environ, {"CI_PREPARE_RIG_TOOLS": "1"}), patch.object(suite.subprocess, "run") as run:
            env = {"PATH": "/usr/bin"}
            suite.prepare_rig_tools(["tests/test_rig_r3d.py"], env)
            self.assertEqual(run.call_count, 2)
            self.assertIn(str(ROOT / "agents/rig/forge/install_tools.py"), run.call_args_list[0].args[0])
            self.assertIn("ci", run.call_args_list[1].args[0])
            self.assertIn("--ignore-scripts", run.call_args_list[1].args[0])
            self.assertTrue(all(call.kwargs["check"] for call in run.call_args_list))
            self.assertIn(str(ROOT / ".tmp/forge-tools/bin"), env["PATH"].split(os.pathsep))
            self.assertIn(str(ROOT / "agents/rig/forge/node_modules/.bin"), env["PATH"].split(os.pathsep))

    def test_failed_integrity_install_stops_before_tests(self):
        failure = subprocess.CalledProcessError(1, "installer")
        with patch.dict(os.environ, {"CI_PREPARE_RIG_TOOLS": "1"}), patch.object(suite.subprocess, "run", side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                suite.prepare_rig_tools(["tests/test_rig_r3d.py"], {"PATH": "/usr/bin"})

    def test_unsharded_ci_also_prepares_tools(self):
        with patch.dict(os.environ, {"CI_PREPARE_RIG_TOOLS": "1"}), patch.object(suite.subprocess, "run") as run:
            suite.prepare_rig_tools(["--ignore=tests/ci_security"], {"PATH": "/usr/bin"})
            self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
