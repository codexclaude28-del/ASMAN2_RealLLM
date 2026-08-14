"""集成测试：mock 模式跑通六线全流程"""

import asyncio


async def test_full_pipeline_mock(engine):
    await engine.build_network()
    task_id = await engine.run("帮我做一本能火的玄幻小说，要有视频")

    progress = {}
    for _ in range(160):
        progress = await engine.get_progress(task_id)
        if progress["status"] == "completed":
            break
        await asyncio.sleep(0.5)

    assert progress["status"] == "completed", f"任务未完成: {progress}"

    passenger = engine.occ.get_passenger(task_id)
    # 三个切片站的产物齐全
    assert "merged_W2_SLICE" in passenger.baggage
    assert "merged_P3_SLICE" in passenger.baggage
    assert "merged_D3_SLICE" in passenger.baggage
    # 终点站已走完
    assert "V_END" in passenger.completed_stops
    # metrics 正确
    metrics = engine.get_metrics()
    assert metrics["counters"]["tasks_completed"] >= 1
    await engine.shutdown()
