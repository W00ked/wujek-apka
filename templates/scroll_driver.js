(function () {
  function sleep(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function normalizeToken(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .replace(/^_+|_+$/g, "");
  }

  function buildRuntimeSegments(videoScript) {
    const segments = Array.isArray(videoScript?.segments) ? videoScript.segments : [];
    const totalMs = segments.reduce((sum, item) => sum + Number(item.duration_sec || 0) * 1000, 0);
    const targetMs = Number(videoScript?.target_ui_duration_sec || 0) * 1000;
    const configuredEndHoldMs = Math.max(0, Number(videoScript?.end_hold_sec || 0) * 1000);
    const endHoldMs = targetMs > 0 ? Math.min(configuredEndHoldMs, targetMs) : configuredEndHoldMs;
    const budgetMs = targetMs > 0 ? Math.max(0, targetMs - endHoldMs) : totalMs;
    const scale = totalMs > 0 && budgetMs > 0 ? budgetMs / totalMs : 1;

    const runtimeSegments = segments.map((segment, index) => {
      const durationMs = Math.max(500, Number(segment.duration_sec || 0) * scale * 1000);
      const pauseMs = clamp(Number(segment.pause_after_sec || 0) * scale * 1000, 180, Math.max(180, durationMs * 0.42));
      const moveMs = index === 0 ? Math.max(220, durationMs * 0.28) : Math.max(260, durationMs - pauseMs);
      const microCues = Array.isArray(segment.micro_cues)
        ? segment.micro_cues.map((cue) => ({
            type: cue.type,
            target: cue.target,
            offsetMs: clamp(Number(cue.offset_sec || 0) * scale * 1000, 0, Math.max(0, durationMs - 120)),
          }))
        : [];
      return {
        index,
        sectionId: segment.section_id,
        visualStyle: segment.visual_style || "default",
        cameraMode: segment.camera_mode || "smooth",
        emphasisTargets: Array.isArray(segment.emphasis_targets) ? segment.emphasis_targets : [],
        durationMs,
        moveMs,
        pauseMs: Math.max(160, durationMs - moveMs),
        microCues,
      };
    });
    return { runtimeSegments, endHoldMs };
  }

  function getCanvas() {
    return document.querySelector('[data-motion-root="canvas"]');
  }

  function getSection(sectionId) {
    return document.querySelector(`[data-section-id="${sectionId}"]`);
  }

  function getTargetY(node, topOffset) {
    const maxScrollY = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
    return clamp(node.getBoundingClientRect().top + window.scrollY - topOffset, 0, maxScrollY);
  }

  function createScrollTween(section, topOffset, durationMs, easeName) {
    const state = { progress: 0, startY: 0, endY: 0 };
    const tl = window.gsap.timeline();
    tl.call(() => {
      state.progress = 0;
      state.startY = window.scrollY;
      state.endY = section ? getTargetY(section, topOffset) : window.scrollY;
    });
    tl.to(state, {
      progress: 1,
      duration: Math.max(0.16, durationMs / 1000),
      ease: easeName || "power2.inOut",
      immediateRender: false,
      onUpdate() {
        const nextY = state.startY + (state.endY - state.startY) * state.progress;
        window.scrollTo(0, nextY);
      },
    });
    return tl;
  }

  function getElementsForSection(section) {
    if (!section) {
      return {};
    }
    return {
      heading: section.querySelector('[data-motion-target="section_heading"]'),
      stats: Array.from(
        section.querySelectorAll('[data-motion-target="glycemic_load"], [data-motion-target="calories"]')
      ),
      macros: Array.from(
        section.querySelectorAll(
          '[data-motion-target="carbohydrates"], [data-motion-target="sugars"], [data-motion-target="fat"], [data-motion-target="saturated"], [data-motion-target="protein"]'
        )
      ),
      ingredients: Array.from(section.querySelectorAll('[data-motion-target="ingredient-row"]')),
      insights: Array.from(section.querySelectorAll('[data-motion-target="insight-paragraph"]')),
      risks: Array.from(section.querySelectorAll('[data-motion-target="risk-badge"]')),
    };
  }

  function resetMotionElement(node) {
    if (!node) {
      return;
    }
    window.gsap.set(node, {
      clearProps: "transform,opacity,filter,backgroundColor,boxShadow,x,y,scale,autoAlpha",
      autoAlpha: 1,
      x: 0,
      y: 0,
      scale: 1,
    });
  }

  function initializeMotionState(runtimeSegments) {
    window.scrollTo(0, 0);
    resetMotionElement(getCanvas());

    runtimeSegments.forEach((segment) => {
      const section = getSection(segment.sectionId);
      if (!section) {
        return;
      }
      resetMotionElement(section);
      const elements = getElementsForSection(section);
      [
        elements.heading,
        ...(elements.stats || []),
        ...(elements.macros || []),
        ...(elements.ingredients || []),
        ...(elements.insights || []),
        ...(elements.risks || []),
      ].forEach(resetMotionElement);
    });
  }

  function resolveTarget(target) {
    if (!target) {
      return null;
    }
    if (target === "canvas") {
      return getCanvas();
    }
    if (["header", "meal_intro", "nutrition", "ingredients", "insights"].includes(target)) {
      return getSection(target);
    }
    if (target.startsWith("ingredient:")) {
      const nameToken = normalizeToken(target.split(":").slice(1).join(":"));
      return Array.from(document.querySelectorAll('[data-motion-target="ingredient-row"]')).find((node) => {
        return normalizeToken(node.dataset.ingredientName) === nameToken;
      }) || null;
    }
    if (target.startsWith("insight:")) {
      const index = target.split(":")[1];
      return document.querySelector(`[data-motion-target="insight-paragraph"][data-insight-index="${index}"]`);
    }
    if (target.startsWith("risk:")) {
      const index = target.split(":")[1];
      return document.querySelector(`[data-motion-target="risk-badge"][data-risk-index="${index}"]`);
    }
    return document.querySelector(`[data-motion-target="${target}"]`);
  }

  function cameraPunchIn(root, amount) {
    const target = root || getCanvas();
    if (!target) {
      return window.gsap.timeline();
    }
    return window.gsap
      .timeline()
      .to(target, { scale: amount || 1.018, duration: 0.18, ease: "power2.out" })
      .to(target, { scale: 1, duration: 0.32, ease: "power2.inOut" });
  }

  function sectionReveal(section) {
    if (!section) {
      return window.gsap.timeline();
    }
    const tl = window.gsap.timeline();
    const elements = getElementsForSection(section);
    tl.set(section, { autoAlpha: 1 });
    if (elements.heading) {
      tl.fromTo(
        elements.heading,
        { autoAlpha: 0.6, y: 10 },
        { autoAlpha: 1, y: 0, duration: 0.24, ease: "power2.out", immediateRender: false },
        0
      );
    }
    if (elements.stats.length) {
      tl.fromTo(
        elements.stats,
        { autoAlpha: 0.78, y: 12, scale: 0.985 },
        { autoAlpha: 1, y: 0, scale: 1, duration: 0.22, stagger: 0.16, ease: "power2.out", immediateRender: false },
        0.08
      );
    }
    return tl;
  }

  function statPulse(target) {
    if (!target) {
      return window.gsap.timeline();
    }
    return window.gsap
      .timeline()
      .to(target, {
        scale: 1.045,
        y: -4,
        duration: 0.16,
        ease: "power2.out",
        boxShadow: "0 16px 34px rgba(30, 58, 36, 0.18)",
      })
      .to(target, { scale: 1, y: 0, duration: 0.28, ease: "power2.inOut", boxShadow: "0 8px 32px rgba(0,0,0,0.02)" });
  }

  function ingredientStagger(section) {
    const items = section ? Array.from(section.querySelectorAll('[data-motion-target="ingredient-row"]')) : [];
    if (!items.length) {
      return window.gsap.timeline();
    }
    return window.gsap.timeline().fromTo(
      items,
      { autoAlpha: 0.45, y: 26, scale: 0.986 },
      { autoAlpha: 1, y: 0, scale: 1, duration: 0.28, stagger: 0.08, ease: "power2.out", immediateRender: false }
    );
  }

  function ingredientFocus(target) {
    if (!target) {
      return window.gsap.timeline();
    }
    const badges = Array.from(target.querySelectorAll('[data-motion-target="ingredient-badge"]'));
    const tl = window.gsap.timeline();
    tl.to(target, { scale: 1.02, y: -6, duration: 0.18, ease: "power2.out" }).to(
      target,
      { scale: 1, y: 0, duration: 0.28, ease: "power2.inOut" }
    );
    if (badges.length) {
      tl.fromTo(
        badges,
        { scale: 0.92, autoAlpha: 0.72 },
        { scale: 1, autoAlpha: 1, duration: 0.18, stagger: 0.05, ease: "back.out(2)", immediateRender: false },
        0.02
      );
    }
    return tl;
  }

  function insightSpotlight(target) {
    if (!target) {
      return window.gsap.timeline();
    }
    return window.gsap
      .timeline()
      .to(target, { backgroundColor: "rgba(255,255,255,0.55)", scale: 1.015, y: -4, duration: 0.2, ease: "power2.out" })
      .to(target, { backgroundColor: "rgba(255,255,255,0)", scale: 1, y: 0, duration: 0.34, ease: "power2.inOut" });
  }

  function accentNudge(target) {
    if (!target) {
      return window.gsap.timeline();
    }
    return window.gsap.timeline().to(target, { x: 10, duration: 0.12, ease: "power1.out" }).to(target, {
      x: 0,
      duration: 0.22,
      ease: "power2.out",
    });
  }

  function cameraSettle(root) {
    const target = root || getCanvas();
    if (!target) {
      return window.gsap.timeline();
    }
    return window.gsap.timeline();
  }

  function sectionSettle(target) {
    if (!target) {
      return window.gsap.timeline();
    }
    return window.gsap.timeline().to(target, { autoAlpha: 1, duration: 0.18, ease: "none" });
  }

  function getCueAnimation(cue, segment) {
    const target = resolveTarget(cue.target);
    const root = getCanvas();
    switch (cue.type) {
      case "camera_punch":
        return cameraPunchIn(root, segment.sectionId === "header" ? 1.024 : 1.014);
      case "section_reveal":
        return sectionReveal(getSection(segment.sectionId));
      case "stat_pulse":
        return statPulse(target);
      case "ingredient_stagger":
        return ingredientStagger(getSection(segment.sectionId));
      case "ingredient_focus":
        return ingredientFocus(target);
      case "insight_spotlight":
        return insightSpotlight(target);
      case "camera_settle":
        return cameraSettle(root);
      case "section_settle":
        return sectionSettle(target);
      case "accent_nudge":
        return accentNudge(target);
      default:
        return window.gsap.timeline();
    }
  }

  function buildSegmentTimeline(segment) {
    const section = getSection(segment.sectionId);
    const topOffset = segment.sectionId === "header" ? 0 : segment.sectionId === "nutrition" ? 22 : 36;
    const totalSec = segment.durationMs / 1000;
    const timeline = window.gsap.timeline();

    timeline.to({}, { duration: totalSec }, 0);
    if (segment.index === 0) {
      timeline.call(() => window.scrollTo(0, section ? getTargetY(section, topOffset) : window.scrollY), [], 0);
    } else {
      const easeName = segment.cameraMode === "scan" ? "power1.out" : "power2.inOut";
      timeline.add(createScrollTween(section, topOffset, segment.moveMs, easeName), 0);
    }

    if (segment.sectionId !== "header") {
      timeline.add(sectionReveal(section), segment.index === 0 ? 0.02 : 0.08);
    }

    segment.microCues.forEach((cue) => {
      timeline.add(getCueAnimation(cue, segment), cue.offsetMs / 1000);
    });

    if (segment.sectionId === "nutrition" && section) {
      const elements = getElementsForSection(section);
      if (elements.macros.length) {
        timeline.fromTo(
          elements.macros,
          { autoAlpha: 0.72, y: 12 },
          { autoAlpha: 1, y: 0, duration: 0.22, stagger: 0.05, ease: "power2.out", immediateRender: false },
          0.28
        );
      }
    }
    if (segment.sectionId === "insights" && section) {
      const elements = getElementsForSection(section);
      if (elements.insights.length) {
        timeline.fromTo(
          elements.insights,
          { autoAlpha: 0.7, y: 14 },
          { autoAlpha: 1, y: 0, duration: 0.24, stagger: 0.08, ease: "power2.out", immediateRender: false },
          0.22
        );
      }
    }

    return timeline;
  }

  async function startVideoScroll() {
    const videoScript = window.__VIDEO_SCRIPT__ || {};
    const { runtimeSegments, endHoldMs } = buildRuntimeSegments(videoScript);
    window.__VIDEO_DONE__ = false;
    window.scrollTo(0, 0);
    await sleep(80);

    if (!window.gsap || !runtimeSegments.length) {
      for (const segment of runtimeSegments) {
        const section = getSection(segment.sectionId);
        if (section) {
          window.scrollTo(0, getTargetY(section, 24));
        }
        await sleep(segment.durationMs);
      }
      if (endHoldMs > 0) {
        await sleep(endHoldMs);
      }
      window.__VIDEO_DONE__ = true;
      return;
    }

    const master = window.gsap.timeline({
      defaults: { overwrite: "auto" },
      onComplete() {
        window.__VIDEO_DONE__ = true;
      },
    });

    runtimeSegments.forEach((segment) => {
      master.add(buildSegmentTimeline(segment));
    });
    if (endHoldMs > 0) {
      master.to({}, { duration: endHoldMs / 1000 });
    }
    master.play(0);

    return new Promise((resolve) => {
      master.eventCallback("onComplete", () => {
        window.__VIDEO_DONE__ = true;
        resolve();
      });
    });
  }

  window.startVideoScroll = startVideoScroll;
  window.__VIDEO_DONE__ = false;
  const initialVideoScript = window.__VIDEO_SCRIPT__ || {};
  const initialRuntime = buildRuntimeSegments(initialVideoScript);
  initializeMotionState(initialRuntime.runtimeSegments);
  window.__VIDEO_READY__ = true;
})();
