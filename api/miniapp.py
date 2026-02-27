"""Handler that serves the Admin Mini App as a single inline HTML page.

The page is designed to run inside a Telegram WebApp container and
communicates with ``/api/admin/*`` endpoints using the
``X-Telegram-Init-Data`` header for authentication.
"""

from __future__ import annotations

from aiohttp import web

_ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Admin</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root {
  --tg-bg: var(--tg-theme-bg-color, #ffffff);
  --tg-text: var(--tg-theme-text-color, #000000);
  --tg-hint: var(--tg-theme-hint-color, #999999);
  --tg-link: var(--tg-theme-link-color, #2678b6);
  --tg-btn: var(--tg-theme-button-color, #2678b6);
  --tg-btn-text: var(--tg-theme-button-text-color, #ffffff);
  --tg-secondary-bg: var(--tg-theme-secondary-bg-color, #f0f0f0);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: var(--tg-bg);
  color: var(--tg-text);
  padding: 16px;
  line-height: 1.5;
}
h1 { font-size: 1.25rem; margin-bottom: 16px; }
section { margin-bottom: 24px; }
section h2 {
  font-size: 1rem;
  margin-bottom: 8px;
  color: var(--tg-link);
}
label { display: block; font-size: 0.85rem; color: var(--tg-hint); margin-bottom: 4px; }
input[type="text"] {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--tg-hint);
  border-radius: 8px;
  background: var(--tg-secondary-bg);
  color: var(--tg-text);
  font-size: 0.95rem;
  margin-bottom: 8px;
}
button {
  display: inline-block;
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  background: var(--tg-btn);
  color: var(--tg-btn-text);
  font-size: 0.95rem;
  cursor: pointer;
}
button:disabled { opacity: 0.5; cursor: default; }
.result {
  margin-top: 12px;
  padding: 12px;
  border-radius: 8px;
  background: var(--tg-secondary-bg);
  white-space: pre-wrap;
  font-size: 0.85rem;
  display: none;
}
.result.visible { display: block; }
.error-banner {
  padding: 12px;
  border-radius: 8px;
  background: #fdecea;
  color: #b71c1c;
  margin-bottom: 16px;
  display: none;
  font-size: 0.9rem;
}
.error-banner.visible { display: block; }
</style>
</head>
<body>
<div id="error-banner" class="error-banner"></div>
<h1>Admin Panel</h1>

<section>
  <h2>Conversions</h2>
  <label for="conv-cats">Category numbers (comma-separated)</label>
  <input type="text" id="conv-cats" placeholder="1, 2, 3" />
  <button id="conv-btn">Get conversions</button>
  <div id="conv-result" class="result"></div>
</section>

<section>
  <h2>Usernames</h2>
  <label for="uname-cat">Category number</label>
  <input type="text" id="uname-cat" placeholder="5" />
  <button id="uname-btn">Get usernames</button>
  <div id="uname-result" class="result"></div>
</section>

<script>
(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var errorBanner = document.getElementById("error-banner");

  function getInitData() {
    return (tg && tg.initData) || "";
  }

  function showError(msg) {
    errorBanner.textContent = msg;
    errorBanner.classList.add("visible");
  }

  function hideError() {
    errorBanner.classList.remove("visible");
    errorBanner.textContent = "";
  }

  function showResult(el, text) {
    el.textContent = text;
    el.classList.add("visible");
  }

  function hideResult(el) {
    el.classList.remove("visible");
    el.textContent = "";
  }

  function adminFetch(path, body) {
    hideError();
    var initData = getInitData();
    if (!initData) {
      showError("Telegram WebApp data is not available. Open this page from Telegram.");
      return Promise.reject(new Error("no initData"));
    }
    return fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Telegram-Init-Data": initData,
        "ngrok-skip-browser-warning": "1"
      },
      body: JSON.stringify(body)
    }).then(function (resp) {
      if (resp.status === 401) {
        showError("Authentication failed (401). Please re-open the Mini App from Telegram.");
        return Promise.reject(new Error("401"));
      }
      if (resp.status === 403) {
        showError("Access denied (403). You are not in the admin list.");
        return Promise.reject(new Error("403"));
      }
      if (!resp.ok) {
        return resp.text().then(function (t) {
          showError("Request failed (" + resp.status + "): " + t);
          return Promise.reject(new Error("HTTP " + resp.status));
        });
      }
      return resp.json();
    });
  }

  /* --- Conversions --- */
  var convBtn = document.getElementById("conv-btn");
  var convCats = document.getElementById("conv-cats");
  var convResult = document.getElementById("conv-result");

  convBtn.addEventListener("click", function () {
    hideResult(convResult);
    var raw = convCats.value.trim();
    if (!raw) return;
    var categories = raw.split(",").map(function (s) { return parseInt(s.trim(), 10); });
    if (categories.some(isNaN)) {
      showError("Please enter valid numbers separated by commas.");
      return;
    }
    convBtn.disabled = true;
    adminFetch("/api/admin/conversions", { categories: categories })
      .then(function (data) {
        showResult(convResult, JSON.stringify(data, null, 2));
      })
      .catch(function () { /* error already shown */ })
      .finally(function () { convBtn.disabled = false; });
  });

  /* --- Usernames --- */
  var unameBtn = document.getElementById("uname-btn");
  var unameCat = document.getElementById("uname-cat");
  var unameResult = document.getElementById("uname-result");

  unameBtn.addEventListener("click", function () {
    hideResult(unameResult);
    var val = parseInt(unameCat.value.trim(), 10);
    if (isNaN(val)) {
      showError("Please enter a valid category number.");
      return;
    }
    unameBtn.disabled = true;
    adminFetch("/api/admin/usernames", { category: val })
      .then(function (data) {
        showResult(unameResult, JSON.stringify(data, null, 2));
      })
      .catch(function () { /* error already shown */ })
      .finally(function () { unameBtn.disabled = false; });
  });
})();
</script>
</body>
</html>
"""


async def miniapp_admin_handler(_request: web.Request) -> web.Response:
    """Serve the Admin Mini App as an inline HTML page."""
    return web.Response(text=_ADMIN_HTML, content_type="text/html")
