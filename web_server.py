"""
ASMAN 2.0 Web Server
FastAPI + WebSocket + 静态前端
"""

import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Dict, Optional

# Windows UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

from asman.engine import MetroEngine
from asman.runtime.config import EngineConfig, LLMConfig, JudgeConfig, load_yaml
from examples.novel.agents import register_all
from examples.novel.bootstrapper import NovelBootstrapper


# ================ 数据模型 ================

class CreateTaskRequest(BaseModel):
    user_input: str
    title: str = ""
    genre: str = ""
    chapters: int = 3
    word_count_per_chapter: int = 1500
    need_video: bool = True


class TaskInfo(BaseModel):
    task_id: str
    title: str
    genre: str
    status: str
    progress: float
    current_station: str
    created_at: float


# ================ 全局状态 ================

engine: Optional[MetroEngine] = None
active_ws_connections: Dict[str, list] = {}
task_registry: Dict[str, dict] = {}  # task_id → metadata


# ================ 应用生命周期 ================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global engine
    provider = os.getenv("LLM_PROVIDER", "mock")
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")

    print(f"[WebServer] 启动引擎 | Provider: {provider}")
    here = Path(__file__).resolve().parent / "examples" / "novel"
    config = EngineConfig(
        network=load_yaml(str(here / "network.yaml")),
        profiles=load_yaml(str(here / "profiles.yaml")),
        llm=LLMConfig(provider=provider, api_key=api_key, base_url=base_url),
        judge=JudgeConfig(enabled=True),
        state_db=str(here / "novel_state.db"),
        skill_db=str(here / "novel_skills.db"),
    )
    register_all()
    engine = MetroEngine(config=config, bootstrapper=NovelBootstrapper())
    await engine.build_network()
    print("[WebServer] 引擎就绪")
    yield
    if engine:
        await engine.shutdown()
    print("[WebServer] 已关闭")


app = FastAPI(title="ASMAN 2.0 Web", lifespan=lifespan)

# 静态文件
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ================ 页面路由 ================

@app.get("/")
async def root():
    return FileResponse("static/index.html")


# ================ REST API ================

@app.get("/api/health")
async def health():
    return {"status": "ok", "provider": engine.llm_client.provider if engine else "unknown"}


@app.post("/api/tasks")
async def create_task(req: CreateTaskRequest):
    """创建新的创作任务"""
    if not engine:
        raise HTTPException(503, "引擎未就绪")

    # 构建用户输入（包含详细参数）
    user_input = req.user_input
    if req.title:
        user_input = f"标题:{req.title} 题材:{req.genre} 章节:{req.chapters}章 字数:{req.word_count_per_chapter}字/章 视频:{'需要' if req.need_video else '不需要'} " + user_input

    task_id = await engine.run(user_input)

    task_registry[task_id] = {
        "task_id": task_id,
        "title": req.title or req.user_input[:40],
        "genre": req.genre or "待推断",
        "user_input": req.user_input,
        "created_at": time.time(),
        "status": "running"
    }

    return {"task_id": task_id, "message": "任务已创建", "user_input": req.user_input[:100]}


@app.get("/api/tasks")
async def list_tasks():
    """列出所有任务"""
    tasks = []
    for tid, meta in task_registry.items():
        try:
            progress = await engine.get_progress(tid)
            tasks.append({
                "task_id": tid,
                "title": meta.get("title", ""),
                "genre": meta.get("genre", ""),
                "status": progress.get("status", "unknown"),
                "progress": progress.get("progress_percent", 0),
                "current_station": progress.get("current_station", ""),
                "created_at": meta.get("created_at", 0)
            })
        except Exception as e:
            tasks.append({
                "task_id": tid,
                "title": meta.get("title", ""),
                "status": "error",
                "error": str(e)
            })
    return {"tasks": sorted(tasks, key=lambda t: t.get("created_at", 0), reverse=True)}


@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """获取任务详情"""
    if not engine:
        raise HTTPException(503, "引擎未就绪")

    try:
        progress = await engine.get_progress(task_id)
    except Exception:
        raise HTTPException(404, "任务未找到")

    meta = task_registry.get(task_id, {})
    return {
        **progress,
        "title": meta.get("title", ""),
        "genre": meta.get("genre", ""),
        "user_input": meta.get("user_input", ""),
        "hermes_summary": engine.get_hermes_summary()
    }


@app.get("/api/tasks/{task_id}/events")
async def get_task_events(task_id: str):
    """获取任务事件轨迹（审计/回溯）"""
    if not engine:
        return {"events": []}
    return {"events": engine.get_events(task_id)}


@app.post("/api/tasks/{task_id}/approve")
async def approve_task(task_id: str):
    """批准挂起的人工门控站点"""
    if not engine:
        raise HTTPException(503, "引擎未就绪")
    if not await engine.approve(task_id):
        raise HTTPException(400, "任务不在挂起状态")
    return {"task_id": task_id, "status": "approved"}


@app.post("/api/tasks/{task_id}/reject")
async def reject_task(task_id: str, reason: str = ""):
    """驳回挂起站点，触发回环"""
    if not engine:
        raise HTTPException(503, "引擎未就绪")
    if not await engine.reject(task_id, reason):
        raise HTTPException(400, "任务不在挂起状态")
    return {"task_id": task_id, "status": "rejected"}


