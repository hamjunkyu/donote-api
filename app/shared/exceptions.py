"""도메인 예외.

서비스 계층은 HTTP 를 모르고 도메인 규칙 위반을 예외로 던진다.
main.py 의 전역 핸들러가 status_code + {"detail": ...} 응답으로 변환한다
(FastAPI HTTPException 과 동일한 응답 형식 유지).
"""


class DomainException(Exception):
    """도메인 규칙 위반. 전역 핸들러가 HTTP 응답으로 변환한다."""

    status_code: int = 400
    detail: str = "잘못된 요청입니다"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class BadRequestError(DomainException):
    """잘못된 요청 (400)."""

    status_code = 400


class ConflictError(DomainException):
    """리소스 상태 충돌 (409)."""

    status_code = 409


class NotFoundError(DomainException):
    """리소스를 찾을 수 없음 (404)."""

    status_code = 404


class ForbiddenError(DomainException):
    """권한 없음 (403)."""

    status_code = 403
