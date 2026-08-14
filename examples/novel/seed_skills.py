"""ASMAN2 Skill 库种子数据
预置一批网文创作 Skill，覆盖 6 条创作线的核心能力。
运行: python seed_skills.py
"""

import sys
import os
from pathlib import Path

# Windows UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from asman.skill.skill_library import SkillLibrary


def seed(lib: SkillLibrary):
    """预置创作 Skill"""

    # ============ 通用写作能力 ============
    universal = [
        {
            "capability": "prose_writing",
            "profile": "玄幻",
            "description": "玄幻小说章节写作 Skill —— 节奏紧凑、画面感强、爽点密集",
            "prompt": (
                "你是一位资深玄幻小说作家。写作要求：\n"
                "1. 开篇300字必须有冲突或悬念\n"
                "2. 每2000字插入一个小爽点（突破/打脸/获得宝物）\n"
                "3. 对话占比30%-40%，避免大段叙述\n"
                "4. 修炼体系术语前后一致\n"
                "5. 章节结尾留钩子（hook）"
            ),
            "tags": ["玄幻", "写作", "爽文", "节奏"],
            "success_rate": 0.92,
            "avg_score": 0.88,
        },
        {
            "capability": "prose_writing",
            "profile": "都市",
            "description": "都市小说写作 Skill —— 真实感强、商战/职场逻辑严密",
            "prompt": (
                "你是一位都市题材专业作家。写作要求：\n"
                "1. 行业细节必须真实（金融/互联网/医疗等）\n"
                "2. 人物对话符合现实职场语境\n"
                "3. 爽点来源：逆袭/打脸/财富积累/权力获得\n"
                "4. 保持适度专业术语，但不过度艰深\n"
                "5. 每章结尾制造期待感"
            ),
            "tags": ["都市", "写作", "商战", "职场"],
            "success_rate": 0.90,
            "avg_score": 0.86,
        },
        {
            "capability": "prose_writing",
            "profile": "仙侠",
            "description": "仙侠小说写作 Skill —— 意境优美、修炼体系完整、法宝功法有诗意",
            "prompt": (
                "你是一位仙侠小说作家。写作要求：\n"
                "1. 修炼体系和境界名称保持统一\n"
                "2. 战斗描写注重意境和画面感，避免纯数值比拼\n"
                "3. 法宝功法命名遵循'功能+意境'原则\n"
                "4. 主角成长线清晰，每次突破伴随心境变化\n"
                "5. 仙侠世界的'仙气'和'人情味'并重"
            ),
            "tags": ["仙侠", "写作", "修炼", "意境"],
            "success_rate": 0.88,
            "avg_score": 0.85,
        },
    ]

    # ============ 大纲构建 ============
    outline_skills = [
        {
            "capability": "outline_construction",
            "profile": "热血升级流",
            "description": "热血升级流大纲构建 —— 经典'废柴逆袭'结构",
            "prompt": (
                "构建热血升级流小说大纲：\n"
                "1. 第一卷：废柴开局 → 意外获得金手指 → 初露锋芒\n"
                "2. 第二卷：进入宗门/学院 → 打脸挑衅者 → 建立班底\n"
                "3. 第三卷：外出历练 → 秘境探险 → 实力突破\n"
                "4. 第四卷：宗门大比/势力争霸 → 扬名立万\n"
                "5. 第五卷及之后：更大世界 → 身世之谜 → 终极对决\n"
                "每卷控制在20-30章，卷末设大高潮"
            ),
            "tags": ["大纲", "升级流", "结构", "节奏"],
            "success_rate": 0.95,
            "avg_score": 0.91,
        },
        {
            "capability": "outline_construction",
            "profile": "悬疑推理",
            "description": "悬疑推理大纲构建 —— 双线叙事 + 反转设计",
            "prompt": (
                "构建悬疑推理小说大纲：\n"
                "1. 明线：主角调查案件的过程\n"
                "2. 暗线：真凶的动机和手法\n"
                "3. 每10章设一个反转点\n"
                "4. 线索分散在前80%内容中，最后20%集中收网\n"
                "5. 确保所有伏笔在结局回收"
            ),
            "tags": ["大纲", "悬疑", "推理", "反转"],
            "success_rate": 0.89,
            "avg_score": 0.87,
        },
    ]

    # ============ 角色设计 ============
    character_skills = [
        {
            "capability": "character_design",
            "profile": "通用",
            "description": "网文角色设计 Skill —— 记忆点 + 成长弧光",
            "prompt": (
                "设计网文角色时遵循：\n"
                "1. 主角：给一个独特标签（身份/性格/能力/外貌），让读者一眼记住\n"
                "2. 反派：必须有合理动机，不要纯粹'坏'\n"
                "3. 女主/男主：独立人格，有自己目标和成长线\n"
                "4. 配角团：每人一个特色能力 + 一个性格缺陷\n"
                "5. 每个角色有'高光时刻'设计（至少1次）"
            ),
            "tags": ["角色", "人设", "人物", "配角"],
            "success_rate": 0.93,
            "avg_score": 0.90,
        },
    ]

    # ============ 世界观构建 ============
    world_skills = [
        {
            "capability": "world_building",
            "profile": "通用",
            "description": "世界观构建 Skill —— 系统化架空世界设计",
            "prompt": (
                "构建架空世界观时确保：\n"
                "1. 力量体系有层级和获得条件（不能凭空变强）\n"
                "2. 经济系统自洽（货币/资源/交易逻辑）\n"
                "3. 社会组织有层级（家族/宗门/国家/联盟）\n"
                "4. 历史有重大事件作为背景（至少3个）\n"
                "5. 地理设定与剧情关联（不是纯设定，要为故事服务）"
            ),
            "tags": ["世界观", "设定", "体系", "架构"],
            "success_rate": 0.91,
            "avg_score": 0.89,
        },
    ]

    # ============ 章节切片 ============
    slice_skills = [
        {
            "capability": "task_decomposition",
            "profile": "通用",
            "description": "章节切片 Skill —— 大纲拆分为可独立写作的章节任务",
            "prompt": (
                "将大纲拆分为章节时注意：\n"
                "1. 每章有独立的'起承转合'小结构\n"
                "2. 每3-5章形成一个'小高潮周期'\n"
                "3. 标注章节间的信息依赖（伏笔/设定传递）\n"
                "4. 控制每章目标字数（3000-5000字）\n"
                "5. 为并行写作标注无依赖的章节组"
            ),
            "tags": ["切片", "拆分", "并行", "调度"],
            "success_rate": 0.94,
            "avg_score": 0.92,
        },
    ]

    # ============ 润色审校 ============
    polish_skills = [
        {
            "capability": "grammar_check",
            "profile": "通用",
            "description": "网文润色 Skill —— 节奏优化 + 爽点增强",
            "prompt": (
                "润色网文章节时检查：\n"
                "1. 删除拖沓的形容词堆砌和废话对白\n"
                "2. 检查'的得地'用法\n"
                "3. 爽点/反转处增加节奏感（短句加速）\n"
                "4. 确保角色声线前后一致\n"
                "5. 检查前后设定矛盾（人名/境界/物品）"
            ),
            "tags": ["润色", "审校", "节奏", "一致性"],
            "success_rate": 0.90,
            "avg_score": 0.87,
        },
        {
            "capability": "style_enhancement",
            "profile": "通用",
            "description": "文笔增强 Skill —— 网感 + 画面感",
            "prompt": (
                "增强网文文笔：\n"
                "1. 关键战斗/情感场景用'五感描写'（视/听/嗅/触/味）\n"
                "2. 减少被动语态，多用主动动词\n"
                "3. 适当使用'网感'表达（弹幕风吐槽/神回复式对白）\n"
                "4. 每500字至少有1个'金句'或记忆点\n"
                "5. 段落控制在3-5行，移动端阅读友好"
            ),
            "tags": ["文笔", "增强", "画面感", "网感"],
            "success_rate": 0.87,
            "avg_score": 0.85,
        },
    ]

    all_skills = universal + outline_skills + character_skills + world_skills + slice_skills + polish_skills

    count = 0
    for s in all_skills:
        try:
            skill_id = lib.store_skill(
                capability=s["capability"],
                profile=s["profile"],
                description=s["description"],
                prompt_template=s["prompt"],
                tags=s["tags"],
                success_rate=s["success_rate"],
                avg_score=s["avg_score"],
            )
            print(f"  [OK] {skill_id}")
            count += 1
        except Exception as e:
            print(f"  [FAIL] {s['capability']}/{s['profile']}: {e}")

    print(f"\n共植入 {count} 个 Skill")
    stats = lib.get_skill_stats()
    print(f"Skill 库总计: {stats['total_skills']} 个")
    if stats['avg_success_rate']:
        print(f"平均成功率: {stats['avg_success_rate']:.1%}")
    if stats['avg_score']:
        print(f"平均评分: {stats['avg_score']:.2f}")


if __name__ == "__main__":
    # 先删除旧库（如果有的话）
    db_path = os.path.join(os.path.dirname(__file__), "asman2_skills.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"已清除旧 Skill 库: {db_path}")

    lib = SkillLibrary(db_path)
    seed(lib)