@app.get("/api/tasks/{task_id}/output")
async def get_task_output(task_id: str):
    """获取任务最终产物"""
    if not engine:
        raise HTTPException(503, "引擎未就绪")

    passenger = engine.occ.get_passenger(task_id)
    if not passenger:
        raise HTTPException(404, "任务未找到")

    baggage = passenger.baggage

    # 提取各类产物
    output = {
        "task_id": task_id,
        "status": passenger.status.value,
        "title": passenger.ticket.config.title if passenger.ticket.config else "",
        "novel": _extract_novel(baggage),
        "outline": _extract_outline(baggage),
        "script": _extract_script(baggage),
        "video": _extract_video(baggage),
        "publish": _extract_publish(baggage),
        "stats": {
            "completed_stops": passenger.completed_stops,
            "fix_count": len(passenger.fix_history),
            "quality_scores": {k: v.average() for k, v in passenger.quality_scores.items()} if hasattr(passenger, 'quality_scores') else {},
            "execution_time": time.time() - passenger.created_at
        }
    }
    return output


@app.get("/api/stats")
async def get_stats():
    """获取全局统计"""
    if not engine:
        return {"tasks_total": len(task_registry), "hermes_summary": {}}

    hermes = engine.get_hermes_summary()
    return {
        "tasks_total": len(task_registry),
        "tasks_running": sum(1 for t in task_registry.values() if t["status"] == "running"),
        "tasks_completed": sum(1 for t in task_registry.values() if t["status"] == "completed"),
        "hermes_summary": hermes
    }


@app.get("/api/metrics")
async def get_metrics():
    """获取运行时指标"""
    if not engine:
        return {"metrics": {}}
    return {"metrics": engine.get_metrics()}


@app.get("/api/topology")
async def get_topology():
    """获取网络拓扑（供可视化）"""
    if not engine:
        return {"name": "", "lines": [], "itinerary": []}
    return engine.get_topology()


# ================ WebSocket（实时进度推送） ================

@app.websocket("/ws/tasks/{task_id}")
async def ws_task_progress(ws: WebSocket, task_id: str):
    await ws.accept()

    if task_id not in active_ws_connections:
        active_ws_connections[task_id] = []
    active_ws_connections[task_id].append(ws)

    try:
        last_progress = -1
        stable_count = 0

        while True:
            if not engine:
                await ws.send_json({"type": "error", "message": "引擎未就绪"})
                break

            try:
                progress = await engine.get_progress(task_id)
            except Exception:
                await ws.send_json({"type": "error", "message": "任务丢失"})
                break

            current = progress.get("progress_percent", 0)
            status = progress.get("status", "")

            if current != last_progress:
                await ws.send_json({
                    "type": "progress",
                    "progress": current,
                    "status": status,
                    "current_station": progress.get("current_station", ""),
                    "completed_stops": progress.get("completed_stops", []),
                    "quality_scores": progress.get("quality_scores", {}),
                    "skill_stats": progress.get("skill_stats", {}),
                    "hermes_workers": progress.get("hermes_workers", {}),
                    "fix_count": progress.get("fix_count", 0),
                    "is_converged": progress.get("is_converged", False)
                })
                last_progress = current

            if status == "completed" or progress.get("is_converged"):
                stable_count += 1
                if stable_count >= 3:
                    await ws.send_json({
                        "type": "completed",
                        "message": "任务已完成",
                        "hermes_summary": engine.get_hermes_summary()
                    })
                    break
            else:
                stable_count = 0

            # 接收客户端消息（用于心跳/控制）
            try:
                data = await asyncio.wait_for(ws.receive_text(), timeout=0.5)
                if data == "ping":
                    await ws.send_text("pong")
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        pass
    finally:
        if task_id in active_ws_connections:
            active_ws_connections[task_id].remove(ws)


# ================ 辅助函数 ================

def _extract_novel(baggage: dict) -> dict:
    """提取小说内容"""
    merged = baggage.get("merged_W2_SLICE", {})
    if isinstance(merged, str):
        return {"content": merged}
    chapters = []
    if isinstance(merged, dict):
        for key, val in merged.items():
            if isinstance(val, dict):
                chapters.append({
                    "title": val.get("title", str(key)),
                    "content": val.get("content", str(val)[:5000])
                })
            elif isinstance(val, str):
                chapters.append({"title": str(key), "content": val[:5000]})
    if not chapters:
        for k, v in baggage.items():
            if "W3" in k or "chapter" in k.lower() or "write" in k.lower():
                if isinstance(v, dict):
                    chapters.append({
                        "title": v.get("title", str(k)),
                        "content": v.get("content", str(v)[:5000])
                    })
    return {"chapters": chapters, "count": len(chapters)}


def _extract_outline(baggage: dict) -> dict:
    """提取大纲"""
    for k in ["output_W1", "W1", "outline"]:
        if k in baggage:
            return baggage[k]
    return {}


def _extract_script(baggage: dict) -> dict:
    """提取剧本"""
    merged = baggage.get("merged_D3_SLICE", {})
    if isinstance(merged, str):
        return {"content": merged}
    scenes = []
    if isinstance(merged, dict):
        for key, val in merged.items():
            scenes.append({"id": key, "content": str(val)[:2000]})
    return {"scenes": scenes, "count": len(scenes)}


def _extract_video(baggage: dict) -> dict:
    """提取视频相关"""
    video_outputs = baggage.get("video_outputs", [])
    return {"outputs": video_outputs, "count": len(video_outputs)}


def _extract_publish(baggage: dict) -> dict:
    """提取发布状态"""
    merged = baggage.get("merged_P3_SLICE", {})
    return {"platforms": merged if isinstance(merged, dict) else {}, "raw": str(merged)[:2000]}


# ================ 启动 ================

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🚇 ASMAN 2.0 Web 服务器")
    print("=" * 60)
    print(f"  前端: http://localhost:8000")
    print(f"  API文档: http://localhost:8000/docs")
    print(f"  Provider: {os.getenv('LLM_PROVIDER', 'mock')}")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
