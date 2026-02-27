"""Handler that serves the Admin Mini App as a single inline HTML page.

The page is designed to run inside a Telegram WebApp container and
communicates with ``/api/admin/*`` endpoints using the
``X-Telegram-Init-Data`` header for authentication.
"""

from __future__ import annotations

from aiohttp import web

_ADMIN_HTML = """\
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Панель администратора</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.15.0/cdn/themes/light.css" />
<script type="module" src="https://cdn.jsdelivr.net/npm/@shoelace-style/shoelace@2.15.0/cdn/shoelace-autoloader.js"></script>
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
  padding: 0;
  line-height: 1.5;
}
.error-banner {
  padding: 12px 16px;
  background: #fdecea;
  color: #b71c1c;
  margin: 0;
  display: none;
  font-size: 0.9rem;
  border-bottom: 1px solid #f5c6cb;
}
.error-banner.visible { display: block; }
.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--tg-secondary-bg);
  border-bottom: 1px solid var(--tg-hint);
}
.top-bar h1 {
  font-size: 1.25rem;
  margin: 0;
}
.range-selector {
  display: flex;
  gap: 4px;
}
.range-selector sl-button::part(base) {
  font-size: 0.85rem;
  padding: 6px 12px;
}
.tab-content {
  padding: 16px;
  display: none;
}
.tab-content.active {
  display: block;
}
.refresh-bar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}
.section {
  margin-bottom: 24px;
}
.section-title {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--tg-link);
}
.metric-card {
  background: var(--tg-secondary-bg);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}
.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}
.metric-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.9rem;
  color: var(--tg-text);
}
.metric-value {
  font-weight: 600;
  font-size: 1rem;
}
.info-icon {
  cursor: help;
  color: var(--tg-hint);
}
.all-time-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #fff3cd;
  color: #856404;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  margin-left: 8px;
}
.conversion-controls {
  margin-bottom: 16px;
}
.group-sizes-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 16px;
  background: var(--tg-secondary-bg);
  border-radius: 8px;
  overflow: hidden;
}
.group-sizes-table th,
.group-sizes-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid var(--tg-hint);
}
.group-sizes-table th {
  background: var(--tg-link);
  color: white;
  font-weight: 600;
  font-size: 0.85rem;
}
.group-sizes-table td {
  font-size: 0.9rem;
}
.group-sizes-table tr:last-child td {
  border-bottom: none;
}
.conversions-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--tg-secondary-bg);
  border-radius: 8px;
  overflow: hidden;
}
.conversions-table th,
.conversions-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid var(--tg-hint);
}
.conversions-table th {
  background: var(--tg-link);
  color: white;
  font-weight: 600;
  font-size: 0.85rem;
}
.conversions-table td {
  font-size: 0.9rem;
}
.conversions-table tr:last-child td {
  border-bottom: none;
}
.conversion-percent {
  display: flex;
  align-items: center;
  gap: 6px;
}
.usernames-section {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 2px solid var(--tg-hint);
}
.usernames-input {
  margin-bottom: 12px;
}
.usernames-list {
  background: var(--tg-secondary-bg);
  border-radius: 8px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
  font-size: 0.85rem;
  white-space: pre-wrap;
  font-family: monospace;
}
</style>
</head>
<body>
<div id="error-banner" class="error-banner"></div>

<div class="top-bar">
  <h1>Панель администратора</h1>
  <div class="range-selector">
    <sl-button size="small" variant="default" data-range="1d">1д</sl-button>
    <sl-button size="small" variant="default" data-range="7d">7д</sl-button>
    <sl-button size="small" variant="default" data-range="1m">1м</sl-button>
    <sl-button size="small" variant="default" data-range="all">Всё</sl-button>
  </div>
</div>

<sl-tab-group>
  <sl-tab slot="nav" panel="overview">Обзор</sl-tab>
  <sl-tab slot="nav" panel="conversions">Конверсии</sl-tab>

  <sl-tab-panel name="overview">
    <div class="tab-content active" id="overview-tab">
      <div class="refresh-bar">
        <sl-button id="overview-refresh" variant="primary" size="small">
          <sl-icon slot="prefix" name="arrow-clockwise"></sl-icon>
          Обновить
        </sl-button>
      </div>
      <div id="overview-content"></div>
    </div>
  </sl-tab-panel>

  <sl-tab-panel name="conversions">
    <div class="tab-content" id="conversions-tab">
      <div class="refresh-bar">
        <sl-button id="conversions-refresh" variant="primary" size="small">
          <sl-icon slot="prefix" name="arrow-clockwise"></sl-icon>
          Обновить
        </sl-button>
      </div>
      
      <div class="conversion-controls">
        <label style="display: block; margin-bottom: 8px; font-size: 0.9rem; font-weight: 600;">Выберите группы конверсий (по порядку):</label>
        <sl-select id="categories-select" multiple clearable placeholder="Выберите категории..." style="width: 100%; margin-bottom: 16px;"></sl-select>
      </div>
      
      <div id="conversions-content"></div>
      
      <div class="usernames-section">
        <div class="section-title">Данные пользователей</div>
        <div class="usernames-input">
          <label style="display: block; margin-bottom: 8px; font-size: 0.9rem; font-weight: 600;">Получить юзернеймы для категории:</label>
          <sl-select id="username-category-select" placeholder="Выберите категорию..." style="width: 100%; margin-bottom: 12px;"></sl-select>
        </div>
        <sl-button id="usernames-btn" variant="default" size="small">Получить юзернеймы</sl-button>
        <div id="usernames-result" class="usernames-list" style="display: none; margin-top: 12px;"></div>
      </div>
    </div>
  </sl-tab-panel>
</sl-tab-group>

<script>
(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    tg.ready();
    tg.expand();
  }

  var errorBanner = document.getElementById("error-banner");
  var currentRange = "7d";
  var categories = [];
  var overviewData = null;
  var conversionsData = null;

  // Range selector
  var rangeButtons = document.querySelectorAll(".range-selector sl-button");
  rangeButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      rangeButtons.forEach(function (b) { b.variant = "default"; });
      btn.variant = "primary";
      currentRange = btn.getAttribute("data-range");
      // Auto-refresh active tab when range changes
      if (document.getElementById("overview-tab").classList.contains("active")) {
        document.getElementById("overview-refresh").click();
      } else if (document.getElementById("conversions-tab").classList.contains("active")) {
        document.getElementById("conversions-refresh").click();
      }
    });
  });
  // Set default
  rangeButtons[1].variant = "primary"; // 7d

  // Tab switching
  var tabGroup = document.querySelector("sl-tab-group");
  tabGroup.addEventListener("sl-tab-show", function (e) {
    document.querySelectorAll(".tab-content").forEach(function (tc) {
      tc.classList.remove("active");
    });
    var panelName = e.detail.name;
    if (panelName === "overview") {
      document.getElementById("overview-tab").classList.add("active");
    } else if (panelName === "conversions") {
      document.getElementById("conversions-tab").classList.add("active");
    }
  });

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

  function adminFetch(path, method, body) {
    hideError();
    var initData = getInitData();
    if (!initData) {
      showError("Данные Telegram WebApp недоступны. Откройте страницу из Telegram.");
      return Promise.reject(new Error("no initData"));
    }
    var opts = {
      method: method,
      headers: {
        "X-Telegram-Init-Data": initData,
        "ngrok-skip-browser-warning": "1"
      }
    };
    if (body) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (resp) {
      if (resp.status === 401) {
        showError("Ошибка аутентификации (401). Перезапустите Mini App из Telegram.");
        return Promise.reject(new Error("401"));
      }
      if (resp.status === 403) {
        showError("Доступ запрещён (403). Вас нет в списке администраторов.");
        return Promise.reject(new Error("403"));
      }
      if (!resp.ok) {
        return resp.text().then(function (t) {
          showError("Ошибка запроса (" + resp.status + "): " + t);
          return Promise.reject(new Error("HTTP " + resp.status));
        });
      }
      return resp.json();
    });
  }

  function renderMetricRow(label, value, tooltip) {
    var row = document.createElement("div");
    row.className = "metric-row";
    
    var labelDiv = document.createElement("div");
    labelDiv.className = "metric-label";
    labelDiv.textContent = label;
    
    if (tooltip) {
      var tooltipEl = document.createElement("sl-tooltip");
      tooltipEl.content = tooltip;
      var icon = document.createElement("sl-icon");
      icon.name = "info-circle";
      icon.className = "info-icon";
      tooltipEl.appendChild(icon);
      labelDiv.appendChild(tooltipEl);
    }
    
    var valueDiv = document.createElement("div");
    valueDiv.className = "metric-value";
    valueDiv.textContent = value;
    
    row.appendChild(labelDiv);
    row.appendChild(valueDiv);
    return row;
  }

  function renderSection(title, rows) {
    var section = document.createElement("div");
    section.className = "section";
    
    var titleDiv = document.createElement("div");
    titleDiv.className = "section-title";
    titleDiv.textContent = title;
    section.appendChild(titleDiv);
    
    var card = document.createElement("div");
    card.className = "metric-card";
    rows.forEach(function (row) { card.appendChild(row); });
    section.appendChild(card);
    
    return section;
  }

  function formatNumber(num) {
    if (num == null) return "—";
    return num.toLocaleString("ru-RU");
  }

  function formatPercent(num) {
    if (num == null) return "—";
    return num.toFixed(1) + "%";
  }

  function renderOverview(data) {
    var container = document.getElementById("overview-content");
    container.innerHTML = "";
    
    // Основные показатели
    var coreRows = [
      renderMetricRow("Новые пользователи", formatNumber(data.core_kpis.new_users), "Пользователи, созданные в выбранном периоде"),
      renderMetricRow("Активные пользователи", formatNumber(data.core_kpis.active_users), "Пользователи с last_active_at в выбранном периоде"),
      renderMetricRow("Сгенерированные отчёты", formatNumber(data.core_kpis.reports_generated), "Отчёты со state=GENERATED, завершённые в выбранном периоде")
    ];
    container.appendChild(renderSection("Основные показатели", coreRows));
    
    // Платежи
    var paymentRows = [
      renderMetricRow("Выручка", formatNumber(data.payments.revenue) + " ₽", "Сумма total_price по SUCCESS платежам в периоде"),
      renderMetricRow("Платящие пользователи", formatNumber(data.payments.paying_users), "Уникальные пользователи с SUCCESS платежами в периоде")
    ];
    
    // By status
    var statusEntries = Object.entries(data.payments.by_status);
    if (statusEntries.length > 0) {
      statusEntries.forEach(function (entry) {
        paymentRows.push(renderMetricRow("  " + entry[0], formatNumber(entry[1]), "Количество платежей по статусу"));
      });
    }
    
    // By option
    var optionEntries = Object.entries(data.payments.revenue_by_option);
    if (optionEntries.length > 0) {
      paymentRows.push(renderMetricRow("Выручка по опциям", "", ""));
      optionEntries.forEach(function (entry) {
        paymentRows.push(renderMetricRow("  " + entry[0], formatNumber(entry[1]) + " ₽", "Выручка по этой опции оплаты"));
      });
    }
    
    container.appendChild(renderSection("Платежи", paymentRows));
    
    // Рефералы
    var refRows = [
      renderMetricRow("Активные рефералы", formatNumber(data.referrals.active_referrers), "Уникальные invited_by среди пользователей, созданных в периоде"),
      renderMetricRow("Новые приглашённые", formatNumber(data.referrals.new_referred_users), "Пользователи, созданные в периоде с invited_by не null"),
      renderMetricRow("Сред. рефералов/реферал", formatNumber(data.referrals.referrals_per_referrer_avg), "Среднее число рефералов на активного реферала"),
      renderMetricRow("Медиана рефералов/реферал", formatNumber(data.referrals.referrals_per_referrer_median), "Медиана рефералов на активного реферала"),
      renderMetricRow("Квалифицированные рефералы", formatNumber(data.referrals.qualified_referrals_count), "Приглашённые с ≥1 событием активации (CLICK_COMPARE)"),
      renderMetricRow("Доля квалифицированных", formatPercent(data.referrals.qualified_referrals_rate), "qualified_referrals_count / new_referred_users"),
      renderMetricRow("Выручка от рефералов", formatNumber(data.referrals.referred_revenue) + " ₽", "Выручка от SUCCESS платежей приглашённых пользователей"),
      renderMetricRow("Оценочный бонус", formatNumber(data.referrals.estimated_bonus_earned) + " ₽", "Сумма ceil(total_price * 0.2) по SUCCESS платежам приглашённых")
    ];
    
    // Воронка
    refRows.push(renderMetricRow("Воронка: Создано", formatNumber(data.referrals.referral_funnel.created), "Приглашённые пользователи, созданные в периоде"));
    refRows.push(renderMetricRow("Воронка: Активировано", formatNumber(data.referrals.referral_funnel.activated), "Приглашённые с событием активации"));
    refRows.push(renderMetricRow("Воронка: Оплачено", formatNumber(data.referrals.referral_funnel.paid), "Приглашённые с SUCCESS платежом"));
    
    // Top referrers
    if (data.referrals.top_referrers_by_referred_users.length > 0) {
      refRows.push(renderMetricRow("Топ рефералов (по пользователям)", "", ""));
      data.referrals.top_referrers_by_referred_users.forEach(function (r, idx) {
        refRows.push(renderMetricRow("  " + (idx + 1) + ". Пользователь " + r.user_id, formatNumber(r.count), "Количество приглашённых"));
      });
    }
    
    if (data.referrals.top_referrers_by_referred_revenue.length > 0) {
      refRows.push(renderMetricRow("Топ рефералов (по выручке)", "", ""));
      data.referrals.top_referrers_by_referred_revenue.forEach(function (r, idx) {
        refRows.push(renderMetricRow("  " + (idx + 1) + ". Пользователь " + r.user_id, formatNumber(r.revenue) + " ₽", "Выручка от приглашённых"));
      });
    }
    
    container.appendChild(renderSection("Рефералы", refRows));
    
    // Повторные отчёты (всё время)
    var rrRows = [
      renderMetricRow("Повторные отчёты", formatNumber(data.repeat_reporters.repeat_reporters_count), "Пользователи с ≥2 сгенерированными отчётами (всё время)"),
      renderMetricRow("Доля повторных", formatPercent(data.repeat_reporters.repeat_reporters_rate), "repeat_reporters_count / total_reporters_count (всё время)")
    ];
    container.appendChild(renderSection("Повторные отчёты (всё время)", rrRows));
    
    // Сегментация плательщиков
    var psRows = [
      renderMetricRow("Новые плательщики", formatNumber(data.payer_segmentation.new_payer_count), "Пользователи с первым SUCCESS платежом в периоде"),
      renderMetricRow("Вернувшиеся плательщики", formatNumber(data.payer_segmentation.returning_payer_count), "Пользователи с SUCCESS платежом до range_start И в периоде"),
      renderMetricRow("Отток плательщиков", formatNumber(data.payer_segmentation.churned_payer_count), "Пользователи с ≥1 SUCCESS платежом ранее, но без платежей за последние 60 дней"),
      renderMetricRow("Однократные плательщики", formatNumber(data.payer_segmentation.one_time_payer_count), "Ровно 1 SUCCESS платеж (всё время)"),
      renderMetricRow("Повторные плательщики", formatNumber(data.payer_segmentation.repeat_payer_count), "2–3 SUCCESS платежа (всё время)"),
      renderMetricRow("Активные плательщики", formatNumber(data.payer_segmentation.power_payer_count), "4+ SUCCESS платежей (всё время)")
    ];
    container.appendChild(renderSection("Сегментация плательщиков", psRows));
  }

  function renderConversions(data) {
    var container = document.getElementById("conversions-content");
    container.innerHTML = "";
    
    if (!data.groups || data.groups.length === 0) {
      container.innerHTML = "<p style='color: var(--tg-hint);'>Выберите категории для просмотра конверсий.</p>";
      return;
    }
    
    // Group sizes table
    var section1 = document.createElement("div");
    section1.className = "section";
    var title1 = document.createElement("div");
    title1.className = "section-title";
    title1.textContent = "Размеры групп";
    section1.appendChild(title1);
    
    var table1 = document.createElement("table");
    table1.className = "group-sizes-table";
    var thead1 = document.createElement("thead");
    var headerRow1 = document.createElement("tr");
    ["Категория", "Название", "Размер"].forEach(function (h) {
      var th = document.createElement("th");
      th.textContent = h;
      headerRow1.appendChild(th);
    });
    thead1.appendChild(headerRow1);
    table1.appendChild(thead1);
    
    var tbody1 = document.createElement("tbody");
    data.groups.forEach(function (g) {
      var tr = document.createElement("tr");
      
      var tdCat = document.createElement("td");
      tdCat.textContent = g.category;
      tr.appendChild(tdCat);
      
      var tdLabel = document.createElement("td");
      var catObj = categories.find(function (c) { return c.category === g.category; });
      var labelText = catObj ? catObj.label : "—";
      tdLabel.textContent = labelText;
      
      if (!g.range_applied) {
        var badge = document.createElement("span");
        badge.className = "all-time-badge";
        var badgeTooltip = document.createElement("sl-tooltip");
        badgeTooltip.content = "Эта группа считается за всё время (период не применяется)";
        var badgeIcon = document.createElement("sl-icon");
        badgeIcon.name = "clock-history";
        badgeIcon.style.fontSize = "0.75rem";
        badgeTooltip.appendChild(badgeIcon);
        badge.appendChild(badgeTooltip);
        var badgeText = document.createTextNode(" Всё время");
        badge.appendChild(badgeText);
        tdLabel.appendChild(badge);
      }
      
      tr.appendChild(tdLabel);
      
      var tdSize = document.createElement("td");
      tdSize.textContent = formatNumber(g.size);
      tr.appendChild(tdSize);
      
      tbody1.appendChild(tr);
    });
    table1.appendChild(tbody1);
    section1.appendChild(table1);
    container.appendChild(section1);
    
    // Conversions table
    if (data.conversions && data.conversions.length > 0) {
      var section2 = document.createElement("div");
      section2.className = "section";
      var title2 = document.createElement("div");
      title2.className = "section-title";
      title2.textContent = "Смежные конверсии";
      section2.appendChild(title2);
      
      var table2 = document.createElement("table");
      table2.className = "conversions-table";
      var thead2 = document.createElement("thead");
      var headerRow2 = document.createElement("tr");
      ["Из", "В", "Конверсия %"].forEach(function (h) {
        var th = document.createElement("th");
        th.textContent = h;
        headerRow2.appendChild(th);
      });
      thead2.appendChild(headerRow2);
      table2.appendChild(thead2);
      
      var tbody2 = document.createElement("tbody");
      data.conversions.forEach(function (c) {
        var tr = document.createElement("tr");
        
        var tdFrom = document.createElement("td");
        var fromCat = categories.find(function (cat) { return cat.category === c.from_category; });
        tdFrom.textContent = fromCat ? fromCat.label : "Категория " + c.from_category;
        tr.appendChild(tdFrom);
        
        var tdTo = document.createElement("td");
        var toCat = categories.find(function (cat) { return cat.category === c.to_category; });
        tdTo.textContent = toCat ? toCat.label : "Категория " + c.to_category;
        tr.appendChild(tdTo);
        
        var tdPercent = document.createElement("td");
        var percentDiv = document.createElement("div");
        percentDiv.className = "conversion-percent";
        
        var percentText = document.createElement("span");
        percentText.textContent = c.percent != null ? formatPercent(c.percent) : "—";
        percentDiv.appendChild(percentText);
        
        var tooltipContent = "Формула: (из ∩ в) / из\\n" +
                             "Числитель: " + formatNumber(c.numerator) + "\\n" +
                             "Знаменатель: " + formatNumber(c.denominator);
        var tooltipEl = document.createElement("sl-tooltip");
        tooltipEl.content = tooltipContent;
        var icon = document.createElement("sl-icon");
        icon.name = "info-circle";
        icon.className = "info-icon";
        tooltipEl.appendChild(icon);
        percentDiv.appendChild(tooltipEl);
        
        tdPercent.appendChild(percentDiv);
        tr.appendChild(tdPercent);
        
        tbody2.appendChild(tr);
      });
      table2.appendChild(tbody2);
      section2.appendChild(table2);
      container.appendChild(section2);
    }
  }

  // Load categories
  function loadCategories() {
    return adminFetch("/api/admin/categories", "GET", null).then(function (data) {
      categories = data.categories;
      var select = document.getElementById("categories-select");
      var usernameSelect = document.getElementById("username-category-select");
      categories.forEach(function (cat) {
        var option = document.createElement("sl-option");
        option.value = cat.category;
        option.textContent = cat.category + ". " + cat.label;
        select.appendChild(option);
        
        var usernameOption = document.createElement("sl-option");
        usernameOption.value = cat.category;
        usernameOption.textContent = cat.category + ". " + cat.label;
        usernameSelect.appendChild(usernameOption);
      });
    });
  }

  // Overview refresh
  document.getElementById("overview-refresh").addEventListener("click", function () {
    var btn = document.getElementById("overview-refresh");
    btn.loading = true;
    adminFetch("/api/admin/overview", "POST", { range: currentRange })
      .then(function (data) {
        overviewData = data;
        renderOverview(data);
      })
      .catch(function () { /* error already shown */ })
      .finally(function () { btn.loading = false; });
  });

  // Conversions refresh
  document.getElementById("conversions-refresh").addEventListener("click", function () {
    var select = document.getElementById("categories-select");
    var selectedCats = select.value;
    if (!selectedCats || selectedCats.length === 0) {
      showError("Выберите хотя бы одну категорию.");
      return;
    }
    var cats = selectedCats.map(function (v) { return parseInt(v, 10); });
    
    var btn = document.getElementById("conversions-refresh");
    btn.loading = true;
    adminFetch("/api/admin/conversions", "POST", { range: currentRange, categories: cats })
      .then(function (data) {
        conversionsData = data;
        renderConversions(data);
      })
      .catch(function () { /* error already shown */ })
      .finally(function () { btn.loading = false; });
  });

  // Usernames
  document.getElementById("usernames-btn").addEventListener("click", function () {
    var select = document.getElementById("username-category-select");
    var val = select.value;
    if (!val) {
      showError("Выберите категорию.");
      return;
    }
    var categoryNum = parseInt(val, 10);
    
    var btn = document.getElementById("usernames-btn");
    var resultDiv = document.getElementById("usernames-result");
    btn.loading = true;
    resultDiv.style.display = "none";
    
    adminFetch("/api/admin/usernames", "POST", { category: categoryNum })
      .then(function (data) {
        var text = "Категория: " + data.category + "\\n" +
                   "Название: " + data.label + "\\n" +
                   "Всего: " + data.total + "\\n\\n";
        if (data.users && data.users.length > 0) {
          text += "Пользователи:\\n";
          data.users.forEach(function (u) {
            text += "  " + u.user_id + ": " + (u.username || "(нет юзернейма)") + "\\n";
          });
        } else {
          text += "Пользователи не найдены.";
        }
        resultDiv.textContent = text;
        resultDiv.style.display = "block";
      })
      .catch(function () { /* error already shown */ })
      .finally(function () { btn.loading = false; });
  });

  // Initialize
  loadCategories().then(function () {
    // Auto-load overview on startup
    document.getElementById("overview-refresh").click();
  });
})();
</script>
</body>
</html>
"""


async def miniapp_admin_handler(_request: web.Request) -> web.Response:
    """Serve the Admin Mini App as an inline HTML page."""
    return web.Response(text=_ADMIN_HTML, content_type="text/html")
