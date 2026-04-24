"""Shared LOGI HTML transforms for Playwright (scroll) and HyperFrames (GSAP timeline)."""

from __future__ import annotations

import re

from .errors import PipelineError


def apply_logi_markup_transforms(template_source: str) -> str:
    """Apply Jinja-friendly markup and motion hooks to raw tamplate.html (no scripts)."""
    ingredient_block = """                <div class="ingredient-item">
                    <div class="ing-thumb" style="background-image: url('{{ ing_thumbnail }}');"></div>
                    <div class="ing-info">
                        <div class="ing-name">{{ ing_name }}</div>
                        <div class="ing-cat">{{ ing_category }}</div>
                        <div class="ing-badges">
                            <span class="badge badge-neutral">~ {{ ing_weight }} g</span>
                            <span class="badge badge-green">GI: 0</span>
                            <span class="badge badge-green">GL: 0</span>
                        </div>
                    </div>
                </div>"""
    ingredient_loop = """                {% for ingredient in ingredients %}
                <div class="ingredient-item" data-motion-target="ingredient-row" data-ingredient-name="{{ ingredient.name }}" data-ingredient-index="{{ loop.index0 }}">
                    <div class="ing-thumb" data-motion-target="ingredient-thumb">
                        {% if ingredient.thumbnail_url %}
                        <img src="{{ ingredient.thumbnail_url }}" alt="" loading="eager" decoding="async" referrerpolicy="no-referrer-when-downgrade" />
                        {% else %}
                        <img src="{{ placeholder_asset }}" alt="" loading="eager" decoding="async" />
                        {% endif %}
                    </div>
                    <div class="ing-info">
                        <div class="ing-name" data-motion-target="ingredient-name">{{ ingredient.name }}</div>
                        {% if ingredient.category %}
                        <div class="ing-cat" data-motion-target="ingredient-category">{{ ingredient.category }}</div>
                        {% endif %}
                        <div class="ing-badges" data-motion-target="ingredient-badges">
                            {% if ingredient.weight_display %}
                            <span class="badge badge-neutral" data-motion-target="ingredient-badge" data-badge-kind="weight">~ {{ ingredient.weight_display }} g</span>
                            {% endif %}
                            {% if ingredient.glycemic_index_label %}
                            <span class="badge badge-green" data-motion-target="ingredient-badge" data-badge-kind="gi">GI: {{ ingredient.glycemic_index_label }}</span>
                            {% endif %}
                        </div>
                    </div>
                </div>
                {% endfor %}"""

    risk_block = """                    <span class="badge badge-red">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M4 15V4M4 15L11.5858 7.41421C12.3668 6.63316 13.6332 6.63317 14.4142 7.41421L15.5858 8.58579C16.3668 9.36683 17.6332 9.36684 18.4142 8.58579L20 7V17.5858L18.4142 19.1716C17.6332 19.9526 16.3668 19.9526 15.5858 19.1716L14.4142 18.0001C13.6332 17.219 12.3668 17.219 11.5858 18.0001L4 25.5858V15ZM4 15H11.5858C12.3668 15 13.6332 15 14.4142 14.219L15.5858 13.0474C16.3668 12.2663 17.6332 12.2663 18.4142 13.0474L20 14.6332" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        {{ risk_name }}
                    </span>"""
    risk_loop = """                    {% for risk in risks %}
                    <span class="badge badge-red" data-motion-target="risk-badge" data-risk-index="{{ loop.index0 }}">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M4 15V4M4 15L11.5858 7.41421C12.3668 6.63316 13.6332 6.63317 14.4142 7.41421L15.5858 8.58579C16.3668 9.36683 17.6332 9.36684 18.4142 8.58579L20 7V17.5858L18.4142 19.1716C17.6332 19.9526 16.3668 19.9526 15.5858 19.1716L14.4142 18.0001C13.6332 17.219 12.3668 17.219 11.5858 18.0001L4 25.5858V15ZM4 15H11.5858C12.3668 15 13.6332 15 14.4142 14.219L15.5858 13.0474C16.3668 12.2663 17.6332 12.2663 18.4142 13.0474L20 14.6332" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        {{ risk }}
                    </span>
                    {% endfor %}"""
    motion_css = """
        /* filter w will-change + background na dzieciach przy scrollu transform = miganie w Chrome/HyperFrames */
        .video-canvas {
            position: relative;
            transform-origin: top center;
            will-change: transform;
        }
        .motion-section,
        [data-motion-group] {
            will-change: transform, opacity;
            backface-visibility: hidden;
            transform-origin: center center;
        }
        [data-motion-target]:not(.ing-thumb) {
            will-change: transform, opacity;
            backface-visibility: hidden;
            transform-origin: center center;
        }
        .motion-section { isolation: isolate; }
        .gl-box, .cal-box, .ingredient-item, .insight-text, .badge { transform-origin: center center; }
        .ing-thumb {
            overflow: hidden;
            contain: strict;
            background-color: var(--color-bg);
        }
        .ing-thumb img {
            display: block;
            width: 100%;
            height: 100%;
            object-fit: cover;
            transform: translateZ(0);
            -webkit-backface-visibility: hidden;
            backface-visibility: hidden;
        }
    """

    transformed = template_source
    transformed = transformed.replace('<html lang="pl">', '<html lang="en">', 1)
    transformed = transformed.replace("<header class=\"app-header\">", "<header class=\"app-header motion-section\" data-section-id=\"header\" data-motion-section=\"header\">", 1)
    transformed = transformed.replace("<section class=\"meal-intro\">", "<section class=\"meal-intro motion-section\" data-section-id=\"meal_intro\" data-motion-section=\"meal_intro\">", 1)
    transformed = transformed.replace("<section class=\"card\">", "<section class=\"card motion-section\" data-section-id=\"nutrition\" data-motion-section=\"nutrition\">", 1)
    transformed = transformed.replace("<section class=\"card\">", "<section class=\"card motion-section\" data-section-id=\"ingredients\" data-motion-section=\"ingredients\">", 1)
    transformed = transformed.replace("<section class=\"card\">", "<section class=\"card motion-section\" data-section-id=\"insights\" data-motion-section=\"insights\">", 1)
    transformed = transformed.replace("<div class=\"video-canvas\">", "<div class=\"video-canvas\" data-motion-root=\"canvas\">", 1)
    transformed = transformed.replace("<span class=\"greeting-text\">", "<span class=\"greeting-text\" data-motion-target=\"header_title\">", 1)
    transformed = transformed.replace("<h1 class=\"meal-title\">", "<h1 class=\"meal-title\" data-motion-target=\"meal_title\">", 1)
    transformed = transformed.replace("<p class=\"meal-desc\">{{ mealDescription }}</p>", "<p class=\"meal-desc\" data-motion-target=\"meal_description\">{{ mealDescription }}</p>", 1)
    transformed = re.sub(r'<h2 class="card-header">', '<h2 class="card-header" data-motion-target="section_heading">', transformed)
    transformed = transformed.replace("<div class=\"top-stats\">", "<div class=\"top-stats\" data-motion-group=\"nutrition_stats\">", 1)
    transformed = transformed.replace("<div class=\"gl-box\">", "<div class=\"gl-box\" data-motion-target=\"glycemic_load\">", 1)
    transformed = transformed.replace("<div class=\"cal-box\">", "<div class=\"cal-box\" data-motion-target=\"calories\">", 1)
    transformed = transformed.replace("<span class=\"gl-value\">", "<span class=\"gl-value\" data-motion-target=\"glycemic_load_value\">", 1)
    transformed = transformed.replace("<span class=\"cal-value\">", "<span class=\"cal-value\" data-motion-target=\"calories_value\">", 1)
    transformed = transformed.replace("<div class=\"macro-row\">", "<div class=\"macro-row\" data-motion-target=\"macro_row\">", 3)
    transformed = transformed.replace(ingredient_block, ingredient_loop, 1)
    transformed = transformed.replace(risk_block, risk_loop, 1)
    transformed = transformed.replace(
        "<div class=\"ingredient-item\">",
        "<div class=\"ingredient-item\" data-motion-target=\"ingredient-row\" data-ingredient-name=\"{{ ing.name }}\" data-ingredient-index=\"{{ loop.index0 }}\">",
    )
    transformed = transformed.replace("<div class=\"ing-thumb\"", "<div class=\"ing-thumb\" data-motion-target=\"ingredient-thumb\"", 1)
    transformed = transformed.replace("<div class=\"ing-name\">", "<div class=\"ing-name\" data-motion-target=\"ingredient-name\">")
    transformed = transformed.replace("<div class=\"ing-cat\">", "<div class=\"ing-cat\" data-motion-target=\"ingredient-category\">")
    transformed = transformed.replace("<div class=\"ing-badges\">", "<div class=\"ing-badges\" data-motion-target=\"ingredient-badges\">")
    transformed = transformed.replace("<span class=\"badge badge-neutral\">", "<span class=\"badge badge-neutral\" data-motion-target=\"ingredient-badge\" data-badge-kind=\"weight\">")
    transformed = transformed.replace("<span class=\"badge badge-green\">GI:", "<span class=\"badge badge-green\" data-motion-target=\"ingredient-badge\" data-badge-kind=\"gi\">GI:")
    transformed = transformed.replace("<span class=\"badge badge-green\">GL:", "<span class=\"badge badge-green\" data-motion-target=\"ingredient-badge\" data-badge-kind=\"gl\">GL:")
    transformed = transformed.replace(
        "<p class=\"meal-desc\" data-motion-target=\"meal_description\">{{ mealDescription }}</p>",
        "{% if mealDescription %}<p class=\"meal-desc\" data-motion-target=\"meal_description\">{{ mealDescription }}</p>{% endif %}",
        1,
    )
    transformed = transformed.replace("<div class=\"macro-row sub-row\">", "<div class=\"macro-row sub-row\" data-motion-target=\"sugars\">", 1)
    transformed = transformed.replace("<div class=\"macro-row sub-row\">", "<div class=\"macro-row sub-row\" data-motion-target=\"saturated\">", 1)
    transformed = transformed.replace(
        "<div class=\"macro-row sub-row\">\n                        <span class=\"macro-name\">Natural sugars</span>\n                        <span class=\"macro-val\">{{ total_sugars }}<span class=\"unit\">g</span></span>\n                    </div>",
        "{% if total_sugars %}<div class=\"macro-row sub-row\" data-motion-target=\"sugars\">\n                        <span class=\"macro-name\">Natural sugars</span>\n                        <span class=\"macro-val\">{{ total_sugars }}<span class=\"unit\">g</span></span>\n                    </div>{% endif %}",
        1,
    )
    transformed = transformed.replace(
        "<div class=\"macro-row sub-row\">\n                        <span class=\"macro-name\">Saturated</span>\n                        <span class=\"macro-val\">{{ total_saturated }}<span class=\"unit\">g</span></span>\n                    </div>",
        "{% if total_saturated %}<div class=\"macro-row sub-row\" data-motion-target=\"saturated\">\n                        <span class=\"macro-name\">Saturated</span>\n                        <span class=\"macro-val\">{{ total_saturated }}<span class=\"unit\">g</span></span>\n                    </div>{% endif %}",
        1,
    )
    transformed = transformed.replace(
        "<p class=\"insight-text\">{{ opinion_text }}</p>",
        "{% for opinion in opinions %}<p class=\"insight-text\" data-motion-target=\"insight-paragraph\" data-insight-index=\"{{ loop.index0 }}\">{{ opinion }}</p>{% endfor %}",
        1,
    )
    transformed = transformed.replace(
        "<p class=\"insight-text\">{{ opinion }}</p>",
        "<p class=\"insight-text\" data-motion-target=\"insight-paragraph\" data-insight-index=\"{{ loop.index0 }}\">{{ opinion }}</p>",
    )
    transformed = transformed.replace(
        "                <h3 class=\"risks-title\">Potential risks</h3>\n                <div class=\"risks-container\">",
        "                {% if risks %}<h3 class=\"risks-title\">Potential risks</h3>\n                <div class=\"risks-container\" data-motion-target=\"risks_container\">",
        1,
    )
    transformed = transformed.replace(
        "<span class=\"badge badge-red\">",
        "<span class=\"badge badge-red\" data-motion-target=\"risk-badge\" data-risk-index=\"{{ loop.index0 }}\">",
    )
    transformed = transformed.replace(
        "                    </div>\n            </section>",
        "                    </div>{% endif %}\n            </section>",
        1,
    )
    macro_targets = {
        "Carbohydrates": "carbohydrates",
        "Fats": "fat",
        "Protein": "protein",
    }
    for label, target in macro_targets.items():
        transformed = transformed.replace(
            f"<div class=\"macro-row\" data-motion-target=\"macro_row\">\n                    <span class=\"macro-name\">{label}</span>",
            f"<div class=\"macro-row\" data-motion-target=\"{target}\">\n                    <span class=\"macro-name\">{label}</span>",
            1,
        )
    transformed = transformed.replace("</style>", motion_css + "\n</style>", 1)
    return transformed


