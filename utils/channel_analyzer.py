"""
频道和群组链接分析器
提供链接提取、分类、验证和元数据获取功能
"""

import re
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse
from telegram import Chat
from telegram.error import TelegramError

from .user_detector import TelegramUserDetector

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    """频道类型枚举"""
    CHANNEL = "channel"  # 频道
    GROUP = "group"  # 群组
    SUPERGROUP = "supergroup"  # 超级群组
    BOT = "bot"  # 机器人
    USER = "user"  # 用户
    UNKNOWN = "unknown"  # 未知


class LinkType(Enum):
    """链接类型枚举"""
    USERNAME = "username"  # @username格式
    T_ME = "t_me"  # t.me/链接
    TELEGRAM_ME = "telegram_me"  # telegram.me/链接
    INVITE = "invite"  # 邀请链接
    JOINCHAT = "joinchat"  # 旧式邀请链接
    UNKNOWN = "unknown"  # 未知格式


@dataclass
class ChannelInfo:
    """频道/群组信息"""
    original_text: str
    username: Optional[str] = None
    invite_code: Optional[str] = None
    link_type: LinkType = LinkType.UNKNOWN
    channel_type: ChannelType = ChannelType.UNKNOWN
    title: Optional[str] = None
    description: Optional[str] = None
    member_count: Optional[int] = None
    is_verified: Optional[bool] = None
    is_scam: Optional[bool] = None
    is_fake: Optional[bool] = None
    is_accessible: bool = False
    error_message: Optional[str] = None
    confidence: float = 0.0
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'original_text': self.original_text,
            'username': self.username,
            'invite_code': self.invite_code,
            'link_type': self.link_type.value,
            'channel_type': self.channel_type.value,
            'title': self.title,
            'description': self.description,
            'member_count': self.member_count,
            'is_verified': self.is_verified,
            'is_scam': self.is_scam,
            'is_fake': self.is_fake,
            'is_accessible': self.is_accessible,
            'error_message': self.error_message,
            'confidence': self.confidence
        }


