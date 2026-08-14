"""LLM-as-Judge 评分输出 schema"""

# 交给 LLM 的结构化输出约束（JSON Schema）
JUDGE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "coherence": {"type": "number", "minimum": 0, "maximum": 1},
        "creativity": {"type": "number", "minimum": 0, "maximum": 1},
        "consistency": {"type": "number", "minimum": 0, "maximum": 1},
        "grammar": {"type": "number", "minimum": 0, "maximum": 1},
        "engagement": {"type": "number", "minimum": 0, "maximum": 1},
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "passed": {"type": "boolean"},
        "weakest": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "coherence", "creativity", "consistency",
        "grammar", "engagement", "score", "passed",
    ],
}

JUDGE_SYSTEM_PROMPT = """你是一个严格的产出质量评判员。根据给定的任务站点和产出内容，从五个维度打分（0 到 1）：
- coherence 连贯性
- creativity 创意性
- consistency 一致性
- grammar 文笔/语法
- engagement 吸引力

只输出一个 JSON 对象，字段为：coherence / creativity / consistency / grammar / engagement / score / passed / weakest / reasons。
score 是五个维度的平均值；passed 表示是否达到 0.85 合格线（布尔）；weakest 是最弱维度名；reasons 是 1-3 条简短理由。
不要输出任何解释或额外文本，只输出 JSON。"""
