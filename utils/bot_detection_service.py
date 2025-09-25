"""
双向机器人检测服务
提供高级的机器人检测算法，结合行为分析和交互模式检测
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict, deque

from .user_detector import TelegramUserDetector

logger = logging.getLogger(__name__)


@dataclass
class UserBehavior:
    """用户行为数据"""
    user_id: int
    message_count: int = 0
    response_times: deque = None  # 响应时间队列
    message_intervals: deque = None  # 消息间隔队列
    command_usage: Dict[str, int] = None  # 命令使用统计
    interaction_patterns: List[str] = None  # 交互模式
    first_seen: datetime = None
    last_seen: datetime = None
    
    def __post_init__(self):
        if self.response_times is None:
            self.response_times = deque(maxlen=20)
        if self.message_intervals is None:
            self.message_intervals = deque(maxlen=20)
        if self.command_usage is None:
            self.command_usage = defaultdict(int)
        if self.interaction_patterns is None:
            self.interaction_patterns = []
        if self.first_seen is None:
            self.first_seen = datetime.now()
        if self.last_seen is None:
            self.last_seen = datetime.now()


class BotDetectionService:
    """双向机器人检测服务"""
    
    def __init__(self, bot_token: str, detection_window_hours: int = 24):
        """
        初始化机器人检测服务
        
        Args:
            bot_token: Telegram机器人Token
            detection_window_hours: 检测窗口时间（小时）
        """
        self.user_detector = TelegramUserDetector(bot_token)
        self.detection_window = timedelta(hours=detection_window_hours)
        self.user_behaviors: Dict[int, UserBehavior] = {}
        self.suspicious_patterns: Dict[int, List[str]] = defaultdict(list)
        
        # 机器人行为阈值
        self.thresholds = {
            'min_response_time': 0.5,  # 最小响应时间（秒）
            'max_response_time': 300,  # 最大合理响应时间（秒）
            'max_message_frequency': 10,  # 最大消息频率（条/分钟）
            'min_message_interval': 1.0,  # 最小消息间隔（秒）
            'suspicious_uniformity': 0.8,  # 可疑一致性阈值
            'pattern_repetition_threshold': 3,  # 模式重复阈值
        }
    
    async def initialize(self):
        """初始化服务"""
        await self.user_detector.initialize()
        logger.info("机器人检测服务初始化完成")
    
    def record_message(self, user_id: int, message_type: str = 'text', 
                      response_time: Optional[float] = None):
        """
        记录用户消息行为
        
        Args:
            user_id: 用户ID
            message_type: 消息类型
            response_time: 响应时间（秒）
        """
        now = datetime.now()
        
        if user_id not in self.user_behaviors:
            self.user_behaviors[user_id] = UserBehavior(user_id=user_id)
        
        behavior = self.user_behaviors[user_id]
        behavior.message_count += 1
        behavior.last_seen = now
        
        # 记录响应时间
        if response_time is not None:
            behavior.response_times.append(response_time)
        
        # 记录消息间隔
        if len(behavior.interaction_patterns) > 0:
            last_time = behavior.last_seen - timedelta(seconds=1)  # 简化计算
            interval = (now - last_time).total_seconds()
            behavior.message_intervals.append(interval)
        
        # 记录交互模式
        behavior.interaction_patterns.append(f"{message_type}_{now.timestamp()}")
        
        # 保持数据窗口大小
        cutoff_time = now - self.detection_window
        behavior.interaction_patterns = [
            pattern for pattern in behavior.interaction_patterns 
            if float(pattern.split('_')[1]) > cutoff_time.timestamp()
        ]
    
    def record_command_usage(self, user_id: int, command: str):
        """
        记录用户命令使用
        
        Args:
            user_id: 用户ID
            command: 命令名称
        """
        if user_id not in self.user_behaviors:
            self.user_behaviors[user_id] = UserBehavior(user_id=user_id)
        
        self.user_behaviors[user_id].command_usage[command] += 1
    
    def _analyze_response_timing(self, user_id: int) -> Dict:
        """分析用户响应时间模式"""
        if user_id not in self.user_behaviors:
            return {'score': 0.0, 'reasons': []}
        
        behavior = self.user_behaviors[user_id]
        if not behavior.response_times:
            return {'score': 0.0, 'reasons': ['无响应时间数据']}
        
        response_times = list(behavior.response_times)
        score = 0.0
        reasons = []
        
        # 1. 检查响应时间过于一致
        if len(response_times) >= 3:
            avg_time = sum(response_times) / len(response_times)
            variance = sum((t - avg_time) ** 2 for t in response_times) / len(response_times)
            std_dev = variance ** 0.5
            
            if std_dev < 0.5 and avg_time < 2.0:  # 标准差很小且平均响应很快
                score += 0.6
                reasons.append(f"响应时间过于一致: 平均{avg_time:.2f}秒, 标准差{std_dev:.2f}")
        
        # 2. 检查响应时间过快
        fast_responses = [t for t in response_times if t < self.thresholds['min_response_time']]
        if len(fast_responses) / len(response_times) > 0.5:
            score += 0.4
            reasons.append(f"响应过快的比例: {len(fast_responses)}/{len(response_times)}")
        
        # 3. 检查模式化的响应时间
        if len(response_times) >= 5:
            # 简单检查是否有重复的时间模式
            time_buckets = defaultdict(int)
            for t in response_times:
                bucket = round(t, 1)  # 精确到0.1秒
                time_buckets[bucket] += 1
            
            max_bucket_count = max(time_buckets.values())
            if max_bucket_count >= len(response_times) * 0.6:
                score += 0.3
                reasons.append("响应时间高度集中在特定值")
        
        return {'score': min(score, 1.0), 'reasons': reasons}
    
    def _analyze_message_frequency(self, user_id: int) -> Dict:
        """分析消息频率模式"""
        if user_id not in self.user_behaviors:
            return {'score': 0.0, 'reasons': []}
        
        behavior = self.user_behaviors[user_id]
        if not behavior.message_intervals:
            return {'score': 0.0, 'reasons': ['无消息间隔数据']}
        
        intervals = list(behavior.message_intervals)
        score = 0.0
        reasons = []
        
        # 1. 检查消息间隔过于规律
        if len(intervals) >= 3:
            avg_interval = sum(intervals) / len(intervals)
            variance = sum((i - avg_interval) ** 2 for i in intervals) / len(intervals)
            std_dev = variance ** 0.5
            
            if std_dev < 1.0 and 1.0 < avg_interval < 10.0:
                score += 0.5
                reasons.append(f"消息间隔过于规律: 平均{avg_interval:.2f}秒")
        
        # 2. 检查高频消息
        short_intervals = [i for i in intervals if i < self.thresholds['min_message_interval']]
        if len(short_intervals) / len(intervals) > 0.3:
            score += 0.4
            reasons.append(f"高频消息比例: {len(short_intervals)}/{len(intervals)}")
        
        # 3. 检查消息爆发模式
        if len(intervals) >= 10:
            burst_count = 0
            for i in range(len(intervals) - 2):
                if all(interval < 2.0 for interval in intervals[i:i+3]):
                    burst_count += 1
            
            if burst_count > len(intervals) * 0.2:
                score += 0.3
                reasons.append(f"检测到爆发性消息模式: {burst_count}次")
        
        return {'score': min(score, 1.0), 'reasons': reasons}
    
    def _analyze_command_patterns(self, user_id: int) -> Dict:
        """分析命令使用模式"""
        if user_id not in self.user_behaviors:
            return {'score': 0.0, 'reasons': []}
        
        behavior = self.user_behaviors[user_id]
        if not behavior.command_usage:
            return {'score': 0.0, 'reasons': ['无命令使用数据']}
        
        score = 0.0
        reasons = []
        
        # 1. 检查命令使用过于集中
        total_commands = sum(behavior.command_usage.values())
        if total_commands > 0:
            max_command_usage = max(behavior.command_usage.values())
            concentration = max_command_usage / total_commands
            
            if concentration > 0.8 and total_commands > 5:
                score += 0.4
                reasons.append(f"命令使用高度集中: {concentration:.2f}")
        
        # 2. 检查异常命令序列
        sorted_commands = sorted(behavior.command_usage.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_commands) >= 2:
            top_command_ratio = sorted_commands[0][1] / sorted_commands[1][1]
            if top_command_ratio > 5:
                score += 0.2
                reasons.append("存在异常的命令使用偏好")
        
        return {'score': min(score, 1.0), 'reasons': reasons}
    
    async def analyze_user_behavior(self, user_id: int) -> Dict:
        """
        综合分析用户行为模式
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 行为分析结果
        """
        try:
            # 获取基础用户信息
            user_type_result = await self.user_detector.detect_user_type(user_id)
            
            # 行为模式分析
            timing_analysis = self._analyze_response_timing(user_id)
            frequency_analysis = self._analyze_message_frequency(user_id)
            command_analysis = self._analyze_command_patterns(user_id)
            
            # 综合评分
            behavior_scores = {
                'timing_score': timing_analysis['score'],
                'frequency_score': frequency_analysis['score'],
                'command_score': command_analysis['score']
            }
            
            # 权重计算
            weights = {'timing_score': 0.4, 'frequency_score': 0.4, 'command_score': 0.2}
            behavior_bot_score = sum(
                score * weights[key] for key, score in behavior_scores.items()
            )
            
            # 结合API检测结果
            api_bot_probability = user_type_result.get('bot_probability', 0.5)
            
            # 最终综合评分
            final_bot_probability = (behavior_bot_score * 0.6 + api_bot_probability * 0.4)
            
            # 确定结果类型
            if final_bot_probability > 0.8:
                result_type = "highly_suspected_bot"
            elif final_bot_probability > 0.6:
                result_type = "suspected_bot"  
            elif final_bot_probability > 0.4:
                result_type = "uncertain"
            else:
                result_type = "likely_human"
            
            # 收集所有原因
            all_reasons = []
            all_reasons.extend(timing_analysis['reasons'])
            all_reasons.extend(frequency_analysis['reasons'])
            all_reasons.extend(command_analysis['reasons'])
            all_reasons.extend(user_type_result.get('analysis_reasons', []))
            
            return {
                'user_id': user_id,
                'result_type': result_type,
                'final_bot_probability': final_bot_probability,
                'behavior_bot_score': behavior_bot_score,
                'api_bot_probability': api_bot_probability,
                'component_scores': behavior_scores,
                'analysis_details': {
                    'timing_analysis': timing_analysis,
                    'frequency_analysis': frequency_analysis,
                    'command_analysis': command_analysis,
                    'user_type_result': user_type_result
                },
                'all_reasons': all_reasons,
                'confidence': abs(final_bot_probability - 0.5) * 2  # 转换为0-1的置信度
            }
            
        except Exception as e:
            logger.error(f"分析用户 {user_id} 行为失败: {e}")
            return {
                'user_id': user_id,
                'result_type': 'error',
                'error': str(e),
                'final_bot_probability': 0.5
            }
    
    def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """获取用户统计信息"""
        if user_id not in self.user_behaviors:
            return None
        
        behavior = self.user_behaviors[user_id]
        return {
            'user_id': user_id,
            'message_count': behavior.message_count,
            'first_seen': behavior.first_seen.isoformat(),
            'last_seen': behavior.last_seen.isoformat(),
            'response_times_count': len(behavior.response_times),
            'message_intervals_count': len(behavior.message_intervals),
            'total_commands': sum(behavior.command_usage.values()),
            'unique_commands': len(behavior.command_usage),
            'interaction_patterns_count': len(behavior.interaction_patterns)
        }
    
    def cleanup_old_data(self):
        """清理过期数据"""
        cutoff_time = datetime.now() - self.detection_window
        
        users_to_remove = []
        for user_id, behavior in self.user_behaviors.items():
            if behavior.last_seen < cutoff_time:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.user_behaviors[user_id]
            if user_id in self.suspicious_patterns:
                del self.suspicious_patterns[user_id]
        
        logger.info(f"清理了 {len(users_to_remove)} 个过期用户数据")
    
    async def batch_analyze_users(self, user_ids: List[int]) -> Dict[int, Dict]:
        """批量分析用户"""
        results = {}
        
        for user_id in user_ids:
            try:
                result = await self.analyze_user_behavior(user_id)
                results[user_id] = result
                
                # 避免API频率限制
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"批量分析用户 {user_id} 失败: {e}")
                results[user_id] = {
                    'user_id': user_id,
                    'result_type': 'error',
                    'error': str(e)
                }
        
        return results
    
    async def cleanup(self):
        """清理资源"""
        await self.user_detector.cleanup()
        logger.info("机器人检测服务已清理")