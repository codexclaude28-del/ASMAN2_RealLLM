"""LLM-as-Judge 单元测试"""

import asyncio

from asman.judge.judge import LLMJudge


def test_parse_json_block():
    judge = LLMJudge()
    parsed = judge._parse('```json\n{"coherence": 0.8, "passed": true}\n```')
    assert parsed["coherence"] == 0.8


def test_parse_plain_json():
    judge = LLMJudge()
    parsed = judge._parse('{"creativity": 0.9}')
    assert parsed["creativity"] == 0.9


def test_parse_invalid():
    judge = LLMJudge()
    assert judge._parse("not json") == {}


def test_to_scores_clamp():
    judge = LLMJudge()
    scores = judge._to_scores({"coherence": 1.5, "creativity": -0.2, "consistency": 0.5,
                               "grammar": 0.6, "engagement": 0.7})
    assert scores.coherence == 1.0   # clamp 上限
    assert scores.creativity == 0.0  # clamp 下限
    assert abs(scores.consistency - 0.5) < 1e-9


def test_heuristic_evaluate():
    judge = LLMJudge()
    scores = judge._heuristic_evaluate({"x": 1})
    assert scores.average() >= 0.85  # 非空产出稳定通过


def test_evaluate_mock():
    judge = LLMJudge()  # 默认 mock provider
    scores = asyncio.run(judge.evaluate({"content": "hello"}, {}, "W3"))
    assert 0 <= scores.average() <= 1.0
