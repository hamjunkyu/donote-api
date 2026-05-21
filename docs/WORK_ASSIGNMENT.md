# Donote 백엔드 정리 작업 분담

> 중간 발표(2026-05-14) 이후 코드 정리 및 spec 위반 픽스 작업. 백엔드 완성 → 프론트엔드 일괄 동기화 순서.

## 🚦 작업 진행 방법

각 PR 작업 시 다음 순서로 진행:

1. 이 문서의 본인 섹션 정독 — 핵심 결정사항, 작업 항목, 함정, 검증 시나리오 확인
2. [FEATURE_SPEC.md](FEATURE_SPEC.md) 의 관련 도메인 섹션 읽기 — spec 의도 파악
3. "핵심 결정 사항 17개" 섹션 확인 — 본인 PR 영향 결정사항 체크
4. "공통 함정 / Edge Cases" 섹션 확인 — 본인 PR 관련 함정 체크
5. 기존 코드 읽기 — 본인 PR 의 "참조 파일" 들 현재 상태 파악
6. 브랜치 생성 → 코드 작성 → 검증 시나리오 실행
7. PR 생성 + 리뷰

### 핵심 원칙
- **결정 사항이 우선** — 기존 코드 패턴과 다르면 결정 사항 따름
- **spec 이 final** — 코드와 다르면 spec 기준으로 수정
- **마이그레이션 동반 PR 은 추가 검증** — SQL 결과 직접 확인 후 머지

## 📋 전체 개요

- **기간**: ~1주 (각자 ~2~3.5일)
- **목표**: spec 위반 픽스 + 버그 픽스 + 확장 기능 (마일스톤/페이지네이션/Export) + 아키텍처 정리
- **워크플로우**: Issue 생략. 브랜치 → 코드 → PR → 리뷰 → 머지
- **브랜치 명명**: `feature/도메인-설명` 또는 `fix/도메인-설명`

## 🎯 작업 분배 요약

| 담당 | PR | 시간 | 영역 |
|---|---|---|---|
| **함준규** | PR1, PR10, PR14, PR16 | ~3.5일 | Settlement + 공유 헬퍼 + 트랜잭션 경계 + 아키텍처 |
| **김동준** | PR2, PR4, PR11 | ~2일 | Goals + Budget + Pagination/필터 |
| **베키** | PR3, PR12, PR13, PR15 | ~2일 | Transactions + Export + API 일관성 + DB constraint |
| **김민수** | PR5, PR6, PR7, PR8, PR9 | ~2일 | CSV + Auth + Categories + Notifications + migration |

## 🔗 PR 의존성

- **베키 PR3 거래 통합** → 김동준 **PR4 예산**, **PR11 페이지네이션** 의존
- **함준규 PR1 정산 통합** → 함준규 **PR10 P1** 의존 (sequential, 본인이 처리)
- 마지막: **PR13 API 일관성** (베키) — 모든 PR 머지 후
- 마지막: **PR16 Eager loading + 도메인 예외** (함준규) — 모든 PR 머지 후
- 최종: **pytest 통합 테스트** — 각자 본인 도메인

---

## 🔑 핵심 결정 사항 (작업 시 반드시 참조)

상세는 [FEATURE_SPEC.md](FEATURE_SPEC.md) 참조.

### 정산 도메인
1. **Creator NOT in participants** — 정산 생성자는 SettlementParticipant 테이블에 추가하지 않음. 본인 몫은 implicit (`total - SUM(participants)`)
2. **split_equal 알고리즘**: `per_person = total // (N+1)` (N=참여자수). 나머지는 creator 가 흡수
3. **SettlementParticipant.amount**: Numeric(12,2) → **Numeric(12,0)** (정수만)
4. **실부담액 = SETTLED-based**: `actual_amount = transaction.amount - SUM(SETTLED 참여자 amount)` (PENDING 차감 안 함)
5. **정산 수정 차단**: SETTLED 참여자 amount/제거 차단 (revert 먼저), COMPLETED 정산 전체 수정 차단

### 거래 도메인
6. **거래 amount**: `int = Field(gt=0)`, `type: Literal["INCOME","EXPENSE"]`
7. **거래 삭제 자유**: 연결된 정산은 FK CASCADE 자동 삭제
8. **거래 amount 수정 시**: settlement.total_amount + 참여자 amount 자동 재분배 (EQUAL) / 0으로 reset (CUSTOM)

### 예산 / 알림
9. **budget amount = `Field(gt=0)`** (0 거부)
10. **알림 플래그 재발화**: 임계값 아래 떨어지면 flag False 리셋
11. **카테고리별 예산 알림**: overall 외 카테고리도 80%/100% 알림

### 목표 (Goals)
12. **G3**: ON_TRACK/BEHIND는 DB persist 안 함 (PERSIST_STATES = {IN_PROGRESS, ACHIEVED, EXPIRED, CANCELLED})
13. **target_date == today + 미달성** → BEHIND
14. **마일스톤 알림**: 25/50/75/100% 도달 시 GOAL_MILESTONE 알림 발생

### 카테고리
15. **시스템 카테고리 15개로 확장**:
   - 지출(11): 식비, 카페/간식, 교통, 생활/마트, 쇼핑, 주거/통신, 의료/건강, 문화/여가, 교육, 경조사/회비, 기타
   - 수입(4): 급여/알바, 용돈, 금융소득, 기타

### API
16. **API prefix `/api/` 통일** (PR13)
17. **Trailing slash 제거** — 모든 `@router.X("/")` → `@router.X("")` (PR13)

---

## 👤 함준규 (~3.5일)

### PR1: Settlement 통합 (1~1.5일)

**목표**: 정산 도메인의 spec 위반/버그 11가지를 한 번에 정리.

