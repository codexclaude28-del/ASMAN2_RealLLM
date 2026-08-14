"""小说创作示例 Agent —— 注册到通用引擎

展示业务如何接入 MetroEngine：实现 Agent 子类并 register_agent。
业务字段（题材/章节数/平台等）统一从 TaskConfig.params 读取。
"""

import random
from typing import Dict, Any, List

from asman.agents.base import Agent
from asman.registry import register_agent


def _params(input_data: Dict) -> Dict:
    config = input_data.get("config", {})
    params = getattr(config, "params", {}) or {}
    return params if isinstance(params, dict) else {}


class IntentParserAgent(Agent):
    """S1: 需求解析"""
    def __init__(self):
        super().__init__("需求解析", "intent_parsing")

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        params = _params(input_data)
        return {
            "parsed_requirements": {
                "genre": params.get("genre", ""),
                "style": params.get("style", ""),
                "target_audience": "18-35岁男性",
                "tone": "热血",
                "key_elements": ["升级", "打脸", "逆袭"],
            },
            "confidence": 0.92,
        }


class BrainstormAgent(Agent):
    """S2: 脑暴发散"""
    def __init__(self):
        super().__init__("脑暴发散", "brainstorming")

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        return {
            "world_building": {"setting": "修真世界，灵气复苏", "power_system": "九重天境界", "unique_mechanic": "签到系统"},
            "characters": [
                {"name": "林凡", "role": "主角", "trait": "废柴逆袭"},
                {"name": "苏清雪", "role": "女主", "trait": "高冷仙子"},
                {"name": "王腾", "role": "反派", "trait": "世家公子"},
            ],
            "plot_hooks": ["开局被退婚", "获得神秘系统", "宗门大比"],
            "creativity_score": random.uniform(0.8, 0.95),
        }


class ResearchAgent(Agent):
    """R1-R3: 参考研究"""
    def __init__(self, name: str, sub_type: str):
        super().__init__(name, "research")
        self.sub_type = sub_type

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        if self.sub_type == "collect":
            return {"collected_sources": 150, "categories": ["世界观", "人设", "剧情"]}
        elif self.sub_type == "dedup":
            return {"unique_sources": 89, "duplicates_removed": 61}
        else:
            return {"hot_tags": ["系统流", "签到", "无敌"], "trend_score": 0.88}


class OutlineAgent(Agent):
    """W1: 大纲构建"""
    def __init__(self):
        super().__init__("大纲构建", "outline")

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        chapters = _params(input_data).get("chapters", 3)

        titles = ["第一章：废物", "第二章：崛起", "第三章：扬名"]
        summaries = ["主角被退婚，获得神秘系统", "主角突破境界，打脸宗门", "主角参加大比，一战成名"]
        outline = []
        for i in range(1, chapters + 1):
            idx = min(i - 1, len(titles) - 1)
            outline.append({"chapter": i, "title": titles[idx], "summary": summaries[idx]})

        return {"total_chapters": chapters, "outline": outline,
                "arc_structure": ["起", "承", "转", "合"], "completeness": 0.95}


class ChapterSliceAgent(Agent):
    """W2: 章节切片"""
    def __init__(self):
        super().__init__("章节切片", "slicer")

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        return {}

    async def slice(self, input_data: Dict) -> List[Dict]:
        outline = input_data.get("output_W1", {}).get("outline", [])
        if not outline:
            params = _params(input_data)
            ch_count = params.get("chapters", 3)
            outline = [{"chapter": i, "title": f"第{i}章", "summary": f"第{i}章内容"}
                       for i in range(1, ch_count + 1)]
        params = _params(input_data)
        slices = []
        for chapter in outline:
            slices.append({
                "id": f"ch{chapter['chapter']}",
                "task": f"写作{chapter['title']}",
                "context": chapter,
                "word_count": params.get("word_count_per_chapter", 3000),
            })
        return slices

    async def merge(self, sub_results: List[Dict]) -> Dict:
        chapters = []
        for result in sorted(sub_results, key=lambda x: str(x.get("slice_id", ""))):
            output = result.get("output", "")
            if isinstance(output, dict):
                output = output.get("content", str(output))
            chapters.append(str(output))
        return {"full_novel": "\n\n".join(chapters),
                "total_chapters": len(chapters), "merged_from": len(sub_results)}


class ChapterWriteAgent(Agent):
    """W3: 章节写作"""
    def __init__(self):
        super().__init__("章节写作", "writer")

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        slice_task = input_data.get("slice_task", {})
        chapter_info = slice_task.get("context", {})
        word_count = slice_task.get("word_count", 3000)

        content = f"【{chapter_info.get('title', '章节')}】\n"
        content += f"{chapter_info.get('summary', '')}\n"
        content += f"[正文内容约{word_count}字...]"

        return {"chapter_num": chapter_info.get("chapter", 0),
                "title": chapter_info.get("title", ""),
                "content": content, "word_count": word_count,
                "quality_estimate": random.uniform(0.82, 0.96)}