class ChannelLinkAnalyzer:
    """频道链接分析器"""
    
    def __init__(self, bot_token: str):
        """
        初始化分析器
        
        Args:
            bot_token: Telegram机器人Token
        """
        self.user_detector = TelegramUserDetector(bot_token)
        self.link_patterns = self._compile_patterns()
        
    def _compile_patterns(self) -> Dict[LinkType, re.Pattern]:
        """编译链接匹配模式"""
        patterns = {
            LinkType.T_ME: re.compile(
                r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)(?:/(\d+))?',
                re.IGNORECASE
            ),
            LinkType.TELEGRAM_ME: re.compile(
                r'(?:https?://)?telegram\.me/([a-zA-Z0-9_]+)',
                re.IGNORECASE
            ),
            LinkType.USERNAME: re.compile(
                r'@([a-zA-Z0-9_]+)',
                re.IGNORECASE
            ),
            LinkType.JOINCHAT: re.compile(
                r'(?:https?://)?t\.me/joinchat/([a-zA-Z0-9_-]+)',
                re.IGNORECASE
            ),
            LinkType.INVITE: re.compile(
                r'(?:https?://)?t\.me/\+([a-zA-Z0-9_-]+)',
                re.IGNORECASE
            )
        }
        return patterns
    
    async def initialize(self):
        """初始化服务"""
        await self.user_detector.initialize()
        logger.info("频道链接分析器初始化完成")
    
    def extract_links_from_text(self, text: str) -> List[ChannelInfo]:
        """
        从文本中提取所有频道/群组链接
        
        Args:
            text: 要分析的文本
            
        Returns:
            List[ChannelInfo]: 提取的链接信息列表
        """
        if not text:
            return []
        
        found_links = []
        processed_identifiers = set()  # 避免重复处理相同的标识符
        
        for link_type, pattern in self.link_patterns.items():
            matches = pattern.finditer(text)
            
            for match in matches:
                channel_info = ChannelInfo(original_text=match.group(0))
                channel_info.link_type = link_type
                
                if link_type in [LinkType.T_ME, LinkType.TELEGRAM_ME, LinkType.USERNAME]:
                    username = match.group(1).lower()
                    if username not in processed_identifiers:
                        channel_info.username = username
                        processed_identifiers.add(username)
                    else:
                        continue  # 跳过重复的用户名
                        
                elif link_type in [LinkType.JOINCHAT, LinkType.INVITE]:
                    invite_code = match.group(1)
                    if invite_code not in processed_identifiers:
                        channel_info.invite_code = invite_code
                        processed_identifiers.add(invite_code)
                    else:
                        continue  # 跳过重复的邀请码
                
                # 初步分类
                channel_info.confidence = self._calculate_initial_confidence(channel_info)
                found_links.append(channel_info)
        
        return found_links
    
    def _calculate_initial_confidence(self, channel_info: ChannelInfo) -> float:
        """计算初始置信度"""
        confidence = 0.5  # 基础置信度
        
        # 根据链接类型调整置信度
        if channel_info.link_type == LinkType.T_ME:
            confidence += 0.3
        elif channel_info.link_type == LinkType.INVITE:
            confidence += 0.4  # 邀请链接通常是真实的群组
        elif channel_info.link_type == LinkType.USERNAME:
            confidence += 0.1  # @用户名格式可能是用户而非频道
        
        # 根据用户名特征调整置信度
        if channel_info.username:
            username = channel_info.username.lower()
            
            # 检查机器人特征
            if username.endswith('bot'):
                channel_info.channel_type = ChannelType.BOT
                confidence -= 0.2
            
            # 检查频道关键词
            channel_keywords = ['channel', 'news', 'official', 'group', 'chat']
            if any(keyword in username for keyword in channel_keywords):
                confidence += 0.2
                
            # 检查长度（太短可能是用户名）
            if len(username) < 5:
                confidence -= 0.1
            elif len(username) > 15:
                confidence += 0.1
        
        return min(max(confidence, 0.0), 1.0)
    
    async def verify_channel_info(self, channel_info: ChannelInfo) -> ChannelInfo:
        """
        验证并获取频道详细信息
        
        Args:
            channel_info: 频道信息对象
            
        Returns:
            ChannelInfo: 更新后的频道信息
        """
        try:
            if not self.user_detector.application:
                await self.user_detector.initialize()
            
            chat = None
            
            # 根据不同类型的标识符获取聊天信息
            if channel_info.username:
                try:
                    chat = await self.user_detector.application.bot.get_chat(f"@{channel_info.username}")
                    channel_info.is_accessible = True
                except TelegramError as e:
                    channel_info.error_message = str(e)
                    channel_info.is_accessible = False
                    logger.debug(f"无法访问用户名 {channel_info.username}: {e}")
            
            elif channel_info.invite_code:
                # 邀请链接无法直接获取信息，需要特殊处理
                channel_info.channel_type = ChannelType.GROUP
                channel_info.confidence += 0.2
                channel_info.error_message = "邀请链接需要加入后才能获取详细信息"
            
            # 如果成功获取到聊天信息
            if chat:
                await self._populate_chat_info(channel_info, chat)
            
        except Exception as e:
            logger.error(f"验证频道信息失败: {e}")
            channel_info.error_message = str(e)
            channel_info.is_accessible = False
        
        return channel_info
    
    async def _populate_chat_info(self, channel_info: ChannelInfo, chat: Chat):
        """
        从Chat对象填充频道信息
        
        Args:
            channel_info: 频道信息对象
            chat: Telegram Chat对象
        """
        channel_info.title = chat.title
        channel_info.description = chat.description
        
        # 确定频道类型
        if chat.type == Chat.CHANNEL:
            channel_info.channel_type = ChannelType.CHANNEL
        elif chat.type == Chat.GROUP:
            channel_info.channel_type = ChannelType.GROUP
        elif chat.type == Chat.SUPERGROUP:
            channel_info.channel_type = ChannelType.SUPERGROUP
        elif chat.type == Chat.PRIVATE:
            channel_info.channel_type = ChannelType.USER
        
        # 获取成员数量
        try:
            member_count = await self.user_detector.application.bot.get_chat_member_count(chat.id)
            channel_info.member_count = member_count
        except Exception as e:
            logger.debug(f"无法获取成员数量: {e}")
        
        # 获取其他属性
        if hasattr(chat, 'is_verified'):
            channel_info.is_verified = chat.is_verified
        if hasattr(chat, 'is_scam'):
            channel_info.is_scam = chat.is_scam
        if hasattr(chat, 'is_fake'):
            channel_info.is_fake = chat.is_fake
        
        # 根据获取的信息调整置信度
        if channel_info.channel_type in [ChannelType.CHANNEL, ChannelType.SUPERGROUP]:
            channel_info.confidence += 0.3
        elif channel_info.channel_type == ChannelType.GROUP:
            channel_info.confidence += 0.2
        
        if channel_info.member_count:
            if channel_info.member_count > 1000:
                channel_info.confidence += 0.2
            elif channel_info.member_count > 100:
                channel_info.confidence += 0.1
        
        if channel_info.is_verified:
            channel_info.confidence += 0.3
        
        if channel_info.is_scam or channel_info.is_fake:
            channel_info.confidence -= 0.5
        
        # 确保置信度在有效范围内
        channel_info.confidence = min(max(channel_info.confidence, 0.0), 1.0)
    
    async def analyze_text_comprehensively(self, text: str, verify_links: bool = True) -> Dict:
        """
        全面分析文本中的频道/群组链接
        
        Args:
            text: 要分析的文本
            verify_links: 是否验证链接有效性
            
        Returns:
            Dict: 分析结果
        """
        if not text:
            return {
                'total_links': 0,
                'channels': [],
                'groups': [],
                'bots': [],
                'users': [],
                'unknown': [],
                'accessible_count': 0,
                'verified_count': 0,
                'suspicious_count': 0,
                'summary': {}
            }
        
        # 提取链接
        extracted_links = self.extract_links_from_text(text)
        
        if verify_links:
            # 验证链接
            verified_links = []
            for link_info in extracted_links:
                try:
                    verified_info = await self.verify_channel_info(link_info)
                    verified_links.append(verified_info)
                    
                    # 避免API频率限制
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    logger.error(f"验证链接失败 {link_info.original_text}: {e}")
                    link_info.error_message = str(e)
                    verified_links.append(link_info)
        else:
            verified_links = extracted_links
        
        # 分类整理
        result = {
            'total_links': len(verified_links),
            'channels': [],
            'groups': [],
            'bots': [],
            'users': [],
            'unknown': [],
            'accessible_count': 0,
            'verified_count': 0,
            'suspicious_count': 0
        }
        
        for link_info in verified_links:
            link_dict = link_info.to_dict()
            
            if link_info.channel_type == ChannelType.CHANNEL:
                result['channels'].append(link_dict)
            elif link_info.channel_type in [ChannelType.GROUP, ChannelType.SUPERGROUP]:
                result['groups'].append(link_dict)
            elif link_info.channel_type == ChannelType.BOT:
                result['bots'].append(link_dict)
            elif link_info.channel_type == ChannelType.USER:
                result['users'].append(link_dict)
            else:
                result['unknown'].append(link_dict)
            
            # 统计计数
            if link_info.is_accessible:
                result['accessible_count'] += 1
            if link_info.is_verified:
                result['verified_count'] += 1
            if link_info.is_scam or link_info.is_fake:
                result['suspicious_count'] += 1
        
        # 生成摘要
        result['summary'] = {
            'has_channels': len(result['channels']) > 0,
            'has_groups': len(result['groups']) > 0,
            'has_bots': len(result['bots']) > 0,
            'channel_count': len(result['channels']),
            'group_count': len(result['groups']),
            'bot_count': len(result['bots']),
            'user_count': len(result['users']),
            'unknown_count': len(result['unknown']),
            'accessibility_rate': result['accessible_count'] / max(result['total_links'], 1),
            'verification_rate': result['verified_count'] / max(result['accessible_count'], 1) if result['accessible_count'] > 0 else 0,
            'suspicious_rate': result['suspicious_count'] / max(result['total_links'], 1)
        }
        
        return result
    
    def categorize_by_purpose(self, analysis_result: Dict) -> Dict:
        """
        根据用途对链接进行分类
        
        Args:
            analysis_result: analyze_text_comprehensively的结果
            
        Returns:
            Dict: 按用途分类的结果
        """
        categories = {
            'business_channels': [],     # 商业频道
            'news_channels': [],         # 新闻频道
            'entertainment_groups': [],  # 娱乐群组
            'support_bots': [],          # 支持机器人
            'personal_contacts': [],     # 个人联系方式
            'suspicious_links': [],      # 可疑链接
            'promotional_content': []    # 推广内容
        }
        
        # 关键词分类
        keywords = {
            'business': ['business', 'shop', 'store', 'service', 'official', 'company'],
            'news': ['news', 'update', 'announce', 'info', 'media'],
            'entertainment': ['fun', 'game', 'chat', 'talk', 'social'],
            'support': ['help', 'support', 'assist', 'service', 'bot'],
            'suspicious': ['free', 'money', 'win', 'prize', 'earn', 'click']
        }
        
        all_links = (analysis_result['channels'] + analysis_result['groups'] + 
                    analysis_result['bots'] + analysis_result['users'])
        
        for link in all_links:
            title = (link.get('title') or '').lower()
            username = (link.get('username') or '').lower()
            description = (link.get('description') or '').lower()
            
            combined_text = f"{title} {username} {description}"
            
            # 分类逻辑
            if link.get('is_scam') or link.get('is_fake'):
                categories['suspicious_links'].append(link)
            elif link.get('channel_type') == 'bot':
                if any(keyword in combined_text for keyword in keywords['support']):
                    categories['support_bots'].append(link)
                else:
                    categories['promotional_content'].append(link)
            elif link.get('channel_type') == 'channel':
                if any(keyword in combined_text for keyword in keywords['business']):
                    categories['business_channels'].append(link)
                elif any(keyword in combined_text for keyword in keywords['news']):
                    categories['news_channels'].append(link)
                else:
                    categories['promotional_content'].append(link)
            elif link.get('channel_type') in ['group', 'supergroup']:
                if any(keyword in combined_text for keyword in keywords['entertainment']):
                    categories['entertainment_groups'].append(link)
                else:
                    categories['promotional_content'].append(link)
            elif link.get('channel_type') == 'user':
                categories['personal_contacts'].append(link)
            else:
                # 根据可疑关键词判断
                if any(keyword in combined_text for keyword in keywords['suspicious']):
                    categories['suspicious_links'].append(link)
                else:
                    categories['promotional_content'].append(link)
        
        return categories
    
    async def cleanup(self):
        """清理资源"""
        await self.user_detector.cleanup()
        logger.info("频道链接分析器已清理")