"""小说创作示例：自举器（模糊输入 → 完整 TaskConfig）

业务参数（题材/章节/平台等）统一写入 TaskConfig.params。
真实系统应接入市场数据 API / 平台榜单 / 读者画像，此处用模拟数据演示。
"""

import random
from typing import Dict, List

from asman.core.models import TaskConfig


class NovelBootstrapper:
    HOT_GENRES = ["玄幻", "都市", "科幻", "悬疑", "历史", "仙侠"]
    PLATFORMS = {
        "起点": {"roi": 0.85, "audience": "男性向", "optimal_chapters": 300},
        "晋江": {"roi": 0.78, "audience": "女性向", "optimal_chapters": 80},
        "番茄": {"roi": 0.90, "audience": "泛读者", "optimal_chapters": 200},
        "七猫": {"roi": 0.72, "audience": "下沉市场", "optimal_chapters": 150},
    }
    STYLES = {
        "玄幻": ["热血升级流", "废柴逆袭", "系统流", "无敌流"],
        "都市": ["神医", "兵王", "重生", "神豪"],
        "科幻": ["星际穿越", "末世生存", "机甲", "高武"],
        "悬疑": ["刑侦", "盗墓", "无限流", "规则怪谈"],
    }

    async def bootstrap(self, user_input: str) -> TaskConfig:
        intent = self._parse_intent(user_input)
        inferred = await self._inference_engine(intent) if intent["vagueness"] > 0.5 else intent
        return await self._generate_config(inferred, user_input)

    def _parse_intent(self, user_input: str) -> Dict:
        user_input = user_input.lower()
        has_novel = any(k in user_input for k in ["小说", "书", "文", "故事"])
        has_video = any(k in user_input for k in ["视频", "短视频", "动画", "漫画"])
        has_hot = any(k in user_input for k in ["火", "爆", "热", "赚钱", "流量"])

        detected_genre = next((g for g in self.HOT_GENRES if g in user_input), None)

        vagueness = 0.0
        if not detected_genre:
            vagueness += 0.3
        if not has_video and not has_novel:
            vagueness += 0.4
        if has_hot:
            vagueness += 0.1

        return {"action": "create_novel", "has_novel": has_novel, "has_video": has_video,
                "detected_genre": detected_genre, "vagueness": min(vagueness, 1.0),
                "user_input": user_input}

    async def _inference_engine(self, intent: Dict) -> Dict:
        if not intent["detected_genre"]:
            intent["detected_genre"] = random.choice(self.HOT_GENRES[:3])

        sorted_platforms = sorted(self.PLATFORMS.items(), key=lambda x: x[1]["roi"], reverse=True)
        selected_platforms = [p[0] for p in sorted_platforms[:2]]

        genre = intent["detected_genre"]
        style = random.choice(self.STYLES.get(genre, ["经典"]))
        need_video = intent.get("has_video", False) or True

        return {**intent, "inferred_genre": genre, "inferred_platforms": selected_platforms,
                "inferred_style": style, "inferred_video": need_video,
                "inferred_chapters": self.PLATFORMS[selected_platforms[0]]["optimal_chapters"]}

    async def _generate_config(self, inferred: Dict, user_input: str) -> TaskConfig:
        genre = inferred.get("inferred_genre") or inferred.get("detected_genre") or "玄幻"
        platforms = inferred.get("inferred_platforms", ["起点", "番茄"])
        style = inferred.get("inferred_style", "热血升级流")
        chapters = inferred.get("inferred_chapters", 100)
        need_video = inferred.get("inferred_video", True)
        title = self._generate_title(genre, style)

        return TaskConfig(
            title=title,
            user_input=user_input,
            quality_threshold=0.85,
            max_retry=3,
            timeout_per_task=300,
            params={
                "genre": genre,
                "chapters": min(chapters, 3),  # Demo 限制 3 章（快速验证切片并行）
                "word_count_per_chapter": 3000,
                "target_platforms": platforms,
                "style": style,
                "need_video": need_video,
            },
        )

    def _generate_title(self, genre: str, style: str) -> str:
        templates = {
            "玄幻": ["万古", "九天", "苍穹", "神域", "至尊"],
            "都市": ["都市", "重生", "神医", "兵王", "神豪"],
            "科幻": ["星际", "末日", "机甲", "高武", "穿越"],
            "悬疑": ["诡秘", "刑侦", "盗墓", "规则", "无限"],
        }
        prefixes = templates.get(genre, ["传奇"])
        suffixes = ["之主", "传说", "纪元", "崛起", "征途"]
        return f"{random.choice(prefixes)}{random.choice(suffixes)}"
