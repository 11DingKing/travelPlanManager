#!/bin/bash
# 旅行计划管理器启动脚本

cd "$(dirname "$0")/backend"

# 检查 Python 是否安装
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "错误: 未找到 Python，请先安装 Python 3"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

echo "启动旅行计划管理器..."
$PYTHON_CMD day.py
