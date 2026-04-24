from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.render_hyperframes import _inject_dynamic_scripts


class HyperFramesInjectTests(unittest.TestCase):
    def test_inject_dynamic_scripts_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            index = Path(tmp) / "index.html"
            index.write_text(
                "<html><body>\n"
                '    <script>\n      window.__timelines = {};\n    </script>\n'
                "</body></html>",
                encoding="utf-8",
            )
            _inject_dynamic_scripts(index)
            first = index.read_text(encoding="utf-8")
            _inject_dynamic_scripts(index)
            second = index.read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(first.count("logi_ad_data.js"), 1)
            self.assertEqual(first.count("dynamic-ad.js"), 1)


if __name__ == "__main__":
    unittest.main()
