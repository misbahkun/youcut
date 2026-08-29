import re
import unittest
from pathlib import Path


PRICING_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "pricing.html"


class PricingScrollLifecycleTest(unittest.TestCase):
    def test_terminal_snap_callbacks_restore_body_inline_style(self):
        # Given: the JavaScript source for the pricing checkout flow.
        pricing_source = PRICING_TEMPLATE.read_text(encoding="utf-8")

        # When: the lifecycle code local to the Snap payment invocation is extracted.
        snap_block_match = re.search(
            r"if\s*\(\s*purchaseModal\s*\)\s*\{.*?"
            r"window\.snap\.pay\s*\(.*?\n\s*\}\s*\);",
            pricing_source,
            re.DOTALL,
        )
        self.assertIsNotNone(snap_block_match, "Snap payment lifecycle block was not found")
        snap_block = snap_block_match.group(0)
        modal_flow_match = re.search(
            r"function\s+openPurchaseModal\s*\([^)]*\)\s*\{.*?"
            r"purchaseModal\.show\s*\(\s*\)\s*;",
            pricing_source,
            re.DOTALL,
        )
        self.assertIsNotNone(modal_flow_match, "Purchase modal lifecycle was not found")
        snapshot_match = re.search(
            r"\b(?P<snapshot>[A-Za-z_$][\w$]*)\s*=\s*"
            r"document\.body\.style\.cssText\s*;",
            modal_flow_match.group(0),
        )

        # Then: one restoration helper uses that snapshot and every terminal callback invokes it.
        self.assertIsNotNone(
            snapshot_match,
            "Snap lifecycle must snapshot document.body.style.cssText before the modal locks it",
        )
        snapshot_name = snapshot_match.group("snapshot")
        helper_pattern = re.compile(
            r"(?:function\s+(?P<function_name>[A-Za-z_$][\w$]*)\s*\(\s*\)"
            r"|(?:const|let)\s+(?P<arrow_name>[A-Za-z_$][\w$]*)\s*=\s*"
            r"\(\s*\)\s*=>)\s*\{(?P<body>.*?)\}",
            re.DOTALL,
        )
        restoration_pattern = re.compile(
            rf"document\.body\.style\.cssText\s*=\s*{re.escape(snapshot_name)}\s*;"
        )
        helpers = [
            match
            for match in helper_pattern.finditer(snap_block)
            if restoration_pattern.search(match.group("body"))
        ]
        self.assertEqual(len(helpers), 1, "Snap lifecycle must define one restoration helper")
        helper = helpers[0]
        helper_name = helper.group("function_name") or helper.group("arrow_name")

        callbacks = {
            match.group("name"): match.group("body")
            for match in re.finditer(
                r"on(?P<name>Success|Pending|Error|Close)\s*:\s*"
                r"function\s*\([^)]*\)\s*\{(?P<body>.*?)\}\s*(?:,|(?=\s*\}))",
                snap_block,
                re.DOTALL,
            )
        }
        self.assertEqual(set(callbacks), {"Success", "Pending", "Error", "Close"})
        for callback_name, callback_body in callbacks.items():
            with self.subTest(callback=callback_name):
                self.assertRegex(
                    callback_body,
                    rf"\b{re.escape(helper_name)}\s*\(\s*\)\s*;",
                    f"on{callback_name} must restore the pre-Snap body inline style",
                )


if __name__ == "__main__":
    unittest.main()
