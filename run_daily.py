#!/usr/bin/env python3
"""유튜브 롱폼 데일리 브리핑 자동화 파이프라인 (철벽 5대 하드게이트 영구 박제 버전).

[절대 타협 없는 5대 철벽 하드게이트 — 단 1건이라도 어기면 즉시 탈락 · 배포 원천 차단]
1. 최신 업로드 엄격 제한: 실행일 기준 최근 90일(1~3개월) 이내 업로드된 영상만 허용!
2. 조회수 폭발 엄격 제한: 조회수 100,000회(10만 뷰) 이상만 허용! (10만 미만 0건!)
3. 순수 롱폼 엄격 제한: 영상 길이 480초(8분) 이상만 허용! (쇼츠·짧은 클립 원천 차단!)
4. 신생·고효율 폭발 채널 엄격 제한: 대형 방송사/뉴스/초대형 메가채널 원천 차단!
   반드시 (채널 총 영상 <= 80개) OR (구독자 <= 30만) OR (조회수 ÷ 구독자 >= 1.5배) 중 1개 이상 실측 충족!
5. 100% 전수 실측 + 배포 직전 assert_hard_gates() 영구 박제:
   모든 영상 URL을 yt-dlp --dump-json 으로 1건 1건 실측하고, 배포 직전 전수 검사에서
   불량 1건이라도 발견되면 예외를 발생시켜 배포를 원천 차단한다. (브라우저 자동 열기 절대 금지!)
"""
from __future__ import annotations

import concurrent.futures
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.parse
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

# ── 5대 철벽 하드게이트 영구 상수 (절대 완화 금지) ──
MAX_AGE_DAYS = 90          # 최근 1~3개월 (90일 이내)
MIN_VIEWS = 100_000        # 최소 10만 뷰 이상
MIN_DURATION_SEC = 480     # 최소 8분(480초) 이상 순수 롱폼
MAX_CHANNEL_VIDEOS_NEW = 80
MAX_SUBS_SMALL = 300_000
MIN_EXPLOSION_RATIO = 1.5  # 조회수 / 구독자 >= 1.5배
MEGA_SUBS_BLOCK = 3_000_000

# 대형 방송사 / 뉴스 / 공식 메가 배급사 블랙리스트 (소문자 부분 일치)
BLOCKED_CHANNEL_KEYWORDS = (
    "kbs", "mbc", "sbs", "jtbc", "ytn", "mbn", "tv조선", "채널a", "연합뉴스", "ebs", "tvn",
    "bbc", "cnn", "fox news", "abc news", "nbc news", "cbs news", "msnbc", "sky news",
    "al jazeera", "reuters", "associated press", "bloomberg", "cnbc", "wall street journal",
    "new york times", "washington post", "the guardian", "vice news", "national geographic",
    "discovery", "history", "a&e", "netflix", "disney", "marvel", "warner bros", "sony pictures",
    "universal pictures", "paramount", "20th century", "hbo", "prime video", "apple tv",
    "law&crime", "courttv", "court tv", "dr. phil", "inside edition", "tmz", "espn",
    "ted-ed", "kurzgesagt", "veritasium", "mrbeast", "pewdiepie", "watchmojo",
    "지식인사이드", "삼프로tv", "슈카월드", "세바시", "김미경", "비온뒤", "명의", "생로병사",
)

WEIGHTS = {"hook": 30.0, "evidence": 30.0, "story": 20.0, "fit": 20.0}

# YouTube 검색 sp 필터 (최신 1개월 우선 + 올해 조회수순 보조)
YT_SP_FILTERS = [
    ("this_month", "EgIIBA%253D%253D"),         # 이번 달 (최근 30일)
    ("this_month_long", "EgYIBBABGAM%253D"),    # 이번 달 + 20분 이상
    ("this_month_mid", "EgYIBBABGAI%253D"),     # 이번 달 + 4~20분
    ("this_year_views", "CAMSBAgFEAE%253D"),    # 올해 + 조회수순 (90일 이내 실측 컷)
]


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
    if s <= 0:
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


def parse_iso_date(s: str | None) -> dt.date | None:
    if not s:
        return None
    s = s.strip()
    try:
        if len(s) == 8 and s.isdigit():
            return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        return dt.date.fromisoformat(s[:10])
    except Exception:
        return None


def fmt_compact(n: Any) -> str:
    try:
        num = int(float(n))
    except (TypeError, ValueError):
        return "-"
    if num >= 10000:
        return f"{num / 10000:.1f}".rstrip("0").rstrip(".") + "만"
    return f"{num:,}"


def is_blocked_channel(name: str) -> bool:
    low = (name or "").lower().strip()
    if not low:
        return True
    for kw in BLOCKED_CHANNEL_KEYWORDS:
        if kw in low:
            return True
    return False


def load_previous_video_ids(today: str) -> set[str]:
    prev: set[str] = set()
    if not ARCHIVE_PATH.exists():
        return prev
    try:
        archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
        for d, ed in (archive.get("editions") or {}).items():
            if d == today:
                continue
            for m in ed.get("materials") or []:
                if m.get("video_id"):
                    prev.add(str(m["video_id"]))
    except Exception:
        pass
    return prev


def _run_yt_url_search(query: str, sp_code: str, limit: int, env: dict[str, str]) -> list[dict[str, Any]]:
    encoded_q = urllib.parse.quote_plus(query)
    url = f"https://www.youtube.com/results?search_query={encoded_q}&sp={sp_code}"
    cmd = [
        YT_DLP,
        "--flat-playlist",
        "--playlist-end",
        str(limit),
        "--dump-json",
        "--no-warnings",
        "--skip-download",
        url,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45, env=env)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for line in res.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if obj.get("id") and len(str(obj["id"])) == 11:
                out.append(obj)
        except json.JSONDecodeError:
            continue
    return out


def probe_video_exact(vid: str, env: dict[str, str]) -> dict[str, Any] | None:
    """개별 영상 URL을 yt-dlp --dump-json 으로 100% 실측 조회 (upload_date, view_count, duration, subs)."""
    url = f"https://www.youtube.com/watch?v={vid}"
    cmd = [
        YT_DLP,
        "--dump-json",
        "--no-warnings",
        "--skip-download",
        "--no-playlist",
        url,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25, env=env)
        if res.returncode != 0 or not res.stdout.strip():
            return None
        return json.loads(res.stdout.splitlines()[0])
    except Exception:
        return None


