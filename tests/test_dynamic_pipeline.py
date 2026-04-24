from __future__ import annotations

import unittest

from src.config import ImageGenerationConfig
from src.image_generation import (
    build_food_image_prompt,
    estimate_generation_cost,
    estimate_image_output_tokens,
)
from src.logi_client import build_scan_payload
from src.r2_uploader import build_public_url, build_r2_object_key, slugify_for_object_key


class ImagePromptTests(unittest.TestCase):
    def test_prompt_uses_dish_and_blocks_bad_ad_artifacts(self) -> None:
        prompt = build_food_image_prompt("burger with fries")
        self.assertIn("burger with fries", prompt)
        self.assertIn("photorealistic", prompt)
        self.assertIn("Avoid text", prompt)
        self.assertIn("watermarks", prompt)

    def test_cost_estimate_uses_high_portrait_image_tokens(self) -> None:
        config = ImageGenerationConfig()
        prompt = build_food_image_prompt("grilled chicken salad")
        estimate = estimate_generation_cost(prompt, config, variants=1)
        self.assertEqual(estimate_image_output_tokens("1024x1536", "high"), 6240)
        self.assertEqual(estimate.image_output_tokens, 6240)
        self.assertGreater(estimate.estimated_cost_usd, 0.18)
        self.assertLess(estimate.estimated_cost_usd, 0.25)


class R2KeyTests(unittest.TestCase):
    def test_object_key_is_stable_and_url_safe(self) -> None:
        self.assertEqual(slugify_for_object_key("Burger with fries!"), "burger-with-fries")
        key = build_r2_object_key(
            dish="Burger with fries!",
            cache_key="abc123",
            extension=".webp",
            key_prefix="logi-food-images",
        )
        self.assertEqual(key, "logi-food-images/burger-with-fries-abc123.webp")
        self.assertEqual(
            build_public_url("https://cdn.example.com/", key),
            "https://cdn.example.com/logi-food-images/burger-with-fries-abc123.webp",
        )


class LogiPayloadTests(unittest.TestCase):
    def test_image_url_payload_excludes_prompt(self) -> None:
        payload = build_scan_payload(
            prompt=None,
            image_url="https://cdn.example.com/meal.webp",
            language="en",
        )
        self.assertEqual(payload["image_url"], "https://cdn.example.com/meal.webp")
        self.assertNotIn("prompt", payload)


if __name__ == "__main__":
    unittest.main()
