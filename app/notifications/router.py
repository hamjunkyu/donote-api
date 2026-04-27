from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid
from typing import List

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.notifications import schemas, service

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=List[schemas.NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """사용자의 알림 목록을 조회한다."""
    return service.get_notifications(db, current_user.id)


@router.patch("/{notification_id}/read")
def read_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """알림을 읽음 처리한다."""
    success = service.mark_notification_as_read(db, current_user.id, notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    return {"message": "알림이 읽음 처리되었습니다."}