def probe_channel_stats(ch_url: str, env: dict[str, str]) -> dict[str, Any]:
    """채널의 총 영상 수(최대 101개까지 실측)와 최근 영상 평균 조회수를 실측."""
    if not ch_url:
        return {"video_count": 999, "avg_views": 0, "video_count_exact": False}
    base = ch_url.rstrip("/")
    videos_url = base if base.endswith("/videos") else f"{base}/videos"
    cmd = [
        YT_DLP,
        "--flat-playlist",
        "--playlist-end",
        "101",
        "--dump-json",
        "--no-warnings",
        "--skip-download",
        videos_url,
    ]
    vids: list[dict[str, Any]] = []
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                vids.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception:
        return {"video_count": 999, "avg_views": 0, "video_count_exact": False}

    cnt = len(vids)
    views_list = [int(v.get("view_count") or 0) for v in vids[:20] if v.get("view_count")]
    avg_v = int(sum(views_list) / len(views_list)) if views_list else 0
    return {
        "video_count": cnt,
        "video_count_exact": cnt < 101,
        "avg_views": avg_v,
    }


def evaluate_channel_eligibility(
    views: int,
    subs: int | None,
    ch_video_count: int,
    ch_name: str,
) -> tuple[bool, str, float | None]:
    """신생·고효율 폭발 채널 하드게이트 판정.

    반환: (통과 여부, 채널 유형 배지, 폭발 배수)
    """
    if is_blocked_channel(ch_name):
        return False, "방송사/메가채널 차단", None

    ratio: float | None = None
    if subs and subs > 0:
        ratio = round(views / subs, 2)

    # 구독자 300만 초과 초대형 메가채널은 폭발 배수가 1.5배 미만이면 원천 차단
    if subs and subs > MEGA_SUBS_BLOCK and (ratio is None or ratio < MIN_EXPLOSION_RATIO):
        return False, "초대형 메가채널 제외", ratio

    is_new_ch = 0 < ch_video_count <= MAX_CHANNEL_VIDEOS_NEW
    is_small_subs = subs is not None and 0 < subs <= MAX_SUBS_SMALL
    is_explosive = ratio is not None and ratio >= MIN_EXPLOSION_RATIO

    if is_new_ch and is_explosive:
        return True, f"🔥 신생 폭발 ({ch_video_count}개 · {ratio:.1f}배)", ratio
    if is_new_ch:
        return True, f"🌱 신생 대박 (총 {ch_video_count}개)", ratio
    if is_explosive:
        return True, f"🚀 구독자 대비 {ratio:.1f}배 폭발", ratio
    if is_small_subs:
        return True, f"⚡ 중소 고효율 (구독 {fmt_compact(subs)})", ratio

    return False, "신생/폭발 기준 미달", ratio


