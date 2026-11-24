#!/usr/bin/env python3
"""유튜브 롱폼 데일리 브리핑 HTML 렌더러 (분야별 10개 총 40개 · 즉시 제작 장전 팩 UI).

data/archive.json 을 읽어 날짜별 아카이브 전환 + 분야별 탭 + 키워드 검색 + 원클릭 복사가 가능한
신문형/작업실형 HTML을 생성한다.
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
  <title>유튜브 롱폼 데일리 브리핑 📰 (매일 오후 1시 · 40개 즉시 작업 팩)</title>
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
      line-height: 1.66;
      font-size: 16px;
      padding-bottom: 100px;
      -webkit-font-smoothing: antialiased;
    }

    .container {
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px 18px;
    }

    /* Newspaper Masthead */
    .masthead {
      background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 55%, #2563eb 100%);
      color: #ffffff;
      border-radius: 28px;
      padding: 34px 32px 28px;
      box-shadow: 0 18px 42px rgba(15, 23, 42, 0.22);
      margin-bottom: 22px;
      position: relative;
      overflow: hidden;
    }

    .masthead::after {
      content: "📰";
      position: absolute;
      right: 28px;
      top: 18px;
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
      font-size: 13px;
      font-weight: 800;
    }

    .badge-live { background: #fef08a; color: #854d0e; }
    .badge-glass { background: rgba(255, 255, 255, 0.16); color: #ffffff; backdrop-filter: blur(6px); }

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
    .guide-link:hover { background: rgba(255, 255, 255, 0.28); }

    .masthead h1 {
      font-size: clamp(26px, 4.2vw, 38px);
      font-weight: 900;
      letter-spacing: -0.03em;
      line-height: 1.22;
      margin-bottom: 10px;
    }

    .masthead-sub {
      font-size: 16.5px;
      color: rgba(255, 255, 255, 0.92);
      max-width: 820px;
    }

    /* Date Archive Bar */
    .archive-bar {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 15px 20px;
      margin-bottom: 20px;
      box-shadow: var(--shadow);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .archive-label { font-weight: 800; font-size: 15px; display: flex; align-items: center; gap: 8px; }
    .archive-pills { display: flex; flex-wrap: wrap; gap: 8px; }

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
    .date-pill:hover { border-color: var(--primary); color: var(--primary); }
    .date-pill.active {
      background: var(--primary);
      color: #ffffff;
      border-color: var(--primary);
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
    }

    /* Summary Card */
    .audit-banner {
      background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
      border: 2px solid #34d399;
      border-radius: var(--radius);
      padding: 16px 22px;
      margin-bottom: 18px;
      box-shadow: var(--shadow);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }
    .audit-title {
      font-size: 16px;
      font-weight: 900;
      color: #065f46;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .audit-pills {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .audit-pill {
      background: #ffffff;
      border: 1.5px solid #6ee7b7;
      color: #065f46;
      padding: 5px 12px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 800;
    }
    .audit-pill.zero {
      background: #059669;
      border-color: #059669;
      color: #ffffff;
    }

    .summary-banner {
      background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
      border: 2px solid #fcd34d;
      border-radius: var(--radius);
      padding: 22px 24px;
      margin-bottom: 24px;
      box-shadow: var(--shadow);
    }

    .summary-title {
      font-size: 18.5px;
      font-weight: 900;
      color: #92400e;
      margin-bottom: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .summary-points { list-style: none; display: grid; gap: 8px; }
    .summary-points li {
      background: rgba(255, 255, 255, 0.88);
      border-radius: 12px;
      padding: 10px 14px;
      font-size: 15px;
      color: #451a03;
      border: 1px solid rgba(245, 158, 11, 0.25);
    }

    /* Quick Nav */
    .quick-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 26px;
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
    .quick-nav a:hover { border-color: var(--primary); color: var(--primary); transform: translateY(-2px); }

    /* Section Header */
    .section-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 36px 0 14px;
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

    .section-header h2 { font-size: 24px; font-weight: 900; letter-spacing: -0.02em; }
    .section-desc { color: var(--text-sub); margin-bottom: 18px; font-size: 15.5px; }

    /* Toolbar: Tabs + Search + Expand All */
    .toolbar {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 16px 18px;
      margin-bottom: 20px;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .cat-tabs { display: flex; flex-wrap: wrap; gap: 8px; }
    .cat-tab {
      border: 1.5px solid var(--border);
      background: var(--surface-soft);
      color: var(--text-sub);
      padding: 8px 15px;
      border-radius: 999px;
      font-weight: 800;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.16s;
    }
    .cat-tab:hover { border-color: var(--primary); color: var(--primary); }
    .cat-tab.active { background: var(--text); color: #ffffff; border-color: var(--text); }

    .search-row {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
      justify-content: space-between;
    }

    .search-input {
      flex: 1 1 280px;
      padding: 10px 15px;
      border: 1.5px solid var(--border);
      border-radius: 12px;
      font-size: 14.5px;
      font-family: inherit;
      outline: none;
      background: var(--surface-soft);
    }
    .search-input:focus { border-color: var(--primary); background: #ffffff; }

    .toolbar-btns { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .count-pill {
      font-size: 13.5px;
      font-weight: 800;
      color: var(--primary-dark);
      background: var(--primary-light);
      padding: 7px 12px;
      border-radius: 999px;
    }

    .ghost-btn {
      border: 1.5px solid var(--border);
      background: var(--surface);
      color: var(--text-sub);
      padding: 8px 13px;
      border-radius: 10px;
      font-size: 13.5px;
      font-weight: 800;
      cursor: pointer;
      transition: all 0.15s;
    }
    .ghost-btn:hover { border-color: var(--primary); color: var(--primary); }

    /* Material Pack Cards */
    .pack-list { display: flex; flex-direction: column; gap: 16px; }

    .pack-card {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      overflow: hidden;
      transition: border-color 0.18s, box-shadow 0.18s;
    }
    .pack-card:hover { border-color: #93c5fd; box-shadow: var(--shadow-hover); }
    .pack-card.open { border-color: var(--primary); }

    .pack-head {
      padding: 20px 22px 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .pack-top-row {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }

    .pack-badges {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }

    .rank-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 4px 11px;
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

    .new-pill {
      background: #dcfce7;
      color: #166534;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
    }

    .keep-pill {
      background: #f1f5f9;
      color: #475569;
      padding: 3px 9px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 800;
    }

    .score-pill-box {
      display: flex;
      align-items: center;
      gap: 10px;
      background: #eff6ff;
      border: 1.5px solid #bfdbfe;
      border-radius: 14px;
      padding: 6px 14px;
    }

    .score-big { font-size: 21px; font-weight: 900; color: var(--primary-dark); line-height: 1; }
    .score-sub { font-size: 12px; color: #1e40af; font-weight: 700; line-height: 1.35; }

    .pack-title {
      font-size: 18px;
      font-weight: 900;
      color: var(--text);
      line-height: 1.38;
    }

    .pack-reason {
      font-size: 14.5px;
      color: var(--text-sub);
    }

    .meta-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      font-size: 12.5px;
      color: var(--text-muted);
    }
    .meta-chip {
      background: #f1f5f9;
      padding: 3px 9px;
      border-radius: 7px;
      font-weight: 700;
    }
    .meta-chip.hot-fresh {
      background: #fef2f2;
      color: #b91c1c;
      border: 1px solid #fecaca;
    }
    .meta-chip.explosion {
      background: #f5f3ff;
      color: #6d28d9;
      border: 1px solid #ddd6fe;
    }
    .meta-chip.views-ok {
      background: #ecfdf5;
      color: #047857;
      border: 1px solid #a7f3d0;
    }

    .copyright-bar {
      background: #f8fafc;
      border-left: 3.5px solid #64748b;
      padding: 7px 11px;
      border-radius: 7px;
      font-size: 13px;
      color: #334155;
    }

    /* Action Buttons Row */
    .action-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      padding-top: 4px;
    }

    .btn-primary {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
      color: #ffffff;
      border: none;
      padding: 10px 16px;
      border-radius: 12px;
      font-size: 14px;
      font-weight: 900;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
      transition: transform 0.14s, opacity 0.14s;
    }
    .btn-primary:hover { transform: translateY(-1px); opacity: 0.94; }

    .btn-copy {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: #f1f5f9;
      color: #1e293b;
      border: 1.5px solid #cbd5e1;
      padding: 9px 14px;
      border-radius: 12px;
      font-size: 13.5px;
      font-weight: 800;
      cursor: pointer;
      transition: all 0.14s;
    }
    .btn-copy:hover { border-color: var(--primary); color: var(--primary); background: #eff6ff; }

    .yt-btn {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      text-decoration: none;
      background: #ef4444;
      color: #ffffff;
      padding: 9px 14px;
      border-radius: 12px;
      font-size: 13.5px;
      font-weight: 800;
      white-space: nowrap;
      transition: opacity 0.15s;
    }
    .yt-btn:hover { opacity: 0.88; }

    .btn-toggle {
      margin-left: auto;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      background: #fffbeb;
      color: #92400e;
      border: 1.5px solid #fcd34d;
      padding: 9px 14px;
      border-radius: 12px;
      font-size: 13.5px;
      font-weight: 800;
      cursor: pointer;
    }
    .btn-toggle:hover { background: #fef3c7; }

    /* Pack Body (Expanded Production Blueprint) */
    .pack-body {
      display: none;
      border-top: 1.5px dashed var(--border);
      background: #fafcff;
      padding: 20px 22px 24px;
    }
    .pack-card.open .pack-body { display: block; }

    .pack-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 14px;
      margin-bottom: 14px;
    }

    .pack-box {
      background: #ffffff;
      border: 1.5px solid var(--border);
      border-radius: 15px;
      padding: 15px 16px;
    }
    .pack-box.full { grid-column: 1 / -1; }

    .box-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 10px;
    }

    .box-lbl {
      font-size: 14px;
      font-weight: 900;
      color: var(--primary-dark);
    }

    .mini-copy {
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      color: #334155;
      padding: 4px 9px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 800;
      cursor: pointer;
    }
    .mini-copy:hover { border-color: var(--primary); color: var(--primary); }

    .title-opt {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 8px;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 9px 11px;
      margin-bottom: 8px;
      font-size: 14.5px;
      font-weight: 800;
      color: var(--text);
    }
    .title-opt:last-child { margin-bottom: 0; }

    /* Thumbnail 2-line Preview */
    .thumb-preview {
      background: linear-gradient(135deg, #090d16 0%, #1e293b 100%);
      border-radius: 14px;
      padding: 20px 18px;
      text-align: center;
      border: 2px solid #334155;
      box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.5);
    }
    .thumb-l1 {
      color: #ffffff;
      font-size: 21px;
      font-weight: 900;
      letter-spacing: -0.02em;
      text-shadow: 0 3px 10px rgba(0,0,0,0.85);
      line-height: 1.25;
    }
    .thumb-l2 {
      color: #ff3b30;
      font-size: 23px;
      font-weight: 900;
      letter-spacing: -0.02em;
      text-shadow: 0 3px 10px rgba(0,0,0,0.9);
      margin-top: 4px;
      line-height: 1.25;
    }

    /* Opening Speech Bubble */
    .opening-quote {
      background: linear-gradient(135deg, #fef2f2 0%, #fff1f2 100%);
      border: 1.5px solid #fecaca;
      border-left: 5px solid #ef4444;
      border-radius: 12px;
      padding: 13px 15px;
      font-size: 15.5px;
      font-weight: 800;
      color: #7f1d1d;
    }

    /* 4 Acts Grid */
    .acts-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }
    .act-card {
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 11px 13px;
    }
    .act-tag {
      display: inline-block;
      font-size: 12px;
      font-weight: 900;
      color: #ffffff;
      background: #334155;
      padding: 2px 8px;
      border-radius: 6px;
      margin-bottom: 6px;
    }
    .act-card:nth-child(1) .act-tag { background: #dc2626; }
    .act-card:nth-child(2) .act-tag { background: #2563eb; }
    .act-card:nth-child(3) .act-tag { background: #d97706; }
    .act-card:nth-child(4) .act-tag { background: #16a34a; }
    .act-txt { font-size: 13.8px; color: var(--text); }

    /* Evidence Checklist */
    .ev-list { list-style: none; display: grid; gap: 7px; }
    .ev-list li {
      background: #f0f9ff;
      border: 1px solid #bae6fd;
      border-radius: 10px;
      padding: 8px 12px;
      font-size: 14px;
      color: #0c4a6e;
      font-weight: 700;
    }

    /* Work Prompt Preview */
    .prompt-pre {
      background: #0f172a;
      color: #e2e8f0;
      border-radius: 12px;
      padding: 14px 16px;
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 13px;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 240px;
      overflow-y: auto;
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
      padding: 20px;
      box-shadow: var(--shadow);
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .ch-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
    .ch-name { font-size: 18px; font-weight: 900; }
    .ch-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
    .ch-stat { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 12px; padding: 9px 11px; }
    .ch-stat-lbl { font-size: 11.5px; color: var(--text-muted); font-weight: 700; }
    .ch-stat-val { font-size: 15px; font-weight: 900; margin-top: 2px; }
    .ch-why {
      background: var(--gold-bg);
      border: 1px solid var(--gold-border);
      border-radius: 12px;
      padding: 11px 13px;
      font-size: 14px;
      color: #78350f;
    }

    /* Deep Dive Cards */
    .deep-card {
      background: var(--surface);
      border: 1.5px solid var(--border);
      border-radius: var(--radius);
      padding: 24px;
      margin-bottom: 20px;
      box-shadow: var(--shadow);
    }

    .deep-head {
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 16px;
      padding-bottom: 12px;
      border-bottom: 1.5px solid var(--border);
    }
    .deep-head h3 { font-size: 19px; font-weight: 900; line-height: 1.35; }

    .six-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 12px;
    }
    .six-box { background: var(--surface-soft); border: 1px solid var(--border); border-radius: 14px; padding: 13px 15px; }
    .six-box.action-box {
      grid-column: 1 / -1;
      background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
      border: 1.5px solid #93c5fd;
    }
    .six-lbl { font-size: 13.5px; font-weight: 900; color: var(--primary-dark); margin-bottom: 6px; }
    .six-txt { font-size: 14.2px; color: var(--text); }

    /* Toast */
    #toast {
      position: fixed;
      left: 50%;
      bottom: 28px;
      transform: translateX(-50%) translateY(90px);
      background: #0f172a;
      color: #ffffff;
      padding: 13px 22px;
      border-radius: 999px;
      font-size: 14.5px;
      font-weight: 800;
      box-shadow: 0 12px 30px rgba(15, 23, 42, 0.35);
      z-index: 9999;
      opacity: 0;
      transition: all 0.24s ease;
      pointer-events: none;
    }
    #toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }

    .footer {
      margin-top: 48px;
      text-align: center;
      color: var(--text-muted);
      font-size: 14px;
      padding: 24px;
      border-top: 1px solid var(--border);
    }

    @media (max-width: 640px) {
      .masthead { padding: 24px 18px; }
      .pack-head, .pack-body { padding: 16px; }
      .btn-toggle { margin-left: 0; width: 100%; justify-content: center; }
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
          <span class="badge badge-glass" id="engine-badge">Jev 100점 · 40개 즉시 작업 팩</span>
        </div>
        <a class="guide-link" href="https://1pronano.github.io/youtube-longform-guide/" target="_blank" rel="noopener">
          📘 기존 교과서 가이드 보러가기 →
        </a>
      </div>
      <h1>유튜브 롱폼 데일리 브리핑 📰</h1>
      <p class="masthead-sub">
        제목만 던져주는 신문이 아닙니다! <strong>4개 황금 분야 × 10개씩 = 매일 총 40개 ‘바로 작업 가능 장전 팩’</strong>을
        Jev 100점 순으로 배달합니다. 파란색 <strong>[⚡ 바로 작업 지시문 복사]</strong> 버튼만 눌러 채팅창에 붙여넣으세요!
      </p>
    </header>

    <div class="archive-bar">
      <div class="archive-label">📅 날짜별 신문 골라보기</div>
      <div class="archive-pills" id="date-pills"></div>
    </div>

    <section class="audit-banner" id="audit-banner">
      <div class="audit-title">🔒 오늘의 철벽 검수 통과 증명 (5대 하드게이트 100% 실측)</div>
      <div class="audit-pills" id="audit-pills"></div>
    </section>

    <section class="summary-banner">
      <div class="summary-title">🧒 초등학생도 한 번에 이해하는 오늘의 3줄 요약</div>
      <ul class="summary-points" id="summary-points"></ul>
    </section>

    <nav class="quick-nav">
      <a href="#sec-materials">① 오늘의 40개 즉시 작업 장전 팩 (분야별 10개 · Jev 순)</a>
      <a href="#sec-channels">② 오늘의 핫한 신생 에셋 채널 추적 🔥</a>
      <a href="#sec-deep">③ 오늘의 떡상 이유 6단 심층 해부 🔬</a>
    </nav>

    <!-- Section 1 -->
    <section id="sec-materials">
      <div class="section-header">
        <div class="section-num">1</div>
        <h2>오늘의 4개 분야 × 10개 = 40개 즉시 작업 장전 팩</h2>
      </div>
      <p class="section-desc">
        <strong>후킹력(30) + 물증 확보(30) + 스토리 몰입(20) + 채널 적합성(20) = 100점 만점</strong>으로 Jev가 직접 줄 세웠어요.
        각 카드마다 <strong>① 원본 URL + 저작권 메모 ② 제목 2안 ③ 썸네일 2줄 ④ 0~4초 오프닝 대사 ⑤ 4막 뼈대 + 1:1 물증 체크리스트 ⑥ 원클릭 작업 지시문</strong>이 전부 들어 있습니다!
      </p>

      <div class="toolbar">
        <div class="cat-tabs" id="cat-tabs"></div>
        <div class="search-row">
          <input type="text" id="search-input" class="search-input" placeholder="🔍 제목, 채널명, 키워드로 40개 장전 팩 바로 찾기..." oninput="onSearchInput(this.value)" />
          <div class="toolbar-btns">
            <span class="count-pill" id="visible-count">40개 표시 중</span>
            <button class="ghost-btn" onclick="toggleAllPacks(true)">📂 모두 펼치기</button>
            <button class="ghost-btn" onclick="toggleAllPacks(false)">📁 모두 접기</button>
          </div>
        </div>
      </div>

      <div class="pack-list" id="pack-list"></div>
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
        각 분야 1등 영상을 <strong>기획 · 키워드 · 이슈 · 0초 후킹 · 영상미 · 바로 카피할 1줄 액션</strong> 6칸으로 알기 쉽게 쪼개 놓았습니다.
      </p>
      <div id="deep-container"></div>
    </section>

    <footer class="footer">
      <p><strong>유튜브 롱폼 데일리 브리핑</strong> · 매일 오후 1시(13:00 KST) 자동 수집 · Jev 100점 채점 · 40개 즉시 작업 장전 팩 · 자동 배포</p>
      <p style="margin-top:6px;">
        기존 정본 교과서 링크는 그대로 보존되어 있습니다:
        <a href="https://1pronano.github.io/youtube-longform-guide/" target="_blank" rel="noopener" style="color:var(--primary);font-weight:700;">
          https://1pronano.github.io/youtube-longform-guide/
        </a>
      </p>
    </footer>
  </div>

  <div id="toast">복사 완료!</div>

  <script id="daily-data" type="application/json">__ARCHIVE_JSON__</script>
  <script>
    const ARCHIVE = JSON.parse(document.getElementById("daily-data").textContent);
    const DATES = Object.keys(ARCHIVE.editions || {}).sort().reverse();
    let currentDate = DATES[0];
    let currentCat = "ALL";
    let searchQuery = "";
    const openIds = new Set();
    const copyStore = {};
    let toastTimer = null;

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

    function showToast(msg) {
      const el = document.getElementById("toast");
      el.textContent = msg;
      el.classList.add("show");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => el.classList.remove("show"), 2400);
    }

    function copyByKey(key, label) {
      const txt = copyStore[key] || "";
      if (!txt) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(txt).then(() => showToast(label)).catch(() => fallbackCopy(txt, label));
      } else {
        fallbackCopy(txt, label);
      }
    }

    function fallbackCopy(txt, label) {
      const ta = document.createElement("textarea");
      ta.value = txt;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        showToast(label);
      } catch (e) {
        showToast("복사에 실패했어요. 직접 선택해서 복사해 주세요.");
      }
      document.body.removeChild(ta);
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
      searchQuery = "";
      document.getElementById("search-input").value = "";
      openIds.clear();
      renderEdition();
    }

    function selectCat(catId) {
      currentCat = catId;
      renderCatTabs();
      renderMaterials();
    }

    function onSearchInput(val) {
      searchQuery = (val || "").trim().toLowerCase();
      renderMaterials();
    }

    function togglePack(id) {
      if (openIds.has(id)) openIds.delete(id);
      else openIds.add(id);
      const card = document.getElementById("card_" + id);
      if (card) {
        card.classList.toggle("open", openIds.has(id));
        const btn = card.querySelector(".btn-toggle");
        if (btn) btn.textContent = openIds.has(id) ? "🔼 장전 팩 접기" : "📦 장전 팩 펼치기";
      }
    }

    function toggleAllPacks(expand) {
      const list = getFilteredMaterials();
      list.forEach(m => {
        if (expand) openIds.add(m.id);
        else openIds.delete(m.id);
      });
      renderMaterials();
    }

    function renderCatTabs() {
      const ed = ARCHIVE.editions[currentDate];
      const mats = ed.materials || [];
      const countOf = cid => mats.filter(m => m.category_id === cid).length;
      const cats = [
        { id: "ALL", label: `전체 (${mats.length}개)` },
        { id: "cat_movie", label: `🎬 옛날 영화 (${countOf("cat_movie")})` },
        { id: "cat_police", label: `🚔 미국 경찰 바디캠 (${countOf("cat_police")})` },
        { id: "cat_senior", label: `📺 어르신 거실 TV (${countOf("cat_senior")})` },
        { id: "cat_global", label: `🌍 해외 대박 빈집 (${countOf("cat_global")})` }
      ];
      document.getElementById("cat-tabs").innerHTML = cats.map(c =>
        `<button class="cat-tab ${currentCat === c.id ? "active" : ""}" onclick="selectCat('${c.id}')">${esc(c.label)}</button>`
      ).join("");
    }

    function getFilteredMaterials() {
      const ed = ARCHIVE.editions[currentDate];
      let list = (ed.materials || []).slice();
      if (currentCat !== "ALL") {
        list = list.filter(m => m.category_id === currentCat);
      }
      if (searchQuery) {
        list = list.filter(m => {
          const p = m.pack || {};
          const hay = [
            m.title, m.channel, m.category_name, m.reason,
            (p.title_options || []).join(" "),
            p.thumb_line1, p.thumb_line2, p.opening_0_4s
          ].join(" ").toLowerCase();
          return hay.includes(searchQuery);
        });
      }
      list.sort((a, b) => (b.total_score || 0) - (a.total_score || 0) || (b.view_count || 0) - (a.view_count || 0));
      return list;
    }

    function renderMaterials() {
      const list = getFilteredMaterials();
      document.getElementById("visible-count").textContent = `${list.length}개 표시 중`;
      const container = document.getElementById("pack-list");

      if (!list.length) {
        container.innerHTML = `<div class="pack-card" style="padding:30px;text-align:center;color:var(--text-muted);">검색 조건에 맞는 소재가 없어요. 다른 단어로 검색해 보세요!</div>`;
        return;
      }

      // 기본으로 첫 1위 카드 1개는 열어두어 바로 장전 팩 구성을 볼 수 있게 함
      if (openIds.size === 0 && !searchQuery && list[0]) {
        openIds.add(list[0].id);
      }

      container.innerHTML = list.map((m, idx) => {
        const displayRank = idx + 1;
        const rCls = displayRank === 1 ? "rank-1" : displayRank === 2 ? "rank-2" : displayRank === 3 ? "rank-3" : "";
        const rankLabel = currentCat === "ALL"
          ? `전체 ${displayRank}위 (분야 ${m.category_rank || displayRank}위)`
          : `${m.category_short || m.category_name} ${m.category_rank || displayRank}위`;
        const s = m.scores || {};
        const p = m.pack || {};
        const tOpts = p.title_options || [m.title, m.title];
        const acts = p.acts || {};
        const evs = p.evidence_checklist || (m.evidence_tip ? [m.evidence_tip] : []);
        const isOpen = openIds.has(m.id);

        const kPrompt = `prompt_${m.id}`;
        const kUrl = `url_${m.id}`;
        const kT1 = `t1_${m.id}`;
        const kT2 = `t2_${m.id}`;
        const kThumb = `thumb_${m.id}`;
        const kOpen = `open_${m.id}`;

        copyStore[kPrompt] = p.work_prompt || `${m.url} 로 ${m.category_name} 롱폼 제작해 줘`;
        copyStore[kUrl] = m.url || "";
        copyStore[kT1] = tOpts[0] || m.title;
        copyStore[kT2] = tOpts[1] || m.title;
        copyStore[kThumb] = `[흰색] ${p.thumb_line1 || ""}\n[빨강] ${p.thumb_line2 || ""}`;
        copyStore[kOpen] = p.opening_0_4s || "";

        return `
          <article class="pack-card ${isOpen ? "open" : ""}" id="card_${esc(m.id)}">
            <div class="pack-head">
              <div class="pack-top-row">
                <div class="pack-badges">
                  <span class="rank-badge ${rCls}">${esc(rankLabel)}</span>
                  <span class="cat-pill" style="background:${esc(m.category_bg || '#eef2ff')};color:${esc(m.category_color || '#2563eb')};">
                    ${esc(m.category_emoji || '📌')} ${esc(m.category_name || '')}
                  </span>
                  ${m.is_new === false ? `<span class="keep-pill">📌 추천 유지</span>` : `<span class="new-pill">🆕 오늘 신규</span>`}
                </div>
                <div class="score-pill-box">
                  <div class="score-big">${Number(m.total_score || 0).toFixed(1)}점</div>
                  <div class="score-sub">
                    후킹 ${Number(s.hook || 0).toFixed(1)} · 물증 ${Number(s.evidence || 0).toFixed(1)}<br/>
                    스토리 ${Number(s.story || 0).toFixed(1)} · 적합 ${Number(s.fit || 0).toFixed(1)}
                  </div>
                </div>
              </div>

              <div class="pack-title">${esc(m.title)}</div>
              <div class="pack-reason">💡 ${esc(m.reason || "")}</div>

              <div class="meta-chips">
                <span class="meta-chip">📺 ${esc(m.channel || '-')}</span>
                <span class="meta-chip views-ok">👀 조회수 ${fmtNum(m.view_count)}회</span>
                <span class="meta-chip ${m.is_super_fresh ? 'hot-fresh' : ''}">${m.is_super_fresh ? '🔥' : '📅'} ${esc(m.upload_date || '-')}${m.age_days !== undefined ? ` (${m.age_days}일 전)` : ''}</span>
                <span class="meta-chip">⏱️ ${esc(m.duration_str || '-')}</span>
                ${m.channel_follower_count ? `<span class="meta-chip">👥 구독 ${fmtNum(m.channel_follower_count)}명</span>` : `<span class="meta-chip">🎬 채널 영상 ${esc(m.channel_video_count_str || '-')}</span>`}
                ${m.channel_badge ? `<span class="meta-chip explosion">${esc(m.channel_badge)}</span>` : ""}
                <span class="meta-chip">🎛️ 프리셋: ${esc(m.preset_name || '롱폼')}</span>
              </div>

              ${m.copyright_note ? `<div class="copyright-bar">🛡️ <strong>저작권 안전 메모:</strong> ${esc(m.copyright_note)}</div>` : ""}

              <div class="action-row">
                <button class="btn-primary" onclick="copyByKey('${esc(kPrompt)}', '⚡ 작업 지시문 복사 완료! 채팅창에 바로 붙여넣으세요!')">
                  ⚡ 바로 작업 지시문 복사
                </button>
                <button class="btn-copy" onclick="copyByKey('${esc(kUrl)}', '📋 원본 소스 URL 복사 완료!')">
                  📋 소스 URL 복사
                </button>
                <a class="yt-btn" href="${esc(m.url)}" target="_blank" rel="noopener">▶ 원본 보기</a>
                <button class="btn-toggle" onclick="togglePack('${esc(m.id)}')">
                  ${isOpen ? "🔼 장전 팩 접기" : "📦 장전 팩 펼치기"}
                </button>
              </div>
            </div>

            <div class="pack-body">
              <div class="pack-grid">
                <div class="pack-box">
                  <div class="box-head">
                    <div class="box-lbl">✍️ ① 바로 쓸 제목 2안 (클릭률 공식)</div>
                  </div>
                  <div class="title-opt">
                    <span>1안) ${esc(tOpts[0])}</span>
                    <button class="mini-copy" onclick="copyByKey('${esc(kT1)}', '제목 1안 복사 완료!')">복사</button>
                  </div>
                  <div class="title-opt">
                    <span>2안) ${esc(tOpts[1])}</span>
                    <button class="mini-copy" onclick="copyByKey('${esc(kT2)}', '제목 2안 복사 완료!')">복사</button>
                  </div>
                </div>

                <div class="pack-box">
                  <div class="box-head">
                    <div class="box-lbl">🖼️ ② 썸네일 2줄 문구 (흰색 + 빨강)</div>
                    <button class="mini-copy" onclick="copyByKey('${esc(kThumb)}', '썸네일 2줄 복사 완료!')">복사</button>
                  </div>
                  <div class="thumb-preview">
                    <div class="thumb-l1">${esc(p.thumb_line1 || "충격적인 진실")}</div>
                    <div class="thumb-l2">${esc(p.thumb_line2 || "결말이 소름 돋는다")}</div>
                  </div>
                </div>

                <div class="pack-box full">
                  <div class="box-head">
                    <div class="box-lbl">🎤 ③ 0~4초 충격 오프닝 대사 (인사말 금지 · 바로 녹음 가능)</div>
                    <button class="mini-copy" onclick="copyByKey('${esc(kOpen)}', '0~4초 오프닝 대사 복사 완료!')">대사 복사</button>
                  </div>
                  <div class="opening-quote">“${esc(p.opening_0_4s || "")}”</div>
                </div>

                <div class="pack-box full">
                  <div class="box-head">
                    <div class="box-lbl">🎬 ④ 4막 기승전결 뼈대 (초등학생도 바로 쓰는 대본 설계도)</div>
                  </div>
                  <div class="acts-grid">
                    <div class="act-card"><span class="act-tag">1막 훅 (0~90초)</span><div class="act-txt">${esc(acts.act1 || "")}</div></div>
                    <div class="act-card"><span class="act-tag">2막 전개</span><div class="act-txt">${esc(acts.act2 || "")}</div></div>
                    <div class="act-card"><span class="act-tag">3막 반전/떡밥</span><div class="act-txt">${esc(acts.act3 || "")}</div></div>
                    <div class="act-card"><span class="act-tag">4막 결말/여운</span><div class="act-txt">${esc(acts.act4 || "")}</div></div>
                  </div>
                </div>

                <div class="pack-box full">
                  <div class="box-head">
                    <div class="box-lbl">🎯 ⑤ 1:1 물증 화면 체크리스트 (이 장면들을 꼭 화면에 띄우세요!)</div>
                  </div>
                  <ul class="ev-list">
                    ${evs.map(e => `<li>☑️ ${esc(e)}</li>`).join("")}
                  </ul>
                </div>

                <div class="pack-box full">
                  <div class="box-head">
                    <div class="box-lbl">⚡ ⑥ 원클릭 작업 지시문 (그대로 복사해서 채팅창에 붙여넣으면 즉시 제작 시작!)</div>
                    <button class="mini-copy" style="background:#2563eb;color:#fff;border-color:#2563eb;" onclick="copyByKey('${esc(kPrompt)}', '⚡ 작업 지시문 복사 완료! 채팅창에 바로 붙여넣으세요!')">⚡ 전체 복사</button>
                  </div>
                  <pre class="prompt-pre">${esc(copyStore[kPrompt])}</pre>
                </div>
              </div>
            </div>
          </article>
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
                ${esc(d.category_emoji || '🔬')} 분야 1위 해부 #${idx + 1} · ${esc(d.category_name || '')}
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

    function renderAuditProof(ed) {
      const box = document.getElementById("audit-pills");
      const p = ed.audit_proof;
      if (!p) {
        box.innerHTML = `<span class="audit-pill">실측 검수 데이터 확인 중</span>`;
        return;
      }
      box.innerHTML = `
        <span class="audit-pill zero">✅ 불량 ${p.defect_count ?? 0}건 (총 ${p.total_count ?? 0}건 통과)</span>
        <span class="audit-pill">👀 최소 조회수 ${esc(p.min_views_str || fmtNum(p.min_views) + '회')}</span>
        <span class="audit-pill">📅 가장 오래된 날짜 ${esc(p.oldest_upload_date || '-')}</span>
        <span class="audit-pill">⏱️ 최소 길이 ${esc(p.min_duration_str || '-')}</span>
        <span class="audit-pill">🔥 최근 30일 초신상 ${p.within_30d_count ?? 0}건</span>
      `;
    }

    function renderEdition() {
      const ed = ARCHIVE.editions[currentDate];
      if (!ed) return;
      document.getElementById("issue-badge").textContent = `제${ed.issue_no || 1}호 · ${currentDate} 발행 (${ed.generated_at || ''})`;
      document.getElementById("engine-badge").textContent = ed.scoring_badge || "Jev 100점 · 철벽 검수 통과";
      document.getElementById("summary-points").innerHTML = (ed.easy_summary || []).map(p => `<li>${esc(p)}</li>`).join("");
      renderAuditProof(ed);
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
    safe_json = json.dumps(archive, ensure_ascii=False, indent=2).replace("</", "<\\/")
    html = HTML_TEMPLATE.replace("__ARCHIVE_JSON__", safe_json)
    DESKTOP_HTML.write_text(html, encoding="utf-8")
    print(f"✅ 데일리 브리핑 HTML 생성 완료: {DESKTOP_HTML} ({DESKTOP_HTML.stat().st_size:,} bytes)")
    return DESKTOP_HTML


if __name__ == "__main__":
    build_html()
