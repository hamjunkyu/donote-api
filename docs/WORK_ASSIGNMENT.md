# Donote 백엔드 정리 작업 분담

> 중간 발표(2026-05-14) 이후 코드 정리 및 spec 위반 픽스 작업. 백엔드 완성 → 프론트엔드 일괄 동기화 순서.

## 📌 진행 상황 (2026-05-28 기준)

- **PR1 함준규 Settlement** — ✅ 머지됨 (commit 37ebbe3)
- **PR2 김동준 Goals 통합 (PR #20)** — 리뷰 중 (16개 코멘트 + 머지 차단 4개)
- **14차 전체 코드 review 완료** — 179개 발견 → REAL 75 + PARTIAL 50 + INTENTIONAL 10 + DEFER 44
- **실질 작업 대상**: REAL 75 + PARTIAL 우선순위 높은 것 ~20 = 약 95개를 14개 PR + 신규 PR-S1/PR-S2 (총 16개) 에 분배

## 🚦 작업 진행 방법

각 PR 작업 시 다음 순서로 진행:

1. 이 문서의 본인 섹션 정독 — 핵심 결정사항, 작업 항목, 함정, 검증 시나리오 확인
2. [FEATURE_SPEC.md](FEATURE_SPEC.md) 의 관련 도메인 섹션 읽기 — spec 의도 파악
3. "핵심 결정 사항 24개" 섹션 확인 — 본인 PR 영향 결정사항 체크
4. "공통 함정 / Edge Cases" 섹션 확인 — 본인 PR 관련 함정 체크
5. 기존 코드 읽기 — 본인 PR 의 "참조 파일" 들 현재 상태 파악
6. 브랜치 생성 → 코드 작성 → 검증 시나리오 실행
7. PR 생성 + 리뷰

### 핵심 원칙
- **결정 사항이 우선** — 기존 코드 패턴과 다르면 결정 사항 따름
- **spec 이 final** — 코드와 다르면 spec 기준으로 수정 (단, 결정 사항으로 spec doc 업데이트한 경우 결정 따름)
- **마이그레이션 동반 PR 은 추가 검증** — SQL 결과 직접 확인 후 머지
- **frontend 변경은 백엔드 완성 후 일괄 새로 작성** — 백엔드 결정 기준으로 진행, frontend는 마지막에 함준규가 동기화

## 📋 전체 개요

- **기간**: ~1주 (각자 ~2.5~4.5일)
- **목표**: spec 위반 픽스 + 버그 픽스 + 확장 기능 (마일스톤/페이지네이션/Export) + 아키텍처 정리 + 179개 발견 사항 흡수
- **워크플로우**: Issue 생략. 브랜치 → 코드 → PR → 리뷰 → 머지
- **브랜치 명명**: `feature/도메인-설명` 또는 `fix/도메인-설명`

## 🎯 작업 분배 요약 (업데이트)

| 담당 | PR | 시간 | 영역 |
|---|---|---|---|
| **함준규** | PR1 ✅ / PR-S1 / PR-S2 / PR10 / PR14 / PR16 | ~4.5일 | Settlement + 공유 헬퍼 + 트랜잭션 경계 + 아키텍처 + 신규 fix |
| **김동준** | PR2 (진행 중) / PR4 / PR11 | ~3일 | Goals + Budget + Pagination/필터 |
| **베키** | PR3 / PR12 / PR13 / PR15 | ~3일 | Transactions + Export + API 일관성 + DB constraint 보강 |
| **김민수** | PR5 / PR6 / PR7 / PR8 / PR9 | ~3일 | CSV (대폭 추가) + Auth + Categories + Notifications + migration |

## 🔗 PR 의존성

- **PR1 함준규** (✅ 머지) → **PR2 김동준** (진행 중)
- **PR2 머지** → **PR-S1 함준규** (Settlement 잔여 fix) + **PR3 베키** (Transactions) 병렬 시작
- **PR-S2 함준규** (dependencies.py 삭제, 5분) — 누구나 가능, 즉시
- **PR3 베키** → **PR4 김동준**, **PR11 김동준**, **PR12 베키** 의존
- **PR-S1 + PR3** → **PR10 함준규** (Option B+, actual_amount 노출) 의존
- **PR10** → **PR14 함준규** (트랜잭션 경계) 의존
- 마지막: **PR13 API 일관성** (베키) — 모든 도메인 PR 머지 후
- 마지막: **PR15 DB constraint 보강** (베키) — 마이그레이션 보강 같이
- 최종 마무리: **PR16 Eager loading + 도메인 예외 + spec doc 보강** (함준규)
- 최종: **pytest 통합 테스트** — 각자 본인 도메인
- 정말 마지막: **frontend 일괄 동기화** (함준규)

---

## 🔑 핵심 결정 사항 24개 (작업 시 반드시 참조)

기존 17개 + 신규 7개 (2026-05-28 확정). 상세는 [FEATURE_SPEC.md](FEATURE_SPEC.md) 참조.

### 정산 도메인
1. **Creator NOT in participants** — 정산 생성자는 SettlementParticipant 테이블에 추가하지 않음. 본인 몫은 implicit (`total - SUM(participants)`)
2. **split_equal 알고리즘**: `per_person = total // (N+1)` (N=참여자수). 나머지는 creator 가 흡수
3. **SettlementParticipant.amount**: Numeric(12,2) → **Numeric(12,0)** (정수만). 모델도 통일 (PR-S1).
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
15. **시스템 카테고리 15개로 확장 (spec 정확한 명단)**:
   - 지출(11): 식비, 카페/간식, 교통, 생활/마트, 쇼핑, 주거/통신, 의료/건강, 문화/여가, 교육, 경조사/회비, **기타**
   - 수입(4): 급여/알바, 용돈, 금융소득, **기타**
   - "기타"가 EXPENSE/INCOME 양쪽 있음 → (name, type) 조합 UNIQUE 필요
   - **결정 사항 21 참조**: 기존 코드의 "기타수익" → spec 의 "기타"+INCOME으로 통일

### API
16. **API prefix `/api/` 통일** (PR13) — **결정 사항 23**으로 `/auth` 도 `/api/auth/` 로 통일
17. **Trailing slash 제거** — 모든 `@router.X("/")` → `@router.X("")` (PR13)

---

### 🆕 신규 결정 사항 (2026-05-28 추가, 7개)

#### 18. PATCH path RESTful 통일 (PR-S1)
- 현재: `PATCH /api/settlements/participants/{pid}/settle` (settlement_id 없음)
- 변경: **`PATCH /api/settlements/{sid}/participants/{pid}/settle`**
- 근거: spec 6.3 ② 입력 명세 일치 + Swagger 그룹핑 + 권한 검증 단순화 (역추적 불필요)
- `revert` endpoint 동일 적용 (`PATCH /api/settlements/{sid}/participants/{pid}/revert`)

#### 19. SETTLEMENT_COMPLETED 알림 추가 (PR-S1)
- spec 9.3 에는 없지만 PROJECT_DEFINITION 2.2 "정산 요청·완료" 명시
- 자동 COMPLETED 시 (마지막 참여자 SETTLED) creator에게 알림 발생
- 메시지 예: "OO님과의 정산이 완료되었습니다 ({total_amount:,}원)"
- frontend 표시는 PR8 김민수 (NotificationType Enum) + 마지막 frontend 동기화
- spec 9.3 doc 보강 (PR16)

#### 20. transaction_date 미래 허용 (코드 변경 없음)
- spec 2.3 에 미래 검증 명시 없음 → 그대로 허용
- 근거: stretch goal "정기 구독" 대비 + over-engineering 회피
- frontend `<input type="date" max="오늘">` 으로 client-side 보호 (마지막 동기화 시)
- spec 2.3 doc 에 "미래 허용 (예약 거래 대비)" 한 줄 추가 (PR16)

#### 21. 시스템 카테고리 명칭 spec 통일
- 기존 코드 "기타수익" 폐기
- spec 그대로: **"기타"+INCOME** + **"기타"+EXPENSE** 양쪽 둘 다
- CSV 폴백 코드: (name, type) 조합 lookup 패턴 (PR5)
- 시스템 카테고리 시드 15개 (PR7)

#### 22. Pagination 패턴 통일
- 공통 schema `PaginatedResponse[T]{items, total, limit, offset}` 정의 (PR11에서 정립)
- 적용 endpoint:
  - `GET /api/transactions` — PR11 김동준 (메인 작업)
  - `GET /api/goals/` + `GET /api/goals/{id}/transactions` — PR11 김동준 (같은 PR 흡수)
  - `GET /api/settlements/` — PR-S1 함준규
  - `GET /api/notifications` — PR8 김민수
- 적용 안 함: `GET /api/categories` (보통 30개 미만), `GET /api/budgets/{ym}` (월별 16개 미만)

#### 23. `/auth` prefix `/api/auth/` 통일
- 기존 spec 1.3 `/auth/login` → 결정에 따라 `/api/auth/login`
- API 일관성 + gateway/proxy 설정 단순
- spec 1.3 doc 업데이트 (PR16)
- PR13에서 prefix 변경

#### 24. User.is_active 컬럼 + deactivate endpoint — **추가 안 함** (spec 따름)
- spec 1.3 에 deactivate 기능 명시 없음
- PR6 작업에서 deactivate 관련 항목 제거 (마이그레이션 X, endpoint X, refresh `is_active` 체크 X)
- 근거: over-engineering 회피, PR6 작업 시간 단축
- 추후 필요 시 별도 PR로 추가

---

## 👤 함준규 (~4.5일)

### PR1: Settlement 통합 ✅ 머지됨 (commit 37ebbe3, 2026-05-25)

PR1 본문은 기존 그대로 (참고용). 새 발견은 PR-S1으로 후속 처리.

---

### 🆕 PR-S2: dependencies.py 삭제 (5분, 즉시)

**Critical 보안**: `app/dependencies.py` 에 인증 우회 MockUser 가 dead code로 존재. 어디서도 import 안 되지만 오타로 `from app.dependencies import get_current_user` 시 **인증 전체 우회**.

**작업 항목**:
- [ ] `app/dependencies.py` 삭제
- [ ] `CONTRIBUTING.md:133` "dependencies.py - auth에만 존재" 거짓 표기 수정 ("auth/dependencies.py 만 존재" 로 변경)

**검증**: grep으로 `from app.dependencies import` 0건 확인 (이미 0건). 삭제 후 서버 정상 동작.

📂 **참조 파일**: `app/dependencies.py`, `CONTRIBUTING.md:133`

---

### 🆕 PR-S1: Settlement 통합 fix (1일, PR2 김동준 머지 후)

**목표**: PR1 머지 후 발견된 Settlement 도메인의 spec 미준수 + drift + 잔여 fix를 한 PR로 정리.

**핵심 결정사항 적용**: 결정 3, 5, 18, 19, 22

**작업 항목**:

#### Numeric drift 모델 수정
- [ ] `app/settlements/models.py:29` Settlement.total_amount `Numeric(12,2)` → `Numeric(12,0)`
- [ ] `app/settlements/models.py:64` SettlementParticipant.amount `Numeric(12,2)` → `Numeric(12,0)`
- 마이그레이션 불필요 (DB는 이미 12,0). 모델만 수정.

#### Spec 6.3 ⑥ cancel 시 참여자 PENDING reset
- [ ] `cancel_settlement` (라인 531-544) 에서 settlement.status = CANCELLED 변경 시 모든 참여자 status = "PENDING" + settled_at = None reset
- [ ] `_ensure_modifiable` 호출 추가 (COMPLETED 가드)

#### Spec 6.3 ① EQUAL 특정 참여자 고정 + 나머지 재분배
- [ ] `split_equal` (라인 166-201) 알고리즘 보강:
  - 입력: 사용자가 특정 참여자 amount 수정 → 해당 참여자 고정, 나머지 인원이 잔여 금액 균등 재분배
  - 알고리즘: `fixed_total = sum(고정 참여자 amounts)`, `remaining_per_person = (total - fixed_total) // (남은 인원 + 1[creator])`
- [ ] split_equal endpoint signature 확장: 선택적 `fixed_participant_ids: list[uuid.UUID]` 받음

#### Spec 6.3 ④ split_custom EQUAL 모드 자동 재분배
- [ ] `split_custom` (라인 204-256) 에서 settlement.split_type == "EQUAL" 인 경우, 받은 amount 외 나머지 참여자도 자동 재분배

#### Spec 6.3 ① CUSTOM amount > 0 검증
- [ ] `schemas.ParticipantCreate.amount` `ge=0` → `gt=0` 변경
- [ ] `schemas.CustomSplitItem.amount` `ge=0` → `gt=0` 변경
- 단, add_participant 시 amount=0 으로 추가 후 split 호출 패턴 유지하려면 ParticipantCreate.amount만 `ge=0` 유지하고 CustomSplitItem.amount는 `gt=0`

#### PATH RESTful 변경 (결정 18)
- [ ] `PATCH /api/settlements/participants/{pid}/settle` → `PATCH /api/settlements/{sid}/participants/{pid}/settle`
- [ ] `PATCH /api/settlements/participants/{pid}/revert` → `PATCH /api/settlements/{sid}/participants/{pid}/revert`
- [ ] service 함수에 settlement_id 받아서 권한 검증 단순화 (역추적 제거)

#### SETTLEMENT_COMPLETED 알림 (결정 19)
- [ ] `mark_participant_settled` (라인 387-392) 자동 COMPLETED 분기에서 `create_notification(settlement.creator_id, "SETTLEMENT_COMPLETED", f"OO님과의 정산이 완료되었습니다 ({int(settlement.total_amount):,}원)")` 추가
- [ ] `mark_settlement_complete` (수동 완료) 도 동일 알림 발생

#### calculate_debts / get_balance 가드
- [ ] `calculate_debts` (라인 286-308) — SETTLED 참여자 제외 (`if p.status == "PENDING"` 필터)
- [ ] `calculate_debts` — CANCELLED 정산이면 빈 배열 반환
- [ ] `get_balance` (라인 265-283) — CANCELLED 정산이면 빈 배열 반환

#### delete_settlement / cancel_settlement 가드
- [ ] `delete_settlement` (라인 519-528) — `_ensure_modifiable` 호출 추가 (COMPLETED 차단)
- [ ] `cancel_settlement` 도 동일

#### add_participant amount=0 알림 조건 분기
- [ ] `add_participant` 알림 메시지 (라인 156-161): amount > 0 일 때만 amount 표시, amount=0 이면 "OO님이 정산에 추가했습니다 (금액 확정 대기)" 같은 메시지

#### 중복 로직 정리
- [ ] `_validate_creator_share` (라인 48-66) vs `split_custom` 합계 검증 (라인 245-250) — helper 호출로 통일

#### Pagination 추가 (결정 22)
- [ ] `GET /api/settlements/` 에 `limit`/`offset` 파라미터 + `PaginatedResponse[SettlementResponse]` 응답 (PR11 패턴 사용, PR11 머지 후)

#### 이메일 → user_id 검색 endpoint (spec 6.3 ①)
- [ ] `GET /api/users/search?email=...` endpoint 추가 (auth 라우터 또는 settlements 라우터)
- 응답: `{id, email, name}` (회원 가입 여부 확인용)
- 비회원 (없는 이메일) 시 404 또는 빈 응답
- 보안: 인증 필요 (다른 사용자 이메일 검색 가능)

**복잡 알고리즘 힌트**:

**Spec 6.3 ① EQUAL 특정 참여자 고정**:
```python
def split_equal_with_fixed(participants, total, fixed_ids):
    fixed_total = sum(int(p.amount) for p in participants if p.id in fixed_ids)
    remaining_participants = [p for p in participants if p.id not in fixed_ids]
    n_remaining = len(remaining_participants) + 1  # creator 포함
    per_person = (total - fixed_total) // n_remaining
    for p in remaining_participants:
        p.amount = per_person
    # creator 몫 = total - fixed_total - (n_remaining-1) * per_person
```

**Cancel 시 참여자 reset**:
```python
def cancel_settlement(...):
    settlement.status = "CANCELLED"
    participants = db.query(...).filter(settlement_id=...).all()
    for p in participants:
        p.status = "PENDING"
        p.settled_at = None
    db.commit()
```

**구현 시 함정**:
- PATH 변경 시 frontend 영향 (어차피 새로 작성이라 OK)
- split_equal에 fixed_participant_ids 추가 시 PR3 베키의 amount cascade update_transaction 과 충돌 가능 (PR3 머지 후 시작)
- SETTLEMENT_COMPLETED 알림은 mark_participant_settled 의 자동 COMPLETED 분기 + mark_settlement_complete 수동 둘 다 발화

**검증 시나리오**:
1. 정산 100원 + 친구 2명 (각 33원, creator 34원) → 친구 A amount 50원으로 직접 수정 → 친구 B는 자동 재분배 (50 - 50)/2 = 25 → creator 25
2. CUSTOM 정산 amount=0 으로 split → 400 (gt=0 위반)
3. PATCH /api/settlements/{sid}/participants/{pid}/settle 호출 → 정상 SETTLED
4. 마지막 참여자 SETTLED → 자동 COMPLETED + creator에게 SETTLEMENT_COMPLETED 알림
5. CANCELLED 정산의 debts/balance 조회 → 빈 배열
6. COMPLETED 정산 삭제 시도 → 400 (modifiable 가드)
7. 정산 cancel → 모든 참여자 PENDING + settled_at NULL 복귀
8. GET /api/users/search?email=test@example.com → 회원 정보 또는 404

📂 **참조 파일**:
- `app/settlements/` 전체
- `app/notifications/service.py` — SETTLEMENT_COMPLETED 알림
- `app/auth/service.py` 또는 `app/auth/router.py` — 이메일 검색 endpoint

---

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

### PR10: P1 Option B+ (1일, PR-S1 + PR3 의존)

**목표**: spec [4.1](FEATURE_SPEC.md#L246) Statistics / [5.1](FEATURE_SPEC.md#L319) Budget 의 "실부담액 기준" 픽스. 정산 결정 (creator NOT in + SETTLED-based) 정확히 반영. **+ Transaction response에 actual_amount 노출** (spec 2.3).

**핵심 결정사항 적용**:
- 결정 1 (creator NOT in)
- 결정 4 (SETTLED-based)

**작업 항목**:
- [ ] **공유 헬퍼 `actual_spent_subquery()` 작성** in `app/transactions/helpers.py` (없으면 생성)
- [ ] **Budget 적용**: `budgets/service.py:get_budget_usage` — Transaction.amount 합산 대신 헬퍼 사용
- [ ] **Statistics 폐기 + 통일**: 기존 `_actual_amount_subquery` 폐기, 공유 헬퍼로 교체
- [ ] **🆕 TransactionResponse에 actual_amount 노출** (spec 2.3):
  - `app/transactions/schemas.py:TransactionResponse` 에 `actual_amount: int` 필드 추가
  - `app/transactions/service.py` get_transactions/get_transaction_by_id 에서 헬퍼 subquery 사용해 actual_amount 같이 반환
  - 정산 없는 거래는 actual_amount = amount
- [ ] **🆕 Statistics 응답 필드 spec 통일** (spec 4.2, 결정 사항 strict):
  - `get_category_statistics` 응답: `total_amount` → 거래 type에 따라 `total_expense` 또는 `total_income`
  - 또는 type별 별도 endpoint 분리

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

### PR14: 트랜잭션 경계 통합 + race condition 해결 (반나절)

**목표**: 거래 생성/수정/삭제 + 알림 발생을 단일 트랜잭션으로. partial commit 방지 + race condition 해결.

**작업 항목**:
- [ ] transactions/service.py 의 create/update/delete_transaction 트랜잭션 경계 통일
- [ ] check_and_notify_budget_threshold / check_and_notify_goal_achievement 에 commit 분리 옵션 추가 (또는 패턴 통일)
- [ ] **🆕 create_notification 내부 commit 제거** — caller가 통째로 commit
- [ ] **🆕 password 변경 + token 삭제 atomic 화** (`auth/router.py:194-199`)
  - 현재: `db.commit()` 후 `delete_all_refresh_tokens` (내부 또 commit). 첫 commit 후 두 번째 실패 시 비번 변경됐는데 다른 기기 토큰 살아있음 → 보안 위험
  - 변경: 둘 다 한 트랜잭션 안에 묶어서 commit
- [ ] **🆕 race condition 해결** (3건):
  - `check_and_notify_goal_achievement` / `check_and_notify_budget_threshold` 동시 호출 시 중복 알림 방지 → SELECT FOR UPDATE 또는 UNIQUE 알림 키
  - `add_participant` (settlements/service.py:140-149) flush 후 검증 실패 시 명시적 rollback 추가
- [ ] **🆕 인프라 보강**:
  - `app/main.py:21-29 lifespan` try/except 추가 (init_default_categories 실패 시 startup 죽지 않게)
  - `app/database.py:8` `create_engine(... pool_pre_ping=True)` 추가 (stale connection 5xx 방어)
  - `app/main.py:39-49 CORS` `allow_methods/headers ["*"]` → 운영 명시 + `allow_origins` env 분리
- [ ] **🆕 PR2 follow-up**: `app/config.py:TEST_DATABASE_URL` 기본값에 password 하드코딩 (`postgresql://postgres:1234/...`). 빈 문자열 또는 `.env` 강제로 변경 (`SECRET_KEY`/`DATABASE_URL` validation 같이 묶음)

**복잡 알고리즘 힌트** (기존 패턴 A 유지):
```python
def create_transaction(...):
    db.add(db_transaction)
    db.flush()  # commit X, ID만 확보
    if type == "EXPENSE":
        check_and_notify_budget_threshold(db, ..., commit=False)
        check_and_notify_goal_achievement(db, ..., commit=False)
    db.commit()  # 마지막에 한 번만

def create_notification(db, ..., commit=True):
    notification = Notification(...)
    db.add(notification)
    if commit:
        db.commit()
        db.refresh(notification)
    return notification
```

**race condition 해결 패턴 (알림 중복 방지)**:
```python
# 마일스톤 알림 unique constraint
class Notification(Base):
    __table_args__ = (
        UniqueConstraint(
            'user_id', 'type', 'message',
            name='uq_notification_user_type_message',
        ),
    )
# 또는 SELECT FOR UPDATE
goal = db.query(Goal).filter(...).with_for_update().first()
```

**구현 시 함정**:
- 기존 알림 함수들이 다른 곳에서도 호출됨 (csv_import 등). `commit: bool = True` 시그니처 추가하면 backward compatible
- main.py lifespan try/except는 logging 같이 추가 (운영 시 디버깅용)

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

### PR16: Eager loading + 도메인 예외 + spec doc 보강 (반나절)

**모든 PR 머지 후 마지막 정리 작업**.

**목표**: 코드 일관성 ↑. N+1 쿼리 패턴 정리 + HTTPException 직접 raise 대신 도메인 예외 클래스 + spec doc 업데이트.

**작업 항목**:
- [ ] **Eager loading 적용** (relationship + lazy strategy):
  - Transaction → Category (`lazy="joined"`)
  - Settlement → participants (`lazy="selectin"`)
  - User → RefreshToken
  - **🆕 모든 모델에 relationship() 정의** (현재 0개)
- [ ] **도메인 예외 클래스** in `app/shared/exceptions.py`:
  - DomainException 베이스 + 구체 클래스들 (GoalNotFound, CategoryInUse, SettlementCompleted, SettledParticipantUnchangeable, NotSettlementOwner, NotSettlementCreator 등)
- [ ] **전역 핸들러 등록** in main.py
- [ ] **라우터 일괄 변경**: HTTPException → 도메인 예외
- [ ] **🆕 settlements/service.py HTTPException 직접 raise 15곳** → 도메인 예외로 교체
- [ ] **🆕 settlements/service.py 문자열 sentinel 3곳** ("NOT_ALL_SETTLED", "NOT_COMPLETED", "NOT_SETTLED") → 도메인 예외로 교체
- [ ] **🆕 categories/service.py:86 raise ValueError("CATEGORY_IN_USE")** → CategoryInUseError 도메인 예외
- [ ] **🆕 "정산을 찾을 수 없습니다" 13곳 중복** → 상수 또는 SettlementNotFoundError 도메인 예외
- [ ] **🆕 PR2 김동준 follow-up (PR2 머지 후 미해결분)**:
  - `goals/service.py:delete_goal` deleted 객체 반환 → bool
  - `goals/service.py:determine_status` target<=0 dead branch 정리
  - `get_goals` elif IN_PROGRESS dead branch 정리
  - **PR #20 머지 후 minor follow-up (2026-05-29 발견)**:
    - `alembic/versions/11f31d77710f_add_milestone_flags_to_goals.py:8-14` 두 번째 docstring 블록 삭제 (첫 번째 fix 누락, 동작 OK이지만 코드 깔끔)
    - `app/goals/service.py:get_goal_progress` 라인 327-329 `elif IN_PROGRESS` dead branch 삭제 (다른 함수 정리 시 누락. `target_amount > 0` 보호로 도달 불가)
    - `app/goals/service.py:update_goal` 라인 ~215, ~244 `calculate_progress` 두 번 호출 → 한 번으로 통일
    - `tests/conftest.py:setup_db` teardown `Base.metadata.drop_all` → `alembic_version` 안 지워져 다음 세션 alembic이 "already at head" 인식 가능. `DROP DATABASE` + `CREATE DATABASE` 또는 `alembic downgrade base` 패턴으로 변경
- [ ] **🆕 service 시그니처 통일** — `current_user` 객체 vs `user_id` 만 받기 → 도메인별 일관성

#### Spec doc 보강 (FEATURE_SPEC.md 업데이트)
- [ ] spec 1.3 토큰 갱신 — "Access Token + Refresh Token 둘 다 새로 발급" 명시 (refresh rotation 코드와 일치)
- [ ] spec 1.3 `/auth/login` → `/api/auth/login` 으로 prefix 통일
- [ ] spec 2.3 `transaction_date` "미래 허용 (예약 거래 대비)" 한 줄 추가
- [ ] spec 6.3 ② `mark_participant_settled` path를 `/api/settlements/{sid}/participants/{pid}/settle` 로 명시
- [ ] spec 6 에 `/api/settlements/{sid}/balance`, `/api/settlements/{sid}/debts`, `/api/settlements/{sid}/participants` endpoint 명시
- [ ] spec 8.3 에 `/api/goals/{id}/transactions`, `/api/goals/{id}/forecast`, `/api/goals/{id}/monthly-trend` endpoint 명시 (없으면)
- [ ] spec 9.3 `SETTLEMENT_COMPLETED` 알림 type 추가
- [ ] CONTRIBUTING.md 섹션 번호 typo (## 7 두 개 → 7, 8 분리)
- [ ] CONTRIBUTING.md vs WORK_ASSIGNMENT.md Issue 정책 불일치 정리 (WORK_ASSIGNMENT 의 "Issue 생략" 으로 통일)

**복잡 알고리즘 힌트**:

**도메인 예외 패턴**:
```python
# app/shared/exceptions.py
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

# 구체 클래스 (한글 메시지)
class GoalNotFound(NotFoundError):
    detail = "목표를 찾을 수 없습니다"

class SettlementNotFound(NotFoundError):
    detail = "정산을 찾을 수 없습니다"

class CategoryInUseError(ConflictError):
    detail = "사용 중인 카테고리는 삭제할 수 없습니다"
```

**전역 핸들러**:
```python
@app.exception_handler(DomainException)
async def domain_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
```

**Eager loading**: SQLAlchemy `relationship()` + `lazy` 파라미터. `lazy="joined"` (1:1, JOIN) vs `lazy="selectin"` (1:N, 추가 쿼리).

**검증 시나리오**:
1. 도메인 예외 raise 시 응답 형식 일관 (`{"detail": "..."}`)
2. EXPLAIN ANALYZE 로 JOIN 으로 1 쿼리 처리 확인
3. 모든 endpoint 회귀 테스트 (예외 변경으로 break 없는지)
4. spec doc 업데이트 후 클라이언트가 보는 endpoint vs 실제 코드 일치 확인

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

## 👤 김동준 (~3일)

### PR2: Goals 통합 (PR #20 진행 중)

**리뷰 코멘트 16개 받음** (2026-05-28 함준규). 머지 차단 4개 + 같은 PR fix 권장 2개 + follow-up 가능 7개 + skip 3개.

#### 머지 차단 (반드시 fix)
- [ ] **1. `alembic/versions/11f31d77710f...:1-26`** 헤더 docstring + import 블록 통째 두 번 적힘. 두 번째 블록 삭제.
- [ ] **2. `tests/conftest.py:11-15 setup_db`** — `settings.DATABASE_URL` (프로덕션 DB) 에 `create_all`. `TEST_DATABASE_URL` 분리 + alembic upgrade 패턴.
- [ ] **3. `tests/conftest.py:22-37 db fixture`** — SAVEPOINT 패턴 누락. `connection.begin_nested()` + `after_transaction_end` listener 추가.
- [ ] **7. `app/goals/service.py:update_goal`** —
  - (a) `target_amount` 변경 시 `is_25/50/75_notified` flag reset
  - (b) `target_date` 변경 시 status 재평가 (EXPIRED → 미래 연장 시 IN_PROGRESS 복귀)

#### 같은 PR fix 권장 (강력 권장)
- [ ] **5. `app/goals/router.py:get_goals` Query**: `Literal["ACHIEVED","EXPIRED","CANCELLED","ON_TRACK","BEHIND"]` (IN_PROGRESS 제외) + docstring/동작 일치
- [ ] **8. `tests/test_goals.py:test_goal_border_day_status`**: `target_date = created_at.date()` 로 변경해서 `total_days <= 0` 분기 실제 검증

#### Follow-up commit 가능 (PR 안 또는 별도)
- [ ] **6. create_goal/update_goal/cancel_goal commit 후 get_goal_by_id 재호출** — 헬퍼로 동적 속성 부착하는 방식 권장
- [ ] **9. PERSIST_STATES 중복 3곳** (91/152/291) → 모듈 상수
- [ ] **10. `_map_goal_response` 동적 setattr** → service에서 dict/dataclass 반환
- [ ] **12. `get_goal_by_id` commit 후 refresh 없음** (get_goal_progress와 비일관)
- [ ] **13. `progress_percentage` 상한 없음** → `min(100, ...)` 백엔드 캡
- [ ] **15. `get_goals` elif IN_PROGRESS dead branch** 삭제
- [ ] **16. tests/conftest.py imports 위치 (PEP 8) + cleanup 중복 (clear() vs pop())**

#### Skip (DEFER)
- ⏭️ **4. status SQL filter** — 목표 100개 미만이면 ms 차이. Python 후처리 OK.
- ⏭️ **11. hysteresis 없음** — 24/25% 경계 거래 반복 시나리오 드뭄.
- ⏭️ **14. get_monthly_trend 헬퍼 미적용** — 단건이라 동작 OK.

#### 추가 (7차 발견)
- [ ] **`app/goals/schemas.py:GoalCreate`** `name` max_length=100, `description` max_length=500 추가 (DB 일치)
- [ ] Error message 영문 → 한글 통일 ("Goal not found" → "목표를 찾을 수 없습니다" 등 7곳)

---

### PR2 (원본 본문): Goals 통합 (1일)

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

### PR4: Budget 통합 (1일, PR3 의존)

**목표**: 예산 도메인의 spec 위반/검증/알림 일괄 픽스 + **응답 형식 spec 통일** + **N+1 해결** + **race condition 해결**.

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

#### 🆕 응답 형식 spec 5.3 통일 (Critical)
- [ ] `get_budget_usage` 응답 구조 spec 그대로:
  ```json
  {
    "year_month": "2026-03",
    "budgets": [
      {"category": null, "label": "전체", "budget": 1000000, "spent": 750000, "remaining": 250000, "usage_rate": 75.0, "status": "SAFE"},
      {"category": "식비", "budget": 350000, "spent": 280000, "remaining": 70000, "usage_rate": 80.0, "status": "WARNING"}
    ]
  }
  ```
- [ ] 현재 `{overall, categories}` 분리 구조 → `{year_month, budgets: []}` 단일 배열로 통합
- [ ] 필드 이름 통일: `budget_amount` → `budget`, `spent_amount` → `spent`, `usage_percentage` → `usage_rate`
- [ ] `remaining` 필드 추가 (현재 없음)
- [ ] `BudgetUsageResponse.status` `Literal["SAFE", "WARNING", "EXCEEDED"]` 적용

#### 🆕 N+1 해결
- [ ] `app/budgets/service.py:110` `db.get(Category)` 루프 → JOIN으로 한 번에 조회

#### 🆕 Race condition 해결
- [ ] `upsert_budget` 동시 호출 시 `UniqueConstraint` 위반 500 → try/except + retry, 또는 PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` 사용

#### 🆕 overall=None 처리 명시
- [ ] `format_usage(None, total_spent)` 호출 시 의미 없는 응답 (budget=0, spent=N, status=SAFE) 대신:
  - 응답에서 overall 제외, 또는 `status="NOT_SET"` 명시

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

**목표**: spec [2.3](FEATURE_SPEC.md#L184) 거래 조회의 페이지네이션 + 필터 + description 검색 구현 + **공통 pagination 패턴 정립** + **goals pagination 흡수**.

**핵심 결정사항 적용**:
- 결정 22 (Pagination 패턴 통일)

**작업 항목**:

#### 공통 pagination schema 정립
- [ ] `app/shared/schemas.py` 또는 `app/common/schemas.py` 에 `PaginatedResponse[T]` Generic schema:
  ```python
  from typing import Generic, TypeVar
  T = TypeVar("T")
  class PaginatedResponse(BaseModel, Generic[T]):
      items: list[T]
      total: int
      limit: int
      offset: int
  ```

#### Transactions pagination + 필터
- [ ] `GET /api/transactions` 쿼리 파라미터 확장:
  - `limit` (default 20, max 100), `offset` (default 0)
  - `type=INCOME|EXPENSE`
  - `category_id=UUID`
  - `date_from`, `date_to` (YYYY-MM-DD)
  - `amount_min`, `amount_max`
  - `keyword` (description ILIKE 검색)
- [ ] 응답: `PaginatedResponse[TransactionResponse]`
- [ ] 정렬: transaction_date DESC, created_at DESC

#### 🆕 Goals pagination 흡수 (본인 도메인)
- [ ] `GET /api/goals/` 에 `limit`/`offset` + `PaginatedResponse[GoalResponse]` 응답
- [ ] `GET /api/goals/{id}/transactions` 에 `limit`/`offset` + `PaginatedResponse[ContributingTransactionResponse]` 응답

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

## 👤 베키 (~3일)

### PR3: Transactions 통합 (1일)

**목표**: 거래 도메인의 핵심 픽스 (amount precision, B1 trigger, T2 category_name, 정산 cascade, 검증) + **hook 누락 보강** + **응답 필드 보강**.

**핵심 결정사항 적용**:
- 결정 6 (amount int + Literal)
- 결정 7 (delete 자유 — FK CASCADE)
- 결정 8 (amount cascade update)

**작업 항목**:
- [ ] **스키마 강화**:
  - amount: `int = Field(gt=0)`
  - type: `Literal["INCOME","EXPENSE"]`
  - 모든 필드에 `Field` 적용 (length, validation)
- [ ] **category_id 소유권 검증** in create_transaction
- [ ] **delete_transaction**: 정산 차단 코드 **제거** (FK CASCADE 가 자동 처리)
- [ ] **delete_transaction**: budget/goal 알림 트리거 추가 (B1)
- [ ] **update_transaction**: amount 변경 시 settlement 연동 (아래 알고리즘)
- [ ] **TransactionResponse 에 category_name 추가** — Category JOIN (T2)

#### 🆕 추가 작업 (전체 review 발견)
- [ ] **update_transaction에 (old_type, old_category_id) 캐싱 + 양쪽 hook 호출**:
  - type을 EXPENSE → INCOME 변경 시 이전 category goal/budget 재평가 (이번 거래가 더이상 EXPENSE 아니라 차감)
  - category_id 변경 시 이전 category + 새 category 양쪽 hook
- [ ] **TransactionResponse에 created_at/updated_at 추가** (REST 컨벤션)
- [ ] **update_transaction amount cascade 시 `_validate_creator_share` 호출** (PR-S1 의존):
  - settlement.total_amount 자동 업데이트 후 creator_share < 0 검증
- [ ] **Error message 한글 통일** ("Transaction not found" → "거래를 찾을 수 없습니다")
- [ ] **Import 순서 PEP 8 정리** (`app/transactions/router.py:1-10` 표준→서드파티→프로젝트)
- [ ] **service 함수 type hint 추가** (`transaction_id: uuid.UUID, current_user: User`)
- [ ] **회귀 테스트**: 실제 API endpoint (`auth_client.delete/patch`) 로 hook 동작 검증 (현재 PR2 conftest 가 hook 수동 호출이라 회귀 못 잡음)

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
- **결정 23** (`/auth` → `/api/auth/` 통일)

**작업 항목**:
- [ ] `app/transactions/router.py:13` prefix `/transactions` → `/api/transactions`
- [ ] **🆕 `app/auth/router.py:25` prefix `/auth` → `/api/auth`** (결정 23)
- [ ] 모든 라우터의 `@router.X("/")` → `@router.X("")` (trailing slash 제거)
  - 영향: transactions, settlements, goals, categories
  - budgets, notifications 는 이미 slash 없음
- [ ] **response_model 누락 전부 채우기**:
  - `app/budgets/router.py:40 DELETE` → MessageResponse 또는 204 + None
  - `app/transactions/router.py:62 DELETE` → 동일
  - `app/goals/router.py:164 DELETE` → 동일
  - `app/notifications/router.py:22 PATCH /{id}/read` → MessageResponse

#### 🆕 HTTP status code 5건 수정
- [ ] `POST /api/budgets` → `status_code=201`
- [ ] `POST /api/transactions` → `status_code=201`
- [ ] `DELETE /api/budgets/{id}` → `status_code=204`
- [ ] `DELETE /api/transactions/{id}` → `status_code=204`
- [ ] `DELETE /api/goals/{id}` → `status_code=204`

#### 🆕 공용 MessageResponse 정의
- [ ] `app/shared/schemas.py` 또는 `app/common/schemas.py` 에 MessageResponse 추출 (settlements 의 정의 옮김)

#### 🆕 Response 응답 Literal 추가
- [ ] `app/settlements/schemas.py:42-43, 86-87` SettlementResponse/SettlementDetailResponse 의 `split_type`/`status` Literal 명시
- [ ] `app/statistics/schemas.py:11 PeriodSummaryResponse.period` Literal

#### 🆕 Error message 일관성
- [ ] 모든 라우터 error message 마침표 일관성 (settlements는 마침표 없음, 나머지는 있음 → 통일)

#### 🆕 OpenAPI 메타데이터 보강
- [ ] 모든 endpoint `summary` 추가 (categories만 현재 있음)
- [ ] `description` 추가
- [ ] 주요 endpoint `examples` 추가

#### 🆕 current_user 타입 hint 추가
- [ ] 모든 router의 `current_user = Depends(get_current_user)` → `current_user: User = Depends(get_current_user)` (PEP 8 / CONTRIBUTING 6.4)

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

### PR15: DB constraint + 인덱스 + 마이그레이션 보강 (반나절)

**목표**: DB 레벨 안전망 (CHECK constraint) + 자주 쿼리되는 컬럼 인덱스 + **초기 마이그레이션 보강** + **race condition 해결 (UNIQUE constraint)**.

**작업 항목**:
- [ ] **CHECK constraint** 마이그레이션:
  - `transactions.amount > 0`
  - `budgets.amount > 0`
  - `goals.target_amount > 0`
  - `settlement_participants.amount >= 0`
  - **🆕 `budgets.year_month ~ '^\d{4}-\d{2}$'`** (schema만 있고 DB CHECK 없음)
- [ ] **Composite 인덱스** 마이그레이션:
  - `Transaction(user_id, transaction_date)`
  - `Transaction(category_id)`
  - `Goal(user_id, category_id)`
  - `Settlement(creator_id)`
  - `Settlement(transaction_id)`
  - `Notification(user_id, is_read)`
  - `SettlementParticipant(settlement_id)`

#### 🆕 PR2 follow-up (2026-05-29 발견)
- [ ] `alembic/env.py:23` `import os` 가 모듈 중간에 inline 위치 → 파일 상단으로 이동 (PEP 8)

#### 🆕 초기 마이그레이션 보강 (3803b7878290)
- [ ] **server_default 추가 마이그레이션** — 모든 nullable=False 컬럼:
  - users.created_at, refresh_tokens.created_at
  - categories: (별도 created_at/updated_at 없음 → PR7에서 추가 결정)
  - import_hashes.created_at
  - transactions.created_at/updated_at
  - settlements.status (default 'PENDING'), created_at
  - settlement_participants.status (default 'PENDING')
  - budgets.is_warning_notified, is_exceeded_notified (default false)
  - notifications.is_read (default false), created_at
  - goals 는 이미 server_default 있음 (3b1823b234e4)
  - 패턴: `op.alter_column('table', 'col', server_default=sa.text('CURRENT_TIMESTAMP'))` 또는 `sa.false()`

#### 🆕 초기 마이그레이션 downgrade 순서 수정
- [ ] `alembic/versions/3803b7878290_create_initial_tables.py:115-122` downgrade 순서 수정:
  - 현재: settlement_participants → settlements → transactions → budgets → import_hashes → categories → **users → refresh_tokens** (FK 위반)
  - 수정: refresh_tokens 를 users 앞으로 (또는 ON DELETE CASCADE 추가)

#### 🆕 초기 마이그레이션 enum DROP TYPE 추가
- [ ] `alembic/versions/3803b7878290_create_initial_tables.py` downgrade에 5개 enum DROP 추가:
  ```python
  op.execute('DROP TYPE settlement_status')
  op.execute('DROP TYPE participant_status')
  op.execute('DROP TYPE transaction_type')
  op.execute('DROP TYPE category_type')
  op.execute('DROP TYPE split_type')
  ```

#### 🆕 Race condition UNIQUE constraint
- [ ] `budgets` partial unique index `WHERE category_id IS NULL` (PostgreSQL NULL distinct 문제 해결)
- [ ] `settlement_participants` partial unique `(settlement_id, user_id) WHERE user_id IS NOT NULL` (add_participant race)
- [ ] `import_hashes` UNIQUE `(user_id, hash)` composite (현재 hash 단독 unique → 다른 사용자 동일 해시 INSERT 실패)

#### 🆕 모델 nullable 명시 보강 (drift 제거)
- [ ] `app/budgets/models.py:36, 37` is_warning/exceeded_notified — `nullable=False, default=False` 명시
- [ ] `app/notifications/models.py:23 is_read, 25 created_at` — `nullable=False` 명시
- [ ] `app/transactions/models.py:34 created_at, 37 updated_at` — `nullable=False` 명시
- 동작 OK이지만 alembic autogenerate 시 잘못된 diff 생성 → 보강

#### 🆕 schema.sql 재생성
- [ ] 마이그레이션 다 적용 후 `pg_dump` 로 `donote-schema.sql` 재생성 (현재 outdated)

#### 🆕 alembic constraint name 명시 보강 (ff0721794a82)
- [ ] `alembic/versions/ff0721794a82:24,31` `op.create_foreign_key(None, ...)` / `op.drop_constraint(None, ...)` 에 명시적 이름 부여 (`refresh_tokens_user_id_fkey`)

**구현 시 함정**:
- server_default 추가는 기존 DB에 영향 X (NOT NULL 컬럼에 default 적용 안 됨, 새 행만)
- partial unique index 는 PostgreSQL specific: `op.create_index('uq_budget_overall', 'budgets', ['user_id', 'year_month'], unique=True, postgresql_where=sa.text('category_id IS NULL'))`
- import_hashes (user_id, hash) 변경 시 기존 hash 단독 UNIQUE constraint 먼저 drop 필요

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

## 👤 김민수 (~3일)

### PR5: CSV Import 정리 (1일) — **가장 많이 추가됨**

**목표**: CSV import 의 보안/검증/UX 정리. spec [7](FEATURE_SPEC.md#L577) 참조. **+ spec 형식 통일 + 안전성 보강 + 한글 처리**.

**핵심 결정사항 적용**:
- 결정 9 (CSV amount=0 skip+errors)
- 결정 21 (시스템 카테고리 "기타"+INCOME/EXPENSE)

**작업 항목**:
- [ ] `except Exception` 제거 — 일반화된 메시지로 (stacktrace 노출 X). 보안: `str(e)` 응답 안 함.
- [ ] amount=0 행 → errors 리스트에 추가 + 저장 skip
- [ ] 파일 크기 5MB 제한 (request 단계에서 거부)
- [ ] 1000행 제한 (spec 7.1)
- [ ] 임포트 끝에 budget/goal 알림 트리거 (영향받은 날짜/카테고리 별)

#### 🆕 한글 CSV "유형" 매핑 (Critical)
- [ ] `app/csv_import/service.py:36` row "유형" 필드 한글 → 영문 매핑:
  ```python
  TYPE_MAP = {"지출": "EXPENSE", "수입": "INCOME"}
  raw_type = row.get("유형", "EXPENSE").strip()
  type_value = TYPE_MAP.get(raw_type, raw_type.upper())
  ```
- 현재: 한글 그대로 전달 → DB enum INCOME/EXPENSE 와 매칭 안 됨 → 모든 행 fail
- spec 7.2 예시: "지출"/"수입" 한글 명시

#### 🆕 transaction_date 명시적 파싱 (Critical)
- [ ] `parse_csv_content` 에서 `row.get("날짜", "").strip()` 받아서 `datetime.strptime(..., "%Y-%m-%d").date()` 명시 변환
- 잘못된 형식이면 row별 error 추가 후 continue (전체 import 중단 X)
- 현재: Pydantic 자동 변환 → 빈 문자열/잘못된 포맷 시 ValidationError → 전체 import 중단

#### 🆕 폴백 카테고리 (name, type) 조합 lookup (Critical)
- [ ] `app/csv_import/service.py:78` 현재 `"기타수익"` 폴백 → 시스템 카테고리에 존재 안 함 (결정 21)
- [ ] 변경: type별 "기타" 카테고리 lookup
  ```python
  fallback = next(
      (c for c in categories if c.name == "기타" and c.type == row.type),
      None,
  )
  category_id = category_map.get(row.category) or (fallback.id if fallback else None)
  ```

#### 🆕 bulk_save_objects atomic + rollback (Critical)
- [ ] `process_import_batch` 라인 104-108 try/except + rollback:
  ```python
  try:
      if new_hashes_to_insert:
          db.bulk_save_objects(new_hashes_to_insert)
      if transactions_to_insert:
          db.bulk_save_objects(transactions_to_insert)
      db.commit()
  except Exception:
      db.rollback()
      raise
  ```
- 현재: 두 번째 실패 시 hash만 남고 transaction 안 들어감 → 다음 import 모두 duplicate (**데이터 소실급**)

#### 🆕 MIME type 검증 + 인코딩 폴백 + CSV injection
- [ ] `app/csv_import/router.py:22` filename 검증:
  - case-insensitive: `file.filename.lower().endswith(".csv")`
  - None 가드: `if not file.filename: raise 400`
  - MIME type 검증: `file.content_type in ("text/csv", "application/vnd.ms-excel")`
- [ ] 인코딩 폴백 순서: utf-8-sig → cp949 → euc-kr → 실패 시 400
- [ ] CSV injection 처리: 메모 첫 글자가 `=+-@` 면 prefix `'` 추가 또는 reject

#### 🆕 ImportHash composite UNIQUE
- [ ] `app/csv_import/models.py:26` `hash` 단독 UNIQUE → `(user_id, hash)` composite (PR15 마이그레이션과 협업)
- 다른 사용자가 같은 해시 가지면 INSERT 실패 → 데이터 손실 방어

#### 🆕 응답 형식 spec 7.3 통일
- [ ] `app/csv_import/schemas.py:ImportResult` 응답 형식 변경:
  ```python
  class ImportResultError(BaseModel):
      row: int
      reason: str
  
  class ImportResult(BaseModel):
      total_rows: int
      imported: int            # 기존 imported_count
      skipped_duplicate: int   # 기존 duplicate_count
      failed: int              # 신규 (현재 errors 카운트 안 함)
      errors: list[ImportResultError]  # 기존 list[str] → dict
      # valid_rows 제거 (응답 폭증 방지)
  ```
- spec 7.3 예시와 정확히 일치

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

### PR6: Auth 정리 (반나절)

**목표**: 인증 도메인 보안 보강. **deactivate 제거 (결정 24)** + spec 미명시 항목 정리 + 신규 보안 보강.

**핵심 결정사항 적용**:
- 결정 24 (deactivate 제거)

**작업 항목**:
- [ ] `get_current_user` 에 `uuid.UUID()` try/except 추가 (E-A1)
- ~~`refresh` 엔드포인트에 `user.is_active` 체크 추가~~ → **결정 24: 제거** (User.is_active 컬럼 자체 추가 안 함)
- ~~Deactivate 엔드포인트 추가~~ → **결정 24: 제거**

#### 🆕 추가 작업 (전체 review)
- [ ] **refresh `payload.get("sub")` None 가드** — `router.py:122-127`
  ```python
  user_id = payload.get("sub")
  if user_id is None:
      raise HTTPException(401, "유효하지 않은 Refresh Token입니다")
  ```
  현재: `uuid.UUID(None)` → TypeError → **500 노출**
- [ ] **비밀번호 max_length 지정** — `app/auth/schemas.py:SignupRequest.password / PasswordChangeRequest.new_password`:
  - `Field(min_length=8, max_length=128)` (bcrypt DoS 방어, 긴 입력으로 bcrypt 비싸짐)
- [ ] **만료 RefreshToken cleanup** — refresh 호출 시 또는 별도 cleanup endpoint 에서 expires_at < now() 인 토큰 삭제
  - 또는 단순히 refresh 시 expires_at 검증 (현재 JWT exp 검증만 함)

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

### PR7: Categories 정리 (1일)

**목표**: 카테고리 중복 차단 + 시스템 카테고리 spec 일치 + **spec 응답 형식** + **type 필터 endpoint** + **삭제 가드**.

**핵심 결정사항 적용**:
- 결정 15 (시스템 카테고리 15개)
- 결정 21 ("기타수익" → "기타"+INCOME 으로 통일)

**작업 항목**:
- [ ] **UNIQUE constraint** 마이그레이션: `(user_id, name, type)` 복합 키
- [ ] **시스템 카테고리 15개로 확장** — `init_default_categories` 수정 (결정 15 정확한 명단, "기타수익" 사용 X)
- [ ] Dev DB 와이프 후 lifespan 자동 시드 (idempotent 동작 확인)

#### 🆕 spec 3.3 응답 형식 통일
- [ ] `CategoryResponse` 에 `is_system: bool` 필드 추가 (computed: `user_id is None`)

#### 🆕 type 필터 endpoint (spec 3.3)
- [ ] `GET /api/categories?type=EXPENSE` 쿼리 파라미터 추가 (`Literal["INCOME", "EXPENSE"] | None`)

#### 🆕 삭제 명시적 가드
- [ ] `delete_category` 현재 IntegrityError catch → ValueError("CATEGORY_IN_USE") 패턴
- [ ] 변경: 명시적으로 transactions/budgets/goals 에서 사용 중인지 사전 체크
- [ ] ValueError 대신 도메인 예외 `CategoryInUseError` (PR16 의존 또는 PR7 자체 정의)

#### 🆕 order_by 추가
- [ ] `get_categories` 에 `.order_by(Category.type, Category.name)` 추가 (현재 비결정적)

#### 🆕 (선택) Category 모델에 created_at/updated_at 추가
- spec 3.2 에는 없지만 일반적 패턴. 결정: spec 따라 **추가 안 함**. 운영 가면 추가.

#### 🆕 csv_import 폴백 코드 정리 (PR5와 연동)
- PR5에서 `(name, type)` 조합 lookup 패턴 사용. PR5와 시드 데이터 일치.

#### 🆕 categories/service.py:47 `.value` dead code 정리
- `data.type.value` → `data.type` (SAEnum 자동 변환)

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

### PR8: Notifications 확장 + 타입 보강 (반나절)

**목표**: 알림 도메인의 누락 엔드포인트 3개 추가 + **타입 enum 보강** + **pagination** + **SETTLEMENT_COMPLETED 지원**.

**핵심 결정사항 적용**:
- 결정 19 (SETTLEMENT_COMPLETED 알림 추가)
- 결정 22 (Pagination)

**작업 항목**:
- [ ] `PATCH /api/notifications/read-all` — 사용자의 모든 미확인 알림 일괄 읽음 처리
- [ ] `GET /api/notifications?unread=true` — 미확인 필터
- [ ] `DELETE /api/notifications/{id}` — 개별 삭제 (하드)

#### 🆕 NotificationType Enum + Literal 검증
- [ ] `app/notifications/constants.py` 또는 `app/notifications/types.py` 에 `NotificationType` Enum:
  ```python
  from enum import StrEnum  # Python 3.11+
  class NotificationType(StrEnum):
      BUDGET_WARNING = "BUDGET_WARNING"
      BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
      GOAL_MILESTONE = "GOAL_MILESTONE"
      GOAL_ACHIEVED = "GOAL_ACHIEVED"
      SETTLEMENT_REQUEST = "SETTLEMENT_REQUEST"
      SETTLEMENT_COMPLETED = "SETTLEMENT_COMPLETED"  # 결정 19 신규
  ```
- [ ] `create_notification(... type: NotificationType ...)` 시그니처 변경
- [ ] 각 도메인 service에서 raw string 대신 Enum 사용 (5곳)
- [ ] `NotificationResponse.type: NotificationType` Literal 검증

#### 🆕 message Field validation
- [ ] `NotificationResponse.message` `max_length=255` (DB 일치)
- [ ] `Notification.message` 모델도 nullable=False 명시

#### 🆕 Pagination (결정 22)
- [ ] `GET /api/notifications` 에 `limit`/`offset` + `PaginatedResponse[NotificationResponse]` (PR11 패턴 사용)

#### 🆕 SETTLEMENT_COMPLETED 알림 처리
- PR-S1 에서 발생시키는 알림. PR8에선 Enum 추가만 (frontend 표시는 마지막 동기화).

#### 🆕 응답 형식
- [ ] `PATCH /api/notifications/{id}/read` 응답에 `response_model=MessageResponse` 명시 (PR13과 같이)

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

백엔드 모든 PR 머지 완료 후 진행. ~2-3일. **백엔드 변경이 frontend 전체 재작성 수준이라 새로 작성 권장**.

### 백엔드 호환 변경 (재작성 필수)
- API prefix 통일 (모든 호출 `/transactions/` + `/auth/` → `/api/transactions`, `/api/auth/`)
- Trailing slash 제거 (모든 `/api/X/` → `/api/X`)
- 정산 본인 행 추가 코드 제거 (settlements.js)
- calculate_debts 응답에서 display_name → participant_id 매칭 + PENDING 만 반환
- DELETE participant 버튼 추가
- 거래 삭제 확인 다이얼로그 (정산 cascade 안내)
- 0원 입력 시 422 에러 표시 (예산, 거래)
- `tx.category_name` 자동 표시 (PR3 T2 머지 후 자동)
- `tx.actual_amount` 표시 (PR10 머지 후 — 더치페이 거래는 amount + actual_amount 둘 다 표시)
- 마일스톤 알림 표시 (GOAL_MILESTONE 새 타입)
- **SETTLEMENT_COMPLETED 알림 표시** (결정 19 새 타입 — "정산 완료" 알림)
- SETTLED 참여자 수정 UI 비활성화
- SETTLEMENT_REQUEST 알림 표시 (이미 준비됨)
- 일괄 읽음/미확인 필터/삭제 알림 UI
- 페이지네이션 UI + 필터 UI (E3) — PaginatedResponse 패턴
- CSV export 다운로드 버튼 (E4)
- 거래 renderList 재작성 (페이지네이션 동반)
- **CSV import 한글 매핑** — "지출"/"수입" 그대로 보내도 됨 (백엔드가 매핑)
- `/api/auth/` 통일 (모든 auth 호출 변경)

### Goals 페이지 수정 (PR2 머지 영향)
- `goals.js:16` "진행중" 탭 `data-status="IN_PROGRESS"` → `data-status="ON_TRACK"` + `data-status="BEHIND"` 둘로 분리 (computed_status에 IN_PROGRESS 없음)
- 또는 "진행중" 탭을 빈 status (전체 - 완료/만료/취소 제외) 로 구성
- `goals.js:171` cancel 버튼 분기 `g.status === 'IN_PROGRESS'` → `!['ACHIEVED','EXPIRED','CANCELLED'].includes(g.status)` 로 변경
- `goals.js:112` 카테고리 필터 `INCOME` → `EXPENSE` (G2 픽스, spec 8: 저축 = EXPENSE 거래)

### API 호출 보강
- `api.js` refresh token 자동 갱신 로직 추가 (401 시 refresh 시도 후 재시도)
- `csv-import.js:161` 직접 fetch → `api.request` 우회 안 함

### 예산 페이지 (PR4 응답 형식 변경 영향)
- `budget.js` 응답 구조 `{overall, categories}` → `{year_month, budgets: []}` 단일 배열
- 필드 이름 변경: `budget_amount` → `budget`, `spent_amount` → `spent`, `usage_percentage` → `usage_rate`
- `remaining` 필드 활용

### 통계 페이지 (PR10 응답 형식 변경 영향)
- `total_amount` → `total_expense` / `total_income` (type 별)

### CSV import 페이지
- 응답 형식 변경 — `imported_count` → `imported`, `duplicate_count` → `skipped_duplicate`, `errors` → `[{row, reason}]`
- `failed` 카운트 추가 표시

### 사용자 검색 (PR-S1 신규)
- 정산 참여자 추가 시 이메일 검색 UI — `GET /api/users/search?email=...`
- 검색 결과로 user_id 자동 채움 + 비회원 모드 토글

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

### F8. Settlement 모델 Numeric drift (PR-S1)
**상황**: PR1 머지된 마이그레이션은 DB를 Numeric(12,0) 으로 변경했는데 모델은 Numeric(12,2) 그대로.
**영향**: PR-S1 에서 모델만 수정 (마이그레이션 불필요). autogenerate 돌리면 의미 없는 diff 생성됨.

### F9. CSV 한글 type 처리 누락 (PR5)
**상황**: spec 7.2 예시는 "지출"/"수입" 한글인데 코드는 영문 그대로 사용 → 한글 CSV 업로드 시 모든 행 fail.
**영향**: PR5 에서 한글→영문 매핑 (`{"지출": "EXPENSE", "수입": "INCOME"}`) 추가 필수.

### F10. dependencies.py 인증 우회 (PR-S2)
**상황**: `app/dependencies.py` 에 MockUser 항상 반환하는 dead code. 어디서도 import 안 되지만 오타로 `app.dependencies` (vs `app.auth.dependencies`) import 시 인증 전체 우회.
**영향**: PR-S2 (5분) 로 파일 삭제. CONTRIBUTING.md:133 거짓 표기도 같이 수정.

### F11. 초기 마이그레이션 drift (PR15)
**상황**: 3803b7878290 에 server_default 누락, downgrade 순서 오류, enum DROP 누락.
**영향**: 운영 가면 alembic upgrade/downgrade 깨짐. PR15 에서 보강.

### F12. Race condition 다수 (PR4, PR14, PR15)
**상황**: add_participant 중복 row, upsert_budget 500, check_and_notify_* 중복 알림. 모두 application 체크만 있고 DB 보호 없음.
**영향**: PR15 partial UNIQUE 인덱스 + PR4 ON CONFLICT + PR14 트랜잭션 경계로 해결.

---

## 🎬 작업 시작 순서 (업데이트 2026-05-28)

**현재 상태**: PR1 ✅ 머지됨, PR2 김동준 진행 중 (코멘트 16개 받음). 아래는 PR2 머지 가정 일정.

| Day | 함준규 | 김동준 | 베키 | 김민수 |
|---|---|---|---|---|
| **Day 0 (지금)** | PR-S2 (5분, 즉시) | PR2 코멘트 처리 (머지 차단 4개 우선) | (대기) | (대기) |
| **Day 1** | PR-S1 시작 (Settlement 통합 fix) | PR2 마무리 + 머지 | PR3 시작 | PR5 시작 |
| **Day 2** | PR-S1 마무리 | PR4 시작 (PR3 후) | PR3 마무리 + PR12 시작 | PR5 마무리 + PR6 시작 |
| **Day 3** | PR10 시작 (PR-S1+PR3 후) | PR4 마무리 + PR11 시작 | PR12 마무리 + PR15 시작 | PR6 마무리 + PR7 시작 |
| **Day 4** | PR10 마무리 + PR14 시작 | PR11 마무리 | PR15 마무리 + PR13 시작 | PR7 마무리 + PR8 시작 |
| **Day 5** | PR14 마무리 + PR16 시작 | (pytest) | PR13 마무리 | PR8 마무리 + PR9 |
| **Week 2** | PR16 마무리 + 다이어그램 + frontend 동기화 | pytest | pytest | pytest |

### 핵심 의존성
- **PR2 머지** → PR-S1 + PR3 + PR5 등 병렬 시작
- **PR3 머지** → PR4, PR11, PR12 시작 가능
- **PR-S1 + PR3 머지** → PR10 시작 가능
- **PR10 머지** → PR14 시작 가능
- **모든 도메인 PR 머지** → PR13 (API 일관성), PR15 (DB constraint), PR16 (마무리)

## 🛑 운영 전 체크리스트 (학기 평가 무관, 추후 작업)

검토 중 발견된 항목 중 학기 프로젝트 평가 무관하지만 운영 가면 반드시 처리 필요. 별도 백로그.

### 인프라 / 보안
- [ ] **`.env` SECRET_KEY 강화** — 운영 환경 분리 + `python -c "import secrets; print(secrets.token_urlsafe(64))"` 로 생성된 값 사용
- [ ] **`app/config.py` validation** — `SECRET_KEY: str = Field(min_length=32)`, `DATABASE_URL` 형식 검증
- [ ] **보안 헤더** — X-Frame-Options, CSP, HSTS, X-Content-Type-Options (middleware 추가)
- [ ] **Rate limiting** — slowapi 또는 nginx 단에서. 로그인 brute force 방어
- [ ] **CORS allow_origins env 분리** — 현재 hardcoded
- [ ] **Logging / observability** — Python logging 도입. 현재 print/logger 0건. uvicorn access log 외 부재
- [ ] **만료 RefreshToken cleanup job** — cron / scheduler 로 주기적 정리

### 코드 품질
- [ ] **모든 모델 `__repr__` 추가** — 디버깅 가독성
- [ ] **type hint 누락** — settlements/service.py + transactions/service.py 거의 모든 함수
- [ ] **Pydantic 패턴 통일** — `class Config` (v1) / `dict` (v2 dict) / `ConfigDict` (v2) 3가지 혼용 → ConfigDict
- [ ] **SQLAlchemy 1.x/2.x 패턴 통일** — legacy `.query()` (대부분) vs 2.x `select()` (statistics) vs `db.scalars()` 혼용
- [ ] **import 순서 (PEP 8)** — isort 적용. 다수 파일 위반
- [ ] **매직 넘버 상수화** — 80/100 (budget), 25/50/75/100 (goals), 500 (csv batch), 5MB, 1000
- [ ] **`if not X` vs `if X is None`** — CONTRIBUTING 6.5 위반 다수
- [ ] **`==` vs `.is_(None)`** — csv_import, goals 의 SQLAlchemy 쿼리 (categories는 OK)
- [ ] **알림 type 5곳 hardcoded** — NotificationType Enum 추출 (PR8에 포함)
- [ ] **datetime.utcnow 13곳** vs `datetime.now(timezone.utc)` (auth만) — F5 결정 작업 안 함

### 인프라 도구
- [ ] **`requirements.txt`** pip freeze → pyproject.toml + uv lock 또는 base/pinned 분리
- [ ] **`.env.example`** placeholder 영문화 ("본인비밀번호" → `<your-postgres-password>`)
- [ ] **`.gitignore`** `.mypy_cache/`, `.ruff_cache/`, `*.log` 추가. `alembic/versions/__pycache__/` redundant 라인 제거
- [ ] **pre-commit hooks** — black, isort, ruff 자동 적용
- [ ] **CI 파이프라인** — GitHub Actions + pytest

### 테스트
- [ ] **테스트 커버리지** — 현재 0% (PR2 의 test_goals.py 외). 각 도메인 happy path + error path 작성. 목표 80%
- [ ] **통합 테스트** — 시나리오 기반 (사용자 가입 → 거래 → 정산 → 통계 사이클)
- [ ] **부하 테스트** — locust 또는 k6

### 운영 가시성
- [ ] **API 메트릭** — Prometheus + Grafana
- [ ] **에러 트래킹** — Sentry
- [ ] **APM** — DataDog / NewRelic

### 마이그레이션 / DB
- [ ] **`donote-schema.sql` 재생성** — PR15 완료 후 `pg_dump` (PR15 마지막 단계)
- [ ] **DB connection pool 튜닝** — pool_size, max_overflow 명시
- [ ] **DB 백업 전략**

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
