"""ASMAN2 产出读取工具
用法: python read_output.py [task_id]
不传 task_id 则列出所有已完成的任务
"""

import sys
import os
import json
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = os.path.join(os.path.dirname(__file__), "asman2_state.db")


def list_tasks():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT passenger_id, status, current_location, segment_idx, updated_at FROM passengers ORDER BY updated_at DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("暂无任务记录")
        return []

    print(f"{'Task ID':<22} {'状态':<12} {'位置':<8} {'进度':<6} {'更新时间'}")
    print("-" * 80)
    ids = []
    for row in rows:
        pid, status, loc, seg, ts = row
        ids.append(pid)
        from datetime import datetime
        time_str = datetime.fromtimestamp(ts).strftime("%m-%d %H:%M:%S")
        print(f"{pid:<22} {status:<12} {loc:<8} {seg}/6     {time_str}")
    return ids


def read_output(task_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT passenger_id, status, baggage, completed_stops FROM passengers WHERE passenger_id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        print(f"任务 {task_id} 不存在")
        return

    pid, status, baggage_str, stops_str = row
    baggage = json.loads(baggage_str) if baggage_str else {}
    stops = json.loads(stops_str) if stops_str else []

    print(f"\n{'='*60}")
    print(f"任务: {pid}")
    print(f"状态: {status}")
    print(f"经过站点: {' → '.join(stops)}")
    print(f"{'='*60}")

    # 小说正文
    novel = baggage.get("merged_W2_SLICE", {})
    if novel:
        print(f"\n[📖 小说正文]")
        if isinstance(novel, dict):
            print(f"  总章节: {novel.get('total_chapters', '?')}")
            full = novel.get("full_novel", "")
            if full:
                print(f"  字数: {len(full)}")
                print(f"\n{full[:2000]}")
                if len(full) > 2000:
                    print(f"\n  ... (共 {len(full)} 字，仅显示前 2000)")

    # 剧本
    script = baggage.get("merged_D3_SLICE", {})
    if script:
        print(f"\n[🎬 剧本]")
        print(json.dumps(script, ensure_ascii=False, indent=2, default=str)[:1500])

    # 视频
    videos = baggage.get("video_outputs", baggage.get("merged_V4", {}))
    if videos:
        print(f"\n[📹 视频方案]")
        print(json.dumps(videos, ensure_ascii=False, indent=2, default=str)[:1000])

    # 发布
    publish = baggage.get("merged_P3_SLICE", {})
    if publish:
        print(f"\n[📤 发布配置]")
        print(json.dumps(publish, ensure_ascii=False, indent=2, default=str)[:1000])

    # 各站点产出摘要
    print(f"\n[🏗 各站点产出]")
    for key in sorted(baggage.keys()):
        if key.startswith("output_"):
            val = baggage[key]
            if isinstance(val, dict):
                summary = str(val)[:120]
            else:
                summary = str(val)[:120]
            print(f"  {key}: {summary}")

    print(f"\n{'='*60}")
    print(f"完整 baggage 共有 {len(baggage)} 个字段")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        read_output(sys.argv[1])
    else:
        ids = list_tasks()
        if ids:
            print(f"\n查看详细产出: python read_output.py <task_id>")
            # 自动读取最新的
            print(f"\n--- 最新任务详情 ---")
            read_output(ids[0])
