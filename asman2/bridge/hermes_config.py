"""
ASMAN-Hermes Bridge Config
Hermes Profile Worker 配置映射
每个地铁站点 = 一个 Hermes Profile Worker

优化策略：
- 简单解析/分类任务 → deepseek-v4-flash (快、便宜)
- 创意写作/分析任务 → deepseek-v4-pro (质量优先)
- token 按实际需求设定，避免过度生成导致超时
"""

from typing import Dict, Any


class HermesProfile:
    """Hermes Profile 定义"""
    def __init__(self, name: str, system_prompt: str, model: str = "deepseek-v4-pro",
                 temperature: float = 0.7, max_tokens: int = 2000,
                 skills: list = None, constraints: list = None):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.skills = skills or []
        self.constraints = constraints or []


# 地铁站点 → Hermes Profile 映射
HERMES_PROFILES = {
    # ============ 1号线 灵感线 ============
    "S1": HermesProfile(
        name="intent_parser",
        system_prompt="解析用户的创作需求，输出JSON: {genre, style, target_audience, tone, key_elements}。简洁准确，不要额外解释。",
        model="deepseek-v4-flash",
        temperature=0.3,
        max_tokens=500,
        skills=["intent_extraction"],
        constraints=["output_json_only", "no_extra_text"]
    ),
    "S2": HermesProfile(
        name="brainstorm_agent",
        system_prompt="基于需求生成世界观、主角设定、核心冲突。各200字内，创意新颖。",
        model="deepseek-v4-pro",
        temperature=0.9,
        max_tokens=1500,
        skills=["world_building", "character_design", "plot_hooks"],
        constraints=["within_200words_each"]
    ),

    # ============ 2号线 参考线 ============
    "R1": HermesProfile(
        name="research_collector",
        system_prompt="列举5个同类热门小说的核心元素（金手指类型、世界观特色、爽点模式）。每条50字以内。",
        model="deepseek-v4-pro",
        temperature=0.5,
        max_tokens=1000,
        skills=["trend_analysis"],
        constraints=["list_5_items", "concise"]
    ),
    "R2": HermesProfile(
        name="research_dedup",
        system_prompt="对输入的素材去重分类，合并相似项，输出结构化标签列表。",
        model="deepseek-v4-flash",
        temperature=0.3,
        max_tokens=800,
        skills=["deduplication", "tagging"],
        constraints=["output_tags_only"]
    ),
    "R3": HermesProfile(
        name="research_analyzer",
        system_prompt="基于素材推荐3个最适合的标签组合策略，每个30字说明理由。",
        model="deepseek-v4-pro",
        temperature=0.6,
        max_tokens=600,
        skills=["tag_analysis", "competitive_analysis"],
        constraints=["3_recommendations"]
    ),

    # ============ 3号线 创作线 ============
    "W1": HermesProfile(
        name="outline_builder",
        system_prompt="构建3章小说大纲。每章一行：章号|标题|核心情节(20字)。格式紧凑。",
        model="deepseek-v4-pro",
        temperature=0.7,
        max_tokens=800,
        skills=["outline_construction", "pacing_design"],
        constraints=["3_chapters", "compact_format"]
    ),
    "W2_SLICE": HermesProfile(
        name="chapter_slicer",
        system_prompt="将大纲切成3个独立写作任务，标注依赖关系。每个任务一行。",
        model="deepseek-v4-flash",
        temperature=0.3,
        max_tokens=400,
        skills=["task_decomposition"],
        constraints=["one_per_line"]
    ),
    "W3": HermesProfile(
        name="chapter_writer",
        system_prompt="根据大纲写一章1500字小说。节奏紧凑、有爽点、结尾留钩子。",
        model="deepseek-v4-pro",
        temperature=0.8,
        max_tokens=3000,
        skills=["prose_writing", "dialogue", "action_scenes"],
        constraints=["~1500_chars", "end_with_hook"]
    ),
    "W4": HermesProfile(
        name="polish_editor",
        system_prompt="润色章节：删除废话、检查设定矛盾、增强爽点节奏。只输出润色后的文本。",
        model="deepseek-v4-pro",
        temperature=0.4,
        max_tokens=2000,
        skills=["grammar_check", "style_enhancement"],
        constraints=["fix_only", "preserve_plot"]
    ),

    # ============ 4号线 发布线 ============
    "P1": HermesProfile(
        name="format_designer",
        system_prompt="生成Markdown排版方案：章节标题格式、分隔符、元数据模板。100字内。",
        model="deepseek-v4-flash",
        temperature=0.3,
        max_tokens=500,
        skills=["typesetting"],
        constraints=["markdown_format"]
    ),
    "P2": HermesProfile(
        name="cover_designer",
        system_prompt="生成小说封面提示词：包含画风、色调、核心元素、排版建议。80字内。",
        model="deepseek-v4-pro",
        temperature=0.9,
        max_tokens=400,
        skills=["cover_design"],
        constraints=["concise_prompt"]
    ),
    "P3_SLICE": HermesProfile(
        name="platform_adapter",
        system_prompt="生成多平台发布适配配置：起点/番茄/七猫各自简介(50字)+标签。",
        model="deepseek-v4-flash",
        temperature=0.4,
        max_tokens=800,
        skills=["platform_optimization"],
        constraints=["per_platform_setting"]
    ),

    # ============ 5号线 剧本线 ============
    "D1": HermesProfile(
        name="script_adapter",
        system_prompt="将小说前3章改编为短剧剧本：标注场景/对白/镜头方向。",
        model="deepseek-v4-pro",
        temperature=0.7,
        max_tokens=2000,
        skills=["scriptwriting", "scene_extraction"],
        constraints=["scene_shot_dialogue_format"]
    ),
    "D2": HermesProfile(
        name="dialogue_writer",
        system_prompt="为剧本角色写3个高光对话场景，保持声线一致，适合短视频(30秒内)。",
        model="deepseek-v4-pro",
        temperature=0.8,
        max_tokens=1000,
        skills=["dialogue_writing"],
        constraints=["30sec_scenes", "voice_consistency"]
    ),
    "D3_SLICE": HermesProfile(
        name="scene_slicer",
        system_prompt="将剧本切成独立拍摄分镜，每个分镜标注：镜号/景别/时长/内容。",
        model="deepseek-v4-flash",
        temperature=0.3,
        max_tokens=1000,
        skills=["storyboard_decomposition"],
        constraints=["numbered_shots"]
    ),

    # ============ 6号线 视频线 ============
    "V1": HermesProfile(
        name="video_storyboard",
        system_prompt="将3个分镜转为AI视频生成提示词(中文)，每个含画风/运镜/光影描述。",
        model="deepseek-v4-pro",
        temperature=0.8,
        max_tokens=1000,
        skills=["video_prompting"],
        constraints=["3_prompts", "zh_cn"]
    ),
    "V2": HermesProfile(
        name="voice_generator",
        system_prompt="为3个角色生成配音配置：性别|年龄感|语速|情感基调。",
        model="deepseek-v4-pro",
        temperature=0.6,
        max_tokens=500,
        skills=["voice_casting"],
        constraints=["3_characters"]
    ),
    "V3": HermesProfile(
        name="video_composer",
        system_prompt="给出视频合成方案：分镜顺序、转场类型、BGM建议、字幕样式。",
        model="deepseek-v4-pro",
        temperature=0.4,
        max_tokens=1000,
        skills=["video_editing"],
        constraints=["composition_plan"]
    ),
    "V4": HermesProfile(
        name="distributor",
        system_prompt="生成3个平台(抖音/B站/小红书)的视频发布文案，各含标题+话题标签。50字内。",
        model="deepseek-v4-flash",
        temperature=0.5,
        max_tokens=600,
        skills=["copywriting"],
        constraints=["3_platforms", "short_copy"]
    ),
}


def get_profile(station_id: str) -> HermesProfile:
    """获取站点对应的 Hermes Profile"""
    return HERMES_PROFILES.get(station_id, HERMES_PROFILES.get("S1"))
