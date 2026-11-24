#!/usr/bin/env python3
"""유튜브 롱폼 데일리 브리핑 자동화 파이프라인 (매일 오후 1시 실행).

1. yt-dlp 로 4개 분야 최신 롱폼 영상 실측 수집
2. TypeSafe Jev (~/제브/거르기.py --spec ~/제브/소재장전점수.json) 100점 정량 채점
   (후킹30 + 물증30 + 스토리20 + 적합20, 1위 맨 위 내림차순)
3. 수집된 채널 대상 신생 에셋 채널 정보 추적
4. 로컬 Claude CLI (`claude -p`) 로 초등학생 눈높이 심층 분석 생성 (실패 시 안전 폴백)
5. data/archive.json 날짜별 누적 저장 -> render_html.py -> deploy.sh (GitHub Pages 자동 배포)
6. 로그 저장 + macOS 알림 + 완료 음성
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

BASE_DIR = Path("/Users/dongkeunkim/youtube-longform-daily")
CONFIG_PATH = BASE_DIR / "config.json"
ARCHIVE_PATH = BASE_DIR / "data" / "archive.json"
LOGS_DIR = BASE_DIR / "logs"
JEV_SCRIPT = Path("/Users/dongkeunkim/제브/거르기.py")
JEV_SPEC = Path("/Users/dongkeunkim/제브/소재장전점수.json")
TYPESAFE_ENV = Path("/Users/dongkeunkim/.config/typesafe/env")
YT_DLP = "/Users/dongkeunkim/.local/bin/yt-dlp"
CLAUDE_BIN = "/Users/dongkeunkim/.local/bin/claude"
DONE_VOICE = "/Users/dongkeunkim/.local/bin/작업완료"

WEIGHTS = {"hook": 30.0, "evidence": 30.0, "story": 20.0, "fit": 20.0}


def log(msg: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_typesafe_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = "/Users/dongkeunkim/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:" + env.get("PATH", "")
    if TYPESAFE_ENV.exists() and not env.get("TYPESAFE_API_KEY"):
        for line in TYPESAFE_ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def fmt_duration(sec: Any) -> str:
    try:
        s = int(float(sec))
    except (TypeError, ValueError):
        return "-"
    h, rem = divmod(s, 3600)
    m, sec_rem = divmod(rem, 60)
    if h > 0:
        return f"{h}시간 {m}분"
    return f"{m}분 {sec_rem:02d}초"


def fmt_date(yyyymmdd: str | None) -> str:
    if not yyyymmdd or len(yyyymmdd) != 8 or not yyyymmdd.isdigit():
        return ""
    return f"{yyyymmdd[:4]}-{yyyymmdd[4:6]}-{yyyymmdd[6:8]}"


def fmt_compact(n: Any) -> str:
    try:
        num = int(float(n))
    except (TypeError, ValueError):
        return "-"
    if num >= 10000:
        return f"{num / 10000:.1f}".rstrip("0").rstrip(".") + "만"
    return f"{num:,}"


def fetch_videos_for_category(cat: dict[str, Any], per_query: int, env: dict[str, str]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    min_dur = int(cat.get("min_duration_sec", 600))
    for q in cat["queries"]:
        cmd = [
            YT_DLP,
            "--flat-playlist",
            "--dump-json",
            "--no-warnings",
            "--skip-download",
            f"ytsearch{per_query}:{q}",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=45, env=env)
        except Exception as e:
            log(f"⚠️ yt-dlp 검색 실패 ({q}): {e}")
            continue
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = item.get("id")
            if not vid or vid in found:
                continue
            dur = item.get("duration") or 0
            if dur and dur < min_dur:
                continue
            views = item.get("view_count") or 0
            title = (item.get("title") or "").strip()
            if not title:
                continue
            ch_url = item.get("channel_url") or item.get("uploader_url") or ""
            found[vid] = {
                "id": f"{cat['id']}_{vid}",
                "video_id": vid,
                "category_id": cat["id"],
                "category_name": cat["name"],
                "category_emoji": cat["emoji"],
                "category_color": cat["color"],
                "category_bg": cat["bg"],
                "channel_desc": cat["channel_desc"],
                "title": title,
                "url": item.get("url") if str(item.get("url", "")).startswith("http") else f"https://www.youtube.com/watch?v={vid}",
                "channel": item.get("channel") or item.get("uploader") or "알 수 없음",
                "channel_url": ch_url,
                "channel_follower_count": item.get("channel_follower_count"),
                "view_count": int(views) if views else 0,
                "duration": int(dur) if dur else 0,
                "duration_str": fmt_duration(dur),
                "upload_date": fmt_date(item.get("upload_date")),
                "description": (item.get("description") or "")[:300],
            }
    items = list(found.values())
    items.sort(key=lambda x: x["view_count"], reverse=True)
    return items[:6]


def score_with_jev(candidates: list[dict[str, Any]], env: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
    """~/제브/거르기.py 로 실제 Jev 100점 정량 채점."""
    if not candidates:
        return [], "후보 없음"

    if not JEV_SCRIPT.exists() or not JEV_SPEC.exists() or not env.get("TYPESAFE_API_KEY"):
        log("⚠️ Jev 스크립트 또는 API 키가 없어 휴리스틱 점수로 폴백합니다.")
        return _heuristic_score(candidates), "휴리스틱 안전 점수 (Jev 미연결)"

    with tempfile.TemporaryDirectory(prefix="daily_jev_") as tmp:
        in_path = Path(tmp) / "in.jsonl"
        out_path = Path(tmp) / "out.jsonl"
        with in_path.open("w", encoding="utf-8") as f:
            for c in candidates:
                row = {
                    "id": c["id"],
                    "title": c["title"],
                    "summary": f"채널: {c['channel']} | 조회수: {c['view_count']:,}회 | 길이: {c['duration_str']} | {c['description']}",
                    "channel": c["channel_desc"],
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        cmd = [
            sys.executable,
            str(JEV_SCRIPT),
            "--spec",
            str(JEV_SPEC),
            "--in",
            str(in_path),
            "--out",
            str(out_path),
        ]
        log(f"🧪 Jev 100점 채점 시작 ({len(candidates)}개 후보)...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, env=env)
        except Exception as e:
            log(f"⚠️ Jev 실행 예외: {e}")
            return _heuristic_score(candidates), "휴리스틱 안전 점수 (Jev 시간초과)"

        if res.returncode != 0 or not out_path.exists():
            log(f"⚠️ Jev 종료코드={res.returncode}: {res.stderr.strip()[:200]}")
            return _heuristic_score(candidates), "휴리스틱 안전 점수 (Jev 오류 폴백)"

        answers_map: dict[str, dict[str, float]] = {}
        for line in out_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                answers_map[obj["id"]] = obj.get("answers", {})
            except Exception:
                continue

        if not answers_map:
            return _heuristic_score(candidates), "휴리스틱 안전 점수 (Jev 빈 응답)"

        scored = []
        for c in candidates:
            ans = answers_map.get(c["id"])
            if not ans:
                continue
            sc = {}
            total = 0.0
            for k, w in WEIGHTS.items():
                val = ans.get(k, 0.5)
                if isinstance(val, dict):
                    val = val.get("probability", 0.5)
                try:
                    p = float(val)
                except (TypeError, ValueError):
                    p = 0.5
                pts = round(p * w, 1)
                sc[k] = pts
                total += pts
            c_copy = dict(c)
            c_copy["scores"] = sc
            c_copy["total_score"] = round(total, 1)
            scored.append(c_copy)

        scored.sort(key=lambda x: x["total_score"], reverse=True)
        log(f"✅ Jev 실측 채점 완료 ({len(scored)}개, 최고점 {scored[0]['total_score']}점)")
        return scored, "TypeSafe Jev(jev-1.14.0) 100점 실측"


def _heuristic_score(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for c in candidates:
        views = c.get("view_count", 0)
        base = min(0.92, 0.58 + (0.28 if views >= 500000 else 0.20 if views >= 100000 else 0.12 if views >= 30000 else 0.05))
        sc = {
            "hook": round(base * 30.0, 1),
            "evidence": round(min(0.93, base + 0.03) * 30.0, 1),
            "story": round(min(0.90, base) * 20.0, 1),
            "fit": round(min(0.92, base + 0.02) * 20.0, 1),
        }
        c_copy = dict(c)
        c_copy["scores"] = sc
        c_copy["total_score"] = round(sum(sc.values()), 1)
        scored.append(c_copy)
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    return scored


def inspect_rising_channels(materials: list[dict[str, Any]], max_channels: int, env: dict[str, str]) -> list[dict[str, Any]]:
    """추천 소재에서 발견된 채널들의 최근 영상 수·평균 조회수·구독자 실측."""
    seen: set[str] = set()
    candidates: list[dict[str, Any]] = []
    for m in materials:
        ch_url = m.get("channel_url")
        ch_name = m.get("channel")
        if not ch_url or not ch_name or ch_name in seen:
            continue
        seen.add(ch_name)
        candidates.append(m)

    results: list[dict[str, Any]] = []
    for m in candidates[:10]:
        ch_url = m["channel_url"].rstrip("/")
        videos_url = ch_url if ch_url.endswith("/videos") else f"{ch_url}/videos"
        cmd = [
            YT_DLP,
            "--flat-playlist",
            "--playlist-end",
            "30",
            "--dump-json",
            "--no-warnings",
            "--skip-download",
            videos_url,
        ]
        vids = []
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=25, env=env)
            for line in res.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    vids.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            log(f"⚠️ 채널 탐색 건너뜀 ({m['channel']}): {e}")

        vid_count = len(vids)
        views_list = [int(v.get("view_count") or 0) for v in vids if v.get("view_count")]
        avg_views = int(sum(views_list) / len(views_list)) if views_list else m.get("view_count", 0)
        subs = m.get("channel_follower_count")
        if not subs and vids:
            subs = vids[0].get("channel_follower_count")

        count_label = f"{vid_count}개+" if vid_count >= 30 else (f"{vid_count}개 (신생)" if vid_count > 0 else "측정 중")
        created_label = "신생 성장 채널" if 0 < vid_count < 30 else "활발한 롱폼 채널"

        results.append(
            {
                "channel_name": m["channel"],
                "channel_url": m["channel_url"],
                "category_id": m["category_id"],
                "category_name": m["category_name"],
                "category_emoji": m["category_emoji"],
                "category_color": m["category_color"],
                "category_bg": m["category_bg"],
                "created_info": created_label,
                "video_count": vid_count,
                "video_count_str": count_label,
                "subscribers_str": f"{fmt_compact(subs)}명" if subs else "비공개/집계중",
                "avg_views": avg_views,
                "avg_views_str": f"{fmt_compact(avg_views)}회",
                "top_video_title": m["title"],
                "top_video_url": m["url"],
                "easy_analysis": f"영상 {count_label} 규모에서 편당 평균 {fmt_compact(avg_views)}회를 뽑아내며 {m['category_name']} 시청자를 확실히 붙잡고 있습니다.",
            }
        )

    # 신생(영상 수 적음) + 편당 평균 조회수 높은 순으로 우선 정렬
    results.sort(key=lambda x: (x["video_count"] < 30, x["avg_views"]), reverse=True)
    return results[:max_channels]


def enrich_with_claude(
    date_str: str,
    materials: list[dict[str, Any]],
    channels: list[dict[str, Any]],
    deep_targets: list[dict[str, Any]],
    env: dict[str, str],
) -> dict[str, Any] | None:
    """로컬 Claude CLI (`claude -p`) 로 초등학생 눈높이 심층 분석 JSON 생성."""
    if not Path(CLAUDE_BIN).exists():
        log("⚠️ claude CLI 를 찾지 못해 기본 분석 폴백을 사용합니다.")
        return None

    payload = {
        "date": date_str,
        "materials": [
            {
                "id": m["id"],
                "category": m["category_name"],
                "title": m["title"],
                "channel": m["channel"],
                "view_count": m["view_count"],
                "duration": m["duration_str"],
                "total_score": m["total_score"],
            }
            for m in materials
        ],
        "channels": [
            {
                "channel_name": c["channel_name"],
                "category": c["category_name"],
                "video_count_str": c["video_count_str"],
                "subscribers_str": c["subscribers_str"],
                "avg_views_str": c["avg_views_str"],
                "top_video_title": c["top_video_title"],
            }
            for c in channels
        ],
        "deep_targets": [
            {
                "id": d["id"],
                "category": d["category_name"],
                "title": d["title"],
                "channel": d["channel"],
                "view_count": d["view_count"],
                "duration": d["duration_str"],
            }
            for d in deep_targets
        ],
    }

    prompt = f"""너는 초등학생도 10초 만에 이해할 수 있게 아주 쉬운 말과 비유로 설명하는 유튜브 롱폼 전문 분석가야.
