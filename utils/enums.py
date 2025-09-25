# -*- coding: utf-8 -*-
"""
系统枚举常量定义
统一管理所有状态值、类型常量，确保系统一致性
"""

from enum import Enum
from typing import Dict, Optional

class MerchantStatus(Enum):
    """
    商户状态统一枚举
    5阶段商户状态管理
    """
    # 核心状态
    PENDING_SUBMISSION = "pending_submission"    # 待提交：商户已绑定但未完成信息填写
    PENDING_APPROVAL = "pending_approval"        # 待审核：信息已提交，等待管理员审批
    APPROVED = "approved"                        # 已审核：管理员审核通过，等待发布
    PUBLISHED = "published"                      # 已发布：帖子已发布到频道，商户活跃
    EXPIRED = "expired"                          # 已过期：帖子过期或商户被暂停
    
    # 遗留兼容状态（向后兼容，逐步废弃）
    ACTIVE = "active"                           # 遗留状态：等同于 PUBLISHED
    INACTIVE = "inactive"                       # 遗留状态：等同于 EXPIRED
    PENDING = "pending"                         # 遗留状态：等同于 PENDING_SUBMISSION

    @classmethod
    def normalize(cls, status: str) -> str:
        """
        将任意状态值标准化
        
        Args:
            status: 原始状态值
            
        Returns:
            标准化的状态值
        """
        legacy_status_mapping = {
            "pending": cls.PENDING_SUBMISSION.value,
            "active": cls.PUBLISHED.value,
            "inactive": cls.EXPIRED.value
        }
        return legacy_status_mapping.get(status, status)
    
    @classmethod
    def get_display_name(cls, status: str) -> str:
        """
        获取状态的中文显示名称
        
        Args:
            status: 状态值
            
        Returns:
            状态的中文显示名称
        """
        display_mapping = {
            # 状态显示
            cls.PENDING_SUBMISSION.value: "待提交信息",
            cls.PENDING_APPROVAL.value: "待审核",
            cls.APPROVED.value: "已审核",
            cls.PUBLISHED.value: "已发布",
            cls.EXPIRED.value: "已过期",
            
            # 遗留兼容显示
            cls.ACTIVE.value: "活跃",
            cls.INACTIVE.value: "暂停",
            cls.PENDING.value: "待审核"
        }
        return display_mapping.get(status, status)
    
    @classmethod
    def get_badge_class(cls, status: str) -> str:
        """
        获取状态对应的CSS徽章样式类
        
        Args:
            status: 状态值
            
        Returns:
            CSS徽章样式类名
        """
        badge_mapping = {
            # 状态样式
            cls.PENDING_SUBMISSION.value: "badge-warning",
            cls.PENDING_APPROVAL.value: "badge-info",
            cls.APPROVED.value: "badge-primary",
            cls.PUBLISHED.value: "badge-success",
            cls.EXPIRED.value: "badge-error",
            
            # 遗留兼容样式
            cls.ACTIVE.value: "badge-success",
            cls.INACTIVE.value: "badge-error",
            cls.PENDING.value: "badge-warning"
        }
        return badge_mapping.get(status, "badge-secondary")
    
    @classmethod
    def is_active_status(cls, status: str) -> bool:
        """
        判断状态是否为活跃状态（可接受订单）
        
        Args:
            status: 状态值
            
        Returns:
            是否为活跃状态
        """
        active_statuses = {
            cls.PUBLISHED.value,
            cls.ACTIVE.value  # V1.0兼容
        }
        return status in active_statuses
    
    @classmethod
    def get_all_statuses(cls) -> list:
        """获取所有标准状态值列表"""
        return [
            cls.PENDING_SUBMISSION.value,
            cls.PENDING_APPROVAL.value,
            cls.APPROVED.value,
            cls.PUBLISHED.value,
            cls.EXPIRED.value
        ]
    
    @classmethod
    def get_all_v1_statuses(cls) -> list:
        """获取所有遗留兼容状态值列表"""
        return [
            cls.ACTIVE.value,
            cls.INACTIVE.value,
            cls.PENDING.value
        ]


class OrderStatus(Enum):
    """
    订单状态统一枚举
    5阶段订单状态管理
    """
    # 订单状态
    ATTEMPT_BOOKING = "尝试预约"        # 用户发起预约请求
    COMPLETED = "已完成"               # 服务已完成
    REVIEWED = "已评价"                # 用户已评价
    MUTUAL_REVIEW = "双方评价"         # 双方都已评价
    SINGLE_REVIEW = "单方评价"         # 只有一方评价
    
    @classmethod
    def get_display_name(cls, status: str) -> str:
        """获取订单状态显示名称"""
        return status  # 订单状态本身就是中文
    
    @classmethod
    def is_completed_status(cls, status: str) -> bool:
        """判断是否为已完成状态"""
        completed_statuses = {
            cls.COMPLETED.value,
            cls.REVIEWED.value,
            cls.MUTUAL_REVIEW.value,
            cls.SINGLE_REVIEW.value
        }
        return status in completed_statuses


class SystemConstants:
    """系统常量定义"""
    
    # 数据库字段命名规范
    TELEGRAM_CHAT_ID_FIELD = "telegram_chat_id"  # 统一使用此字段名
    
    # 默认值
    DEFAULT_MERCHANT_STATUS = MerchantStatus.PENDING_SUBMISSION.value
    DEFAULT_ORDER_STATUS = OrderStatus.ATTEMPT_BOOKING.value
    
    # 系统限制
    MAX_MERCHANT_NAME_LENGTH = 100
    MAX_CONTACT_INFO_LENGTH = 500
    MAX_DESCRIPTION_LENGTH = 2000


# 便捷导入别名
MERCHANT_STATUS = MerchantStatus
ORDER_STATUS = OrderStatus
CONSTANTS = SystemConstants