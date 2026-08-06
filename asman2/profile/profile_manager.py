"""ASMAN 2.0 Profile Manager - Agent Profile隔离"""

from typing import Dict, Any


class ProfileManager:
    PROFILES = {
        "玄幻": {
            "system_prompt": "你是一位资深玄幻小说作家。擅长构建宏大的修真世界观，描写热血升级、废柴逆袭的情节。注意：使用东方玄幻术语，避免科幻元素。",
            "tone": "热血、霸气",
            "forbidden_words": ["飞船", "激光", "AI", "机器人"],
            "required_elements": ["境界", "灵根", "法宝", "宗门"],
        },
        "科幻": {
            "system_prompt": "你是一位硬核科幻作家。擅长构建基于科学原理的未来世界，描写星际文明、技术奇点。注意：保持科学严谨性，避免玄幻元素。",
            "tone": "理性、宏大",
            "forbidden_words": ["修仙", "灵气", "法宝", "宗门"],
            "required_elements": ["科技", "星际", "文明", "物理"],
        },
        "都市": {
            "system_prompt": "你是一位都市小说作家。擅长描写现代都市生活、职场斗争、情感纠葛。注意：贴近现实，避免超自然元素。",
            "tone": "现实、细腻",
            "forbidden_words": ["魔法", "斗气", "飞剑"],
            "required_elements": ["职场", "情感", "都市", "生活"],
        },
        "悬疑": {
            "system_prompt": "你是一位悬疑推理作家。擅长构建复杂的谜题、反转剧情、心理描写。注意：逻辑严密，伏笔回收。",
            "tone": "紧张、烧脑",
            "forbidden_words": ["系统", "签到", "无敌"],
            "required_elements": ["谜题", "线索", "反转", "推理"],
        },
    }

    def __init__(self):
        self.active_profiles: Dict[str, Dict] = {}

    def get_profile(self, genre: str) -> Dict[str, Any]:
        return self.PROFILES.get(genre, self.PROFILES["玄幻"])

    def apply_profile(self, agent, genre: str):
        profile = self.get_profile(genre)
        agent.system_prompt = profile["system_prompt"]
        agent.tone = profile["tone"]
        agent.forbidden_words = profile["forbidden_words"]
        agent.required_elements = profile["required_elements"]
        return agent

    def validate_output(self, output: str, genre: str) -> Dict:
        profile = self.get_profile(genre)
        violations = []
        for word in profile["forbidden_words"]:
            if word in output:
                violations.append(f"使用了禁用词: {word}")
        missing = []
        for elem in profile["required_elements"]:
            if elem not in output:
                missing.append(f"缺少必要元素: {elem}")
        return {
            "valid": len(violations) == 0,
            "violations": violations,
            "missing_elements": missing
        }
