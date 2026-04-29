"""
TimeoutReminder 和 timeout_reminder hook 的单元测试
"""

import pytest
import time
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from agentscope_agent.timeout import (
    TimeoutReminder,
    TimeoutReminderConfig,
    set_timeout_reminder,
    get_timeout_reminder,
)
from agentscope_agent.hooks.timeout_reminder import (
    create_timeout_reminder_hook,
    register_timeout_reminder_hook,
)


class TestTimeoutReminderConfig:
    """TimeoutReminderConfig 测试"""
    
    def test_default_values(self):
        """测试默认配置值"""
        config = TimeoutReminderConfig()
        assert config.enabled is True
        assert config.reminder_start == 1800.0
        assert config.reminder_interval == 300.0
        assert config.countdown_threshold == 300.0
    
    def test_custom_values(self):
        """测试自定义配置值"""
        config = TimeoutReminderConfig(
            enabled=False,
            reminder_start=600.0,
            reminder_interval=60.0,
            countdown_threshold=120.0,
        )
        assert config.enabled is False
        assert config.reminder_start == 600.0
        assert config.reminder_interval == 60.0
        assert config.countdown_threshold == 120.0


class TestTimeoutReminder:
    """TimeoutReminder 测试"""
    
    def test_basic_initialization(self):
        """测试基本初始化"""
        reminder = TimeoutReminder(run_timeout=3600)
        assert reminder.run_timeout == 3600
        assert reminder.config.enabled is True
        assert reminder._last_reminder_time is None
        assert reminder._last_round_warned is False
    
    def test_custom_config(self):
        """测试自定义配置初始化"""
        config = TimeoutReminderConfig(enabled=False)
        reminder = TimeoutReminder(run_timeout=1800, config=config)
        assert reminder.config.enabled is False
    
    def test_get_remaining_time(self):
        """测试获取剩余时间"""
        reminder = TimeoutReminder(run_timeout=100)
        remaining = reminder.get_remaining_time()
        # 刚创建，剩余时间应该接近 100 秒
        assert 99 <= remaining <= 100
    
    def test_get_elapsed_time(self):
        """测试获取已运行时间"""
        reminder = TimeoutReminder(run_timeout=100)
        elapsed = reminder.get_elapsed_time()
        # 刚创建，已运行时间应该接近 0
        assert 0 <= elapsed <= 1
    
    def test_is_expired_false(self):
        """测试未超时"""
        reminder = TimeoutReminder(run_timeout=3600)
        assert reminder.is_expired() is False
    
    def test_is_expired_true(self):
        """测试已超时"""
        reminder = TimeoutReminder(run_timeout=0)
        assert reminder.is_expired() is True
    
    def test_is_last_round_true(self):
        """测试最后一轮（剩余 < 60 秒）"""
        reminder = TimeoutReminder(run_timeout=30)
        assert reminder.is_last_round() is True
    
    def test_is_last_round_false(self):
        """测试非最后一轮（剩余 >= 60 秒）"""
        reminder = TimeoutReminder(run_timeout=120)
        assert reminder.is_last_round() is False
    
    def test_should_remind_disabled(self):
        """测试禁用时不提醒"""
        config = TimeoutReminderConfig(enabled=False)
        reminder = TimeoutReminder(run_timeout=60, config=config)
        assert reminder.should_remind_now() is False
    
    def test_should_remind_out_of_range(self):
        """测试超出提醒范围时不提醒"""
        config = TimeoutReminderConfig(reminder_start=1800)
        reminder = TimeoutReminder(run_timeout=3600, config=config)  # 剩余 1 小时
        assert reminder.should_remind_now() is False
    
    def test_should_remind_in_countdown_mode(self):
        """测试倒数模式时应该提醒"""
        config = TimeoutReminderConfig(
            reminder_start=1800,
            countdown_threshold=300,
        )
        reminder = TimeoutReminder(run_timeout=180, config=config)  # 剩余 3 分钟
        assert reminder.should_remind_now() is True
    
    def test_should_remind_in_normal_range_first_time(self):
        """测试普通范围内首次应该提醒"""
        config = TimeoutReminderConfig(
            reminder_start=1800,
            reminder_interval=300,
            countdown_threshold=300,
        )
        reminder = TimeoutReminder(run_timeout=1500, config=config)  # 剩余 25 分钟
        assert reminder.should_remind_now() is True
    
    def test_should_remind_in_normal_range_interval_check(self):
        """测试普通范围内间隔检查"""
        config = TimeoutReminderConfig(
            reminder_start=1800,
            reminder_interval=300,
            countdown_threshold=300,
        )
        reminder = TimeoutReminder(run_timeout=1500, config=config)
        
        # 首次应该提醒
        assert reminder.should_remind_now() is True
        
        # 获取消息会更新 last_reminder_time
        reminder.get_reminder_message()
        
        # 间隔内不应该提醒
        assert reminder.should_remind_now() is False
    
    def test_get_reminder_message_normal(self):
        """测试普通提醒消息"""
        config = TimeoutReminderConfig(
            reminder_start=1800,
            countdown_threshold=300,
        )
        reminder = TimeoutReminder(run_timeout=1500, config=config)  # 剩余 25 分钟
        msg = reminder.get_reminder_message()
        assert msg is not None
        assert "剩余时间" in msg
        assert "⏰" in msg
    
    def test_get_reminder_message_countdown(self):
        """测试倒数模式提醒消息"""
        config = TimeoutReminderConfig(
            reminder_start=1800,
            countdown_threshold=300,
        )
        reminder = TimeoutReminder(run_timeout=180, config=config)  # 剩余 3 分钟
        msg = reminder.get_reminder_message()
        assert msg is not None
        assert "倒计时" in msg
        assert "收尾" in msg
    
    def test_get_reminder_message_last_round(self):
        """测试最后一轮提醒消息"""
        config = TimeoutReminderConfig(enabled=True)
        reminder = TimeoutReminder(run_timeout=30, config=config)  # 剩余 30 秒
        msg = reminder.get_reminder_message()
        assert msg is not None
        assert "最后一轮" in msg
        assert "交付" in msg
    
    def test_get_reminder_message_last_round_once(self):
        """测试最后一轮提醒只触发一次"""
        config = TimeoutReminderConfig(enabled=True)
        reminder = TimeoutReminder(run_timeout=30, config=config)
        
        msg1 = reminder.get_reminder_message()
        assert msg1 is not None
        assert "最后一轮" in msg1
        
        msg2 = reminder.get_reminder_message()
        assert msg2 is None  # 第二次应该返回 None
    
    def test_get_reminder_message_disabled(self):
        """测试禁用时返回 None"""
        config = TimeoutReminderConfig(enabled=False)
        reminder = TimeoutReminder(run_timeout=60, config=config)
        assert reminder.get_reminder_message() is None
    
    def test_format_remaining_time_seconds(self):
        """测试格式化秒"""
        reminder = TimeoutReminder(run_timeout=100)
        result = reminder._format_remaining_time(45)
        assert result == "45 秒"
    
    def test_format_remaining_time_minutes(self):
        """测试格式化分钟"""
        reminder = TimeoutReminder(run_timeout=100)
        result = reminder._format_remaining_time(300)
        assert result == "5 分钟"
    
    def test_format_remaining_time_minutes_and_seconds(self):
        """测试格式化分钟和秒"""
        reminder = TimeoutReminder(run_timeout=100)
        result = reminder._format_remaining_time(185)
        assert result == "3 分 5 秒"
    
    def test_format_remaining_time_hours(self):
        """测试格式化小时"""
        reminder = TimeoutReminder(run_timeout=10000)
        result = reminder._format_remaining_time(3600)
        assert result == "1 小时"
    
    def test_format_remaining_time_hours_and_minutes(self):
        """测试格式化小时和分钟"""
        reminder = TimeoutReminder(run_timeout=10000)
        result = reminder._format_remaining_time(5400)
        assert result == "1 小时 30 分钟"


