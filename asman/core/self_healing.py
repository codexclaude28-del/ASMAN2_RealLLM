"""
ASMAN Self-Healing Scheduler
自愈调度器：系统自己发现问题、自己修复
"""

import asyncio
import time
from typing import Dict, List, Optional, Any
from .models import Passenger, PassengerStatus


class AgentHealth:
    """Agent健康状态"""
    def __init__(self, agent_id: str, capability: str):
        self.agent_id = agent_id
        self.capability = capability
        self.healthy = True
        self.failure_count = 0
        self.last_heartbeat = time.time()
        self.total_requests = 0
        self.success_requests = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.success_requests / self.total_requests

    def is_healthy(self) -> bool:
        if not self.healthy:
            return False
        if time.time() - self.last_heartbeat > 30:  # 30秒无心跳
            return False
        if self.failure_count > 5:
            return False
        return True


class SelfHealingScheduler:
    """
    自愈调度器
    每10秒执行一次全系统体检
    """

    def __init__(self, network, occ, dispatcher):
        self.network = network
        self.occ = occ
        self.dispatcher = dispatcher
        self.agent_health: Dict[str, AgentHealth] = {}
        self.running = False
        self.check_interval = 10

    def register_agent(self, agent_id: str, capability: str):
        self.agent_health[agent_id] = AgentHealth(agent_id, capability)

    async def heartbeat(self, agent_id: str, success: bool = True):
        """Agent心跳上报"""
        health = self.agent_health.get(agent_id)
        if health:
            health.last_heartbeat = time.time()
            health.total_requests += 1
            if success:
                health.success_requests += 1
                health.failure_count = 0
            else:
                health.failure_count += 1

    async def health_check_loop(self):
        """健康检查主循环"""
        self.running = True
        while self.running:
            await self._check_all()
            await asyncio.sleep(self.check_interval)

    async def _check_all(self):
        """执行全系统体检"""
        # 检查1：Agent健康
        for agent_id, health in list(self.agent_health.items()):
            if not health.is_healthy():
                await self._heal_agent(agent_id, health)

        # 检查2：子乘客重组追踪
        for station in self.network.stations.values():
            if hasattr(station, 'parent_tracking'):
                await self._check_stalled_tracking(station)

        # 检查3：乘客超时
        for passenger in list(self.occ.registry.values()):
            if passenger.status == PassengerStatus.PROCESSING:
                if time.time() - passenger.created_at > passenger.ticket.config.timeout_per_task:
                    await self._handle_timeout_passenger(passenger)

        # 检查4：Hub拥堵
        for hub in self.network.hubs.values():
            if hub.platform.get_waiting_count() > 50:
                await self._heal_congestion(hub)

    async def _heal_agent(self, agent_id: str, health: AgentHealth):
        """Agent故障自愈"""
        # 策略1：标记不健康，触发切换
        health.healthy = False

        # 找到同能力的备用Agent
        backup = self._find_backup(health.capability, exclude=agent_id)
        if backup:
            await self.dispatcher.switch_agent(agent_id, backup)
            health.healthy = True
            health.failure_count = 0
        else:
            # 策略2：降级处理
            await self.dispatcher.degrade_agent(agent_id)

    def _find_backup(self, capability: str, exclude: str) -> Optional[str]:
        """查找同能力备用Agent"""
        for agent_id, health in self.agent_health.items():
            if agent_id != exclude and health.capability == capability and health.is_healthy():
                return agent_id
        return None

    async def _check_stalled_tracking(self, station):
        """检查卡住的切片追踪"""
        if not hasattr(station, 'parent_tracking'):
            return

        for parent_id, tracking in list(station.parent_tracking.items()):
            # 检查是否超时（5分钟）
            if time.time() - tracking.get("start_time", 0) > 300:
                missing = tracking["total"] - tracking["arrived"]
                for _ in range(missing):
                    # 用兜底Agent补全
                    fallback_result = await self._fallback_generate(
                        tracking["parent_passenger"].baggage
                    )
                    tracking["results"].append(fallback_result)
                    tracking["arrived"] += 1

                # 强制重组
                if tracking["arrived"] >= tracking["total"]:
                    await station.reassemble(parent_id)

    async def _fallback_generate(self, context: Dict) -> Dict:
        """兜底生成：用轻量级策略补全缺失部分"""
        return {
            "fallback": True,
            "content": "[兜底生成内容]",
            "quality": "acceptable"
        }

    async def _handle_timeout_passenger(self, passenger: Passenger):
        """处理超时乘客"""
        passenger.status = PassengerStatus.FAILED
        passenger.baggage["timeout_error"] = f"Task timed out after {passenger.ticket.config.timeout_per_task}s"

        # 如果是子乘客，通知切片站
        if passenger.is_sub and passenger.parent_id:
            # 强制标记为已到达（用兜底结果）
            for station in self.network.stations.values():
                if hasattr(station, 'on_sub_passenger_arrive'):
                    await station.on_sub_passenger_arrive(passenger)

    async def _heal_congestion(self, hub):
        """缓解Hub拥堵"""
        # 增加该Hub所在线路的列车频率（Hub 即 Station，直接取 line_id）
        line = self.network.get_line(hub.line_id)
        if line:
            await self.dispatcher.urgent_dispatch(line.line_id)
