#!/bin/bash
# 双击运行：第一次自动安装，然后弹出浏览器窗口让你登录 NTULearn，最后打开看板。
cd "$(dirname "$0")" || exit 1
PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "需要 Python 3.9 或更新版本：https://www.python.org/downloads/"
  read -r -p "按回车关闭窗口" _; exit 1
fi
if [ ! -x .venv/bin/ntulearn ]; then
  echo "第一次运行，正在安装，大约需要半分钟……"
  if ! { "$PY" -m venv .venv && .venv/bin/python -m pip install -q --disable-pip-version-check -e .; }; then
    read -r -p "安装失败，请检查网络后重试。按回车关闭窗口" _; exit 1
  fi
fi
if [ $# -eq 0 ]; then .venv/bin/ntulearn go; else .venv/bin/ntulearn "$@"; fi
status=$?
echo
read -r -p "完成，按回车关闭窗口" _
exit $status