class TestGlobalTimeoutReminder:
    """全局 TimeoutReminder 访问测试"""
    
    def test_set_and_get(self):
        """测试设置和获取"""
        reminder = TimeoutReminder(run_timeout=100)
        set_timeout_reminder(reminder)
        
        retrieved = get_timeout_reminder()
        assert retrieved is reminder
        
        # 清理
        set_timeout_reminder(None)
    
    def test_get_default_none(self):
        """测试默认值为 None"""
        set_timeout_reminder(None)
        assert get_timeout_reminder() is None
    
    def test_set_none(self):
        """测试设置为 None"""
        reminder = TimeoutReminder(run_timeout=100)
        set_timeout_reminder(reminder)
        set_timeout_reminder(None)
        
        assert get_timeout_reminder() is None


class TestTimeoutReminderHook:
    """timeout_reminder hook 测试"""
    
    @pytest.fixture
    def mock_agent(self):
        """创建 mock agent"""
        agent = MagicMock()
        agent.memory = AsyncMock()
        agent.memory.add = AsyncMock()
        return agent
    
    @pytest.mark.asyncio
    async def test_hook_no_reminder_set(self, mock_agent):
        """测试没有设置 reminder 时不做任何操作"""
        set_timeout_reminder(None)
        
        hook = create_timeout_reminder_hook()
        kwargs = {"msg": MagicMock()}
        
        result = await hook(mock_agent, kwargs)
        
        assert result is kwargs
        mock_agent.memory.add.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_hook_no_message_needed(self, mock_agent):
        """测试不需要提醒时不添加消息"""
        # 设置一个超出提醒范围的 reminder
        config = TimeoutReminderConfig(reminder_start=1800)
        reminder = TimeoutReminder(run_timeout=3600, config=config)
        set_timeout_reminder(reminder)
        
        hook = create_timeout_reminder_hook()
        kwargs = {"msg": MagicMock()}
        
        result = await hook(mock_agent, kwargs)
        
        assert result is kwargs
        mock_agent.memory.add.assert_not_called()
        
        # 清理
        set_timeout_reminder(None)
    
    @pytest.mark.asyncio
    async def test_hook_adds_reminder_message(self, mock_agent):
        """测试需要提醒时添加 system 消息"""
        # 设置一个需要提醒的 reminder
        config = TimeoutReminderConfig(
            enabled=True,
            reminder_start=1800,
            countdown_threshold=300,
        )
        reminder = TimeoutReminder(run_timeout=180, config=config)  # 剩余 3 分钟
        set_timeout_reminder(reminder)
        
        hook = create_timeout_reminder_hook()
        kwargs = {"msg": MagicMock()}
        
        result = await hook(mock_agent, kwargs)
        
        assert result is kwargs
        mock_agent.memory.add.assert_called_once()
        
        # 检查添加的消息
        call_args = mock_agent.memory.add.call_args
        added_msg = call_args[0][0]
        assert added_msg.role == "system"
        assert "倒计时" in added_msg.content
        
        # 清理
        set_timeout_reminder(None)
    
    @pytest.mark.asyncio
    async def test_hook_no_memory(self):
        """测试 agent 没有 memory 时不报错"""
        agent = MagicMock()
        agent.memory = None
        
        config = TimeoutReminderConfig(enabled=True)
        reminder = TimeoutReminder(run_timeout=30, config=config)
        set_timeout_reminder(reminder)
        
        hook = create_timeout_reminder_hook()
        kwargs = {"msg": MagicMock()}
        
        # 不应该报错
        result = await hook(agent, kwargs)
        assert result is kwargs
        
        # 清理
        set_timeout_reminder(None)
    
    def test_register_hook(self, mock_agent):
        """测试注册 hook"""
        register_timeout_reminder_hook(mock_agent)
        
        mock_agent.register_instance_hook.assert_called_once()
        call_args = mock_agent.register_instance_hook.call_args
        
        assert call_args.kwargs["hook_type"] == "pre_reply"
        assert call_args.kwargs["hook_name"] == "timeout_reminder"
        assert callable(call_args.kwargs["hook"])


