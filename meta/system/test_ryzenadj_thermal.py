"""Cooling cap regression checks using a fake SMU; never changes host limits."""

import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).with_name("ryzenadj-thermal")


class ThermalCapTests(unittest.TestCase):
    def run_helper(self, limits, read_status=0):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = root / "limits.txt"
            fixture.write_text(
                "CPU Family: Cezanne\n"
                + "\n".join(
                    f"| {name} | {value} | parameter |"
                    for name, value in limits.items()
                )
                + "\n"
            )
            calls = root / "calls.jsonl"
            fake = root / "ryzenadj"
            fake.write_text(
                "#!/usr/bin/python3\n"
                "import json, os, pathlib, sys\n"
                "if sys.argv[1:] == ['--info']:\n"
                "    print(pathlib.Path(os.environ['LIMIT_FIXTURE']).read_text())\n"
                "    sys.exit(int(os.environ['READ_STATUS']))\n"
                "with open(os.environ['LIMIT_CALLS'], 'a') as output:\n"
                "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            )
            fake.chmod(0o755)
            helper = root / "ryzenadj-thermal"
            helper.write_text(
                SOURCE.read_text().replace(
                    "ryzenadj=/usr/bin/ryzenadj", f"ryzenadj={shlex.quote(str(fake))}"
                )
            )
            environment = {
                **os.environ,
                "LIMIT_FIXTURE": str(fixture),
                "LIMIT_CALLS": str(calls),
                "READ_STATUS": str(read_status),
            }
            result = subprocess.run(
                ["bash", str(helper)],
                check=False,
                env=environment,
                capture_output=True,
                text=True,
            )
            writes = (
                [json.loads(line) for line in calls.read_text().splitlines()]
                if calls.exists()
                else []
            )
            return result, writes

    def firmware_limits(self):
        return {
            "STAPM LIMIT": "45.000",
            "PPT LIMIT FAST": "65.000",
            "PPT LIMIT SLOW": "54.000",
            "THM LIMIT CORE": "95.000",
        }

    def test_caps_high_firmware_limits(self):
        result, writes = self.run_helper(self.firmware_limits())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(writes), 1)
        self.assertCountEqual(
            writes[0],
            [
                "--stapm-limit=40000",
                "--fast-limit=55000",
                "--slow-limit=45000",
                "--tctl-temp=90",
            ],
        )

    def test_preserves_lower_power_and_temperature_limits(self):
        limits = dict.fromkeys(self.firmware_limits(), "35.000")
        limits["THM LIMIT CORE"] = "85.000"
        result, writes = self.run_helper(limits)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(writes, [])

    def test_only_caps_values_above_their_ceilings(self):
        limits = self.firmware_limits()
        limits["STAPM LIMIT"] = "30.000"
        limits["PPT LIMIT SLOW"] = "38.000"
        result, writes = self.run_helper(limits)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(writes), 1)
        self.assertCountEqual(writes[0], ["--fast-limit=55000", "--tctl-temp=90"])

    def test_does_not_rewrite_unchanged_limits(self):
        limits = dict(
            zip(self.firmware_limits(), ["40.000", "55.000", "45.000", "90.000"])
        )
        result, writes = self.run_helper(limits)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(writes, [])

    def test_missing_metric_fails_without_writing(self):
        limits = self.firmware_limits()
        del limits["PPT LIMIT SLOW"]
        result, writes = self.run_helper(limits)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PPT LIMIT SLOW", result.stderr)
        self.assertEqual(writes, [])

    def test_invalid_metric_fails_without_writing(self):
        limits = self.firmware_limits()
        limits["PPT LIMIT FAST"] = "N/A"
        result, writes = self.run_helper(limits)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PPT LIMIT FAST", result.stderr)
        self.assertEqual(writes, [])

    def test_failed_read_does_not_write(self):
        result, writes = self.run_helper(self.firmware_limits(), read_status=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(writes, [])


if __name__ == "__main__":
    unittest.main()
