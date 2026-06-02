from sqlalchemy import select, func

from app.transactions.models import Transaction
from app.settlements.models import Settlement, SettlementParticipant


def actual_spent_subquery():
    """거래의 실부담액 표현식. amount 에서 SETTLED 참여자가 부담한 금액을 차감한다.

    SETTLED 참여자만 차감한다 (PENDING 은 아직 송금받지 못한 상태라 실부담에 포함).
    CANCELLED 정산은 제외. creator 는 참여자에 포함되지 않으므로 별도 필터 불필요.
    정산이 없거나 SETTLED 참여자가 없으면 실부담액은 amount 와 같다.
    """
    settled_sum = (
        select(func.coalesce(func.sum(SettlementParticipant.amount), 0))
        .join(Settlement, Settlement.id == SettlementParticipant.settlement_id)
        .where(
            Settlement.transaction_id == Transaction.id,
            Settlement.status != "CANCELLED",
            SettlementParticipant.status == "SETTLED",
        )
        .correlate(Transaction)
        .scalar_subquery()
    )
    return (Transaction.amount - settled_sum).label("actual_amount")