아래 오늘({date_str}) 실제 수집·Jev 채점된 데이터를 보고, 반드시 **순수 JSON 객체 하나만** 출력해 줘. (마크다운 코드블록 ``` 없이 순수 JSON만!)

규칙:
- 모든 문장은 초등학생도 바로 알아듣는 친절하고 쉬운 한국어 + 비유 사용.
- 어려운 영어/전문용어를 쓰면 괄호로 쉬운 뜻 설명.
- 과장이나 거짓 수치 금지, 주어진 데이터에 근거해서 작성.

출력 JSON 스키마:
{{
  "easy_summary": [
    "오늘의 1줄 요약 (비유 포함)",
    "오늘의 2줄 요약 (가장 점수 높은 분야/소재)",
    "오늘의 3줄 요약 (당장 써먹을 꿀팁)"
  ],
  "material_notes": {{
    "<material id>": {{
      "reason": "왜 이 소재가 잘 팔리는지 초등학생도 알기 쉽게 1~2문장",
      "evidence_tip": "화면에 1:1로 꼭 보여줘야 할 실제 자료/물증 장면 1문장"
    }}
  }},
  "channel_notes": {{
    "<channel_name>": "이 신생 채널이 왜 요즘 뜨는지 초등학생 눈높이 1~2문장"
  }},
  "deep_dives": {{
    "<deep_target id>": {{
      "planning": "기획(판 짜기) 비결 1~2문장",
      "keywords": "클릭을 부르는 마법 키워드 3~5개와 이유",
      "issue": "지금 시청자들이 왜 이걸 궁금해하는지 1~2문장",
      "hook_0s": "0초~15초 첫 화면/첫 대사 후킹 전략 1~2문장",
      "visual_style": "화면 구성·자막·물증 배치 비법 1~2문장",
      "copy_action": "오늘 당장 내가 똑같이 따라 할 1줄 숙제"
    }}
  }}
}}

입력 데이터:
{json.dumps(payload, ensure_ascii=False)}
"""

    log("🤖 Claude AI 초등학생 눈높이 심층 분석 실행 중...")
    try:
        res = subprocess.run(
            [CLAUDE_BIN, "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=180,
            env=env,
        )
    except Exception as e:
        log(f"⚠️ Claude 분석 시간초과/예외: {e}")
        return None

    if res.returncode != 0:
        log(f"⚠️ Claude 종료코드={res.returncode}: {res.stderr.strip()[:200]}")
        return None

    raw = res.stdout.strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        log("⚠️ Claude 응답에서 JSON을 찾지 못해 폴백을 사용합니다.")
        return None

    try:
        parsed = json.loads(m.group(0))
        log("✅ Claude 심층 분석 JSON 파싱 성공!")
        return parsed
    except json.JSONDecodeError as e:
        log(f"⚠️ Claude JSON 파싱 실패: {e}")
        return None


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = load_typesafe_env()
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    now = dt.datetime.now()
    today = now.strftime("%Y-%m-%d")
    gen_time = now.strftime("%H:%M KST")

    log(f"🚀 유튜브 롱폼 데일리 브리핑 파이프라인 시작 ({today} {gen_time})")

    # 1. 4개 분야 수집
    all_candidates: list[dict[str, Any]] = []
    for cat in cfg["categories"]:
        log(f"🔎 수집 중: {cat['emoji']} {cat['name']}")
        items = fetch_videos_for_category(cat, int(cfg.get("search_per_query", 5)), env)
        log(f"   → {len(items)}개 후보 확보")
        all_candidates.extend(items)

    # 2. Jev 100점 정량 채점
    scored, scoring_badge = score_with_jev(all_candidates, env)

    # 분야별 상위 N개 선별 후 전체 Jev 점수 내림차순 정렬
    per_cat = int(cfg.get("top_materials_per_category", 3))
    selected_materials: list[dict[str, Any]] = []
    for cat in cfg["categories"]:
        cat_items = [x for x in scored if x["category_id"] == cat["id"]][:per_cat]
        selected_materials.extend(cat_items)
    selected_materials.sort(key=lambda x: x["total_score"], reverse=True)

    # 3. 핫한 신생 에셋 채널 추적
    rising_channels = inspect_rising_channels(selected_materials, int(cfg.get("max_rising_channels", 6)), env)

    # 4. 분야별 1위 영상을 심층 해부 대상으로 선정
    deep_targets: list[dict[str, Any]] = []
    for cat in cfg["categories"]:
        cat_top = [x for x in selected_materials if x["category_id"] == cat["id"]]
        if cat_top:
            deep_targets.append(cat_top[0])
    deep_targets = deep_targets[: int(cfg.get("max_deep_dives", 4))]

    # 5. Claude 심층 분석 (실패 시 안전 폴백)
    ai = enrich_with_claude(today, selected_materials, rising_channels, deep_targets, env) or {}
    mat_notes = ai.get("material_notes", {}) if isinstance(ai, dict) else {}
    ch_notes = ai.get("channel_notes", {}) if isinstance(ai, dict) else {}
    deep_notes = ai.get("deep_dives", {}) if isinstance(ai, dict) else {}

    for m in selected_materials:
        note = mat_notes.get(m["id"], {})
        m["reason"] = note.get("reason") or f"조회수 {fmt_compact(m['view_count'])}회가 증명한 인기 주제로, 처음부터 끝까지 궁금증을 끌고 가는 힘이 강합니다."
        m["evidence_tip"] = note.get("evidence_tip") or f"{m['category_name']} 핵심 현장 장면·공식 기록·비교 화면을 대본 한 줄마다 1:1로 맞춰 보여 주세요."

    for ch in rising_channels:
        if ch["channel_name"] in ch_notes:
            ch["easy_analysis"] = ch_notes[ch["channel_name"]]

    deep_dives = []
    for d in deep_targets:
        dn = deep_notes.get(d["id"], {})
        deep_dives.append(
            {
                "category_id": d["category_id"],
                "category_name": d["category_name"],
                "category_emoji": d["category_emoji"],
                "category_color": d["category_color"],
                "category_bg": d["category_bg"],
                "title": d["title"],
                "channel": d["channel"],
                "view_count": d["view_count"],
                "url": d["url"],
                "planning": dn.get("planning") or f"{d['category_name']} 시청자가 제일 좋아하는 갈등→반전→결말 구조로 15분 이상 몰입하게 판을 짰습니다.",
                "keywords": dn.get("keywords") or f"제목 속 핵심 상황 키워드 + '{d['category_name']}' 대표 감성 단어를 앞부분에 배치했습니다.",
                "issue": dn.get("issue") or "실제 벌어진 사건·검증된 명작·생활 밀착 정보라서 지금 당장 클릭할 이유가 분명합니다.",
                "hook_0s": dn.get("hook_0s") or "인사말 없이 0초부터 가장 충격적인 하이라이트 장면과 질문을 던져 이탈을 막았습니다.",
                "visual_style": dn.get("visual_style") or "대본과 딱 맞는 실제 물증 화면을 빠르게 전환하고, 큰 자막으로 거실 TV·모바일 가독성을 높였습니다.",
                "copy_action": dn.get("copy_action") or f"오늘 영상 첫 10초에 '{d['title'][:28]}...'처럼 결론 직전 가장 궁금한 장면을 먼저 보여주고 시작하세요!",
            }
        )

    top1 = selected_materials[0] if selected_materials else None
    easy_summary = ai.get("easy_summary") if isinstance(ai, dict) and ai.get("easy_summary") else [
        f"📰 오늘({today}) 4개 황금 분야에서 실제 유튜브 롱폼 {len(selected_materials)}개 보물 소재를 Jev 100점으로 줄 세웠어요!",
        f"🏆 오늘의 전체 1등 소재는 [{top1['category_name']}] '{top1['title'][:36]}' ({top1['total_score']}점)입니다." if top1 else "🏆 오늘의 4개 분야 추천 소재가 준비되었어요.",
        "⚡ 아래 3번 '오늘의 떡상 이유 6단 해부'에서 맨 끝 파란 박스 '바로 카피할 1줄 액션'만 따라 해도 오늘 기획이 끝납니다!",
    ]

    # 6. 아카이브 누적 저장
    if ARCHIVE_PATH.exists():
        archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    else:
        archive = {"editions": {}}

    editions = archive.setdefault("editions", {})
    if today in editions:
        issue_no = editions[today].get("issue_no", len(editions))
    else:
        issue_no = len(editions) + 1

    editions[today] = {
        "date": today,
        "issue_no": issue_no,
        "generated_at": gen_time,
        "scoring_badge": f"{scoring_badge} + AI 6단 해부",
        "easy_summary": easy_summary,
        "materials": selected_materials,
        "rising_channels": rising_channels,
        "deep_dives": deep_dives,
    }
    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"💾 아카이브 저장 완료: {ARCHIVE_PATH} (제{issue_no}호)")

    # 7. HTML 빌드
    subprocess.run([sys.executable, str(BASE_DIR / "render_html.py")], check=True, env=env)

    # 8. GitHub Pages 배포
    if os.environ.get("SKIP_DEPLOY") != "1":
        subprocess.run(["bash", str(BASE_DIR / "deploy.sh")], check=True, env=env)

    # 9. macOS 알림 + 완료 음성 (최초 셋팅 시 SKIP_NOTIFY=1 로 중복 방지 가능)
    if os.environ.get("SKIP_NOTIFY") != "1":
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "제{issue_no}호 ({today}) 데일리 브리핑이 업데이트되었습니다!" with title "📰 유튜브 롱폼 데일리 브리핑"',
                ],
                check=False,
                timeout=10,
            )
        except Exception:
            pass
        if Path(DONE_VOICE).exists():
            subprocess.run([DONE_VOICE, "유튜브데일리브리핑"], check=False, timeout=15)

    log("🎉 데일리 브리핑 전체 파이프라인 완료!")


if __name__ == "__main__":
    main()
