"""
ASMAN Bootstrapper
自举启动器：用户一句话 → 自动推断全部参数
"""

import random
from typing import Dict, List
from .models import TaskConfig


class Bootstrapper:
    """
    自动售票机：将模糊用户输入转化为完整任务配置
    在真实系统中，这里应接入市场数据API、读者画像、平台数据
    此处用模拟数据演示架构逻辑
    """

    # 模拟市场数据
    HOT_GENRES = ["玄幻", "都市", "科幻", "悬疑", "历史", "仙侠"]
    PLATFORMS = {
        "起点": {"roi": 0.85, "audience": "男性向", "optimal_chapters": 300},
        "晋江": {"roi": 0.78, "audience": "女性向", "optimal_chapters": 80},
        "番茄": {"roi": 0.90, "audience": "泛读者", "optimal_chapters": 200},
        "七猫": {"roi": 0.72, "audience": "下沉市场", "optimal_chapters": 150}
    }
    STYLES = {
        "玄幻": ["热血升级流", "废柴逆袭", "系统流", "无敌流"],
        "都市": ["神医", "兵王", "重生", "神豪"],
        "科幻": ["星际穿越", "末世生存", "机甲", "高武"],
        "悬疑": ["刑侦", "盗墓", "无限流", "规则怪谈"]
    }

    async def bootstrap(self, user_input: str) -> TaskConfig:
        """主入口：模糊输入 → 完整配置"""

        # 第一层：意图解析
        intent = self._parse_intent(user_input)

        # 第二层：如果意图模糊，自治推断
        if intent["vagueness"] > 0.5:
            inferred = await self._inference_engine(intent)
        else:
            inferred = intent

        # 第三层：参数生成
        config = await self._generate_config(inferred, user_input)

        return config

    def _parse_intent(self, user_input: str) -> Dict:
        """解析用户意图"""
        user_input = user_input.lower()

        # 检测关键词
        has_novel = any(k in user_input for k in ["小说", "书", "文", "故事"])
        has_video = any(k in user_input for k in ["视频", "短视频", "动画", "漫画"])
        has_hot = any(k in user_input for k in ["火", "爆", "热", "赚钱", "流量"])

        # 检测题材
        detected_genre = None
        for genre in self.HOT_GENRES:
            if genre in user_input:
                detected_genre = genre
                break

        vagueness = 0.0
        if not detected_genre:
            vagueness += 0.3
        if not has_video and not has_novel:
            vagueness += 0.4
        if has_hot:
            vagueness += 0.1  # "能火"很模糊

        return {
            "action": "create_novel",
            "has_novel": has_novel,
            "has_video": has_video,
            "detected_genre": detected_genre,
            "vagueness": min(vagueness, 1.0),
            "user_input": user_input
        }

    async def _inference_engine(self, intent: Dict) -> Dict:
        """
        自治推断引擎：不追问用户，用数据自己决定
        真实系统应接入：市场数据API、平台榜单、读者画像
        """
        # 模拟：选择当前热度最高的题材
        if not intent["detected_genre"]:
            # 模拟市场分析结果
            intent["detected_genre"] = random.choice(self.HOT_GENRES[:3])

        # 模拟：选择ROI最高的平台组合
        sorted_platforms = sorted(
            self.PLATFORMS.items(),
            key=lambda x: x[1]["roi"],
            reverse=True
        )

        # 选择前2个平台
        selected_platforms = [p[0] for p in sorted_platforms[:2]]

        # 模拟：根据题材选风格
        genre = intent["detected_genre"]
        style = random.choice(self.STYLES.get(genre, ["经典"]))

        # 模拟：决定是否要视频
        need_video = intent.get("has_video", False) or True  # 默认都做视频

        return {
            **intent,
            "inferred_genre": genre,
            "inferred_platforms": selected_platforms,
            "inferred_style": style,
            "inferred_video": need_video,
            "inferred_chapters": self.PLATFORMS[selected_platforms[0]]["optimal_chapters"]
        }

    async def _generate_config(self, inferred: Dict, user_input: str) -> TaskConfig:
        """生成最终配置"""
        genre = inferred.get("inferred_genre") or inferred.get("detected_genre") or "玄幻"
        platforms = inferred.get("inferred_platforms", ["起点", "番茄"])
        style = inferred.get("inferred_style", "热血升级流")
        chapters = inferred.get("inferred_chapters", 100)
        need_video = inferred.get("inferred_video", True)

        # 自动生成标题
        title = self._generate_title(genre, style)

        return TaskConfig(
            title=title,
            genre=genre,
            chapters=min(chapters, 50),  # Demo限制50章
            word_count_per_chapter=3000,
            target_platforms=platforms,
            style=style,
            need_video=need_video,
            quality_threshold=0.85,
            max_retry=3,
            timeout_per_task=300,
            user_input=user_input
        )

    def _generate_title(self, genre: str, style: str) -> str:
        """自动生成标题"""
        templates = {
            "玄幻": ["万古", "九天", "苍穹", "神域", "至尊"],
            "都市": ["都市", "重生", "神医", "兵王", "神豪"],
            "科幻": ["星际", "末日", "机甲", "高武", "穿越"],
            "悬疑": ["诡秘", "刑侦", "盗墓", "规则", "无限"]
        }
        prefixes = templates.get(genre, ["传奇"])
        suffixes = ["之主", "传说", "纪元", "崛起", "征途"]
        return f"{random.choice(prefixes)}{random.choice(suffixes)}"