class TestTimeoutMonitor:
    """timeout_monitor 协程测试"""
    
    @pytest.fixture
    def mock_agents(self):
        """创建 mock agents"""
        agent1 = MagicMock()
        agent1.interrupt = AsyncMock()
        
        agent2 = MagicMock()
        agent2.interrupt = AsyncMock()
        
        return [agent1, agent2]
    
    @pytest.mark.asyncio
    async def test_monitor_waits_until_deadline(self, mock_agents):
        """测试监控器等待到 deadline"""
        from agentscope_agent.timeout import timeout_monitor
        
        # 设置很短的超时，便于测试
        config = TimeoutReminderConfig(teardown=0.1)  # 0.1 秒 teardown
        reminder = TimeoutReminder(run_timeout=0.1, config=config)  # 0.1 秒超时
        
        # 运行 monitor
        await timeout_monitor(mock_agents, reminder)
        
        # 应该调用了所有 agent 的 interrupt
        for agent in mock_agents:
            agent.interrupt.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_interrupts_in_order(self, mock_agents):
        """测试按顺序中断 agents"""
        from agentscope_agent.timeout import timeout_monitor
        
        config = TimeoutReminderConfig(teardown=0.05)
        reminder = TimeoutReminder(run_timeout=0.05, config=config)
        
        call_order = []
        
        async def record_interrupt_1():
            call_order.append(1)
        
        async def record_interrupt_2():
            call_order.append(2)
        
        mock_agents[0].interrupt = record_interrupt_1
        mock_agents[1].interrupt = record_interrupt_2
        
        await timeout_monitor(mock_agents, reminder)
        
        # 应该按顺序调用
        assert call_order == [1, 2]
    
    @pytest.mark.asyncio
    async def test_monitor_handles_agent_without_interrupt(self):
        """测试处理没有 interrupt 方法的 agent"""
        from agentscope_agent.timeout import timeout_monitor
        
        agent_with_interrupt = MagicMock()
        agent_with_interrupt.interrupt = AsyncMock()
        
        agent_without_interrupt = MagicMock(spec=[])  # 没有 interrupt 方法
        
        config = TimeoutReminderConfig(teardown=0.05)
        reminder = TimeoutReminder(run_timeout=0.05, config=config)
        
        # 不应该报错
        await timeout_monitor([agent_with_interrupt, agent_without_interrupt], reminder)
        
        agent_with_interrupt.interrupt.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_handles_none_agent(self):
        """测试处理 None agent"""
        from agentscope_agent.timeout import timeout_monitor
        
        agent = MagicMock()
        agent.interrupt = AsyncMock()
        
        config = TimeoutReminderConfig(teardown=0.05)
        reminder = TimeoutReminder(run_timeout=0.05, config=config)
        
        # 不应该报错
        await timeout_monitor([agent, None], reminder)
        
        agent.interrupt.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_handles_interrupt_exception(self):
        """测试处理 interrupt 抛异常"""
        from agentscope_agent.timeout import timeout_monitor
        
        agent1 = MagicMock()
        agent1.interrupt = AsyncMock(side_effect=Exception("interrupt failed"))
        
        agent2 = MagicMock()
        agent2.interrupt = AsyncMock()
        
        config = TimeoutReminderConfig(teardown=0.05)
        reminder = TimeoutReminder(run_timeout=0.05, config=config)
        
        # 不应该报错，第二个 agent 仍应被中断
        await timeout_monitor([agent1, agent2], reminder)
        
        agent1.interrupt.assert_called_once()
        agent2.interrupt.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_can_be_cancelled(self, mock_agents):
        """测试监控器可以被取消"""
        from agentscope_agent.timeout import timeout_monitor
        
        # 设置较长的超时
        config = TimeoutReminderConfig(teardown=10)
        reminder = TimeoutReminder(run_timeout=10, config=config)
        
        task = asyncio.create_task(timeout_monitor(mock_agents, reminder))
        
        # 等一下然后取消
        await asyncio.sleep(0.05)
        task.cancel()
        
        with pytest.raises(asyncio.CancelledError):
            await task
        
        # 不应该调用 interrupt（因为被取消了）
        for agent in mock_agents:
            agent.interrupt.assert_not_called()


