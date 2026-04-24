(function () {
  var DEBOUNCE_MS = 40;
  var debounceTimer = null;

  function data() {
    return window.LOGI_AD_DATA || window.__LOGI_AD_DATA__ || {};
  }

  function text(id, value) {
    var node = document.getElementById(id);
    if (node && value !== undefined && value !== null && String(value).trim()) {
      var next = String(value);
      if (node.textContent !== next) node.textContent = next;
    }
  }

  function image(id, value) {
    var node = document.getElementById(id);
    if (node && value) {
      var next = String(value);
      if (node.getAttribute("src") !== next) node.setAttribute("src", next);
    }
  }

  function metric(name) {
    return (data().metrics || {})[name];
  }

  function metricValue(name) {
    var item = metric(name);
    if (item && typeof item === "object" && "value" in item) return item.value;
    return item;
  }

  function mealName() {
    return ((data().meal || {}).name || data().dish || "This meal").trim();
  }

  function foodImage() {
    var item = data().food_image || {};
    if (item.public_url) return item.public_url;
    var isNested = window.location.pathname.indexOf("/compositions/") >= 0;
    return (isNested && item.nested_asset) || item.asset || "";
  }

  function glLabel(prefix) {
    var value = metricValue("glycemic_load");
    if (!value || value === "N/A") return prefix ? prefix + " checking" : "GL checking";
    return (prefix || "GL") + " " + value;
  }

  function glColor() {
    var gl = metric("glycemic_load") || {};
    if (gl.band === "high") return "#ee001b";
    if (gl.band === "medium") return "#ff8500";
    if (gl.band === "low") return "#4b9d6c";
    return "#111827";
  }

  function ensureLiveCard() {
    var root = document.getElementById("results-root");
    if (!root || document.getElementById("dynamic-journal-card")) return;
    var m = data().metrics || {};
    var card = document.createElement("div");
    card.id = "dynamic-journal-card";
    card.style.cssText = [
      "position:absolute",
      "left:172px",
      "top:1110px",
      "width:760px",
      "height:236px",
      "border-radius:44px",
      "background:#fff",
      "box-shadow:0 24px 80px rgba(17,24,39,.20)",
      "z-index:80",
      "padding:28px 28px 24px 204px",
      "font-family:Inter,Arial,sans-serif",
      "color:#111827"
    ].join(";");
    card.innerHTML =
      '<img src="' + foodImage() + '" style="position:absolute;left:28px;top:28px;width:150px;height:150px;object-fit:cover;border-radius:28px;">' +
      '<div style="position:absolute;left:130px;top:28px;width:78px;height:78px;border-radius:0 28px 0 28px;background:' + glColor() + ';color:#fff;text-align:center;font-size:36px;font-weight:850;line-height:78px;">' + metricValue("glycemic_load") + '</div>' +
      '<div style="font-size:43px;font-weight:820;line-height:1.05;letter-spacing:-1.2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + mealName() + '</div>' +
      '<div style="display:flex;gap:26px;margin-top:24px;color:#737b8a;font-size:28px;font-weight:610;">' +
      '<span>Cal <b style="color:#111827">' + m.calories + '</b></span>' +
      '<span>Carb <b style="color:#111827">' + m.carbs + '</b></span>' +
      '<span>Fat <b style="color:#111827">' + m.fat + '</b></span>' +
      '<span>Protein <b style="color:#111827">' + m.protein + '</b></span>' +
      "</div>";
    root.appendChild(card);
  }

  function ensureNutritionPanel() {
    var root = document.getElementById("nutrition-root");
    if (!root || document.getElementById("dynamic-nutrition-panel")) return;
    var m = data().metrics || {};
    var panel = document.createElement("div");
    panel.id = "dynamic-nutrition-panel";
    panel.style.cssText = [
      "position:absolute",
      "left:150px",
      "top:420px",
      "width:780px",
      "border-radius:46px",
      "background:#fff",
      "box-shadow:0 24px 80px rgba(17,24,39,.18)",
      "z-index:82",
      "padding:34px",
      "font-family:Inter,Arial,sans-serif",
      "color:#111827"
    ].join(";");
    panel.innerHTML =
      '<div style="font-size:42px;font-weight:850;color:#4b9d6c;margin-bottom:26px;">Nutrition Label</div>' +
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:22px;">' +
      '<div style="border-radius:28px;background:' + glColor() + ';color:#fff;padding:24px;text-align:center;"><div style="font-size:29px;">Glycemic Load</div><div style="font-size:66px;font-weight:900;">' + metricValue("glycemic_load") + "</div></div>" +
      '<div style="border-left:3px solid #e2e6eb;padding-left:34px;"><div style="font-size:31px;">Calories</div><div style="font-size:66px;font-weight:900;">' + m.calories + "</div></div>" +
      "</div>" +
      '<div style="margin-top:26px;font-size:34px;line-height:1.85;">Carbs <b style="float:right;">' + m.carbs + ' g</b><br>Fat <b style="float:right;">' + m.fat + ' g</b><br>Protein <b style="float:right;">' + m.protein + " g</b></div>";
    root.appendChild(panel);
  }

  function apply() {
    var d = data();
    if (!d || Object.keys(d).length === 0) return;
    var m = d.metrics || {};
    var ingredients = d.ingredients || [];
    var risks = d.risks || [];
    var insights = d.insights || [];
    image("hook-food-image", foodImage());
    text("hook-dish-name", mealName());
    text("hook-main-line", "This looks delicious.");
    text("hook-main-line-2", glLabel("LOGI found GL"));
    text("hook-subcopy", "One food photo becomes calories, glycemic load, ingredients, and plain-English insights.");
    text("hook-scan-value", glLabel("GL"));
    text("add-headline", "Drop " + mealName() + " into LOGI");
    text("add-caption", "The app starts from one food photo and turns it into structured nutrition data.");
    text("scan-subline", "LOGI checks the image against ingredients, portions, macros, and glycemic load.");
    text("scan-chip-1", mealName().split(" ").slice(0, 2).join(" "));
    text("scan-chip-2", ingredients[0] ? ingredients[0].name : "ingredients");
    text("scan-chip-3", glLabel("glycemic load"));
    text("results-caption", mealName() + " returns with calories, macros, and glycemic load in the journal.");
    text("results-pop-gl", glLabel("GL"));
    text("results-pop-cal", m.calories + " cal");
    text("results-pop-carb", m.carbs + "g carbs");
    text("nutrition-callout-gl", "Glycemic Load: " + metricValue("glycemic_load"));
    text("nutrition-callout-cal", m.calories + " calories");
    text("nutrition-callout-carb", m.carbs + "g carbohydrates");
    text(
      "ingredients-caption",
      ingredients
        .slice(0, 5)
        .map(function (item) {
          return item.name;
        })
        .join(", ") + " - each ingredient gets its own nutrition context."
    );
    text("ingredients-tag-1", glLabel("meal GL"));
    text("ingredients-tag-2", ingredients.length + " ingredients");
    text("insights-risk-1", risks[0]);
    text("insights-risk-2", risks[1]);
    text("insights-risk-3", risks[2]);
    text("insights-takeaway", insights[0] || "Better choices start with seeing what is actually inside.");
    text("cta-subtitle", "Turn " + mealName() + " into calories, glycemic load, ingredients, and plain-English meal insights.");
    ensureLiveCard();
    ensureNutritionPanel();
  }

  function scheduleApply() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(function () {
      debounceTimer = null;
      try {
        apply();
      } catch (e) {}
    }, DEBOUNCE_MS);
  }

  function watchDom() {
    var mo = new MutationObserver(function (mutations) {
      var i;
      var j;
      for (i = 0; i < mutations.length; i++) {
        var nodes = mutations[i].addedNodes;
        for (j = 0; j < nodes.length; j++) {
          if (nodes[j].nodeType === 1) {
            scheduleApply();
            return;
          }
        }
      }
    });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }

  function boot() {
    apply();
    watchDom();
    window.addEventListener("load", scheduleApply, { once: true });
  }

  window.LOGI_DYNAMIC_AD = { apply: apply, scheduleApply: scheduleApply };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
