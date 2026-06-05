from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
import uuid
from typing import Optional

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.shared.schemas import PaginatedResponse
from app.notifications import schemas, service

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("", response_model=PaginatedResponse[schemas.NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    unread: Optional[bool] = Query(None, description="true 면 미확인 알림만 조회"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """사용자의 알림 목록을 최신순으로 조회한다."""
    items, total = service.get_notifications(
        db, current_user.id, unread=unread, limit=limit, offset=offset
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.patch("/read-all", response_model=schemas.MessageResponse)
def read_all_notifications(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """사용자의 모든 미확인 알림을 읽음 처리한다."""
    count = service.mark_all_as_read(db, current_user.id)
    return {"message": f"{count}개의 알림을 읽음 처리했습니다."}


@router.patch("/{notification_id}/read", response_model=schemas.MessageResponse)
def read_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """알림을 읽음 처리한다."""
    success = service.mark_notification_as_read(db, current_user.id, notification_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="알림을 찾을 수 없습니다.")
    return {"message": "알림이 읽음 처리되었습니다."}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    """본인 소유 알림을 삭제한다."""
    success = service.delete_notification(db, current_user.id, notification_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="알림을 찾을 수 없습니다.")
    return None
