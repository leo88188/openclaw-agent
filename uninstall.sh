#!/bin/bash
# OpenClaw Agent 停止/卸载脚本（Linux + macOS 通用）
# 用法:
#   bash uninstall.sh          # 仅停止服务
#   bash uninstall.sh --remove # 停止并删除所有文件

set -e

REMOVE=false
[[ "$1" == "--remove" ]] && REMOVE=true

OS=$(uname -s)

if [[ "$OS" == "Darwin" ]]; then
    # ── macOS (launchd) ──
    LABEL="com.openclaw.agent"
    PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
    INSTALL_DIR="$HOME/.openclaw-agent"

    echo "🍎 macOS 检测到"
    if launchctl print "gui/$(id -u)/${LABEL}" &>/dev/null; then
        launchctl bootout "gui/$(id -u)/${LABEL}" 2>/dev/null || true
        echo "✅ 服务已停止"
    else
        echo "⚠️  服务未运行"
    fi

    if $REMOVE; then
        rm -f "$PLIST"
        rm -rf "$INSTALL_DIR"
        echo "🗑️  已删除: $PLIST"
        echo "🗑️  已删除: $INSTALL_DIR"
        echo "✅ 卸载完成"
    else
        echo ""
        echo "服务已停止。如需彻底卸载，运行:"
        echo "  bash uninstall.sh --remove"
    fi

else
    # ── Linux (systemd) ──
    INSTALL_DIR="/opt/openclaw-agent"
    SERVICE="openclaw-agent"

    echo "🐧 Linux 检测到"
    if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
        systemctl stop "$SERVICE"
        echo "✅ 服务已停止"
    else
        echo "⚠️  服务未运行"
    fi

    if $REMOVE; then
        systemctl disable "$SERVICE" 2>/dev/null || true
        rm -f "/etc/systemd/system/${SERVICE}.service"
        systemctl daemon-reload 2>/dev/null || true
        rm -rf "$INSTALL_DIR"
        echo "🗑️  已删除: /etc/systemd/system/${SERVICE}.service"
        echo "🗑️  已删除: $INSTALL_DIR"
        echo "✅ 卸载完成"
    else
        echo ""
        echo "服务已停止。如需彻底卸载，运行:"
        echo "  sudo bash uninstall.sh --remove"
    fi
fi