class PolishAgent(Agent):
    """W4: 润色审校"""
    def __init__(self):
        super().__init__("润色审校", "polish")

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        chapter = input_data.get("output_W3", {})
        return {"polished_content": f"[润色后]{chapter.get('content', '')}",
                "grammar_fixes": random.randint(3, 15),
                "style_enhancements": random.randint(5, 20),
                "final_quality": random.uniform(0.85, 0.98)}


class PublishAgent(Agent):
    """P1-P2: 发布相关"""
    def __init__(self, name: str, sub_type: str):
        super().__init__(name, "publish")
        self.sub_type = sub_type

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        if self.sub_type == "format":
            return {"format": "epub/mobi/txt", "chapters_indexed": True}
        else:
            return {"cover_url": "https://cdn.example.com/cover.jpg", "style": "玄幻风"}


class PlatformSliceAgent(Agent):
    """P3: 平台切片"""
    def __init__(self):
        super().__init__("平台切片", "slicer")

    async def slice(self, input_data: Dict) -> List[Dict]:
        platforms = _params(input_data).get("target_platforms", [])
        novel = input_data.get("merged_W2_SLICE", {})
        return [{"id": p, "task": f"适配{p}格式",
                 "context": {"platform": p, "novel": novel}} for p in platforms]

    async def merge(self, sub_results: List[Dict]) -> Dict:
        status = {}
        for result in sub_results:
            platform = result.get("slice_id", "unknown")
            status[platform] = {"published": True,
                                "url": f"https://{platform}.com/novel/12345",
                                "timestamp": "2026-08-01"}
        return {"publish_status": status}


class ScriptAgent(Agent):
    """D1-D2: 剧本改编"""
    def __init__(self, name: str, sub_type: str):
        super().__init__(name, "script")
        self.sub_type = sub_type

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        if self.sub_type == "adapt":
            return {"script_structure": "三幕式", "scenes": 30, "adaptation_rate": 0.85}
        else:
            return {"dialogues": 120, "character_voice_consistency": 0.92}


class SceneSliceAgent(Agent):
    """D3: 分镜切片"""
    def __init__(self):
        super().__init__("分镜切片", "slicer")

    async def slice(self, input_data: Dict) -> List[Dict]:
        scenes_data = input_data.get("output_D1", {}).get("scenes", 3)
        if isinstance(scenes_data, list):
            scenes_count = len(scenes_data)
        elif isinstance(scenes_data, dict):
            scenes_count = len(scenes_data)
        else:
            scenes_count = int(scenes_data) if scenes_data else 3
        return [{"id": f"scene{i}", "task": f"生成分镜{i}",
                 "context": {"scene_num": i, "duration": 30}}
                for i in range(1, scenes_count + 1)]

    async def merge(self, sub_results: List[Dict]) -> Dict:
        return {"total_scenes": len(sub_results),
                "scene_sequence": [str(r.get("slice_id", "")) for r in sub_results],
                "total_duration": len(sub_results) * 30}


class VideoAgent(Agent):
    """V1-V4: 视频生成"""
    def __init__(self, name: str, sub_type: str):
        super().__init__(name, "video")
        self.sub_type = sub_type

    async def execute(self, input_data: Dict, passenger_id: str) -> Dict:
        await super().execute(input_data, passenger_id)
        if self.sub_type == "storyboard":
            return {"video_segments": 30, "resolution": "1080p"}
        elif self.sub_type == "voice":
            return {"voice_clips": 30, "tts_model": "GPT-SoVITS"}
        elif self.sub_type == "compose":
            return {"final_video": "video.mp4", "duration": 900}
        else:
            return {"platforms": ["抖音", "B站", "快手"], "views_estimate": 100000}


# ============ 注册到引擎 ============

def register_all():
    register_agent("intent_parser", IntentParserAgent)
    register_agent("brainstorm", BrainstormAgent)
    register_agent("research_collect", lambda: ResearchAgent("全网采集", "collect"))
    register_agent("research_dedup", lambda: ResearchAgent("去重整理", "dedup"))
    register_agent("research_analyze", lambda: ResearchAgent("标签分析", "analyze"))
    register_agent("outline", OutlineAgent)
    register_agent("chapter_slice", ChapterSliceAgent)
    register_agent("chapter_write", ChapterWriteAgent)
    register_agent("polish", PolishAgent)
    register_agent("publish_format", lambda: PublishAgent("排版生成", "format"))
    register_agent("publish_cover", lambda: PublishAgent("封面设计", "cover"))
    register_agent("platform_slice", PlatformSliceAgent)
    register_agent("script_adapt", lambda: ScriptAgent("结构改编", "adapt"))
    register_agent("script_dialogue", lambda: ScriptAgent("对白生成", "dialogue"))
    register_agent("scene_slice", SceneSliceAgent)
    register_agent("video_storyboard", lambda: VideoAgent("分镜视频", "storyboard"))
    register_agent("video_voice", lambda: VideoAgent("AI配音", "voice"))
    register_agent("video_compose", lambda: VideoAgent("视频合成", "compose"))
    register_agent("video_distribute", lambda: VideoAgent("多平台投放", "distribute"))
