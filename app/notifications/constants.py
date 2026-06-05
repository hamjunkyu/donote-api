"""알림 타입 상수."""

from enum import Enum


class NotificationType(str, Enum):
    """발송 가능한 알림 타입. 모든 도메인은 이 값을 사용한다."""

    BUDGET_WARNING = "BUDGET_WARNING"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    GOAL_MILESTONE = "GOAL_MILESTONE"
    GOAL_ACHIEVED = "GOAL_ACHIEVED"
    SETTLEMENT_REQUEST = "SETTLEMENT_REQUEST"
    SETTLEMENT_COMPLETED = "SETTLEMENT_COMPLETED"