def inject_playwright_scripts(transformed: str) -> str:
    body_script = """    <script>
        window.__VIDEO_SCRIPT__ = {{ video_script_json | safe }};
        window.__VIDEO_READY__ = false;
    </script>
    <script src="gsap.min.js"></script>
    <script src="scroll_driver.js"></script>
"""
    out, n = re.subn(r"(?is)\s*</body>", body_script.rstrip() + "\n</body>", transformed, count=1)
    if n != 1:
        raise PipelineError(
            "could not inject video scripts — missing </body> in template (tamplate.html)",
            code=40,
            step="render",
        )
    return out


def inject_hyperframes_wrapper_and_scripts(transformed: str) -> str:
    """Wrap canvas in HyperFrames root and register a GSAP timeline (scroll simulation)."""
    transformed = transformed.replace("<body>", '<body style="overflow:hidden;margin:0;">', 1)
    transformed = transformed.replace(
        '<div class="video-canvas" data-motion-root="canvas">',
        """<div id="hf-root" data-composition-id="{{ hf_composition_id }}" data-width="{{ hf_width }}" data-height="{{ hf_height }}" data-start="0" data-duration="{{ hf_composition_duration }}" data-track-index="0">
    <div class="video-canvas" data-motion-root="canvas">""",
        1,
    )
    out, n = re.subn(
        r"(\s*</div>)\s*\r?\n\s*</body>",
        r"\1\n    </div>\n</body>",
        transformed,
        count=1,
    )
    if n != 1:
        raise PipelineError(
            "could not wrap HyperFrames root — unexpected </body> structure in template",
            code=40,
            step="render",
        )
    hf_script = r"""    <script src="assets/gsap.min.js"></script>
    <script>
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true });
      const canvas = document.querySelector('[data-motion-root="canvas"]');
      const viewport = {{ hf_height }};
      const maxY = Math.max(0, (canvas ? canvas.scrollHeight : 0) - viewport);
      const dur = {{ hf_gsap_duration }};
      if (canvas) {
        tl.to(canvas, { y: -maxY, duration: dur, ease: "none", force3D: true }, 0);
      }
      window.__timelines["{{ hf_composition_id }}"] = tl;
    </script>
"""
    out2, n2 = re.subn(r"(?is)\s*</body>", hf_script.rstrip() + "\n</body>", out, count=1)
    if n2 != 1:
        raise PipelineError(
            "could not inject HyperFrames scripts — missing </body> in template",
            code=40,
            step="render",
        )
    return out2


def build_playwright_runtime_template(template_source: str) -> str:
    t = apply_logi_markup_transforms(template_source)
    return inject_playwright_scripts(t)


def build_hyperframes_runtime_template(template_source: str) -> str:
    t = apply_logi_markup_transforms(template_source)
    return inject_hyperframes_wrapper_and_scripts(t)