def fetch_verified_videos_for_category(
    cat: dict[str, Any],
    per_query: int,
    target_candidates: int,
    today_date: dt.date,
    prev_vids: set[str],
    channel_cache: dict[str, dict[str, Any]],
    env: dict[str, str],
) -> list[dict[str, Any]]:
    """5대 철벽 하드게이트를 100% 실측 통과한 영상만 수집 (절대 저조회수/옛날영상 완화 금지!)."""
    min_dur = max(MIN_DURATION_SEC, int(cat.get("min_duration_sec", MIN_DURATION_SEC)))
    cutoff_date = today_date - dt.timedelta(days=MAX_AGE_DAYS)

    raw_pool: dict[str, dict[str, Any]] = {}
    verified: dict[str, dict[str, Any]] = {}

    def gather_flat(queries: list[str], sp_subset: list[tuple[str, str]]) -> list[str]:
        tasks = [(q, sp_name, sp_code) for q in queries for sp_name, sp_code in sp_subset]
        new_ids: list[str] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futs = {pool.submit(_run_yt_url_search, q, sp_code, per_query, env): (q, sp_name) for q, sp_name, sp_code in tasks}
            for fut in concurrent.futures.as_completed(futs):
                rows = fut.result() or []
                for item in rows:
                    vid = str(item.get("id") or "")
                    if not vid or vid in raw_pool or vid in verified:
                        continue
                    # 1차 사전 컷 (이미 확실히 탈락인 쇼츠/저조회수/방송사는 실측 호출 절약)
                    dur = int(item.get("duration") or 0)
                    if dur > 0 and dur < min_dur:
                        continue
                    views = item.get("view_count")
                    if views is not None and int(views) > 0 and int(views) < MIN_VIEWS:
                        continue
                    ch_name = item.get("channel") or item.get("uploader") or ""
                    if ch_name and is_blocked_channel(ch_name):
                        continue
                    raw_pool[vid] = item
                    new_ids.append(vid)
        # 알려진 조회수 높은 순으로 실측 우선순위 정렬
        new_ids.sort(key=lambda vid: int(raw_pool[vid].get("view_count") or 0), reverse=True)
        return new_ids

    def verify_batch(vids_to_probe: list[str], max_probe: int) -> None:
        batch = vids_to_probe[:max_probe]
        if not batch:
            return
        log(f"   🔍 [{cat['name']}] 후보 {len(batch)}개 1:1 실측 조회 중 (yt-dlp --dump-json)...")
        probed_pass: list[dict[str, Any]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            futs = {pool.submit(probe_video_exact, vid, env): vid for vid in batch}
            for fut in concurrent.futures.as_completed(futs):
                data = fut.result()
                if not data:
                    continue
                vid = str(data.get("id") or "")
                if not vid or vid in verified:
                    continue
                views = int(data.get("view_count") or 0)
                dur = int(data.get("duration") or 0)
                up_raw = data.get("upload_date")
                up_date = parse_iso_date(up_raw)
                ch_name = (data.get("channel") or data.get("uploader") or "").strip()

                # 하드게이트 1, 2, 3 즉시 판정
                if views < MIN_VIEWS:
                    continue
                if dur < min_dur:
                    continue
                if not up_date or up_date < cutoff_date or up_date > today_date + dt.timedelta(days=1):
                    continue
                if is_blocked_channel(ch_name):
                    continue

                probed_pass.append(data)

        if not probed_pass:
            return

        # 3단계: 통과한 영상의 채널 총 영상 수 실측 (캐시 활용)
        urls_needed = []
        for d in probed_pass:
            cu = d.get("channel_url") or d.get("uploader_url") or ""
            if cu and cu not in channel_cache and cu not in urls_needed:
                urls_needed.append(cu)

        if urls_needed:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                cfuts = {pool.submit(probe_channel_stats, cu, env): cu for cu in urls_needed}
                for fut in concurrent.futures.as_completed(cfuts):
                    cu = cfuts[fut]
                    channel_cache[cu] = fut.result()

        # 4단계: 신생·고효율 폭발 채널 하드게이트 적용
        for data in probed_pass:
            vid = str(data["id"])
            views = int(data["view_count"])
            dur = int(data["duration"])
            up_date = parse_iso_date(data["upload_date"])
            assert up_date is not None
            age_days = max(0, (today_date - up_date).days)
            ch_name = (data.get("channel") or data.get("uploader") or "알 수 없음").strip()
            ch_url = data.get("channel_url") or data.get("uploader_url") or ""
            subs = data.get("channel_follower_count")
            subs_int = int(subs) if subs is not None and int(subs) > 0 else None

            cstats = channel_cache.get(ch_url, {"video_count": 999, "avg_views": views, "video_count_exact": False})
            ch_vid_cnt = int(cstats.get("video_count") or 999)

            ok, ch_badge, ratio = evaluate_channel_eligibility(views, subs_int, ch_vid_cnt, ch_name)
            if not ok:
                continue

            ch_cnt_str = f"{ch_vid_cnt}개" if ch_vid_cnt < 101 else "100개+"
            verified[vid] = {
                "id": f"{cat['id']}_{vid}",
                "video_id": vid,
                "category_id": cat["id"],
                "category_name": cat["name"],
                "category_short": cat.get("short_name", cat["name"]),
                "category_emoji": cat["emoji"],
                "category_color": cat["color"],
                "category_bg": cat["bg"],
                "preset_name": cat.get("preset_name", "인물형 롱폼"),
                "channel_desc": cat["channel_desc"],
                "copyright_note": cat.get("copyright_note", "원본 해설 각색 및 1:1 물증 화면 구성 필수"),
                "title": (data.get("title") or "").strip(),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "channel": ch_name,
                "channel_url": ch_url,
                "channel_follower_count": subs_int,
                "channel_video_count": ch_vid_cnt,
                "channel_video_count_str": ch_cnt_str,
                "channel_avg_views": int(cstats.get("avg_views") or views),
                "explosion_ratio": ratio,
                "channel_badge": ch_badge,
                "channel_verified": True,
                "view_count": views,
                "duration": dur,
                "duration_str": fmt_duration(dur),
                "upload_date": up_date.isoformat(),
                "age_days": age_days,
                "is_super_fresh": age_days <= 30,
                "description": (data.get("description") or "")[:300],
                "is_new": vid not in prev_vids,
            }

    # 라운드 1: 메인 쿼리 × 최신 1개월 필터 (최우선!)
    ids_r1 = gather_flat(cat.get("queries", []), YT_SP_FILTERS[:3])
    verify_batch(ids_r1, max_probe=45)
    log(f"   ↳ [{cat['name']}] 1차(최근 30일) 철벽 통과: {len(verified)}개")

    # 라운드 2: 부족하면 메인 쿼리 × 올해 조회수순 + 폴백 쿼리 × 이번 달
    if len(verified) < target_candidates:
        ids_r2 = gather_flat(cat.get("queries", []), [YT_SP_FILTERS[3]])
        ids_r2 += gather_flat(cat.get("fallback_queries", []), YT_SP_FILTERS[:3])
        verify_batch(ids_r2, max_probe=55)
        log(f"   ↳ [{cat['name']}] 2차(확장 검색) 철벽 통과 누적: {len(verified)}개")

    # 라운드 3: 그래도 10개 미만이면 폴백 쿼리 × 올해 조회수순 (90일/10만+/8분+/신생폭발 절대 유지!)
    if len(verified) < 10:
        ids_r3 = gather_flat(cat.get("fallback_queries", []), [YT_SP_FILTERS[3]])
        verify_batch(ids_r3, max_probe=55)
        log(f"   ↳ [{cat['name']}] 3차(심층 검색) 철벽 통과 누적: {len(verified)}개")

    # 정렬: 30일 이내 초신상 우선 + 폭발 배수 + 조회수
    results = list(verified.values())
    results.sort(
        key=lambda x: (
            1 if x["is_super_fresh"] else 0,
            1 if x["is_new"] else 0,
            x["explosion_ratio"] or 0.0,
            x["view_count"],
        ),
        reverse=True,
    )
    return results[: max(target_candidates, 10)]


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
                ratio_s = f"{c['explosion_ratio']:.1f}배" if c.get("explosion_ratio") else "신생"
                row = {
                    "id": c["id"],
                    "title": c["title"],
                    "summary": (
                        f"채널: {c['channel']} ({c['channel_badge']}) | "
                        f"업로드: {c['upload_date']} ({c['age_days']}일 전) | "
                        f"조회수: {c['view_count']:,}회 (폭발배수 {ratio_s}) | "
                        f"길이: {c['duration_str']} | {c['description']}"
                    ),
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
        log(f"🧪 Jev 100점 채점 시작 ({len(candidates)}개 철벽 통과 후보)...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=240, env=env)
        except Exception as e:
            log(f"⚠️ Jev 실행 예외: {e}")
            return _heuristic_score(candidates), "휴리스틱 안전 점수 (Jev 시간초과)"

        if res.returncode != 0 or not out_path.exists():
            log(f"⚠️ Jev 종료코드={res.returncode}: {res.stderr.strip()[:200]}")
            return _heuristic_score(candidates), "휴리스틱 안전 점수 (Jev 오류 폴백)"

        answers_map: dict[str, dict[str, Any]] = {}
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

        scored: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for c in candidates:
            ans = answers_map.get(c["id"])
            if not ans:
                missing.append(c)
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
            c_copy["scored_by"] = "jev-1.14.0"
            scored.append(c_copy)

        if missing:
            scored.extend(_heuristic_score(missing))

        scored.sort(key=lambda x: (x["total_score"], x["view_count"]), reverse=True)
        log(f"✅ Jev 실측 채점 완료 ({len(answers_map)}/{len(candidates)}개 실측, 최고점 {scored[0]['total_score']}점)")
        return scored, "TypeSafe Jev(jev-1.14.0) 100점 실측"


def _heuristic_score(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    for c in candidates:
        views = c.get("view_count", 0)
        base = min(0.92, 0.65 + (0.24 if views >= 1_000_000 else 0.18 if views >= 300_000 else 0.12))
        sc = {
            "hook": round(base * 30.0, 1),
            "evidence": round(min(0.92, base + 0.03) * 30.0, 1),
            "story": round(min(0.89, base) * 20.0, 1),
            "fit": round(min(0.91, base + 0.02) * 20.0, 1),
        }
        c_copy = dict(c)
        c_copy["scores"] = sc
        c_copy["total_score"] = round(sum(sc.values()), 1)
        c_copy["scored_by"] = "fallback"
        scored.append(c_copy)
    scored.sort(key=lambda x: (x["total_score"], x["view_count"]), reverse=True)
    return scored


def build_rising_channels(materials: list[dict[str, Any]], max_channels: int) -> list[dict[str, Any]]:
    """이미 100% 실측 통과한 신생·폭발 채널들 중 가장 핫한 채널만 추려 정리."""
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for m in materials:
        ch_name = m.get("channel")
        if not ch_name or ch_name in seen:
            continue
        seen.add(ch_name)
        subs = m.get("channel_follower_count")
        ratio = m.get("explosion_ratio")
        avg_v = m.get("channel_avg_views") or m["view_count"]
        vid_cnt = m.get("channel_video_count", 0)
        results.append(
            {
                "channel_name": ch_name,
                "channel_url": m.get("channel_url", ""),
                "category_id": m["category_id"],
                "category_name": m["category_name"],
                "category_emoji": m["category_emoji"],
                "category_color": m["category_color"],
                "category_bg": m["category_bg"],
                "created_info": m.get("channel_badge", "신생 폭발 채널"),
                "video_count": vid_cnt,
                "video_count_str": m.get("channel_video_count_str", "-"),
                "subscribers_str": f"{fmt_compact(subs)}명" if subs else "비공개",
                "explosion_str": f"{ratio:.1f}배" if ratio else "신생 대박",
                "avg_views": avg_v,
                "avg_views_str": f"{fmt_compact(avg_v)}회",
                "top_video_title": m["title"],
                "top_video_url": m["url"],
                "top_video_views": m["view_count"],
                "top_video_date": m["upload_date"],
                "easy_analysis": (
                    f"최근 {m['age_days']}일 전 올린 영상이 {fmt_compact(m['view_count'])}회를 돌파하며 "
                    f"({m['channel_badge']}) 지금 당장 벤치마킹해야 할 초고효율 채널입니다."
                ),
            }
        )

    results.sort(
        key=lambda x: (
            1 if 0 < x["video_count"] <= MAX_CHANNEL_VIDEOS_NEW else 0,
            x["top_video_views"],
        ),
        reverse=True,
    )
    return results[:max_channels]


def _call_claude_json(prompt: str, env: dict[str, str], timeout_sec: int = 120) -> dict[str, Any] | None:
    if not Path(CLAUDE_BIN).exists():
        return None
    try:
        res = subprocess.run(
            [
                CLAUDE_BIN,
                "-p",
                prompt,
                "--model",
                "haiku",
                "--tools",
                "",
                "--no-session-persistence",
                "--output-format",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            env=env,
        )
    except Exception as e:
        log(f"⚠️ Claude 호출 예외: {e}")
        return None
    if res.returncode != 0:
        log(f"⚠️ Claude 종료코드={res.returncode}: {res.stderr.strip()[:160]}")
        return None
    raw = res.stdout.strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def enrich_category_packs(cat_name: str, cat_items: list[dict[str, Any]], env: dict[str, str]) -> dict[str, dict[str, Any]]:
    slim = [
        {
            "id": m["id"],
            "rank": m["category_rank"],
            "title": m["title"],
            "channel": m["channel"],
            "views": fmt_compact(m["view_count"]),
            "upload_date": m["upload_date"],
            "age_days": m["age_days"],
            "channel_badge": m["channel_badge"],
            "duration": m["duration_str"],
            "score": m["total_score"],
            "desc": (m.get("description") or "")[:160],
        }
        for m in cat_items
    ]
    prompt = f"""너는 초등학생도 바로 따라 만들 수 있게 아주 쉬운 말로 유튜브 롱폼 '즉시 제작 장전 팩'을 짜주는 PD야.
분야: [{cat_name}] (총 {len(slim)}개 · 전부 최근 90일 이내 10만 뷰 이상 실측 대박 소재!)
아래 소재 모두에 대해, 제목만 주지 말고 **당장 오늘 영상 제작에 들어갈 수 있는 5가지 설계도**를 순수 JSON으로 출력해 줘. (마크다운 ``` 없이 순수 JSON 객체 하나만!)

규칙:
- 모든 문장은 초등학생도 쉽게 이해하는 친절한 한국어. (원본이 영어 제목이면 한국어 시청자용으로 완전 맛깔나게 각색!)
- title_options: 클릭률 높은 제목 2안 (숫자/따옴표/결말숨기기 공식 사용, 각 28~44자).
- thumb_line1: 썸네일 1줄 (하얀색 글씨, 5단어 이내, 짧고 강렬).
- thumb_line2: 썸네일 2줄 (빨간색 글씨, 5단어 이내, 반전/충격 핵심).
- opening_0_4s: 0~4초 충격 오프닝 대사 (절대 "안녕하세요" 금지! 첫 문장부터 바로 사건·반전으로 시작).
- acts: 4막 기승전결 뼈대 (act1 훅 / act2 전개 / act3 반전·떡밥 / act4 결말·여운 — 각 1문장).
- evidence_checklist: 화면에 1:1로 꼭 띄워야 할 실제 물증/장면 3개 (배열).
- reason: 최근 며칠 만에 왜 이렇게 조회수가 폭발했는지 쉬운 1문장.

출력 JSON 스키마:
{{
  "<id>": {{
    "reason": "...",
    "title_options": ["제목 1안", "제목 2안"],
    "thumb_line1": "하얀색 1줄",
    "thumb_line2": "빨간색 2줄",
    "opening_0_4s": "0~4초 첫 대사",
    "acts": {{
      "act1": "1막 훅 (0~90초) ...",
      "act2": "2막 전개 ...",
      "act3": "3막 반전/떡밥 ...",
      "act4": "4막 결말/여운 ..."
    }},
    "evidence_checklist": ["물증 화면 1", "물증 화면 2", "물증 화면 3"]
  }}
}}

소재 목록:
{json.dumps(slim, ensure_ascii=False)}
"""
    log(f"🤖 [{cat_name}] 즉시 작업 장전 팩 AI 생성 중...")
    parsed = _call_claude_json(prompt, env, timeout_sec=180)
    if isinstance(parsed, dict) and parsed:
        log(f"✅ [{cat_name}] 장전 팩 {len(parsed)}/{len(slim)}개 AI 생성 완료!")
        return parsed
    log(f"⚠️ [{cat_name}] AI 응답 폴백 사용")
    return {}


def enrich_summary_and_deep(
    date_str: str,
    top_materials: list[dict[str, Any]],
    channels: list[dict[str, Any]],
    deep_targets: list[dict[str, Any]],
    env: dict[str, str],
) -> dict[str, Any]:
    payload = {
        "date": date_str,
        "top_materials": [
            {
                "category": m["category_name"],
                "title": m["title"],
                "views": fmt_compact(m["view_count"]),
                "upload_date": m["upload_date"],
                "age_days": m["age_days"],
                "score": m["total_score"],
            }
            for m in top_materials[:8]
        ],
        "channels": [
            {
                "channel_name": c["channel_name"],
                "category": c["category_name"],
                "created_info": c["created_info"],
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
                "views": fmt_compact(d["view_count"]),
                "upload_date": d["upload_date"],
                "duration": d["duration_str"],
            }
            for d in deep_targets
        ],
    }
    prompt = f"""너는 초등학생도 10초 만에 이해할 수 있게 아주 쉬운 말과 비유로 설명하는 유튜브 롱폼 전문 분석가야.
오늘({date_str}) 100% 철벽 검수(최근 90일 이내 + 10만 뷰 이상 + 8분 이상 롱폼 + 신생/폭발 채널)를 통과한 브리핑의 3줄 요약, 신생 채널 분석, 분야별 1위 6단 해부를 순수 JSON 객체 하나만 출력해 줘. (마크다운 ``` 금지)

출력 JSON 스키마:
{{
  "easy_summary": [
    "오늘의 1줄 요약 (최근 1~3개월 10만+ 대박 소재만 골랐다는 강조 + 비유)",
    "오늘의 2줄 요약 (가장 점수 높은 1등 소재와 폭발 조회수)",
    "오늘의 3줄 요약 (파란 복사 버튼 눌러서 바로 제작하는 꿀팁)"
  ],
  "channel_notes": {{
    "<channel_name>": "이 채널이 최근 왜 이렇게 폭발적으로 크고 있는지 초등학생 눈높이 1~2문장"
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

데이터:
{json.dumps(payload, ensure_ascii=False)}
"""
    log("🤖 오늘의 3줄 요약 · 신생 채널 · 6단 해부 AI 생성 중...")
    return _call_claude_json(prompt, env, timeout_sec=150) or {}


def build_fallback_pack(m: dict[str, Any]) -> dict[str, Any]:
    cat_id = m["category_id"]
    short_t = re.sub(r"\s+", " ", m["title"]).strip()[:28]
    views_s = fmt_compact(m["view_count"])
    age_s = f"{m['age_days']}일 전"

    if cat_id == "cat_movie":
        return {
            "reason": f"불과 {age_s}에 올라와 {views_s}회가 터진 검증된 구작 영화 스토리로, 결말까지 눈을 못 떼게 만드는 복수·반전 구조가 탄탄합니다.",
            "title_options": [
                f'"{short_t}" 모두가 놓친 충격 결말, 지금 보면 소름 돋는 이유',
                f"불과 {age_s} {views_s}회 폭발한 전설의 영화, 마지막 5분이 미쳤다 [결말포함]",
            ],
            "thumb_line1": "마지막 5분 충격 반전",
            "thumb_line2": "진짜 범인은 따로 있었다",
            "opening_0_4s": "아무도 믿지 않았던 단 한 번의 거짓말이, 20분 뒤 모두의 운명을 완전히 뒤집어 놓습니다.",
            "acts": {
                "act1": "1막 훅 (0~90초): 영화 속 가장 충격적인 반전 직전 장면을 먼저 던지고 '왜 이런 일이?' 질문을 겁니다.",
                "act2": "2막 전개: 주인공이 평범한 일상에서 벗어나 위기에 빠지는 결정적 사건을 3~5초 컷 전환으로 빠르게 몰아칩니다.",
                "act3": "3막 반전/떡밥: 초반에 스쳐 지나갔던 작은 단서가 사실 엄청난 함정이었음이 드러나는 순간을 강조합니다.",
                "act4": "4막 결말/여운: 통쾌하거나 소름 돋는 엔딩을 해설하고, 시청자 댓글을 부르는 한 줄 질문으로 마무리합니다.",
            },
            "evidence_checklist": [
                "주인공 표정이 굳어지는 결정적 클로즈업 컷 (3~5초 이내 전환)",
                "초반 복선 소품·장소와 후반 반전 장면을 나란히 비교하는 화면",
                "저작권 안전을 위한 좌우반전·미세 배속·자체 한국어 해설 자막",
            ],
        }
    if cat_id == "cat_police":
        return {
            "reason": f"{age_s} 업로드돼 {views_s}회가 터진 실제 미국 경찰 바디캠 풀영상으로, 현장 긴장감과 체포 반전이 시청 지속시간을 끝까지 끌어올립니다.",
            "title_options": [
                f'"저는 아무 잘못 없어요" 당당하던 용의자가 3분 만에 무너진 순간 [미국경찰 바디캠]',
                f"{age_s} {views_s}회 폭발한 미국 경찰 바디캠, 트렁크 열자 현장이 얼어붙었다",
            ],
            "thumb_line1": "당당하게 거짓말하던 용의자",
            "thumb_line2": "트렁크 열자 현장 초토화",
            "opening_0_4s": '"경찰관님, 저 진짜 억울해요!" 그렇게 소리치던 남자가 불과 3분 뒤 수갑을 차고 바닥에 주저앉습니다.',
            "acts": {
                "act1": "1막 훅 (0~90초): 사이렌 소리와 함께 경찰이 현장에 도착해 결정적 증거를 발견하기 1초 전 장면으로 멈춥니다.",
                "act2": "2막 전개: 신고 접수 배경과 용의자의 뻔뻔한 거짓 변명을 바디캠 시간표(타임스탬프)와 함께 보여줍니다.",
                "act3": "3막 반전/떡밥: 경찰이 CCTV·차량 조회·현장 수색으로 거짓말을 하나씩 깨부수는 숨 막히는 대치 장면을 넣습니다.",
                "act4": "4막 결말/여운: 실제 체포·기소·최종 형량 결과를 자막 카드로 깔끔하게 정리하며 사이다 엔딩을 만듭니다.",
            },
            "evidence_checklist": [
                "경찰 바디캠 실제 현장 출동 및 대치 장면 (타 채널 로고 크롭)",
                "용의자 진술과 실제 증거가 어긋나는 순간 빨간 하이라이트 자막",
                "사건 발생 위치 지도 및 최종 법원 판결·형량 요약 카드",
            ],
        }
    if cat_id == "cat_senior":
        return {
            "reason": f"{age_s}에 올라와 {views_s}회 폭발한 6070 어르신 거실 TV 최애 주제로, 내 지갑·건강과 직결되어 끝까지 시청하는 비율이 높습니다.",
            "title_options": [
                f"60대 넘어서 이거 모르면 매달 손해 봅니다 | {short_t} 핵심 정리",
                f'"미리 알았으면 좋았을 걸" {age_s} {views_s}회 터진 {short_t} 3가지 비법',
            ],
            "thumb_line1": "60대 이후 모르면 큰 손해",
            "thumb_line2": "지금 당장 확인하세요",
            "opening_0_4s": "혹시 올해 바뀌는 이 기준, 아직도 예전 방식 그대로 알고 계시진 않나요? 모르고 지나치면 매달 큰돈이 새어나갑니다.",
            "acts": {
                "act1": "1막 훅 (0~90초): 어르신이 가장 걱정하는 손해·건강 문제를 숫자로 콕 짚어 '오늘 3가지만 기억하세요'라고 안내합니다.",
                "act2": "2막 전개: 공식 기관 자료와 쉬운 생활 비유로 왜 이런 변화가 생겼는지 초등학생도 알 만큼 또박또박 풀어줍니다.",
                "act3": "3막 반전/떡밥: 대부분이 착각하는 치명적 실수 1가지와, 반대로 챙기면 이득 보는 숨은 꿀팁을 비교표로 보여줍니다.",
                "act4": "4막 결말/여운: 오늘 바로 따라 할 수 있는 체크리스트 3줄을 큰 글씨로 요약하고 따뜻한 응원으로 마무리합니다.",
            },
            "evidence_checklist": [
                "국민연금공단·건강보험공단·통계청 등 공식 수치 비교표 (큰 글씨)",
                "헷갈리는 기준을 O/X로 한눈에 보여주는 거실 TV용 큼직한 자막 카드",
                "실제 신청 방법·주의사항 3단계 요약 화면",
            ],
        }
    return {
        "reason": f"불과 {age_s} 만에 해외에서 {views_s}회가 터진 신상 빈집 다큐 소재로, 한국엔 아직 경쟁이 적어 선점 효과가 큽니다.",
        "title_options": [
            f"전 세계를 충격에 빠뜨린 미스터리 실화 | {short_t}의 진짜 비밀",
            f"불과 {age_s} 해외에서 {views_s}회 난리 난 사건, 한국엔 아직 안 알려진 전말",
        ],
        "thumb_line1": "해외에서 난리 난 충격 실화",
        "thumb_line2": "결국 드러난 소름 돋는 진실",
        "opening_0_4s": "전 세계 전문가들이 10년 넘게 풀지 못했던 기이한 사건, 그런데 단 한 장의 사진이 모든 비밀을 풀어버렸습니다.",
        "acts": {
            "act1": "1막 훅 (0~90초): 사건의 가장 기이한 미스터리 결과물을 먼저 띄우고 '어떻게 이런 일이 가능했을까?' 호기심을 폭발시킵니다.",
            "act2": "2막 전개: 사건이 시작된 배경, 인물, 장소를 세계 지도와 타임라인 그래픽으로 흥미진진하게 따라갑니다.",
            "act3": "3막 반전/떡밥: 아무도 예상 못 한 결정적 증언과 숨겨진 진짜 원인이 밝혀지는 순간 극적인 분위기 전환을 줍니다.",
            "act4": "4막 결말/여운: 사건 이후의 실제 결말과 오늘날 우리에게 남긴 교훈을 여운 있게 정리합니다.",
        },
        "evidence_checklist": [
            "사건 발생 국가·도시를 확대하는 지도 애니메이션 및 타임라인",
            "당시 해외 신문 기사 헤드라인·공식 보고서·실제 현장 사진 1:1 매칭",
            "핵심 숫자·인물 관계를 한눈에 정리하는 다크 에디토리얼 인포그래픽",
        ],
    }


def build_work_prompt(m: dict[str, Any]) -> str:
    pack = m["pack"]
    acts = pack["acts"]
    ev_str = " / ".join(pack["evidence_checklist"])
    preset = m.get("preset_name", "인물형 롱폼")
    ratio_s = f"{m['explosion_ratio']:.1f}배" if m.get("explosion_ratio") else "신생 대박"
    return (
        f"[즉시 제작 요청 · {m['category_name']} / 프리셋: {preset}]\n"
        f"- 원본 소스 URL: {m['url']}\n"
        f"- 실측 지표: 업로드 {m['upload_date']} ({m['age_days']}일 전) · 조회수 {m['view_count']:,}회 · 길이 {m['duration_str']} · {m['channel']} ({ratio_s})\n"
        f"- 추천 제목 1안: {pack['title_options'][0]}\n"
        f"- 추천 제목 2안: {pack['title_options'][1]}\n"
        f"- 썸네일 2줄: [흰색] {pack['thumb_line1']} / [빨강] {pack['thumb_line2']}\n"
        f"- 0~4초 오프닝 대사: \"{pack['opening_0_4s']}\"\n"
        f"- 4막 기승전결 뼈대:\n"
        f"  1) {acts['act1']}\n"
        f"  2) {acts['act2']}\n"
        f"  3) {acts['act3']}\n"
        f"  4) {acts['act4']}\n"
        f"- 1:1 물증 화면 체크리스트: {ev_str}\n"
        f"- 저작권 안전 수칙: {m['copyright_note']}\n"
        f"위 장전 팩 그대로 썸네일 문구 확정 → 90초 콜드오픈 → 본편 2세대 롱폼(1080p GPU · 앞단 완결)으로 바로 제작 시작해 줘!"
    )


def merge_pack(m: dict[str, Any], ai_item: dict[str, Any] | None) -> dict[str, Any]:
    fb = build_fallback_pack(m)
    ai_item = ai_item if isinstance(ai_item, dict) else {}

    t_opts = ai_item.get("title_options")
    if not isinstance(t_opts, list) or len(t_opts) < 2 or not all(isinstance(x, str) and x.strip() for x in t_opts[:2]):
        t_opts = fb["title_options"]
    else:
        t_opts = [t_opts[0].strip(), t_opts[1].strip()]

    acts_raw = ai_item.get("acts") if isinstance(ai_item.get("acts"), dict) else {}
    acts = {
        "act1": (acts_raw.get("act1") or fb["acts"]["act1"]).strip(),
        "act2": (acts_raw.get("act2") or fb["acts"]["act2"]).strip(),
        "act3": (acts_raw.get("act3") or fb["acts"]["act3"]).strip(),
        "act4": (acts_raw.get("act4") or fb["acts"]["act4"]).strip(),
    }

    ev_raw = ai_item.get("evidence_checklist")
    if isinstance(ev_raw, list) and len(ev_raw) >= 2 and all(isinstance(x, str) and x.strip() for x in ev_raw):
        ev_list = [x.strip() for x in ev_raw[:4]]
    else:
        ev_list = fb["evidence_checklist"]

    m["reason"] = (ai_item.get("reason") or fb["reason"]).strip()
    m["evidence_tip"] = ev_list[0]
    m["pack"] = {
        "title_options": t_opts,
        "thumb_line1": (ai_item.get("thumb_line1") or fb["thumb_line1"]).strip(),
        "thumb_line2": (ai_item.get("thumb_line2") or fb["thumb_line2"]).strip(),
        "opening_0_4s": (ai_item.get("opening_0_4s") or fb["opening_0_4s"]).strip(),
        "acts": acts,
        "evidence_checklist": ev_list,
    }
    m["pack"]["work_prompt"] = build_work_prompt(m)
    return m


def assert_hard_gates(edition: dict[str, Any], today_date: dt.date) -> dict[str, Any]:
    """배포 직전 영구 박제 철벽 전수 검증 — 단 1건이라도 불량이면 배포 원천 차단!"""
    mats = edition.get("materials") or []
    if not mats:
        raise RuntimeError("❌ [하드게이트 차단] 통과한 소재가 0건입니다! 배포를 중단합니다.")

    cutoff_date = today_date - dt.timedelta(days=MAX_AGE_DAYS)
    defects: list[str] = []
    views_list: list[int] = []
    dates_list: list[dt.date] = []
    durs_list: list[int] = []
    ratios_list: list[float] = []
    within_30d = 0

    for idx, m in enumerate(mats, start=1):
        vid = m.get("video_id", f"idx_{idx}")
        v = int(m.get("view_count") or 0)
        d = int(m.get("duration") or 0)
        up = parse_iso_date(m.get("upload_date"))
        ch_ok = bool(m.get("channel_verified"))

        if v < MIN_VIEWS:
            defects.append(f"[{vid}] 조회수 미달: {v:,} < {MIN_VIEWS:,}")
        if d < MIN_DURATION_SEC:
            defects.append(f"[{vid}] 길이 미달(쇼츠/단편): {d}초 < {MIN_DURATION_SEC}초")
        if not up or up < cutoff_date:
            defects.append(f"[{vid}] 업로드일 초과: {m.get('upload_date')} < {cutoff_date.isoformat()}")
        if not ch_ok:
            defects.append(f"[{vid}] 신생/폭발 채널 기준 미통과: {m.get('channel')}")

        views_list.append(v)
        durs_list.append(d)
        if up:
            dates_list.append(up)
            if (today_date - up).days <= 30:
                within_30d += 1
        if m.get("explosion_ratio"):
            ratios_list.append(float(m["explosion_ratio"]))

    if defects:
        detail = "\n".join(defects[:10])
        raise RuntimeError(f"❌ [하드게이트 배포 원천 차단] 불량 {len(defects)}건 발견!\n{detail}")

    min_v = min(views_list)
    max_v = max(views_list)
    oldest_d = min(dates_list).isoformat()
    newest_d = max(dates_list).isoformat()
    min_dur = min(durs_list)
    avg_ratio = round(sum(ratios_list) / len(ratios_list), 1) if ratios_list else 0.0

    proof = {
        "passed": True,
        "total_count": len(mats),
        "defect_count": 0,
        "min_views": min_v,
        "min_views_str": f"{min_v:,}회",
        "max_views": max_v,
        "max_views_str": f"{fmt_compact(max_v)}회",
        "oldest_upload_date": oldest_d,
        "newest_upload_date": newest_d,
        "cutoff_date": cutoff_date.isoformat(),
        "min_duration_sec": min_dur,
        "min_duration_str": fmt_duration(min_dur),
        "within_30d_count": within_30d,
        "avg_explosion_ratio": avg_ratio,
    }
    log(
        f"🔒 [철벽 하드게이트 100% 통과 증명] 총 {proof['total_count']}건 | 불량 0건 | "
        f"최소 조회수 {proof['min_views_str']} | 가장 오래된 날짜 {proof['oldest_upload_date']} (기준 {proof['cutoff_date']} 이후) | "
        f"최소 길이 {proof['min_duration_str']} | 최근 30일 이내 {proof['within_30d_count']}건"
    )
    return proof


def main() -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    env = load_typesafe_env()
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    now = dt.datetime.now()
    today_date = now.date()
    today = today_date.isoformat()
    gen_time = now.strftime("%H:%M KST")

    per_query = int(cfg.get("search_per_query", 16))
    cand_per_cat = int(cfg.get("candidates_per_category", 14))
    top_per_cat = int(cfg.get("top_materials_per_category", 10))

    log(
        f"🚀 유튜브 롱폼 데일리 브리핑 (철벽 5대 하드게이트) 시작 ({today} {gen_time}) — "
        f"기준: 90일 이내 ({(today_date - dt.timedelta(days=MAX_AGE_DAYS)).isoformat()}~) · 10만 뷰+ · 8분+ · 신생/폭발 채널만"
    )
    prev_vids = load_previous_video_ids(today)
    channel_cache: dict[str, dict[str, Any]] = {}

    # 1. 4개 분야 철벽 실측 수집
    all_candidates: list[dict[str, Any]] = []
    for cat in cfg["categories"]:
        log(f"🔎 철벽 실측 수집 중: {cat['emoji']} {cat['name']}")
        items = fetch_verified_videos_for_category(
            cat, per_query, cand_per_cat, today_date, prev_vids, channel_cache, env
        )
        log(f"   ✅ [{cat['name']}] 철벽 5대 기준 통과: {len(items)}개 (30일 이내 {sum(1 for x in items if x['is_super_fresh'])}개)")
        all_candidates.extend(items)

    if not all_candidates:
        raise RuntimeError("❌ 전 분야에서 철벽 기준 통과 소재가 0건입니다. 배포를 중단합니다.")

    # 2. 전원 Jev 100점 정량 채점
    scored, scoring_badge = score_with_jev(all_candidates, env)

    # 분야별 상위 10개 엄격 내림차순 선별 (부족해도 절대 불량 끼워넣지 않음!)
    selected_materials: list[dict[str, Any]] = []
    cat_groups: dict[str, list[dict[str, Any]]] = {}
    for cat in cfg["categories"]:
        cat_items = [x for x in scored if x["category_id"] == cat["id"]]
        cat_items.sort(key=lambda x: (x["total_score"], x["view_count"]), reverse=True)
        chosen = cat_items[:top_per_cat]
        for idx, item in enumerate(chosen, start=1):
            item["category_rank"] = idx
        cat_groups[cat["id"]] = chosen
        selected_materials.extend(chosen)
        if chosen:
            log(f"   🏆 {cat['emoji']} {cat['name']}: {len(chosen)}개 확정 (1위 {chosen[0]['total_score']}점 · 최소조회 {min(x['view_count'] for x in chosen):,}회)")
        else:
            log(f"   ⚠️ {cat['name']}: 0개 (불량 끼워넣기 금지 원칙 유지)")

    # 전체 순위 부여 (Jev 점수 내림차순)
    selected_materials.sort(key=lambda x: (x["total_score"], x["view_count"]), reverse=True)
    for idx, item in enumerate(selected_materials, start=1):
        item["overall_rank"] = idx

    # 3. 핫한 신생·폭발 채널 리스트 구성 (이미 100% 실측 완료)
    rising_channels = build_rising_channels(selected_materials, int(cfg.get("max_rising_channels", 8)))

    # 4. 분야별 1위 영상을 심층 해부 대상으로 선정
    deep_targets: list[dict[str, Any]] = []
    for cat in cfg["categories"]:
        if cat_groups.get(cat["id"]):
            deep_targets.append(cat_groups[cat["id"]][0])
    deep_targets = deep_targets[: int(cfg.get("max_deep_dives", 4))]

    # 5. 즉시 작업 장전 팩 + 요약/채널/6단 해부 AI 생성 (5개씩 청크 병렬)
    all_ai_packs: dict[str, dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pack_futs: dict[concurrent.futures.Future, str] = {}
        for cat in cfg["categories"]:
            c_items = cat_groups.get(cat["id"]) or []
            for start in range(0, len(c_items), 5):
                chunk = c_items[start : start + 5]
                label = f"{cat['name']} ({start + 1}~{start + len(chunk)}위)"
                pack_futs[pool.submit(enrich_category_packs, label, chunk, env)] = label
        summary_fut = pool.submit(enrich_summary_and_deep, today, selected_materials, rising_channels, deep_targets, env)

        for fut, cname in pack_futs.items():
            try:
                res_map = fut.result()
                all_ai_packs.update(res_map)
            except Exception as e:
                log(f"⚠️ [{cname}] 장전 팩 스레드 오류: {e}")

        try:
            ai_summary = summary_fut.result() or {}
        except Exception as e:
            log(f"⚠️ 요약/해부 스레드 오류: {e}")
            ai_summary = {}

    for m in selected_materials:
        merge_pack(m, all_ai_packs.get(m["id"]))

    ch_notes = ai_summary.get("channel_notes", {}) if isinstance(ai_summary, dict) else {}
    deep_notes = ai_summary.get("deep_dives", {}) if isinstance(ai_summary, dict) else {}

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
                "upload_date": d["upload_date"],
                "age_days": d["age_days"],
                "url": d["url"],
                "planning": dn.get("planning") or f"{d['category_name']} 시청자가 제일 좋아하는 갈등→반전→결말 구조로 10분 이상 몰입하게 판을 짰습니다.",
                "keywords": dn.get("keywords") or f"제목 속 핵심 상황 키워드 + '{d['category_name']}' 대표 감성 단어를 앞부분에 배치했습니다.",
                "issue": dn.get("issue") or f"불과 {d['age_days']}일 전에 올라와 {fmt_compact(d['view_count'])}회가 터진 지금 당장 가장 뜨거운 주제입니다.",
                "hook_0s": dn.get("hook_0s") or "인사말 없이 0초부터 가장 충격적인 하이라이트 장면과 질문을 던져 이탈을 막았습니다.",
                "visual_style": dn.get("visual_style") or "대본과 딱 맞는 실제 물증 화면을 빠르게 전환하고, 큰 자막으로 거실 TV·모바일 가독성을 높였습니다.",
                "copy_action": dn.get("copy_action") or f"오늘 영상 첫 10초에 '{d['title'][:28]}...'처럼 결론 직전 가장 궁금한 장면을 먼저 보여주고 시작하세요!",
            }
        )

    top1 = selected_materials[0] if selected_materials else None
    easy_summary = ai_summary.get("easy_summary") if isinstance(ai_summary, dict) and ai_summary.get("easy_summary") else [
        f"🔒 오늘({today})은 90일 이내 + 10만 뷰 이상 + 8분 이상 롱폼 + 신생·폭발 채널만 100% 실측 통과한 {len(selected_materials)}개 진짜 대박 소재만 담았어요!",
        f"🏆 오늘의 전체 1등 소재는 [{top1['category_name']}] '{top1['title'][:36]}' ({top1['total_score']}점 · {fmt_compact(top1['view_count'])}회)입니다." if top1 else "🏆 오늘의 철벽 통과 소재가 준비되었어요.",
        "⚡ 마음에 드는 카드의 파란색 [⚡ 바로 작업 지시문 복사] 버튼만 눌러 채팅창에 붙여넣으면 오늘 영상 제작이 1초 만에 시작됩니다!",
    ]

    # 6. 에디션 구성 + ★배포 직전 영구 박제 철벽 하드게이트 검증★
    edition_obj: dict[str, Any] = {
        "date": today,
        "issue_no": 1,
        "generated_at": gen_time,
        "scoring_badge": f"{scoring_badge} · 철벽 통과 {len(selected_materials)}개",
        "easy_summary": easy_summary,
        "materials": selected_materials,
        "rising_channels": rising_channels,
        "deep_dives": deep_dives,
    }
    audit_proof = assert_hard_gates(edition_obj, today_date)
    edition_obj["audit_proof"] = audit_proof

    # 7. 아카이브 저장 (기존 불량 구버전 에디션은 자동 정리하여 불량 0건 유지)
    if ARCHIVE_PATH.exists():
        archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    else:
        archive = {"editions": {}}

    editions = archive.setdefault("editions", {})
    # 과거 에디션 중 audit_proof.passed != True 인 구버전 불량 데이터 제거
    clean_editions = {
        d: ed for d, ed in editions.items()
        if d != today and (ed.get("audit_proof") or {}).get("passed") is True
    }
    issue_no = len(clean_editions) + 1
    edition_obj["issue_no"] = issue_no
    clean_editions[today] = edition_obj
    archive["editions"] = clean_editions

    ARCHIVE_PATH.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"💾 아카이브 저장 완료: {ARCHIVE_PATH} (제{issue_no}호 · 철벽 통과 {len(selected_materials)}개 · 불량 0건)")

    # 8. HTML 빌드 (브라우저 자동 열기 절대 없음!)
    subprocess.run([sys.executable, str(BASE_DIR / "render_html.py")], check=True, env=env)

    # 9. GitHub Pages 배포
    if os.environ.get("SKIP_DEPLOY") != "1":
        subprocess.run(["bash", str(BASE_DIR / "deploy.sh")], check=True, env=env)

    # 10. macOS 알림 + 완료 음성 (브라우저 실행 없음!)
    if os.environ.get("SKIP_NOTIFY") != "1":
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "제{issue_no}호 ({today}) 철벽 검수 통과 {len(selected_materials)}개 (불량 0건 · 최소 {audit_proof["min_views_str"]}) 배달 완료!" with title "🔒 유튜브 롱폼 데일리 브리핑"',
                ],
                check=False,
                timeout=10,
            )
        except Exception:
            pass
        if Path(DONE_VOICE).exists():
            subprocess.run([DONE_VOICE, "유튜브데일리브리핑"], check=False, timeout=15)

    log("🎉 데일리 브리핑 철벽 파이프라인 완료!")


if __name__ == "__main__":
    main()
