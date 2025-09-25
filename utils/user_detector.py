"""
Telegram用户信息检测工具
提供用户名检测、频道群组链接提取、机器人双向检测等功能
"""

import re
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Union
from telegram import User, Chat
from telegram.ext import Application

logger = logging.getLogger(__name__)


class TelegramUserDetector:
    """Telegram用户信息检测器"""
    
    def __init__(self, bot_token: str):
        """
        初始化用户检测器
        
        Args:
            bot_token: 机器人Token
        """
        self.bot_token = bot_token
        self.application = None
    
    async def initialize(self):
        """初始化Telegram应用"""
        try:
            self.application = Application.builder().token(self.bot_token).build()
            await self.application.initialize()
            logger.info("Telegram用户检测器初始化成功")
        except Exception as e:
            logger.error(f"初始化Telegram应用失败: {e}")
            raise
    
    async def get_user_info(self, user_id: int) -> Dict:
        """
        获取用户详细信息
        
        Args:
            user_id: Telegram用户ID
            
        Returns:
            Dict: 用户信息字典
        """
        try:
            if not self.application:
                await self.initialize()
            
            # 获取用户信息
            user = await self.application.bot.get_chat(user_id)
            
            user_info = {
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': self._get_full_name(user.first_name, user.last_name),
                'bio': user.bio if hasattr(user, 'bio') else None,
                'is_bot': getattr(user, 'is_bot', False),
                'language_code': user.language_code if hasattr(user, 'language_code') else None,
                'detected_info': {}
            }
            
            # 检测用户名中的机器人特征
            if user_info['username']:
                user_info['detected_info']['bot_indicators'] = self._detect_bot_username_patterns(user_info['username'])
            
            # 检测bio中的频道/群组链接
            if user_info['bio']:
                user_info['detected_info']['channel_links'] = self._extract_channel_links(user_info['bio'])
                user_info['detected_info']['group_links'] = self._extract_group_links(user_info['bio'])
            
            # 检测姓名中的特征
            name_analysis = self._analyze_name_patterns(user_info['full_name'])
            user_info['detected_info']['name_analysis'] = name_analysis
            
            logger.info(f"获取用户 {user_id} 信息成功")
            return user_info
            
        except Exception as e:
            logger.error(f"获取用户 {user_id} 信息失败: {e}")
            raise
    
    def _get_full_name(self, first_name: Optional[str], last_name: Optional[str]) -> str:
        """构造完整姓名"""
        parts = []
        if first_name:
            parts.append(first_name)
        if last_name:
            parts.append(last_name)
        return " ".join(parts) if parts else ""
    
    def _detect_bot_username_patterns(self, username: str) -> Dict:
        """
        检测用户名中的机器人特征模式
        
        Args:
            username: 用户名
            
        Returns:
            Dict: 检测结果
        """
        if not username:
            return {'has_bot_indicators': False, 'indicators': [], 'confidence': 0.0}
        
        username_lower = username.lower()
        indicators = []
        confidence = 0.0
        
        # 机器人关键词检测
        bot_keywords = ['bot', 'robot', '机器人', 'auto', 'ai', 'assistant', 'helper']
        for keyword in bot_keywords:
            if keyword in username_lower:
                indicators.append(f"包含关键词: {keyword}")
                confidence += 0.3
        
        # 数字结尾模式（常见于机器人）
        if re.search(r'\d{2,}$', username):
            indicators.append("用户名以多位数字结尾")
            confidence += 0.2
        
        # 下划线模式
        if username.count('_') >= 2:
            indicators.append("包含多个下划线")
            confidence += 0.1
        
        # 特殊前缀模式
        prefixes = ['auto_', 'bot_', 'ai_', 'sys_']
        for prefix in prefixes:
            if username_lower.startswith(prefix):
                indicators.append(f"以 {prefix} 开头")
                confidence += 0.4
        
        confidence = min(confidence, 1.0)  # 限制最大置信度
        
        return {
            'has_bot_indicators': len(indicators) > 0,
            'indicators': indicators,
            'confidence': confidence
        }
    
    def _extract_channel_links(self, text: str) -> List[Dict]:
        """
        提取文本中的频道链接
        
        Args:
            text: 要分析的文本
            
        Returns:
            List[Dict]: 频道链接列表
        """
        if not text:
            return []
        
        channels = []
        
        # Telegram频道链接模式
        patterns = [
            r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)',  # t.me链接
            r'@([a-zA-Z0-9_]+)',  # @用户名格式
            r'telegram\.me/([a-zA-Z0-9_]+)',  # telegram.me链接
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                channel_name = match.group(1)
                if channel_name and not channel_name.lower().endswith('bot'):
                    channels.append({
                        'name': channel_name,
                        'full_match': match.group(0),
                        'type': 'channel_or_user',
                        'confidence': 0.8
                    })
        
        # 去重
        seen = set()
        unique_channels = []
        for channel in channels:
            if channel['name'].lower() not in seen:
                seen.add(channel['name'].lower())
                unique_channels.append(channel)
        
        return unique_channels
    
    def _extract_group_links(self, text: str) -> List[Dict]:
        """
        提取文本中的群组链接
        
        Args:
            text: 要分析的文本
            
        Returns:
            List[Dict]: 群组链接列表
        """
        if not text:
            return []
        
        groups = []
        
        # 群组邀请链接模式
        patterns = [
            r'(?:https?://)?t\.me/joinchat/([a-zA-Z0-9_-]+)',  # 邀请链接
            r'(?:https?://)?t\.me/\+([a-zA-Z0-9_-]+)',  # 新式邀请链接
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                invite_code = match.group(1)
                groups.append({
                    'invite_code': invite_code,
                    'full_match': match.group(0),
                    'type': 'group_invite',
                    'confidence': 0.9
                })
        
        return groups
    
    def _analyze_name_patterns(self, name: str) -> Dict:
        """
        分析姓名模式特征
        
        Args:
            name: 完整姓名
            
        Returns:
            Dict: 分析结果
        """
        if not name:
            return {'has_patterns': False, 'patterns': [], 'language_hints': []}
        
        patterns = []
        language_hints = []
        
        # 检测中文字符
        if re.search(r'[\u4e00-\u9fff]', name):
            language_hints.append('包含中文字符')
        
        # 检测英文模式
        if re.search(r'^[a-zA-Z\s]+$', name):
            language_hints.append('纯英文姓名')
        
        # 检测数字
        if re.search(r'\d', name):
            patterns.append('姓名包含数字')
        
        # 检测特殊字符
        if re.search(r'[^\w\s\u4e00-\u9fff]', name):
            patterns.append('包含特殊字符')
        
        # 检测长度异常
        if len(name) > 50:
            patterns.append('姓名异常长')
        
        return {
            'has_patterns': len(patterns) > 0 or len(language_hints) > 0,
            'patterns': patterns,
            'language_hints': language_hints,
            'length': len(name)
        }
    
    async def detect_user_type(self, user_id: int) -> Dict:
        """
        综合检测用户类型
        
        Args:
            user_id: 用户ID
            
        Returns:
            Dict: 用户类型检测结果
        """
        try:
            user_info = await self.get_user_info(user_id)
            
            # 综合判断逻辑
            bot_score = 0.0
            human_score = 0.0
            reasons = []
            
            # 1. 官方is_bot标志
            if user_info.get('is_bot', False):
                bot_score += 1.0
                reasons.append("Telegram官方标记为机器人")
            else:
                human_score += 0.3
                reasons.append("Telegram官方标记为用户")
            
            # 2. 用户名分析
            username_analysis = user_info['detected_info'].get('bot_indicators', {})
            if username_analysis.get('has_bot_indicators', False):
                confidence = username_analysis.get('confidence', 0.0)
                bot_score += confidence * 0.7
                reasons.extend([f"用户名分析: {ind}" for ind in username_analysis.get('indicators', [])])
            
            # 3. 姓名分析
            name_analysis = user_info['detected_info'].get('name_analysis', {})
            if name_analysis.get('has_patterns', False):
                if '姓名异常长' in name_analysis.get('patterns', []):
                    bot_score += 0.2
                    reasons.append("姓名异常长")
                if '姓名包含数字' in name_analysis.get('patterns', []):
                    bot_score += 0.1
                    reasons.append("姓名包含数字")
            
            # 4. 有频道链接但无bio内容可能是营销号
            has_channels = len(user_info['detected_info'].get('channel_links', [])) > 0
            has_bio = bool(user_info.get('bio'))
            
            if has_channels and not has_bio:
                bot_score += 0.3
                reasons.append("有频道链接但无个人简介")
            
            # 归一化分数
            total_score = bot_score + human_score
            if total_score > 0:
                bot_probability = bot_score / total_score
                human_probability = human_score / total_score
            else:
                bot_probability = 0.5
                human_probability = 0.5
            
            # 判断结果
            if bot_probability > 0.7:
                user_type = "suspected_bot"
                confidence = bot_probability
            elif bot_probability > 0.4:
                user_type = "uncertain"
                confidence = 0.5
            else:
                user_type = "likely_human"
                confidence = human_probability
            
            return {
                'user_type': user_type,
                'confidence': confidence,
                'bot_probability': bot_probability,
                'human_probability': human_probability,
                'analysis_reasons': reasons,
                'raw_info': user_info
            }
            
        except Exception as e:
            logger.error(f"用户类型检测失败: {e}")
            raise
    
    async def batch_detect_users(self, user_ids: List[int]) -> Dict[int, Dict]:
        """
        批量检测用户类型
        
        Args:
            user_ids: 用户ID列表
            
        Returns:
            Dict: 用户ID到检测结果的映射
        """
        results = {}
        
        for user_id in user_ids:
            try:
                result = await self.detect_user_type(user_id)
                results[user_id] = result
                
                # 避免API频率限制
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"检测用户 {user_id} 失败: {e}")
                results[user_id] = {
                    'user_type': 'error',
                    'error': str(e)
                }
        
        return results
    
    async def cleanup(self):
        """清理资源"""
        if self.application:
            await self.application.shutdown()
            logger.info("Telegram用户检测器已清理")