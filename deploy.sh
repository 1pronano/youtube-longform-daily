#!/usr/bin/env bash
set -euo pipefail

SRC="/Users/dongkeunkim/Desktop/유튜브_롱폼_데일리_브리핑.html"
DIR="/Users/dongkeunkim/youtube-longform-daily"
DST="$DIR/index.html"

if [[ ! -f "$SRC" ]]; then
  echo "❌ 원본 HTML 파일을 찾을 수 없습니다: $SRC" >&2
  exit 1
fi

python3 - "$SRC" "$DST" <<'PY'
import re
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
html = src.read_text(encoding="utf-8")

# 외부 공개 페이지에 로컬 경로나 사용자명이 노출되지 않도록 마스킹
html = re.sub(r'<a\s+href="file:///[^"]+">([^<]+)</a>', r'<strong>\1</strong>', html)
html = re.sub(r'/Users/[^/\s"\'<>]+/', '~/', html)

dst.write_text(html, encoding="utf-8")
print(f"✅ 배포용 index.html 생성 완료 ({dst.stat().st_size:,} bytes)")
PY

cd "$DIR"
touch .nojekyll

git add index.html .nojekyll deploy.sh config.json render_html.py run_daily.py data/archive.json 2>/dev/null || git add index.html .nojekyll deploy.sh

if git diff --cached --quiet; then
  echo "ℹ️ 변경된 내용이 없어 이미 최신 상태입니다."
else
  git commit -m "daily: 유튜브 롱폼 데일리 브리핑 업데이트 ($(date '+%Y-%m-%d %H:%M'))"
  git push -u origin main
  echo "🚀 GitHub Pages 배포 푸시 완료: https://1pronano.github.io/youtube-longform-daily/"
fi