spec [6](FEATURE_SPEC.md#L399) 정산 / [6.4](FEATURE_SPEC.md#L573) 실부담액 참조.

**핵심 결정사항 적용** (반드시):
- 결정 1, 2, 3, 4, 5 (정산 도메인 전체)
- 결정 7 (거래 삭제 자유 — FK CASCADE)

**작업 항목**:
- [ ] **FK CASCADE 마이그레이션** (2 곳):
  - settlement_participants.settlement_id
  - settlements.transaction_id
- [ ] **SettlementParticipant.amount** Numeric(12,2) → Numeric(12,0) 마이그레이션
- [ ] **create_settlement**: creator 자동 추가 코드 제거 + 검증 추가
  - 본인 추가 불가 (participant.user_id == current_user.id 거부)
  - 같은 user_id 중복 추가 불가
  - 내 몫 < 0 시 400
- [ ] **split_equal 재작성**: 아래 알고리즘
- [ ] **read 권한 검증** (4 endpoints): view_settlement, view_balance, get_debts, get_participants — service에서 creator_id 체크
- [ ] **write 권한 검증**: split_equal, split_custom — current_user 전달 + creator_id 체크
- [ ] **calculate_debts**: response에 participant_id 추가 (S3). creator name 은 User 테이블에서 직접 조회 (creator 가 participants에 없으므로)
- [ ] **빈 참여자 mark_complete 가드** — participants 0개면 400
- [ ] **자동 COMPLETED 전환** — mark_participant_settled 끝에 전원 SETTLED 체크
- [ ] **DELETE /api/settlements/{sid}/participants/{pid}** 엔드포인트 추가
- [ ] **정산 수정 차단** (해석 iii):
  - SETTLED 참여자: amount 수정/제거 차단
  - COMPLETED 정산: 모든 수정 차단
- [ ] **GET /api/settlements?role=creator|participant** 필터 추가
- [ ] **회원 참여자에게 SETTLEMENT_REQUEST 알림** — add_participant 시 user_id 있으면 알림 생성
- [ ] **response_model 14개 채우기** — 정산 라우터의 모든 endpoint

**복잡 알고리즘 힌트**:

**split_equal** (creator implicit math):
```
total = settlement.total_amount
N = len(participants)        # creator 제외 인원
n_total = N + 1              # creator 포함 인원
per_person = total // n_total

각 participant.amount = per_person
creator 몫 = total - (N × per_person)  ← DB 저장 안 함, 계산만
```
예: 100 / (본인 + 친구2) → per_person=33, 친구 각 33, 본인 implicit 34.

**FK CASCADE 마이그레이션**:
- `op.drop_constraint(...)` + `op.create_foreign_key(..., ondelete='CASCADE')`
- 두 FK 모두 CASCADE: `settlement_participants.settlement_id`, `settlements.transaction_id`

**구현 시 함정**:
- **F1**: SettlementParticipant.amount 컬럼 타입 변경 시 기존 소수값 반올림됨 → **Dev DB 와이프 권장**
- **E-A4**: calculate_debts 의 "creator" 폴백 문자열 — creator 가 participants 에 없으므로 `db.query(User).filter(User.id == settlement.creator_id).first().name` 으로 조회
- **알림 의존성**: SETTLEMENT_REQUEST 알림 emit 위해 `create_notification` 호출 — PR8 (Notifications 확장) 과 무관, 기존 함수 사용

**검증 시나리오**:
1. 본인 참여자 추가 시도 → 400
2. 100원 거래 + 친구 2명 정산 → split_equal → 각 33원, 본인 implicit 34원
3. 권한 우회 시도 (다른 사용자 settlement_id) → 403/404
4. 첫 친구 SETTLED → 정산 IN_PROGRESS
5. 두 번째 친구 SETTLED → 정산 자동 COMPLETED
6. COMPLETED 정산 수정 시도 → 400
7. SETTLED 참여자 amount 수정 시도 → 400 (revert 먼저)
8. 거래 삭제 → 정산 + 참여자 자동 cascade 삭제

📂 **참조 파일**:
- `app/settlements/` 전체
- `alembic/versions/3803b7878290_create_initial_tables.py:84-108` — 초기 마이그레이션
- `app/auth/models.py` — User 모델 (creator name 조회)
- `app/notifications/service.py:31-41` — create_notification

---

### PR10: P1 Option B+ (1일, PR1 의존)

**목표**: spec [4.1](FEATURE_SPEC.md#L246) Statistics / [5.1](FEATURE_SPEC.md#L319) Budget 의 "실부담액 기준" 픽스. 정산 결정 (creator NOT in + SETTLED-based) 정확히 반영.

**핵심 결정사항 적용**:
- 결정 1 (creator NOT in)
- 결정 4 (SETTLED-based)

**작업 항목**:
- [ ] **공유 헬퍼 `actual_spent_subquery()` 작성** in `app/transactions/helpers.py` (없으면 생성)
- [ ] **Budget 적용**: `budgets/service.py:get_budget_usage` — Transaction.amount 합산 대신 헬퍼 사용
- [ ] **Statistics 폐기 + 통일**: 기존 `_actual_amount_subquery` 폐기, 공유 헬퍼로 교체

**복잡 알고리즘 힌트**:

**actual_spent_subquery 의 핵심**:
```
actual_amount = Transaction.amount - SUM(participant.amount)
where:
  - settlement.status != "CANCELLED"
  - participant.status == "SETTLED"
  - creator 필터 불필요 (Decision A 로 creator 는 participants 에 없음)
```

SQLAlchemy 패턴: correlated subquery. `select(...).correlate(Transaction).scalar_subquery()` 사용.

**Budget 적용 시**:
- 기존: `func.sum(Transaction.amount)` 합산
- 변경: `func.sum(actual_spent_subquery())` 같은 패턴

**구현 시 함정**:
- F1 (PR1 에서 정수 통일) 후라 반올림 정책 불필요
- 통계와 예산 모두 동일 헬퍼 사용 → 일관성

**검증 시나리오**:
1. 거래 9000원 (혼자) → budget 9000 spent (정산 없음)
2. 거래 9000원 + 친구 2명 정산 (각 3000원, PENDING) → budget 여전히 9000 (PENDING 차감 안 함)
3. 친구 1명 SETTLED → budget 6000
4. 친구 2명 SETTLED → budget 3000 (자동 COMPLETED)
5. Statistics 결과도 동일

📂 **참조 파일**:
- `app/budgets/service.py:50-117` — get_budget_usage
- `app/statistics/service.py:9-23` — `_actual_amount_subquery` (폐기)
- `app/transactions/helpers.py` — 신규 생성
- `app/settlements/models.py` — SettlementParticipant.status enum

---

### PR14: 트랜잭션 경계 통합 (1시간)

**목표**: 거래 생성/수정/삭제 + 알림 발생을 단일 트랜잭션으로. partial commit 방지.

**작업 항목**:
- [ ] transactions/service.py 의 create/update/delete_transaction 트랜잭션 경계 통일
- [ ] check_and_notify_budget_threshold / check_and_notify_goal_achievement 에 commit 분리 옵션 추가 (또는 패턴 통일)

**복잡 알고리즘 힌트**:

**패턴 A (recommended)**: `db.flush()` 사용해서 ID 확보, 마지막에 한 번만 `db.commit()`:
```
db.add(transaction)
db.flush()  # commit X, ID 확보만
[알림 함수 호출 — commit X]
db.commit()  # 마지막에 한 번만
```

알림 함수 시그니처에 `commit: bool = True` 추가 → False 일 때 db.commit() 호출 안 함.

**패턴 B**: try/except + db.rollback() — 단순하지만 트랜잭션 의도 덜 명확.

**구현 시 함정**:
- 기존 알림 함수 (check_and_notify_*) 가 내부적으로 commit 호출. 그대로 두면 트랜잭션 분리됨
- create_notification 도 commit 호출 — 동일하게 처리 필요

**검증 시나리오**:
1. 정상 시나리오 동작 확인
2. 알림 함수에서 강제 raise 발생 → 거래도 rollback (DB 에 row 없음 확인)

📂 **참조 파일**:
- `app/transactions/service.py`
- `app/budgets/service.py:120-150` — check_and_notify_budget_threshold
- `app/goals/service.py:348-380` — check_and_notify_goal_achievement
- `app/notifications/service.py:31-41` — create_notification

---

### PR16: Eager loading + 도메인 예외 클래스 (3시간)

**모든 PR 머지 후 마지막 정리 작업**.

**목표**: 코드 일관성 ↑. N+1 쿼리 패턴 정리 + HTTPException 직접 raise 대신 도메인 예외 클래스.

**작업 항목**:
- [ ] **Eager loading 적용** (relationship + lazy strategy):
  - Transaction → Category (`lazy="joined"`)
  - Settlement → participants (`lazy="selectin"`)
- [ ] **도메인 예외 클래스** in `app/shared/exceptions.py`:
  - DomainException 베이스 + 구체 클래스들 (GoalNotFound, CategoryInUse, SettlementCompleted, SettledParticipantUnchangeable, NotSettlementOwner 등)
- [ ] **전역 핸들러 등록** in main.py
- [ ] **라우터 일괄 변경**: HTTPException → 도메인 예외

**복잡 알고리즘 힌트**:

**도메인 예외 패턴**:
```python
class DomainException(Exception):
    status_code = 500
    detail = "도메인 에러"

class NotFoundError(DomainException):
    status_code = 404
class UnauthorizedError(DomainException):
    status_code = 403
class ValidationError(DomainException):
    status_code = 400
class ConflictError(DomainException):
    status_code = 409

# 구체 클래스
class GoalNotFound(NotFoundError):
    detail = "목표를 찾을 수 없습니다"
```

**전역 핸들러**: `@app.exception_handler(DomainException)` 로 등록, JSONResponse 반환.

**Eager loading**: SQLAlchemy `relationship()` + `lazy` 파라미터. `lazy="joined"` (1:1, JOIN) vs `lazy="selectin"` (1:N, 추가 쿼리).

**검증 시나리오**:
1. 도메인 예외 raise 시 응답 형식 일관 (`{"detail": "..."}`)
2. EXPLAIN ANALYZE 로 JOIN 으로 1 쿼리 처리 확인
3. 모든 endpoint 회귀 테스트 (예외 변경으로 break 없는지)

📂 **참조 파일**:
- `app/shared/exceptions.py` — 신규 생성
- `app/main.py` — 핸들러 등록
- 모든 router.py — HTTPException → 도메인 예외 변경
- `app/transactions/models.py`, `app/settlements/models.py` — relationship 추가

---

## 👤 김동준 (~2일)

### PR2: Goals 통합 (1일)

**목표**: 목표 도메인 4개 critical bug (G2, G3, G4, G5) + E-A3 + 마일스톤 알림(E1) + N+1 helper 한 PR로.

spec [8](FEATURE_SPEC.md) 저축 목표 참조.

**핵심 결정사항 적용**:
- 결정 12 (G3 DB persist 차단)
- 결정 13 (E-A3 target_date=today → BEHIND)
- 결정 14 (마일스톤 알림 25/50/75/100)
- 결정 10 (알림 재발화)

**작업 항목**:
- [ ] **G2 픽스 (프론트엔드)**: `donote-frontend/src/pages/goals.js:112` `INCOME` → `EXPENSE` (한 줄)
- [ ] **G3 픽스 (DB persist 차단)**: ON_TRACK/BEHIND 는 응답만, DB 저장 X
- [ ] **G4 픽스 (GoalResponse 확장)**: current_amount, progress_percentage, remaining_amount, status (computed) 추가
- [ ] **G5 픽스 (status filter 서비스 단)**: get_goals 에서 computed status 로 필터링
- [ ] **E-A3 픽스**: determine_status 의 `total_days <= 0` → `BEHIND` (현재 `ON_TRACK`)
- [ ] **N+1 helper 추출**: `_goal_progress_subquery()` 작성, 5곳에 적용
- [ ] **마일스톤 알림 E1**:
  - Goal 모델에 is_25_notified, is_50_notified, is_75_notified 컬럼 3개 추가 (마이그레이션)
  - check_and_notify_goal_achievement 확장: 25/50/75% 도달 시 GOAL_MILESTONE 알림
- [ ] **알림 플래그 재발화 (결정 10)**: 임계값 아래 떨어지면 플래그 False 리셋

**복잡 알고리즘 힌트**:

**PERSIST_STATES 가드** (G3 fix):
```
PERSIST_STATES = {IN_PROGRESS, ACHIEVED, EXPIRED, CANCELLED}

if computed_status in PERSIST_STATES and goal.status != computed_status:
    goal.status = computed_status
    db.commit()
# ON_TRACK/BEHIND 는 DB 저장하지 않음
```

**마일스톤 + 재발화 (4 단계 임계값)**:
```
ratio = current / target

for threshold, flag in [(0.25, "is_25_notified"), (0.5, "is_50_notified"), (0.75, "is_75_notified"), (1.0, "is_achieved_notified")]:
    if ratio >= threshold:
        if not getattr(goal, flag):
            # 알림 발생 + 플래그 True
    else:
        # 임계값 아래 → 플래그 False (재발화 가능)

100% 달성 시 추가: status=ACHIEVED, achieved_at 기록
100% 아래 떨어지면: status=IN_PROGRESS, achieved_at=None 복귀
```

**N+1 helper (correlated subquery)**:
```python
def _goal_progress_subquery():
    """Goal.id 별 current_amount 계산하는 correlated subquery."""
    return (
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(
            Transaction.user_id == Goal.user_id,
            Transaction.category_id == Goal.category_id,
            Transaction.type == "EXPENSE",
            Transaction.created_at >= Goal.created_at,
        )
        .correlate(Goal)
        .scalar_subquery()
    )
```
사용: `db.execute(select(Goal, progress_subq.label("current_amount")).where(...))`.

**구현 시 함정**:
- **F2**: 모든 *_notified 플래그는 임계값 아래 떨어질 때 False 리셋 필요 (재발화)
- **F7**: get_goals N+1 — helper subquery 사용 필수
- **결정 11과 통일**: 알림 재발화 로직은 PR4 (Budget) 와 동일 패턴이어야 함

**검증 시나리오**:
1. 목표 100만원 생성 → 진행률 0%
2. 25만원 저축 거래 → 25% 알림 + ON_TRACK
3. 50만원 더 → 50% 알림
4. 50만원 더 → 100% 달성 + GOAL_ACHIEVED + status=ACHIEVED
5. 거래 50만원 삭제 → 75/100 플래그 리셋, status=IN_PROGRESS 복귀
6. 다시 50만원 → 75%, 100% **재알림**
7. `/api/goals/{id}/progress` 호출 → ON_TRACK/BEHIND 정상 반환 (500 crash 없음)
8. 목록 조회 → current_amount, progress_percentage 응답에 포함
9. `/api/goals/?status=BEHIND` → 시간 진행률 vs 진행률 비교해서 BEHIND 인 것만 반환

📂 **참조 파일**:
- `app/goals/` 전체
- `app/notifications/service.py` — GOAL_MILESTONE / GOAL_ACHIEVED 알림 emit
- `donote-frontend/src/pages/goals.js:112` — G2 픽스

---

### PR4: Budget 통합 (0.5일, PR3 의존)

**목표**: 예산 도메인의 spec 위반/검증/알림 일괄 픽스.

spec [5](FEATURE_SPEC.md#L317) 예산 참조.

**핵심 결정사항 적용**:
- 결정 9 (amount Field gt=0)
- 결정 10 (재발화)
- 결정 11 (카테고리별 알림)

**작업 항목**:
- [ ] amount: `Field(gt=0)` (현재 `ge=0` → 변경, 마이그레이션 불필요)
- [ ] category_id 소유권 검증 in upsert_budget (본인/시스템 카테고리만)
- [ ] 카테고리별 알림 추가 — overall + 카테고리 예산 모두 80%/100% 체크
- [ ] 임계값 아래 복귀 시 플래그 리셋 (재발화)
- [ ] 금액 변경 시 플래그 리셋 (upsert 의 update branch)

**복잡 알고리즘 힌트**:

**임계값 + 재발화 로직** (`_check_threshold_with_reset` 헬퍼 권장):
```
for budget in (overall + 카테고리별 budgets):
    percentage = usage.percentage
    
    # 100% EXCEEDED
    if percentage >= 100:
        if not budget.is_exceeded_notified:
            create_notification(BUDGET_EXCEEDED)
            budget.is_exceeded_notified = True
    else:
        # 100% 아래로 떨어지면 리셋 (재발화 가능)
        if budget.is_exceeded_notified:
            budget.is_exceeded_notified = False
    
    # 80% WARNING — 동일 패턴
```

**금액 변경 시**: `upsert_budget` 의 update 분기에서:
```
budget.amount = amount
budget.is_warning_notified = False
budget.is_exceeded_notified = False
```

**구현 시 함정**:
- **F2**: PR2 마일스톤 재발화 와 패턴 통일
- `check_and_notify_budget_threshold` 가 PR3 (B1 trigger fix) 에서 delete_transaction 에도 호출됨 → 정상 동작 확인

**검증 시나리오**:
1. amount=0 예산 생성 → 422
2. 다른 사용자 category_id 사용 → 403
3. 식비 예산 10만원 설정, 8만원 거래 → 80% + 카테고리별 WARNING 알림
4. 8만원 거래 삭제 → 0% 복귀, flag 리셋
5. 8만원 다시 추가 → 다시 WARNING 알림 (재발화)
6. 예산 10만원 → 20만원 변경 → flag 리셋
7. overall 예산도 별개로 동작 확인

📂 **참조 파일**:
- `app/budgets/` 전체
- `app/categories/models.py` — 소유권 검증
- `app/notifications/service.py` — 알림 emit

---

### PR11: E3 Pagination + Theme 2 필터 (1일, PR3 의존)

**목표**: spec [2.3](FEATURE_SPEC.md#L184) 거래 조회의 페이지네이션 + 필터 + description 검색 구현.

**작업 항목**:
- [ ] `GET /api/transactions` 쿼리 파라미터 확장:
  - `limit` (default 20, max 100), `offset` (default 0)
  - `type=INCOME|EXPENSE`
  - `category_id=UUID`
  - `date_from`, `date_to` (YYYY-MM-DD)
  - `amount_min`, `amount_max`
  - `keyword` (description ILIKE 검색)
- [ ] 응답: `TransactionListResponse{items, total, limit, offset}`
- [ ] 정렬: transaction_date DESC, created_at DESC

**구현 힌트**:
- FastAPI `Query` 로 쿼리 파라미터 정의 + Literal/UUID 타입 검증
- 필터 조건은 쿼리에 `.filter()` 체이닝
- `query.count()` 로 total (필터 후, pagination 전)
- description ILIKE: `Transaction.description.ilike(f"%{keyword}%")` — NULL 자동 제외됨
- Category JOIN (T2 fix 와 같은 패턴) 으로 category_name 응답 포함

**구현 시 함정**:
- T2 (PR3 의 category_name JOIN) 와 같은 패턴 사용 → 코드 일관성
- 인덱스 활용 위해 PR15 (composite 인덱스) 머지 후가 좋음 (선택)

**검증 시나리오**:
1. 거래 100건 → `?limit=20` → 20개, total=100
2. `?type=EXPENSE` → EXPENSE 만
3. `?keyword=점심` → description 에 "점심" 포함 거래만
4. 복합 필터 적용
5. `?keyword=NONE` → `{items: [], total: 0}` 응답

📂 **참조 파일**:
- `app/transactions/router.py`, service.py, schemas.py, models.py
- `app/categories/models.py` — Category JOIN

---

## 👤 베키 (~2일)

### PR3: Transactions 통합 (0.5~1일)

**목표**: 거래 도메인의 핵심 픽스 (amount precision, B1 trigger, T2 category_name, 정산 cascade, 검증).

**핵심 결정사항 적용**:
- 결정 6 (amount int + Literal)
- 결정 7 (delete 자유 — FK CASCADE)
- 결정 8 (amount cascade update)

**작업 항목**:
- [ ] **스키마 강화**:
  - amount: `int = Field(gt=0)`
  - type: `Literal["INCOME","EXPENSE"]`
- [ ] **category_id 소유권 검증** in create_transaction
- [ ] **delete_transaction**: 정산 차단 코드 **제거** (FK CASCADE 가 자동 처리)
- [ ] **delete_transaction**: budget/goal 알림 트리거 추가 (B1)
- [ ] **update_transaction**: amount 변경 시 settlement 연동 (아래 알고리즘)
- [ ] **TransactionResponse 에 category_name 추가** — Category JOIN (T2)

**복잡 알고리즘 힌트**:

**update_transaction amount cascade** (spec 2.3):
```
old_amount = transaction.amount
transaction.amount = new_amount
db.commit()

if old_amount != new_amount:
    settlement = 해당 거래의 settlement (status != CANCELLED)
    if settlement:
        settlement.total_amount = new_amount
        
        if EQUAL:
            # 자동 재분배 (creator 나머지 흡수)
            n_total = len(participants) + 1
            per_person = new_amount // n_total
            for p in participants:
                if p.status != "SETTLED":  # SETTLED 는 유지 (송금 완료 사실)
                    p.amount = per_person
        elif CUSTOM:
            for p in participants:
                if p.status != "SETTLED":
                    p.amount = 0  # 사용자가 재입력해야
```

**Category JOIN** (T2 fix):
```python
rows = db.query(Transaction, Category.name.label("category_name")).join(
    Category, Category.id == Transaction.category_id
).filter(...).all()
```

**구현 시 함정**:
- **F6**: T2 는 dict lookup 아닌 SQL JOIN 으로 처리 (N+1 회피)
- **결정 8**: SETTLED 참여자 amount 는 변경하지 않음 (송금 완료 사실 보존)
- delete_transaction 의 B1 trigger: transaction 삭제 후 호출. transaction.transaction_date / category_id 미리 추출 필요

**검증 시나리오**:
1. amount=0 거래 생성 → 422
2. amount=1.5 (소수) → 422 (int 강제)
3. type="WRONG" → 422 (Literal 검증)
4. 다른 사용자 category 사용 → 403
5. 거래 조회 시 category_name 포함
6. 거래 삭제 → 정산 cascade 자동 삭제 (PR1 의 CASCADE 가 처리)
7. 거래 삭제 후 budget 80% 아래로 떨어지면 → 알림 플래그 리셋 (PR4 와 연동)
8. EQUAL 정산의 거래 amount 5000 → 10000 변경 → settlement.total + 참여자 재분배 확인

📂 **참조 파일**:
- `app/transactions/` 전체
- `app/categories/models.py` — Category JOIN
- `app/settlements/service.py` — amount cascade 시 참조
- `app/budgets/service.py`, `app/goals/service.py` — B1 trigger 호출

---

### PR13: API 일관성 (0.5일, 가장 마지막)

**모든 도메인 PR 머지 후 진행**.

**핵심 결정사항 적용**:
- 결정 16 (`/api/` 통일)
- 결정 17 (no trailing slash)

**작업 항목**:
- [ ] `app/transactions/router.py:13` prefix `/transactions` → `/api/transactions`
- [ ] 모든 라우터의 `@router.X("/")` → `@router.X("")` (trailing slash 제거)
  - 영향: transactions, settlements, goals, categories
  - budgets, notifications 는 이미 slash 없음
- [ ] **response_model 누락 전부 채우기** — 정산/다른 도메인 누락분
- [ ] **OpenAPI 메타데이터 보강**: summary, description, examples

**구현 힌트**:
- `grep -rn '@router\.[a-z]*("/")' app/*/router.py` 로 영향 위치 확인
- `/{id}` 같은 path param 있는 endpoint 는 변경 X
- response_model 은 각 도메인 schemas.py 의 기존 클래스 활용

**검증 시나리오**:
1. Swagger UI 에서 모든 endpoint `/api/...` 시작 + no trailing slash
2. transactions 호출 시 `/api/transactions` 정상, `/transactions` 는 404
3. 모든 응답에 schema 명시

📂 **참조 파일**:
- 모든 도메인 router.py — 패턴 변경
- 모든 도메인 schemas.py — response_model 정의

---

### PR12: E4 데이터 Export (0.5일)

**목표**: 거래 데이터 CSV 다운로드. import 포맷과 round-trip 가능.

**작업 항목**:
- [ ] `GET /api/transactions/export` 엔드포인트 (CSV)
- [ ] CSV 형식: 날짜, 유형, 카테고리, 금액, 메모 (import 와 동일 컬럼)
- [ ] UTF-8 BOM (Excel 한글 호환)
- [ ] 카테고리는 이름 문자열 (UUID X)
- [ ] 천단위 콤마 없음 (raw number)
- [ ] (선택) `?date_from=&date_to=` 필터링

**구현 힌트**:
- FastAPI `StreamingResponse` + `media_type="text/csv"` 사용
- `Content-Disposition: attachment; filename="..."` 헤더로 다운로드 강제
- CSV 헤더: `날짜,유형,카테고리,금액,메모`
- type 매핑: `{"INCOME": "수입", "EXPENSE": "지출"}` (import 와 동일)

**구현 시 함정**:
- import 포맷과 정확히 일치해야 round-trip 안전 (`csv_import/service.py:22-40` 컬럼 헤더 확인)
- BOM 누락 시 Excel 에서 한글 깨짐

**검증 시나리오**:
1. 거래 5개 생성 → export → CSV 다운로드
2. Excel 열어서 한글 정상 표시
3. 같은 CSV 를 `POST /api/import/csv` 로 재업로드 → 중복 0개 (round-trip 안전)

📂 **참조 파일**:
- `app/transactions/router.py` — 새 엔드포인트
- `app/csv_import/service.py:22-40` — import 포맷 확인

---

### PR15: DB constraint + 인덱스 (1시간)

**목표**: DB 레벨 안전망 (CHECK constraint) + 자주 쿼리되는 컬럼 인덱스.

**작업 항목**:
- [ ] **CHECK constraint** 마이그레이션:
  - `transactions.amount > 0`
  - `budgets.amount > 0`
  - `goals.target_amount > 0`
  - `settlement_participants.amount >= 0`
- [ ] **Composite 인덱스** 마이그레이션:
  - `Transaction(user_id, transaction_date)`
  - `Transaction(category_id)`
  - `Goal(user_id, category_id)`
  - `Settlement(creator_id)`
  - `Settlement(transaction_id)`
  - `Notification(user_id, is_read)`
  - `SettlementParticipant(settlement_id)`

**구현 힌트**:
- `op.create_check_constraint(name, table, condition)` 패턴
- `op.create_index(name, table, columns)` 패턴
- 모두 순수 추가 (rollback 안전)

**구현 시 함정**:
- 기존 DB 에 위반 데이터 (amount=0 등) 있으면 CHECK 추가 실패 → 사전 정리 또는 Dev DB 와이프
- 학기 프로젝트는 작은 DB 라 인덱스 성능 차이 미미 (production 패턴 보여주기 목적)

**검증 시나리오**:
1. 마이그레이션 성공 (에러 없음)
2. psql 로 amount=0 직접 INSERT 시도 → CHECK 위반 에러
3. EXPLAIN ANALYZE 로 인덱스 사용 확인

📂 **참조 파일**:
- `alembic/versions/` — 새 마이그레이션 생성
- 각 도메인 models.py — 모델 구조 확인

---

## 👤 김민수 (~2일)

### PR5: CSV Import 정리 (0.5일)

**목표**: CSV import 의 보안/검증/UX 정리. spec [7](FEATURE_SPEC.md#L577) 참조.

**핵심 결정사항 적용**:
- 결정 9 (CSV amount=0 skip+errors)

**작업 항목**:
- [ ] `except Exception` 제거 — 일반화된 메시지로 (stacktrace 노출 X)
- [ ] amount=0 행 → errors 리스트에 추가 + 저장 skip
- [ ] 파일 크기 5MB 제한 (request 단계에서 거부)
- [ ] 1000행 제한 (spec 7.1)
- [ ] 임포트 끝에 budget/goal 알림 트리거 (영향받은 날짜/카테고리 별)

**구현 힌트**:
- 파일 크기: `await file.read()` 후 `len(content) > MAX_FILE_SIZE` 검사 → 400 응답
- 행 수: 파싱 전 `content.count("\n") > 1000` 또는 파싱 시 행 카운트
- amount=0 처리: `process_import_batch` 안에서 amount <= 0 인 행 건너뛰고 result.errors 에 메시지 추가
- 알림 트리거: process_csv_import 끝에 `affected_dates` / `affected_categories` 수집 후 일괄 호출

**구현 시 함정**:
- except Exception 제거 후에도 ValueError (예: 알려진 검증 실패) 는 400 으로 핸들. 그 외 예외는 FastAPI 가 500 처리
- 잘못된 인코딩 시도 → 400 응답 (UnicodeDecodeError 처리)

**검증 시나리오**:
1. 6MB 파일 → 400 응답
2. 1001행 CSV → 400 응답
3. amount=0 행 포함 CSV → 정상 행만 import, errors 에 amount=0 행 명시
4. 같은 파일 두 번 업로드 → duplicate_count = total_rows
5. 예산 임계값 도달하는 거래 포함 CSV → import 후 BUDGET_WARNING 알림

📂 **참조 파일**:
- `app/csv_import/` 전체
- `app/budgets/service.py`, `app/goals/service.py` — 알림 트리거 호출

---

### PR6: Auth 정리 (0.5일)

**목표**: 인증 도메인 보안 보강 + 누락 기능 (deactivate).

**작업 항목**:
- [ ] `get_current_user` 에 `uuid.UUID()` try/except 추가 (E-A1)
- [ ] `refresh` 엔드포인트에 `user.is_active` 체크 추가
- [ ] Deactivate 엔드포인트 추가: `PATCH /auth/me/deactivate`

**구현 힌트**:
- E-A1: `uuid.UUID(user_id_str)` 호출 시 `ValueError` / `TypeError` 발생 → 401 응답
- refresh: db 에서 user 조회 후 `user.is_active` 확인 → 비활성이면 401
- deactivate: `current_user.is_active = False`, `current_user.deactivated_at = datetime.utcnow()`, 모든 refresh token 무효화 (`delete_all_refresh_tokens` 호출)

**구현 시 함정**:
- User 모델에 `is_active`, `deactivated_at` 컬럼 존재 확인 (없으면 마이그레이션 추가)
- access token 은 deactivate 후에도 만료 전까진 동작 (30분). 즉시 차단 효과는 제한적

**검증 시나리오**:
1. 비활성 사용자 refresh token 시도 → 401
2. 조작된 access token (잘못된 uuid 형식) → 401 (500 아님)
3. `PATCH /auth/me/deactivate` 호출 → 응답 OK + user.is_active=False
4. deactivate 후 refresh 시도 → 401

📂 **참조 파일**:
- `app/auth/` 전체
- 특히 `app/auth/dependencies.py:62` — uuid 변환 위치
- `app/auth/models.py` — User 모델 (is_active 컬럼 확인)

---

### PR7: Categories 정리 (0.5~1일)

**목표**: 카테고리 중복 차단 + 시스템 카테고리 spec 일치.

**핵심 결정사항 적용**:
- 결정 15 (시스템 카테고리 15개)

**작업 항목**:
- [ ] **UNIQUE constraint** 마이그레이션: `(user_id, name, type)` 복합 키
- [ ] **시스템 카테고리 15개로 확장** — `init_default_categories` 수정
- [ ] Dev DB 와이프 후 lifespan 자동 시드 (idempotent 동작 확인)

**구현 힌트**:
- UNIQUE 컬럼 조합: `(user_id, name, type)` 이 권장 — "기타" 가 EXPENSE/INCOME 양쪽 있어서 (name, type) 같이 unique 해야 함
- `init_default_categories` 가 idempotent 해야 함 — 이미 있으면 skip 로직 추가
- 15개 카테고리 (지출 11 + 수입 4) 는 결정 15 의 리스트 그대로

**구현 시 함정**:
- `(user_id, name)` 만 unique 로 잡으면 같은 사용자가 "기타" EXPENSE + "기타" INCOME 두 개 못 만듦. 결정 D 의 spec 은 "기타" 가 양쪽 있음. → (user_id, name, type) 복합 키 필요
- 시스템 카테고리는 user_id IS NULL. PostgreSQL 의 기본 UNIQUE 는 NULL 다중 허용. (name, type) 만 unique 한 partial index 추가 검토 (선택)
- init 시 기존 카테고리 있는지 SELECT 후 INSERT — idempotent

**검증 시나리오**:
1. Dev DB 와이프 + alembic upgrade head + 서버 시작 → 15개 자동 시드
2. 같은 이름 + 같은 type 카테고리 생성 시도 → 409/422
3. "기타" EXPENSE / "기타" INCOME 동시 존재 확인 (다른 type 이라 OK)
4. 서버 두 번 재시작 → 카테고리 중복 안 생성 (idempotent)

📂 **참조 파일**:
- `app/categories/` 전체
- 특히 `app/categories/service.py:10-34` — init_default_categories
- `alembic/versions/` — UNIQUE 마이그레이션

---

### PR8: Notifications 확장 (0.5일)

**목표**: 알림 도메인의 누락 엔드포인트 3개 추가.

**작업 항목**:
- [ ] `PATCH /api/notifications/read-all` — 사용자의 모든 미확인 알림 일괄 읽음 처리
- [ ] `GET /api/notifications?unread=true` — 미확인 필터
- [ ] `DELETE /api/notifications/{id}` — 개별 삭제 (하드)

**구현 힌트**:
- read-all: `UPDATE notifications SET is_read=true WHERE user_id=:uid AND is_read=false`
- unread filter: 기존 list 에 쿼리 파라미터 추가, where 조건에 `is_read=false` 추가
- 삭제: 본인 알림 확인 후 DELETE

**검증 시나리오**:
1. 알림 5개 생성 → `GET /api/notifications` → 5개
2. `?unread=true` → 미확인만
3. `PATCH /api/notifications/read-all` → 모두 읽음
4. `DELETE /api/notifications/{id}` → 1개 삭제
5. 다른 사용자 알림 삭제 시도 → 404

📂 **참조 파일**:
- `app/notifications/` 전체

---

### PR9: settlement_status migration cleanup (30분)

**목표**: 마이그레이션 파일의 enum 값 (`IN_PROGRESS`) 과 코드 (`PENDING`) 불일치 정리.

**작업 항목**:
- [ ] 새 마이그레이션: `ALTER TYPE settlement_status RENAME VALUE 'IN_PROGRESS' TO 'PENDING'`
- [ ] (선택) initial migration 파일 [3803b7878290:90](alembic/versions/3803b7878290_create_initial_tables.py#L90) 의 `IN_PROGRESS` → `PENDING` 도 함께 수정 (fresh install history correctness)
- [ ] downgrade 도 작성

**구현 힌트**:
- `alembic revision -m "..."` 으로 새 파일 생성
- `op.execute("ALTER TYPE ...")` 사용

**검증 시나리오**:
1. `alembic upgrade head` 실행 성공
2. `psql -c "SELECT unnest(enum_range(NULL::settlement_status))"` → PENDING, COMPLETED, CANCELLED
3. 새 환경 (DB 와이프) → 처음부터 PENDING (initial migration 도 수정한 경우)

📂 **참조 파일**:
- `alembic/versions/3803b7878290_create_initial_tables.py:90` — 잘못된 값 위치
- 새 마이그레이션 파일 — 작성 위치

---

## 별도 (코드 외)

- **PR18 클래스 다이어그램 업데이트** — Goal, Notification, ImportHash 추가. Eraser.io DiagramGPT 재생성. 함준규가 시간 날 때 (30분).

## 마지막 프론트엔드 일괄 동기화 (함준규)

백엔드 모든 PR 머지 완료 후 진행. ~1~2일.

통합 변경:
- G2 픽스 (goals.js:112 INCOME → EXPENSE)
- API prefix 통일 (모든 호출 `/transactions/` → `/api/transactions`)
- Trailing slash 제거 (모든 `/api/X/` → `/api/X`)
- 정산 본인 행 추가 코드 제거 (settlements.js)
- calculate_debts 응답에서 display_name → participant_id 매칭
- DELETE participant 버튼 추가
- 거래 삭제 확인 다이얼로그 (정산 cascade 안내)
- 0원 입력 시 422 에러 표시 (예산, 거래)
- tx.category_name 자동 표시 (이미 기대 중)
- 마일스톤 알림 표시 (GOAL_MILESTONE 새 타입)
- SETTLED 참여자 수정 UI 비활성화
- SETTLEMENT_REQUEST 알림 표시 (이미 준비됨)
- 일괄 읽음/미확인 필터/삭제 알림 UI
- 페이지네이션 UI + 필터 UI (E3)
- CSV export 다운로드 버튼 (E4)
- 거래 renderList 재작성 (페이지네이션 동반)

## pytest 통합 테스트 (전원, ~2~3일)

각자 본인 도메인 테스트 작성:
- 함준규: Settlement + Auth + Goals 일부 + cross-cutting 테스트
- 김동준: Goals + Budget + Notification + Statistics 테스트
- 베키: Transactions + API integration 테스트
- 김민수: CSV + Categories + Auth 단순 테스트

---

## 🪤 공통 함정 / Edge Cases (작업 시 반드시 확인)

작업 중 헷갈리거나 빠뜨리기 쉬운 항목. 본인 작업과 관련된 함정은 미리 체크.

### F1. Numeric scale 불일치 (정산 작업 시)
**상황**: 현재 SettlementParticipant.amount = Numeric(12,2) (소수). 다른 amount 는 Numeric(12,0) (정수).
**영향**: PR1 작업 시 Numeric(12,0) 으로 통일하는 마이그레이션 필요. 기존 dev DB 의 소수값 (33.33 등) 은 ALTER 시 반올림됨. **Dev DB 와이프 권장**.

### F2. 모든 *_notified 플래그 (예산/목표 작업 시)
**상황**: budget의 is_warning_notified, is_exceeded_notified / goal의 is_25_notified 등 — 한 번 True 되면 영구.
**영향**: PR4 (Budget), PR2 (Goals 마일스톤) 에서 임계값 아래 떨어지면 False 리셋 로직 통일 필요.

### F3. 프론트엔드 renderList (E3 작업 시)
**상황**: 거래 페이지의 renderList 는 클라이언트 사이드 필터/그룹핑.
**영향**: PR11 백엔드 페이지네이션 도입 시 프론트 재작성 필요 (마지막 단계 함준규가 처리).

### F4. 시스템 카테고리 데이터 마이그레이션 (Categories 작업 시)
**상황**: PR7 에서 시스템 카테고리 15개 확장 시.
**영향**: 기존 5개 + 새로 10개 추가. Dev DB 와이프 후 lifespan 자동 시드 권장.

### F5. ~~datetime.utcnow~~ (작업에서 제외)
**상황**: 결정대로 작업 안 함.

### F6. T2 (category_name) JOIN 필수 (Transactions 작업 시)
**상황**: PR3 에서 TransactionResponse 에 category_name 추가 시.
**영향**: dict lookup 으로 처리하면 N+1 발생. **반드시 SQL JOIN** 으로 처리.

### F7. N+1 in check_and_notify_goal_achievement (Goals 작업 시)
**상황**: Goals 영역에서 goal 마다 calculate_progress 호출.
**영향**: PR2 에서 공유 헬퍼 `_goal_progress_subquery()` 추출하여 5곳에 적용.

### E-A1. uuid.UUID(user_id) malformed crash (Auth 작업 시)
**상황**: `auth/dependencies.py:62` — 잘못된 UUID 입력 시 ValueError → 500 (401이어야).
**영향**: PR6 에서 try/except 추가.

### E-A2. budget amount=0 (Budget 작업 시)
**상황**: 결정대로 Field(gt=0) 적용 → 0 거부.

### E-A3. target_date=today edge (Goals 작업 시)
**상황**: 현재 `target_date < today` 만 EXPIRED. 결정대로 `total_days <= 0` → BEHIND 로 변경.

### E-A4. calculate_debts creator 폴백 (Settlement 작업 시)
**상황**: creator가 participants에 없으면 "to" 필드에 "creator" 문자열 반환.
**영향**: PR1 에서 S3 fix 와 같이 처리. **creator name 은 User 테이블에서 직접 조회** (Decision A 에서 creator 는 어차피 participants 에 없음).

### E-A5. CSV import amount=0 행 (CSV 작업 시)
**상황**: 결정대로 errors + skip.

---

## 🎬 작업 시작 순서 (Day 1)

| Day | 함준규 | 김동준 | 베키 | 김민수 |
|---|---|---|---|---|
| **Day 1 (월)** | PR1 시작 | PR2 시작 | PR3 시작 | PR5 시작 |
| **Day 2 (화)** | PR1 마무리 | PR2 마무리 | PR3 마무리 + PR12 시작 | PR5 마무리, PR6 시작 |
| **Day 3 (수)** | PR10 시작 | PR4 시작 (PR3 후) | PR12 마무리, PR15 | PR6 마무리, PR7 시작 |
| **Day 4 (목)** | PR10 마무리 | PR11 시작 | PR15 마무리, PR13 시작 | PR7 마무리, PR8 시작 |
| **Day 5 (금)** | PR14 + PR16 | PR11 마무리 | PR13 마무리 | PR8 마무리, PR9 |
| **Week 2** | pytest 분담, 다이어그램 | pytest | pytest | pytest |

## 📝 공통 사항

### Dev DB 와이프
PR1 (정산 마이그레이션) + PR7 (시스템 카테고리 확장) 영향:
- 본인 로컬 DB 와이프 후 alembic upgrade head + lifespan으로 자동 재시드
- 또는 다음 명령어:
  ```sh
  psql -U postgres -c "DROP DATABASE donote;"
  psql -U postgres -c "CREATE DATABASE donote;"
  alembic upgrade head
  ```

### 충돌 방지
- 본인 PR 시작 전 `git pull origin main` 으로 최신 상태 확인
- 다른 사람 PR 머지 시 본인 브랜치에 `git merge main` 또는 `git rebase main`

### PR 제목 컨벤션
- `feat: 도메인 영역 작업 요약` (예: `feat: 정산 권한 검증 및 F1 알고리즘 적용`)
- 본문에 변경 항목 체크리스트 + 검증 방법

### Frontend 작업 (마지막 단계, 함준규)
백엔드 모든 PR 머지 후 함준규가 일괄 처리. 위 "마지막 프론트엔드 일괄 동기화" 섹션 참조.

---

## 📚 참고 자료

- [FEATURE_SPEC.md](FEATURE_SPEC.md) — 기능 명세서 (가장 중요)