class TestTimeoutReminderIntegration:
    """集成测试场景"""
    
    def test_full_lifecycle(self):
        """测试完整生命周期"""
        # 1. 创建并设置
        config = TimeoutReminderConfig(
            enabled=True,
            reminder_start=600,
            reminder_interval=60,
            countdown_threshold=120,
        )
        reminder = TimeoutReminder(run_timeout=500, config=config)
        set_timeout_reminder(reminder)
        
        # 2. 获取全局 reminder
        global_reminder = get_timeout_reminder()
        assert global_reminder is reminder
        
        # 3. 检查状态
        assert not global_reminder.is_expired()
        assert global_reminder.get_remaining_time() > 0
        
        # 4. 获取提醒消息（在范围内）
        msg = global_reminder.get_reminder_message()
        assert msg is not None
        
        # 5. 清理
        set_timeout_reminder(None)
        assert get_timeout_reminder() is None
    
    def test_countdown_progression(self):
        """测试倒数模式的消息变化"""
        config = TimeoutReminderConfig(
            enabled=True,
            reminder_start=1800,
            countdown_threshold=300,
        )
        
        # 模拟不同剩余时间的消息
        test_cases = [
            (1500, "剩余时间"),  # 25 分钟 - 普通提醒
            (180, "倒计时"),     # 3 分钟 - 倒数模式
            (30, "最后一轮"),    # 30 秒 - 最后一轮
        ]
        
        for timeout, expected_text in test_cases:
            reminder = TimeoutReminder(run_timeout=timeout, config=config)
            msg = reminder.get_reminder_message()
            assert msg is not None, f"timeout={timeout} should have message"
            assert expected_text in msg, f"timeout={timeout}: expected '{expected_text}' in '{msg}'"
