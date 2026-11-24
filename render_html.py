#!/usr/bin/env python3
"""유튜브 롱폼 데일리 브리핑 HTML 렌더러.

data/archive.json 을 읽어 날짜별 아카이브 전환이 가능한 신문형 HTML을 생성한다.
로컬 file:// 로 열어도 CORS 에러 없이 즉시 동작하도록 JSON 데이터를 HTML 내부에 내장한다.
"""
from __future__ import annotations

import json
from pathlib import Path

BASE_DIR = Path("/Users/dongkeunkim/youtube-longform-daily")
ARCHIVE_PATH = BASE_DIR / "data" / "archive.json"
DESKTOP_HTML = Path("/Users/dongkeunkim/Desktop/유튜브_롱폼_데일리_브리핑.html")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>유튜브 롱폼 데일리 브리핑 📰 (매일 오후 1시 배달)</title>
  <style>
    :root {
      --bg: #f4f6fb;
      --surface: #ffffff;
      --surface-soft: #f8fafc;
      --text: #18212f;
      --text-sub: #475569;
      --text-muted: #64748b;
      --border: #e2e8f0;
      --primary: #2563eb;
      --primary-dark: #1d4ed8;
      --primary-light: #dbeafe;
      --gold: #d97706;
      --gold-bg: #fffbeb;
      --gold-border: #fde68a;
      --green: #16a34a;
      --green-bg: #f0fdf4;
      --red: #dc2626;
      --red-bg: #fef2f2;
      --purple: #7c3aed;
      --purple-bg: #f5f3ff;
      --radius: 20px;
      --radius-sm: 13px;
      --shadow: 0 8px 26px rgba(15, 23, 42, 0.06);
      --shadow-hover: 0 14px 34px rgba(37, 99, 235, 0.13);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: "Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.68;
      font-size: 16.5px;
      padding-bottom: 90px;
      -webkit-font-smoothing: antialiased;
    }

    .container {
      max-width: 1080px;
      margin: 0 auto;
      padding: 24px 18px;
    }

    /* Newspaper Masthead */
    .masthead {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
      color: #ffffff;
      border-radius: 28px;
      padding: 36px 34px 30px;
      box-shadow: 0 18px 42px rgba(15, 23, 42, 0.22);
      margin-bottom: 22px;
      position: relative;
      overflow: hidden;
    }

    .masthead::after {
      content: "📰";
      position: absolute;
      right: 28px;
      top: 20px;
      font-size: 84px;
      opacity: 0.14;
      pointer-events: none;
    }

    .masthead-top {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 16px;
      padding-bottom: 14px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.18);
      font-size: 14px;
    }

    .badge-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 13px;
      border-radius: 999px;
      font-size: 13.5px;
      font-weight: 800;
    }

    .badge-live {
      background: #fef08a;
      color: #854d0e;
    }

    .badge-glass {
      background: rgba(255, 255, 255, 0.16);
      color: #ffffff;
      backdrop-filter: blur(6px);
    }

    .guide-link {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #ffffff;
      text-decoration: none;
      background: rgba(255, 255, 255, 0.16);
      border: 1px solid rgba(255, 255, 255, 0.32);
      padding: 6px 14px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 13.5px;
      transition: background 0.18s;
    }

    .guide-link:hover {
      background: rgba(255, 255, 255, 0.28);
    }

    .masthead h1 {
      font-size: clamp(27px, 4.2vw, 39px);
      font-weight: 900;
      letter-spacing: -0.03em;
      line-height: 1.22;
      margin-bottom: 10px;
    }

    .masthead-sub {
      font-size: 17px;
      color: rgba(255, 255, 255, 0.9);
      max-width: 780px;
    }

    /* Date Archive Bar */
    .archive-bar {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 16px 20px;
      margin-bottom: 22px;
      box-shadow: var(--shadow);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .archive-label {
      font-weight: 800;
      font-size: 15px;
      color: var(--text);
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .archive-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .date-pill {
      border: 1.5px solid var(--border);
      background: var(--surface-soft);
      color: var(--text-sub);
      padding: 7px 14px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.16s;
    }

    .date-pill:hover {
      border-color: var(--primary);
      color: var(--primary);
    }

    .date-pill.active {
      background: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
    }

    /* Kid-Friendly Summary Card */
    .summary-banner {
      background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
      border: 2px solid #fcd34d;
      border-radius: var(--radius);
      padding: 24px 26px;
      margin-bottom: 26px;
      box-shadow: var(--shadow);
    }

    .summary-title {
      font-size: 19px;
      font-weight: 900;
      color: #92400e;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .summary-points {
      list-style: none;
      display: grid;
      gap: 8px;
    }

    .summary-points li {
      background: rgba(255, 255, 255, 0.85);
      border-radius: 12px;
      padding: 11px 15px;
      font-size: 15.5px;
      color: #451a03;
      border: 1px solid rgba(245, 158, 11, 0.25);
    }

    /* Quick Nav */
    .quick-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 28px;
    }

    .quick-nav a {
      text-decoration: none;
      background: var(--surface);
      color: var(--text);
      border: 1.5px solid var(--border);
      padding: 10px 16px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 14.5px;
      transition: all 0.18s;
      box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
    }

    .quick-nav a:hover {
      border-color: var(--primary);
      color: var(--primary);
      transform: translateY(-2px);
    }

    /* Section Header */
    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 38px 0 18px;
    }

    .section-num {
      width: 42px;
      height: 42px;
      border-radius: 14px;
      background: var(--primary);
      color: #ffffff;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      font-weight: 900;
      flex-shrink: 0;
    }

    .section-header h2 {
      font-size: 25px;
      font-weight: 900;
      letter-spacing: -0.02em;
    }

    .section-desc {
      color: var(--text-sub);
      margin-bottom: 18px;
      font-size: 15.5px;
    }

    /* Filter Tabs */
    .cat-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }

    .cat-tab {
      border: 1.5px solid var(--border);
      background: var(--surface);
      color: var(--text-sub);
      padding: 8px 15px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.16s;
    }

    .cat-tab.active {
      background: var(--text);
      color: #ffffff;
      border-color: var(--text);
    }

    /* Score Table */
    .table-wrap {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      overflow-x: auto;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 780px;
    }

    th {
      background: #f1f5f9;
      color: #334155;
      font-weight: 800;
      font-size: 13.5px;
      text-align: left;
      padding: 14px 14px;
      border-bottom: 1.5px solid var(--border);
      white-space: nowrap;
    }

    td {
      padding: 15px 14px;
      border-bottom: 1px solid #eef2f6;
      vertical-align: top;
      font-size: 14.5px;
    }

    tr:last-child td { border-bottom: none; }
    tr:hover td { background: #f8fbff; }

    .rank-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 34px;
      height: 30px;
      border-radius: 10px;
      font-weight: 900;
      font-size: 14px;
      background: #e2e8f0;
      color: #334155;
    }

    .rank-1 { background: #fef08a; color: #854d0e; }
    .rank-2 { background: #e2e8f0; color: #1e293b; }
    .rank-3 { background: #fed7aa; color: #9a3412; }

    .cat-pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 800;
      white-space: nowrap;
    }

    .score-big {
      font-size: 20px;
      font-weight: 900;
      color: var(--primary-dark);
      line-height: 1.1;
    }

    .score-sub {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 4px;
      white-space: nowrap;
    }

    .mat-title {
      font-weight: 800;
      font-size: 15.5px;
      color: var(--text);
      margin-bottom: 6px;
      line-height: 1.4;
    }

    .mat-reason {
      color: var(--text-sub);
      font-size: 14px;
      margin-bottom: 6px;
    }

    .mat-evidence {
      background: #f0f9ff;
      border-left: 3px solid #0284c7;
      padding: 6px 10px;
      border-radius: 6px;
      font-size: 13.5px;
      color: #0c4a6e;
    }

    .yt-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      text-decoration: none;
      background: #ef4444;
      color: #ffffff;
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 800;
      white-space: nowrap;
      transition: opacity 0.15s;
    }

    .yt-btn:hover { opacity: 0.88; }

    .meta-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
      font-size: 12px;
      color: var(--text-muted);
    }

    .meta-chip {
      background: #f1f5f9;
      padding: 2px 8px;
      border-radius: 6px;
      font-weight: 700;
    }

    /* Rising Channels Grid */
    .channel-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 18px;
      margin-bottom: 24px;
    }

    .channel-card {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 22px;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 12px;
      transition: transform 0.16s, box-shadow 0.16s;
    }

    .channel-card:hover {
      transform: translateY(-2px);
      box-shadow: var(--shadow-hover);
    }

    .ch-top {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
    }

    .ch-name {
      font-size: 19px;
      font-weight: 900;
      color: var(--text);
    }

    .ch-stats {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 8px;
    }

    .ch-stat {
      background: var(--surface-soft);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 9px 11px;
    }

    .ch-stat-lbl {
      font-size: 11.5px;
      color: var(--text-muted);
      font-weight: 700;
    }

    .ch-stat-val {
      font-size: 15px;
      font-weight: 900;
      color: var(--text);
      margin-top: 2px;
    }

    .ch-why {
      background: var(--gold-bg);
      border: 1px solid var(--gold-border);
      border-radius: 12px;
      padding: 12px 14px;
      font-size: 14px;
      color: #78350f;
    }

    /* Deep Dive Cards */
    .deep-card {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 26px;
      margin-bottom: 22px;
      box-shadow: var(--shadow);
    }

    .deep-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
      padding-bottom: 14px;
      border-bottom: 1.5px solid var(--border);
    }

    .deep-head h3 {
      font-size: 20px;
      font-weight: 900;
      line-height: 1.35;
    }

    .six-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
      gap: 12px;
    }

    .six-box {
      background: var(--surface-soft);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px 16px;
    }

    .six-box.action-box {
      grid-column: 1 / -1;
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      border: 1.5px solid #93c5fd;
    }

    .six-lbl {
      font-size: 13.5px;
      font-weight: 900;
      color: var(--primary-dark);
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .six-box.action-box .six-lbl {
      color: #1e3a8a;
      font-size: 15px;
    }

    .six-txt {
      font-size: 14.5px;
      color: var(--text);
    }

    .footer {
      margin-top: 48px;
      text-align: center;
      color: var(--text-muted);
      font-size: 14px;
      padding: 24px;
      border-top: 1px solid var(--border);
    }

    @media (max-width: 640px) {
      .masthead { padding: 24px 20px; }
      .deep-card { padding: 18px; }
    }
  </style>
</head>
<body>
  <div class="container">
    <header class="masthead">
      <div class="masthead-top">
        <div class="badge-row">
          <span class="badge badge-live">🕐 매일 오후 1시 자동 배달</span>
          <span class="badge badge-glass" id="issue-badge">제1호 · 로딩 중</span>
          <span class="badge badge-glass" id="engine-badge">Jev 100점 + AI 심층 해부</span>
        </div>
        <a class="guide-link" href="https://1pronano.github.io/youtube-longform-guide/" target="_blank" rel="noopener">
          📘 기존 교과서 가이드 보러가기 →
        </a>
      </div>
      <h1>유튜브 롱폼 데일리 브리핑 📰</h1>
      <p class="masthead-sub">
        초등학생도 1분 만에 이해하는 <strong>매일 오후 1시 유튜브 롱폼 신문</strong>!
        오늘 제일 잘 팔릴 4개 분야 소재(Jev 100점 순) · 막 뜨고 있는 신생 채널 · 떡상 이유 6단 해부까지 한 번에 배달합니다.
      </p>
    </header>

    <div class="archive-bar">
      <div class="archive-label">📅 날짜별 신문 골라보기</div>
      <div class="archive-pills" id="date-pills"></div>
    </div>

    <section class="summary-banner">
      <div class="summary-title">🧒 초등학생도 한 번에 이해하는 오늘의 3줄 요약</div>
      <ul class="summary-points" id="summary-points"></ul>
    </section>

    <nav class="quick-nav">
      <a href="#sec-materials">① 오늘의 4개 분야 추천 소재 (Jev 100점 순)</a>
      <a href="#sec-channels">② 오늘의 핫한 신생 에셋 채널 추적 🔥</a>
      <a href="#sec-deep">③ 오늘의 떡상 이유 6단 심층 해부 🔬</a>
    </nav>

    <!-- Section 1 -->
    <section id="sec-materials">
      <div class="section-header">
        <div class="section-num">1</div>
        <h2>오늘의 4개 분야 추천 소재 (Jev 100점 높은 순)</h2>
      </div>
      <p class="section-desc">
        <strong>후킹력(30) + 물증 확보(30) + 스토리 몰입(20) + 채널 적합성(20) = 100점 만점</strong>으로 Jev가 직접 채점했어요.
        제일 점수가 높은 <strong>1등 보물 소재가 맨 위</strong>에 올라와 있습니다!
      </p>

      <div class="cat-tabs" id="cat-tabs"></div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>순위</th>
              <th>분야</th>
              <th>Jev 점수</th>
              <th>소재 제목 · 쉬운 선정 근거 · 1:1 물증 포인트</th>
              <th>원본</th>
            </tr>
          </thead>
          <tbody id="materials-tbody"></tbody>
        </table>
      </div>
    </section>

    <!-- Section 2 -->
    <section id="sec-channels">
      <div class="section-header">
        <div class="section-num">2</div>
        <h2>오늘의 핫한 신생 에셋 채널 추적 🔥</h2>
      </div>
      <p class="section-desc">
        영상 몇 개 안 올렸는데도 조회수가 펑펑 터지고 있는 <strong>요즘 제일 잘나가는 새내기 채널</strong>들이에요.
        어떻게 시작해서 빨리 컸는지 한눈에 비교해 보세요!
      </p>
      <div class="channel-grid" id="channels-grid"></div>
    </section>

    <!-- Section 3 -->
    <section id="sec-deep">
      <div class="section-header">
        <div class="section-num">3</div>
        <h2>오늘의 떡상 이유 심층 분석 (6단 해부 🔬)</h2>
      </div>
      <p class="section-desc">
        “왜 하필 이 영상만 조회수가 터졌을까?” 궁금증을 <strong>기획 · 키워드 · 이슈 · 0초 후킹 · 영상미 · 바로 카피할 1줄 액션</strong> 6칸으로 알기 쉽게 쪼개 놓았습니다.
      </p>
      <div id="deep-container"></div>
    </section>

    <footer class="footer">
      <p><strong>유튜브 롱폼 데일리 브리핑</strong> · 매일 오후 1시(13:00 KST) 자동 수집 · Jev 채점 · AI 심층 분석 · 자동 배포</p>
      <p style="margin-top:6px;">
        기존 정본 교과서 링크는 그대로 보존되어 있습니다:
        <a href="https://1pronano.github.io/youtube-longform-guide/" target="_blank" rel="noopener" style="color:var(--primary);font-weight:700;">
          https://1pronano.github.io/youtube-longform-guide/
        </a>
      </p>
    </footer>
  </div>

  <script id="daily-data" type="application/json">__ARCHIVE_JSON__</script>
  <script>
    const ARCHIVE = JSON.parse(document.getElementById("daily-data").textContent);
    const DATES = Object.keys(ARCHIVE.editions || {}).sort().reverse();
    let currentDate = DATES[0];
    let currentCat = "ALL";

    function esc(s) {
      return String(s ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
    }

    function fmtNum(n) {
      if (n === null || n === undefined || n === "") return "-";
      const num = Number(n);
      if (Number.isNaN(num)) return String(n);
      if (num >= 10000) return (num / 10000).toFixed(1).replace(/\.0$/, "") + "만";
      return num.toLocaleString("ko-KR");
    }

    function renderDatePills() {
      const box = document.getElementById("date-pills");
      box.innerHTML = DATES.map((d, idx) => {
        const ed = ARCHIVE.editions[d];
        const label = idx === 0 ? `${d} (최신 제${ed.issue_no || 1}호)` : `${d} (제${ed.issue_no || 1}호)`;
        return `<button class="date-pill ${d === currentDate ? "active" : ""}" onclick="selectDate('${d}')">${esc(label)}</button>`;
      }).join("");
    }

    function selectDate(d) {
      currentDate = d;
      currentCat = "ALL";
      renderEdition();
    }

    function selectCat(catId) {
      currentCat = catId;
      renderMaterials();
      renderCatTabs();
    }

    function renderCatTabs() {
      const ed = ARCHIVE.editions[currentDate];
      const cats = [
        { id: "ALL", label: `전체 보기 (${(ed.materials || []).length}개)` },
        { id: "cat_movie", label: "🎬 옛날 외국 영화" },
        { id: "cat_police", label: "🚔 미국 경찰 바디캠" },
        { id: "cat_senior", label: "📺 어르신 거실 TV" },
        { id: "cat_global", label: "🌍 해외 대박 빈집" }
      ];
      document.getElementById("cat-tabs").innerHTML = cats.map(c =>
        `<button class="cat-tab ${currentCat === c.id ? "active" : ""}" onclick="selectCat('${c.id}')">${esc(c.label)}</button>`
      ).join("");
    }

    function renderMaterials() {
      const ed = ARCHIVE.editions[currentDate];
      const list = (ed.materials || [])
        .filter(m => currentCat === "ALL" || m.category_id === currentCat)
        .slice()
        .sort((a, b) => (b.total_score || 0) - (a.total_score || 0));

      const tbody = document.getElementById("materials-tbody");
      tbody.innerHTML = list.map((m, i) => {
        const rank = i + 1;
        const rCls = rank === 1 ? "rank-1" : rank === 2 ? "rank-2" : rank === 3 ? "rank-3" : "";
        const s = m.scores || {};
        return `
          <tr>
            <td><span class="rank-badge ${rCls}">${rank}위</span></td>
            <td>
              <span class="cat-pill" style="background:${esc(m.category_bg || '#eef2ff')};color:${esc(m.category_color || '#2563eb')};">
                ${esc(m.category_emoji || '📌')} ${esc(m.category_name || '')}
              </span>
            </td>
            <td>
              <div class="score-big">${Number(m.total_score || 0).toFixed(1)}점</div>
              <div class="score-sub">
                후킹 ${Number(s.hook || 0).toFixed(1)} · 물증 ${Number(s.evidence || 0).toFixed(1)}<br/>
                스토리 ${Number(s.story || 0).toFixed(1)} · 적합 ${Number(s.fit || 0).toFixed(1)}
              </div>
            </td>
            <td>
              <div class="mat-title">${esc(m.title)}</div>
              <div class="mat-reason">💡 <strong>선정 근거:</strong> ${esc(m.reason)}</div>
              <div class="mat-evidence">🎯 <strong>1:1 물증 매칭:</strong> ${esc(m.evidence_tip)}</div>
              <div class="meta-chips">
                <span class="meta-chip">📺 ${esc(m.channel || '-')}</span>
                <span class="meta-chip">👀 조회수 ${fmtNum(m.view_count)}회</span>
                <span class="meta-chip">⏱️ ${esc(m.duration_str || '-')}</span>
                ${m.upload_date ? `<span class="meta-chip">📅 ${esc(m.upload_date)}</span>` : ""}
              </div>
            </td>
            <td>
              <a class="yt-btn" href="${esc(m.url)}" target="_blank" rel="noopener">▶ 보기</a>
            </td>
          </tr>
        `;
      }).join("");
    }

    function renderChannels() {
      const ed = ARCHIVE.editions[currentDate];
      const grid = document.getElementById("channels-grid");
      grid.innerHTML = (ed.rising_channels || []).map(ch => `
        <article class="channel-card">
          <div class="ch-top">
            <div>
              <span class="cat-pill" style="background:${esc(ch.category_bg || '#eef2ff')};color:${esc(ch.category_color || '#2563eb')};margin-bottom:6px;">
                ${esc(ch.category_emoji || '🔥')} ${esc(ch.category_name || '')}
              </span>
              <div class="ch-name">${esc(ch.channel_name)}</div>
            </div>
            ${ch.channel_url ? `<a class="yt-btn" href="${esc(ch.channel_url)}" target="_blank" rel="noopener">채널 가기</a>` : ""}
          </div>
          <div class="ch-stats">
            <div class="ch-stat">
              <div class="ch-stat-lbl">📅 개설/활동</div>
              <div class="ch-stat-val">${esc(ch.created_info || '-')}</div>
            </div>
            <div class="ch-stat">
              <div class="ch-stat-lbl">🎬 총 영상 수</div>
              <div class="ch-stat-val">${esc(ch.video_count_str || '-')}</div>
            </div>
            <div class="ch-stat">
              <div class="ch-stat-lbl">👥 구독자</div>
              <div class="ch-stat-val">${esc(ch.subscribers_str || '-')}</div>
            </div>
            <div class="ch-stat">
              <div class="ch-stat-lbl">⚡ 편당 평균뷰</div>
              <div class="ch-stat-val">${esc(ch.avg_views_str || '-')}</div>
            </div>
          </div>
          <div class="ch-why">
            <strong>🧒 쉽게 풀이한 떡상 비결:</strong><br/>
            ${esc(ch.easy_analysis)}
          </div>
          ${ch.top_video_title ? `
            <div style="font-size:13.5px;color:var(--text-sub);">
              🔥 대표 히트작:
              <a href="${esc(ch.top_video_url || ch.channel_url || '#')}" target="_blank" rel="noopener" style="color:var(--primary);font-weight:700;">
                ${esc(ch.top_video_title)}
              </a>
            </div>
          ` : ""}
        </article>
      `).join("");
    }

    function renderDeepDives() {
      const ed = ARCHIVE.editions[currentDate];
      const box = document.getElementById("deep-container");
      box.innerHTML = (ed.deep_dives || []).map((d, idx) => `
        <article class="deep-card">
          <div class="deep-head">
            <div>
              <span class="cat-pill" style="background:${esc(d.category_bg || '#eef2ff')};color:${esc(d.category_color || '#2563eb')};margin-bottom:6px;">
                ${esc(d.category_emoji || '🔬')} 분석 #${idx + 1} · ${esc(d.category_name || '')}
              </span>
              <h3>${esc(d.title)}</h3>
              <div style="font-size:13.5px;color:var(--text-muted);margin-top:4px;">
                채널: <strong>${esc(d.channel || '-')}</strong> · 조회수 <strong>${fmtNum(d.view_count)}회</strong>
              </div>
            </div>
            ${d.url ? `<a class="yt-btn" href="${esc(d.url)}" target="_blank" rel="noopener">▶ 원본 영상 보기</a>` : ""}
          </div>
          <div class="six-grid">
            <div class="six-box">
              <div class="six-lbl">🎯 ① 기획 (판 짜기)</div>
              <div class="six-txt">${esc(d.planning)}</div>
            </div>
            <div class="six-box">
              <div class="six-lbl">🔑 ② 키워드 (클릭 마법 단어)</div>
              <div class="six-txt">${esc(d.keywords)}</div>
            </div>
            <div class="six-box">
              <div class="six-lbl">🔥 ③ 이슈 (지금 왜 궁금할까?)</div>
              <div class="six-txt">${esc(d.issue)}</div>
            </div>
            <div class="six-box">
              <div class="six-lbl">⚡ ④ 0초 후킹 (첫 3초 붙잡기)</div>
              <div class="six-txt">${esc(d.hook_0s)}</div>
            </div>
            <div class="six-box">
              <div class="six-lbl">🎨 ⑤ 영상미 (화면·편집 비법)</div>
              <div class="six-txt">${esc(d.visual_style)}</div>
            </div>
            <div class="six-box action-box">
              <div class="six-lbl">✅ ⑥ 오늘 당장 카피할 1줄 액션</div>
              <div class="six-txt"><strong>${esc(d.copy_action)}</strong></div>
            </div>
          </div>
        </article>
      `).join("");
    }

    function renderEdition() {
      const ed = ARCHIVE.editions[currentDate];
      if (!ed) return;
      document.getElementById("issue-badge").textContent = `제${ed.issue_no || 1}호 · ${currentDate} 발행 (${ed.generated_at || ''})`;
      document.getElementById("engine-badge").textContent = ed.scoring_badge || "Jev 100점 + AI 심층 해부";
      document.getElementById("summary-points").innerHTML = (ed.easy_summary || []).map(p => `<li>${esc(p)}</li>`).join("");
      renderDatePills();
      renderCatTabs();
      renderMaterials();
      renderChannels();
      renderDeepDives();
    }

    renderEdition();
  </script>
</body>
</html>
"""


def build_html() -> Path:
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    # </script> 이스케이프 방어
    safe_json = json.dumps(archive, ensure_ascii=False, indent=2).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__ARCHIVE_JSON__", safe_json)
    DESKTOP_HTML.write_text(html, encoding="utf-8")
    print(f"✅ 데일리 브리핑 HTML 생성 완료: {DESKTOP_HTML} ({DESKTOP_HTML.stat().st_size:,} bytes)")
    return DESKTOP_HTML


if __name__ == "__main__":
    build_html()
