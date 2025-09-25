#!/bin/bash
# macOS 双击执行：强制终止本项目相关进程 + 重置数据库（默认备份 + 保留地区）
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"
cd "$ROOT" || exit 1

if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

echo "[INFO] 项目根目录: $ROOT"

# 1) 强制终止当前项目下运行的 run.py/bot.py 进程
echo "[INFO] 正在查找并终止运行中的进程(run.py/bot.py/scheduler.py)..."
PIDS=$(ps ax -o pid=,command= | grep -E "[p]ython[0-9]? .*(run\\.py|bot\\.py|scheduler\\.py)" | grep -F "$ROOT" | awk '{print $1}')
if [ -n "$PIDS" ]; then
  echo "$PIDS" | while read -r pid; do
    if [ -n "$pid" ]; then
      echo "  - 终止 PID $pid"
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  # 强制杀掉仍存活的
  for pid in $PIDS; do
    if ps -p "$pid" >/dev/null 2>&1; then
      echo "  - 强制结束 PID $pid"
      kill -KILL "$pid" 2>/dev/null || true
    fi
  done
else
  echo "  - 未发现需要终止的进程"
fi

# 2) 执行重置（默认保留基础地区）并在末尾做一次列验证
"$PY" tools/reset_all_data.py --yes --preserve-regions "$@"

# 3) 验证 merchants.adv_sentence 字段是否存在（便于人肉确认）
echo "[INFO] 验证 merchants.adv_sentence 字段..."
$PY - <<'PYEOF'
from pathmanager import PathManager
import sqlite3
db_path = PathManager.get_database_path()
conn = sqlite3.connect(db_path)
cur = conn.execute("PRAGMA table_info(merchants)")
cols = [r[1] for r in cur.fetchall()]
conn.close()
print("[OK] adv_sentence 存在" if 'adv_sentence' in cols else "[WARN] adv_sentence 不存在！")
PYEOF

echo "\n完成。按任意键关闭..."
read -r -n 1 _ || true
