# 기능 명세서 (Feature Specification)

**프로젝트명**: Donote

## 1. 회원 인증 (Authentication)

### 1.1 개요
사용자 식별 및 보안을 위한 JWT 기반 무상태(Stateless) 인증 시스템.

### 1.2 데이터 구조

**사용자 (users)**

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 사용자 고유 ID |
| email | STRING | 이메일 (고유, 로그인 ID) |
| password_hash | STRING | bcrypt 해싱된 비밀번호 |
| name | STRING | 실명 (2~20자) |
| created_at | DATETIME | 가입 시각 |

### 1.3 기능 상세

#### 회원가입
- **입력**:

  | 필드 | 필수 | 조건 |
  |---|---|---|
  | 이메일 | O | 이메일 형식 (RFC 5322), 중복 불가 |
  | 비밀번호 | O | 최소 8자, 영문 + 숫자 조합 |
  | 비밀번호 확인 | O | 비밀번호와 일치해야 함 |
  | 이름 | O | 2~20자, 실명 (정산 시 상대방에게 표시됨) |

- **동작**:
  1. 모든 필드 유효성 검증
  2. 이메일 중복 여부 확인 → 중복 시 409 Conflict
  3. 비밀번호를 bcrypt로 해싱하여 저장
  4. 사용자 레코드 생성 후 사용자 ID 반환
- **실패 응답**:
  - 유효성 실패: 422 Unprocessable Entity (어떤 필드가 왜 실패했는지 명시)
  - 이메일 중복: 409 Conflict

#### 로그인
- **입력**:

  | 필드 | 필수 | 조건 |
  |---|---|---|
  | 이메일 | O | 가입된 이메일 |
  | 비밀번호 | O | 해당 계정의 비밀번호 |

- **동작**:
  1. 이메일로 사용자 조회
  2. 입력된 비밀번호와 저장된 해시 비교
  3. 일치 시 Access Token (단기, 30분) + Refresh Token (장기, 7일) 발급
  4. Refresh Token은 DB에 저장하여 관리
- **실패 시**: 401 Unauthorized (이메일/비밀번호 구분 없이 "이메일 또는 비밀번호가 일치하지 않습니다" 메시지 → 보안상 어떤 필드가 틀렸는지 노출하지 않음)

#### 토큰 갱신
- **입력**: Refresh Token
- **동작**:
  1. Refresh Token의 유효성 및 만료 여부 확인
  2. DB에 저장된 Refresh Token과 일치 여부 확인
  3. 유효하면 새로운 Access Token 발급
- **실패 시**: 401 응답, 재로그인 요구

#### 로그아웃
- **입력**: Refresh Token
- **동작**:
  1. DB에서 해당 Refresh Token 삭제 (무효화)
  2. 클라이언트는 로컬에 저장된 토큰을 삭제

#### 내 정보 조회
- **입력**: 없음 (Access Token에서 사용자 식별)
- **동작**:
  1. Access Token에서 user_id 추출
  2. 사용자 정보 반환 (id, email, name, created_at)
- **응답**: 비밀번호 해시는 절대 반환하지 않음

#### 비밀번호 변경
- **입력**:

  | 필드 | 필수 | 조건 |
  |---|---|---|
  | 현재 비밀번호 | O | 기존 비밀번호 확인용 |
  | 새 비밀번호 | O | 최소 8자, 영문 + 숫자 조합 |
  | 새 비밀번호 확인 | O | 새 비밀번호와 일치해야 함 |

- **동작**:
  1. 현재 비밀번호가 맞는지 확인
  2. 불일치 시 400 Bad Request
  3. 새 비밀번호를 bcrypt로 해싱하여 저장
  4. 기존 Refresh Token 전체 무효화 (보안상 재로그인 유도)

#### 인증 흐름 요약
```
[클라이언트]                           [서버]
    │                                    │
    ├── POST /auth/signup ──────────────►│ 회원가입
    │                                    │
    ├── POST /auth/login ───────────────►│ Access + Refresh Token 반환
    │◄───────────────────────────────────┤
    │                                    │
    ├── GET /api/... ───────────────────►│ Authorization: Bearer {AccessToken}
    │   (Header에 Access Token 포함)      │ → 토큰 검증 후 응답
    │◄───────────────────────────────────┤
    │                                    │
    ├── POST /auth/refresh ─────────────►│ Refresh Token으로 새 Access Token 발급
    │◄───────────────────────────────────┤
    │                                    │
    ├── POST /auth/logout ──────────────►│ Refresh Token 무효화
    │                                    │
```

---

## 2. 지출/수입 관리 (Transactions)

### 2.1 개요
사용자의 모든 금전 거래를 기록하고 조회하는 핵심 CRUD 기능.
통화 단위는 **KRW(원)** 고정.

### 2.2 데이터 구조

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 거래 고유 ID |
| user_id | UUID | 소유자 (FK → users) |
| type | ENUM | `INCOME` / `EXPENSE` |
| amount | DECIMAL | 금액 (양수, KRW) |
| category_id | UUID | 카테고리 (FK → categories) |
| description | STRING | 메모/설명 (선택) |
| transaction_date | DATE | 거래 발생일 |
| transaction_time | TIME (nullable) | 거래 발생 시각 (선택 입력, 미입력 시 NULL) |
| created_at | DATETIME | 기록 생성 시각 |
| updated_at | DATETIME | 최종 수정 시각 |

### 2.3 기능 상세

#### 거래 생성
- **입력**: type, amount, category_id, description(선택), transaction_date, transaction_time(선택)
- **동작**:
  1. 요청 데이터 유효성 검증 (금액 > 0, 카테고리 존재 여부 등)
  2. 현재 로그인 사용자의 user_id를 자동 매핑
  3. DB에 거래 레코드 삽입
  4. 생성된 거래 정보 반환

#### 거래 수정
- **입력**: transaction_id, 수정할 필드들
- **동작**:
  1. 해당 거래가 존재하는지, 본인의 거래인지 확인
  2. 부분 수정(PATCH) 지원: 보낸 필드만 업데이트
  3. updated_at 자동 갱신
- **금액 변경 시 정산 연동**:
  - 더치페이가 연결된 거래의 amount 변경 → settlement.total_amount 자동 업데이트
  - EQUAL 모드: 참여자별 amount 자동 재분배 (creator 나머지 흡수 알고리즘)
  - CUSTOM 모드: 참여자별 금액 0으로 초기화 → 사용자가 다시 입력해야 함
  - SETTLED 참여자의 amount는 유지 (송금 완료 사실 보존)

#### 거래 삭제
- **입력**: transaction_id
- **동작**:
  1. 본인 거래 확인
  2. 연결된 정산이 있어도 삭제 허용 (가계부 기록의 자유 원칙)
  3. 하드 삭제 처리
- **연쇄 동작 (FK CASCADE)**:
  - 연결된 정산(Settlement) 자동 삭제
  - 정산의 참여자(SettlementParticipant) 자동 삭제
- **클라이언트 UX 권장**:
  - 정산이 연결된 경우 삭제 전 사용자 확인 다이얼로그 표시
  - "이 거래에 연결된 정산이 함께 삭제됩니다" 안내
- **삭제 방식**: 하드 삭제

#### 거래 조회

**단건 조회**:
- transaction_id로 상세 정보 반환
- 더치페이가 연결된 경우: 원래 금액(amount)과 실부담액(actual_amount) 모두 표시

**목록 조회**:
- 기본: 최신순 정렬, 페이지네이션 (offset + limit)
- 더치페이 연결된 거래는 원래 금액(amount)과 실부담액(actual_amount) 모두 표시
- **필터 옵션**:
  - `type`: 지출만 / 수입만
  - `category_id`: 특정 카테고리
  - `date_from`, `date_to`: 날짜 범위
  - `amount_min`, `amount_max`: 금액 범위
  - `keyword`: 메모 텍스트 검색
- **정렬 옵션**: 날짜순(기본), 금액순

#### 거래 조회 동작 흐름
```
GET /api/transactions?type=EXPENSE&date_from=2026-03-01&date_to=2026-03-31&category_id=xxx

1. Access Token에서 user_id 추출
2. 해당 user의 거래만 필터링 (다른 사용자 데이터 접근 불가)
3. 쿼리 파라미터 기반 WHERE 조건 조립
4. 페이지네이션 적용
5. 결과 반환: { items: [...], total: 45, page: 1, limit: 20 }
```

---

## 3. 카테고리 관리 (Categories)

### 3.1 개요
거래를 분류하기 위한 카테고리 시스템. 시스템 기본 카테고리 + 사용자 커스텀 카테고리.

### 3.2 데이터 구조

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 카테고리 고유 ID |
| user_id | UUID (nullable) | NULL이면 시스템 기본, 값이 있으면 사용자 커스텀 |
| name | STRING | 카테고리명 |
| type | ENUM | `INCOME` / `EXPENSE` |

### 3.3 기능 상세

#### 시스템 기본 카테고리 (수정/삭제 불가)

**지출용** (11개):
식비, 카페/간식, 교통, 생활/마트, 쇼핑, 주거/통신, 의료/건강, 문화/여가, 교육, 경조사/회비, 기타

**수입용** (4개):
급여/알바, 용돈, 금융소득, 기타

#### 커스텀 카테고리 CRUD
- **생성**: 이름, 유형(지출/수입) 지정 → 해당 사용자에게만 표시
- **수정**: 이름 변경 가능
- **삭제**: 해당 카테고리를 사용 중인 거래가 있으면 → 삭제 차단 (거래를 먼저 다른 카테고리로 이동 또는 삭제 필요)
- **조회**: 시스템 기본 + 내 커스텀 카테고리 통합 목록 반환

#### 카테고리 조회 동작
```
GET /api/categories?type=EXPENSE

응답:
[
  { id: "...", name: "식비",    type: "EXPENSE", is_system: true  },
  { id: "...", name: "교통",    type: "EXPENSE", is_system: true  },
  ...
  { id: "...", name: "헬스장",  type: "EXPENSE", is_system: false },  ← 커스텀
]
```

---

## 4. 통계 (Statistics)

### 4.1 개요
사용자의 거래 데이터를 집계하여 소비 패턴을 분석하는 읽기 전용 API.
모든 통계는 **실부담액(actual_amount) 기준**으로 집계한다. (더치페이로 돌려받은 금액을 차감한 실제 내 지출)

### 4.2 기능 상세

#### 기간별 합계
- **입력**: 기간 단위 (daily / weekly / monthly), 시작일, 종료일
- **동작**:
  1. 해당 기간의 거래를 단위별로 그룹핑
  2. 각 그룹의 지출 합계, 수입 합계 계산
- **응답 예시** (월별):
```json
{
  "period": "monthly",
  "data": [
    { "label": "2026-01", "income": 1500000, "expense": 1200000 },
    { "label": "2026-02", "income": 1500000, "expense": 980000 },
    { "label": "2026-03", "income": 1500000, "expense": 750000 }
  ]
}
```

#### 카테고리별 통계
- **입력**: 시작일, 종료일, 유형 (지출/수입)
- **동작**:
  1. 기간 내 거래를 카테고리별로 그룹핑
  2. 각 카테고리의 합계, 비율(%) 계산
  3. 금액 내림차순 정렬
- **응답 예시**:
```json
{
  "total_expense": 980000,
  "categories": [
    { "name": "식비",   "amount": 350000, "ratio": 35.7 },
    { "name": "교통",   "amount": 150000, "ratio": 15.3 },
    { "name": "쇼핑",   "amount": 120000, "ratio": 12.2 },
    ...
  ]
}
```

#### 월간 리포트
- **입력**: 연-월 (예: 2026-03)
- **동작**:
  1. 해당 월의 총수입, 총지출, 순수익(수입-지출) 계산
  2. 카테고리별 지출 TOP 5 추출
  3. 전월 대비 지출 증감률 계산
  4. 일평균 지출 계산
- **응답 예시**:
```json
{
  "month": "2026-03",
  "total_income": 1500000,
  "total_expense": 750000,
  "net": 750000,
  "daily_average_expense": 37500,
  "vs_last_month": {
    "expense_change": -23.5,
    "message": "전월 대비 23.5% 감소"
  },
  "top_categories": [
    { "name": "식비", "amount": 280000 },
    { "name": "교통", "amount": 95000 },
    ...
  ]
}
```

---

## 5. 예산 관리 (Budget)

### 5.1 개요
월별 지출 한도를 설정하고, 현재 소비 상황을 실시간으로 추적하는 기능.
지출 집계는 통계와 동일하게 **실부담액(actual_amount) 기준**으로 계산한다.

### 5.2 데이터 구조

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 예산 고유 ID |
| user_id | UUID | 소유자 |
| year_month | STRING | 대상 연월 (예: "2026-03") |
| category_id | UUID (nullable) | NULL이면 전체 예산, 값이 있으면 카테고리별 예산 |
| amount | DECIMAL | 예산 금액 |

### 5.3 기능 상세

#### 예산 설정
- **입력**: year_month, amount, category_id(선택)
- **동작**:
  1. 같은 연월 + 같은 카테고리의 기존 예산이 있으면 → 금액 업데이트
  2. 없으면 → 새로 생성
  3. 전체 예산과 카테고리별 예산은 독립적으로 존재 가능
- **예시**:
  - 3월 전체 예산: 100만원
  - 3월 식비 예산: 35만원
  - 3월 교통 예산: 10만원

#### 예산 현황 조회
- **입력**: year_month
- **동작**:
  1. 설정된 예산 목록 조회
  2. 각 예산에 대해 해당 월의 실제 지출 합계를 실시간 계산
  3. 잔여액, 소진율(%) 산출
- **응답 예시**:
```json
{
  "year_month": "2026-03",
  "budgets": [
    {
      "category": null,
      "label": "전체",
      "budget": 1000000,
      "spent": 750000,
      "remaining": 250000,
      "usage_rate": 75.0,
      "status": "SAFE"
    },
    {
      "category": "식비",
      "budget": 350000,
      "spent": 280000,
      "remaining": 70000,
      "usage_rate": 80.0,
      "status": "WARNING"
    }
  ]
}
```

#### 예산 삭제
- **입력**: budget_id
- **동작**:
  1. 해당 예산이 본인의 것인지 확인
  2. 하드 삭제 (해당 월의 예산 설정 해제)
- 삭제해도 기존 거래 데이터에는 영향 없음

#### 예산 상태 기준

| 상태 | 조건 | 설명 |
|---|---|---|
| `SAFE` | 소진율 < 80% | 정상 범위 |
| `WARNING` | 80% ≤ 소진율 < 100% | 주의 필요 |
| `EXCEEDED` | 소진율 ≥ 100% | 예산 초과 |

---

## 6. 더치페이 정산 (Dutch Pay Settlement)

### 6.1 개요
지출 기록에 더치페이 정보를 연결하여, 다른 사람에게 받아야 할 금액을 추적하고 정산 상태를 관리하는 기능.

### 6.2 데이터 구조

**정산 그룹 (settlements)**

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 정산 고유 ID |
| transaction_id | UUID | 연결된 지출 (FK → transactions) |
| creator_id | UUID | 정산 생성자 (= 결제한 사람) |
| total_amount | DECIMAL | 정산 대상 총 금액 |
| split_type | ENUM | `EQUAL` (균등) / `CUSTOM` (직접 입력) |
| status | ENUM | `IN_PROGRESS` / `COMPLETED` / `CANCELLED` |
| created_at | DATETIME | 생성 시각 |

**정산 참여자 (settlement_participants)**

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 참여자 레코드 ID |
| settlement_id | UUID | 정산 그룹 (FK → settlements) |
| user_id | UUID (nullable) | 회원이면 계정 연결, 비회원이면 NULL |
| display_name | STRING | 표시 이름 (회원/비회원 모두 필수) |
| amount | DECIMAL | 이 참여자가 내야 할 금액 |
| status | ENUM | `PENDING` / `SETTLED` |
| settled_at | DATETIME (nullable) | 정산 완료 시각 |

### 6.3 기능 상세

#### ① 정산 생성

- **입력**: transaction_id, split_type, participants 배열
- **동작**:
  1. 해당 거래가 본인의 지출(EXPENSE)인지 확인
  2. 이미 연결된 정산이 있는지 확인 (중복 방지)
  3. split_type에 따라 금액 분배:
     - `EQUAL`: total_amount ÷ (참여자 수 + 1[나]) → 각자 부담금 정수 계산
       - 알고리즘: `per_person = total // (N + 1)` (N = 참여자 수)
       - 나누어떨어지지 않는 나머지 금액은 기록자(나)에게 귀속
       - 예: 100원, 친구 2명 → per_person = 100 // 3 = 33 → 친구 각 33원, 나 implicit = 100 - 66 = 34원
       - 특정 참여자의 금액을 직접 수정하면 해당 참여자는 금액 고정, 나머지 인원이 잔여 금액을 균등 재분배
     - `CUSTOM`: 클라이언트가 각 참여자별 금액 직접 지정 (정수만)
  4. 참여자 레코드 생성 (나를 제외한 사람들만 SettlementParticipant 테이블에 저장)
     - 내 몫은 implicit (DB에 저장되지 않고 `total - SUM(participants)` 로 계산)
  5. 참여자 중 user_id가 있으면 → 해당 사용자에게 SETTLEMENT_REQUEST 알림 자동 생성
  6. 회원 참여자 연결: 이메일로 검색하여 연결, 미가입 사용자는 비회원(이름만 입력)으로 등록
  7. 금액 단위: KRW 정수 (소수점 없음)
- **검증**:
  - 참여자 최소 1명 이상
  - 내 몫 = 전체 금액 - 참여자 금액 합계 → 내 몫 < 0 이면 400 Bad Request 반환
  - CUSTOM 모드: 각 참여자 금액 > 0 검증
  - 같은 사람(동일 user_id) 중복 추가 불가
  - 생성자(나) 자신을 참여자로 추가 불가

**동작 흐름 예시**:
```
나: 저녁 50,000원 지출 기록 완료 (transaction_id: txn_001)

POST /api/settlements
{
  "transaction_id": "txn_001",
  "split_type": "EQUAL",
  "participants": [
    { "display_name": "A", "user_id": "user_a_id" },   ← 회원
    { "display_name": "B", "user_id": "user_b_id" },   ← 회원
    { "display_name": "김철수" }                         ← 비회원 (user_id 없음)
  ]
}

결과:
- 4인 균등 분배 → 1인당 12,500원
- 나의 실부담액: 12,500원 (정산 생성 시점에 즉시 확정)
- participant A: 12,500원 PENDING (A의 화면에 요청 표시됨)
- participant B: 12,500원 PENDING (B의 화면에 요청 표시됨)
- participant 김철수: 12,500원 PENDING (비회원이라 내가 관리)
```

#### ② 정산 완료 처리

**내가 수동으로 처리하는 경우 (비회원 또는 직접 확인)**:
- **입력**: settlement_id, participant_id
- **동작**:
  1. 해당 정산의 생성자가 본인인지 확인
  2. 참여자 상태를 `PENDING` → `SETTLED`로 변경
  3. settled_at에 현재 시각 기록
  4. 모든 참여자가 SETTLED면 → 정산 전체 상태를 `COMPLETED`로 변경

**상대방(회원)이 직접 처리하는 경우**:
- **입력**: settlement_id, participant_id
- **동작**:
  1. 해당 participant의 user_id가 본인인지 확인
  2. 상태를 `PENDING` → `SETTLED`로 변경
  3. 이하 동일

**동작 흐름**:
```
[초기 상태]
  A: PENDING (12,500원)
  B: PENDING (12,500원)
  김철수: PENDING (12,500원)
  → 정산 상태: IN_PROGRESS
  → 내 실부담: 12,500원 (생성 시점에 확정, 이후 변동 없음)
  → 미수금(아직 못 돌려받은 돈): 37,500원

[A가 입금 후, A가 직접 "정산 완료" 클릭]
  A: SETTLED ✓
  → 미수금: 37,500 - 12,500 = 25,000원

[김철수가 카톡으로 송금, 내가 수동으로 "받음" 처리]
  김철수: SETTLED ✓
  → 미수금: 25,000 - 12,500 = 12,500원

[B가 입금 후 완료 처리]
  B: SETTLED ✓
  → 전원 완료 → 정산 상태: COMPLETED
  → 미수금: 0원
```

#### ③ 정산 현황 조회

**내가 만든 정산 목록**:
```
GET /api/settlements?role=creator

→ 내가 결제한 건들의 정산 진행률 확인
  - 저녁 50,000원: 2/3 완료 (66%)
  - 택시 16,000원: 3/3 완료 (100%)
```

**내가 요청받은 정산 목록** (회원 연결 시):
```
GET /api/settlements?role=participant

→ 다른 사람이 나에게 보낸 정산 요청
  - OO님의 점심 32,000원 중 8,000원 → PENDING
  - XX님의 생일파티 100,000원 중 20,000원 → SETTLED
```

#### ④ 정산 수정
- **조건**: 정산 생성자만 가능
- **수정 가능 항목**: 참여자 추가/제거, 참여자별 금액 변경, 분배 방식 변경
- **수정 제한 (세밀 처리)**:
  - **IN_PROGRESS 정산**:
    - 새 참여자 추가: 허용
    - PENDING 참여자 amount 수정/제거: 허용
    - SETTLED 참여자 amount 수정/제거: **차단** (revert 먼저 필요)
    - split_type 변경: 허용
  - **COMPLETED 정산**: 모든 수정 차단 (revert로 IN_PROGRESS 복원 후 수정 가능)
  - **CANCELLED 정산**: 모든 수정 차단
- **동작**:
  1. 해당 정산의 생성자가 본인인지 확인
  2. 정산 상태 및 참여자 상태 검증 (위 제한 적용)
  3. 요청된 필드 업데이트
  4. EQUAL 모드에서 특정 참여자 금액 수정 시: ①과 동일하게 나머지 인원 자동 재분배
  5. 금액 변경 시: 내 몫 < 0 이면 400 Bad Request 반환
  6. 회원 참여자가 있는 경우 변경 사항이 상대방 화면에 반영됨
- **검증**: ① 정산 생성과 동일한 검증 규칙 적용 (중복 추가 불가, 본인 추가 불가 등)
- **참고**: SETTLED 처리된 참여자는 "송금 받은 사실"을 보존하기 위해 직접 수정 차단. 필요 시 revert로 PENDING 복원 후 수정.

#### ⑤ 정산 완료 되돌리기 (SETTLED → PENDING)
- **조건**: 정산 생성자 또는 해당 참여자 본인(회원)
- **동작**:
  1. 참여자 상태를 `SETTLED` → `PENDING`으로 변경
  2. settled_at 초기화 (NULL)
  3. 정산 전체 상태가 `COMPLETED`였으면 → `IN_PROGRESS`로 되돌림

#### ⑥ 정산 취소
- **조건**: 정산 생성자만 가능, 언제든 취소 가능
- **동작**:
  1. 정산 상태를 `CANCELLED`로 변경
  2. 모든 참여자 상태 초기화
  3. 실부담액 계산에서 제외
- **참고**: 기록 관리 특성상 SETTLED 상태인 참여자가 있어도 취소 허용

### 6.4 실부담액 계산 로직
```
실부담액 = 원래 지출 금액 - Σ(SETTLED 상태인 참여자의 amount)

예: 50,000원 지출, 참여자 A(12,500원 PENDING), B(12,500원 PENDING), C(12,500원 PENDING)
→ 정산 생성 시점: 실부담액 = 50,000원 (아무도 송금 안 함)
→ A가 SETTLED 처리: 실부담액 = 50,000 - 12,500 = 37,500원
→ B가 SETTLED 처리: 실부담액 = 50,000 - 25,000 = 25,000원
→ C가 SETTLED 처리: 실부담액 = 50,000 - 37,500 = 12,500원 (모두 SETTLED → 정산 COMPLETED)
```

**실부담액은 SETTLED 진행에 따라 실시간으로 변동**한다. 친구로부터 돈을 실제로 돌려받을 때마다
통계/예산의 지출 집계에서 자연스럽게 차감된다.

참여자별 PENDING 상태는 **"아직 돌려받지 못한 돈" (= 미수금)** 을 의미하며,
SETTLED 상태는 **"돈을 받았으니 내 실제 지출에서 제외"** 됨을 의미한다.

이 설계는 **현금 흐름 (Cash Flow) 기반** 접근으로, 사용자의 통장 잔액 변동과 일치하는 직관적인 가계부 동작을 제공한다.

**CANCELLED 상태인 정산은 실부담액 계산에서 제외**된다 (참여자 amount 무시).

---

## 7. CSV 대량 가져오기 (Bulk Import)

### 7.1 개요
외부에서 내보낸 CSV 파일을 업로드하여 거래 데이터를 한 번에 등록하는 기능.
해싱 기반 중복 방어로 같은 파일을 여러 번 업로드해도 데이터가 중복 생성되지 않음.

**제한 사항**:
- 파일 크기: 최대 5MB
- 최대 행 수: 1,000행
- 지원 형식: 서비스 전용 CSV 형식만 지원 (은행별 템플릿은 추후 확장)

### 7.2 지원 CSV 형식

**기본 형식** (공통):
```csv
날짜,유형,금액,카테고리,메모
2026-03-15,지출,15000,식비,점심 김치찌개
2026-03-15,수입,1500000,급여,3월 알바비
2026-03-16,지출,1350,교통,버스
```

### 7.3 기능 상세

#### 업로드 및 처리 흐름
```
1. 클라이언트가 CSV 파일 업로드
   POST /api/import/csv  (multipart/form-data)

2. 서버에서 파일 파싱
   - 인코딩 감지 (UTF-8, EUC-KR 등)
   - 헤더 행 분석하여 컬럼 매핑
   - 각 행을 내부 스키마로 변환

3. 행별 유효성 검증
   - 날짜 형식: YYYY-MM-DD (ISO 8601)만 허용, 불일치 시 에러
   - 금액이 양수인지
   - 필수 필드 누락 여부

4. 중복 검사 (해싱)
   - 각 행에 대해: hash = SHA256(user_id + 날짜 + 금액 + 메모 + 파일 내 행 번호)
   - 행 번호를 포함하여, 같은 날 같은 금액의 실제 별개 거래는 정상 등록
   - 같은 파일 재업로드 시에는 행 번호가 동일하므로 중복 스킵
   - DB에 동일 해시가 존재하면 → 스킵 (중복)
   - 존재하지 않으면 → 신규 삽입

5. 결과 반환
```

#### 응답 예시
```json
{
  "total_rows": 150,
  "imported": 142,
  "skipped_duplicate": 6,
  "failed": 2,
  "errors": [
    { "row": 45, "reason": "금액이 유효하지 않음: 'abc'" },
    { "row": 98, "reason": "날짜 형식 오류: '2026/13/01'" }
  ]
}
```

#### 카테고리 매칭
- CSV의 카테고리 텍스트 → 시스템/커스텀 카테고리와 이름 매칭 시도
- 매칭 실패 시 → "기타" 카테고리로 자동 분류
- 매칭 결과를 응답에 포함하여 사용자가 확인 가능

---

## 8. 저축 목표 (Savings Goals)

### 8.1 개요
사용자가 특정 카테고리에 연결된 저축 목표를 설정하고, 해당 카테고리의 거래 합계로 진행률을 자동 추적하는 기능. 마일스톤(25/50/75/100%) 도달 시 자동 알림.

### 8.2 데이터 구조

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 목표 고유 ID |
| user_id | UUID | 소유자 (FK → users) |
| name | STRING | 목표 이름 (예: "여행자금") |
| target_amount | DECIMAL | 목표 금액 (양수) |
| target_date | DATE (nullable) | 달성 목표일 (선택) |
| category_id | UUID | 연결 카테고리 (FK → categories) |
| description | STRING (nullable) | 목표 메모 |
| status | ENUM | `IN_PROGRESS` / `ACHIEVED` / `EXPIRED` / `CANCELLED` |
| created_at | DATETIME | 생성 시각 |
| achieved_at | DATETIME (nullable) | 달성 시각 |
| is_25_notified | BOOLEAN | 25% 마일스톤 알림 발생 여부 |
| is_50_notified | BOOLEAN | 50% 마일스톤 알림 발생 여부 |
| is_75_notified | BOOLEAN | 75% 마일스톤 알림 발생 여부 |
| is_achieved_notified | BOOLEAN | 100% 달성 알림 발생 여부 |

### 8.3 기능 상세

#### 목표 생성
- **입력**: name, target_amount, target_date(선택), category_id, description(선택)
- **검증**: target_amount > 0, category 본인 소유 또는 시스템 카테고리
- **동작**:
  1. 새 Goal 레코드 생성 (status: IN_PROGRESS)
  2. 진행률 0%로 시작 (created_at 이후 거래만 카운트)

#### 목표 목록 조회
- **입력**: status 필터 (선택)
- **응답**: 각 목표에 current_amount, progress_percentage, status (계산값) 포함
- **status 종류**:
  - **영구 상태** (DB 저장): `IN_PROGRESS`, `ACHIEVED`, `EXPIRED`, `CANCELLED`
  - **계산 상태** (응답만): `ON_TRACK` (시간 대비 진행률 OK), `BEHIND` (시간 대비 뒤처짐)
- **응답 예시**:
```json
[
  {
    "id": "...",
    "name": "여행자금",
    "target_amount": 1000000,
    "current_amount": 500000,
    "progress_percentage": 50.0,
    "target_date": "2026-06-30",
    "status": "ON_TRACK",
    "category_id": "..."
  }
]
```

#### 진행률 자동 계산
- **로직**: 연결 카테고리의 **EXPENSE 거래 합계** = current_amount
  - 저축 = 일반 계좌에서 빠져나가는 돈 → EXPENSE로 분류
  - 예: "저축-여행" 카테고리에 50만원 EXPENSE 기록 → 여행자금 진행률 +50만원
- **시점**: goal.created_at 이후 거래만 카운트 (created_at < goal.created_at 거래 제외)

#### 상태 자동 판정 알고리즘
```
1. CANCELLED → CANCELLED 유지
2. target_amount <= 0 → ACHIEVED (current > 0) or IN_PROGRESS
3. progress_ratio >= 1.0 → ACHIEVED
4. target_date < today → EXPIRED
5. target_date 없음 → ON_TRACK
6. total_days <= 0 (마감일 == 오늘) → BEHIND
7. progress_ratio >= time_ratio → ON_TRACK
8. 그 외 → BEHIND
```

ON_TRACK / BEHIND 는 계산 상태이므로 DB에 persist 하지 않음.

#### 목표 수정
- **수정 가능**: name, target_amount, target_date, category_id, description
- **category_id 변경 시**: 진행률 재계산 (새 카테고리의 거래 기준)
- **target_amount = 0** → 422 거부

#### 목표 삭제
- **입력**: goal_id
- **동작**: 영구 삭제 (하드 삭제)

#### 목표 취소 (CANCELLED)
- **입력**: goal_id
- **동작**: status를 CANCELLED로 변경 (기록은 유지, 더 이상 진행률 추적 안 함)
- 삭제와 달리 기록 보존

#### 마일스톤 알림 (자동 생성)
- **트리거**: 거래 생성/수정/삭제 시
- **조건 및 동작**:
  - 진행률 >= 25% 이고 is_25_notified == false → 알림 생성, 플래그 True
  - 진행률 >= 50% 이고 is_50_notified == false → 알림 생성, 플래그 True
  - 진행률 >= 75% 이고 is_75_notified == false → 알림 생성, 플래그 True
  - 진행률 >= 100% 이고 is_achieved_notified == false → 알림 생성, 플래그 True, status=ACHIEVED, achieved_at 기록
- **플래그 리셋**: 진행률이 해당 임계값 아래로 떨어지면 플래그 False로 리셋 (재발화 가능)
  - 예: 거래 삭제로 50% → 40% 떨어지면 is_50_notified=False, 다시 50% 도달 시 재알림

#### 진행률 상세 조회
- **응답**: progress_percentage, remaining_amount, days_remaining, status, 예상 달성일(forecast), 월별 추이

---

## 9. 알림 시스템 (Notifications)

### 9.1 개요
사용자에게 주요 이벤트를 자동으로 알리는 능동적 시스템. DB 기반 알림 레코드를 폴링 방식으로 조회.

### 9.2 데이터 구조

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 알림 고유 ID |
| user_id | UUID | 수신자 (FK → users) |
| type | STRING | 알림 유형 (아래 참고) |
| message | STRING | 알림 본문 |
| is_read | BOOLEAN | 읽음 여부 |
| created_at | DATETIME | 발생 시각 |

### 9.3 알림 유형

| Type | 트리거 | 메시지 예시 |
|---|---|---|
| `BUDGET_WARNING` | 예산 사용률 80% 도달 | "이번달 식비 예산의 80%를 사용했습니다" |
| `BUDGET_EXCEEDED` | 예산 사용률 100% 초과 | "이번달 예산이 100% 사용되었습니다" |
| `GOAL_MILESTONE` | 저축 목표 25/50/75% 도달 | "여행자금 목표 75% 달성!" |
| `GOAL_ACHIEVED` | 저축 목표 100% 달성 | "🎉 목표 달성! 여행자금" |
| `SETTLEMENT_REQUEST` | 정산 참여자로 추가됨 | "OO님이 12,500원 정산을 요청했습니다" |

### 9.4 기능 상세

#### 알림 목록 조회
- **입력**: unread 필터 (선택)
- **응답**: 최신순 정렬된 알림 목록

#### 알림 읽음 처리
- **입력**: notification_id
- **동작**: is_read = true로 변경

#### 일괄 읽음 처리
- **동작**: 사용자의 모든 미확인 알림을 읽음 처리

#### 알림 삭제
- **입력**: notification_id
- **동작**: 알림 레코드 삭제 (하드 삭제)

#### 자동 알림 생성 로직
- **임계값 플래그 관리**: 같은 임계값 중복 알림 방지
  - 예: 예산 80% 알림 발생 후 is_warning_notified=True → 80% 유지/초과 동안 재알림 X
  - 임계값 아래로 떨어지면 플래그 False로 리셋 → 다시 도달 시 재알림 가능 (재발화)

---

## 10. 확장 기능 (Stretch Goals)

> 아래 기능들은 코어 기능(1~9) 완성 후, 여유가 있을 때 추가하는 기능입니다.

### 8.1 OCR + LLM 자동 분류

#### 개요
영수증 이미지를 업로드하면 텍스트를 추출하고, AI가 카테고리를 자동 분류하여 거래 초안을 생성하는 기능.
사용자는 초안을 확인/수정한 뒤 확정하면 실제 거래로 등록된다.

#### 데이터 구조

**영수증 (receipts)**

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 영수증 고유 ID |
| user_id | UUID | 업로드한 사용자 |
| image_url | STRING | 저장된 이미지 경로 |
| status | ENUM | `PROCESSING` / `COMPLETED` / `FAILED` |
| raw_text | TEXT (nullable) | OCR 추출 원본 텍스트 |
| parsed_date | DATE (nullable) | 추출된 거래 날짜 |
| parsed_amount | DECIMAL (nullable) | 추출된 금액 |
| parsed_store | STRING (nullable) | 추출된 상호명 |
| parsed_category_id | UUID (nullable) | LLM이 분류한 카테고리 |
| transaction_id | UUID (nullable) | 확정 후 연결된 거래 (FK → transactions) |
| error_message | STRING (nullable) | 실패 시 에러 내용 |
| created_at | DATETIME | 업로드 시각 |

#### 기능 상세

**① 영수증 업로드**
- **입력**: 이미지 파일 (multipart/form-data)
- **제한**: 파일 크기 최대 10MB, 지원 형식 JPG/PNG
- **동작**:
  1. 이미지 파일 저장
  2. 영수증 레코드 생성 (status: `PROCESSING`)
  3. 즉시 응답 반환 (receipt_id, status)
  4. 백그라운드에서 비동기 처리 시작

**② 비동기 처리 파이프라인**
```
1. Google Cloud Vision API로 이미지 → 텍스트 추출 (OCR)
   - 실패 시 → status: "FAILED", error_message 저장, 종료

2. 추출된 텍스트에서 정보 파싱
   - 날짜: 정규표현식으로 날짜 패턴 탐색
   - 금액: "합계", "총액", "결제금액" 등 키워드 주변 숫자 추출
   - 상호명: 텍스트 최상단 또는 사업자 정보 영역에서 추출

3. Gemini 1.5 Flash API에 Few-Shot 프롬프트로 카테고리 분류 요청
   - 입력: 상호명 + 추출 텍스트 요약
   - 출력: 시스템 카테고리 중 하나
   - 실패 시 → 카테고리를 "기타"로 설정 (Fallback)

4. 파싱 결과를 영수증 레코드에 저장, status: "COMPLETED"
```

**③ 처리 결과 조회**
- **입력**: receipt_id
- **응답**:
```json
{
  "id": "...",
  "status": "COMPLETED",
  "parsed_date": "2026-03-20",
  "parsed_amount": 15000,
  "parsed_store": "김밥천국 대학로점",
  "parsed_category": "식비",
  "raw_text": "김밥천국 대학로점\n...\n합계: 15,000원"
}
```

**④ 거래 확정**
- **입력**: receipt_id + 사용자가 수정한 필드 (선택)
- **동작**:
  1. 파싱 결과 기반으로 거래(transaction) 생성 (type은 EXPENSE 고정 - 영수증 = 지출)
  2. 사용자가 날짜, 금액, 카테고리를 수정했으면 수정된 값으로 생성
  3. 영수증 레코드의 transaction_id에 생성된 거래 연결
- **검증**: status가 `COMPLETED`인 영수증만 확정 가능

**⑤ 영수증 목록 조회**
- 처리 상태별 필터링 (PROCESSING / COMPLETED / FAILED)
- 확정 여부 필터링 (transaction_id 유무)


### 8.2 정기 구독 관리 (Scheduler)

#### 개요
매월 반복되는 고정 지출(넷플릭스, 통신비 등)을 등록하면, 스케줄러가 매월 자동으로 거래를 생성하는 기능.

#### 데이터 구조

**정기 구독 (subscriptions)**

| 필드 | 타입 | 설명 |
|---|---|---|
| id | UUID | 구독 고유 ID |
| user_id | UUID | 소유자 |
| name | STRING | 구독명 (예: "넷플릭스") |
| amount | DECIMAL | 월 결제 금액 |
| category_id | UUID | 카테고리 (FK → categories) |
| billing_day | INTEGER | 결제일 (1~31) |
| start_date | DATE | 구독 시작일 |
| end_date | DATE (nullable) | 구독 종료일 (NULL이면 해지 전까지 계속) |
| is_active | BOOLEAN | 활성 여부 |
| created_at | DATETIME | 등록 시각 |

#### 기능 상세

**① 구독 등록**
- **입력**: name, amount, category_id, billing_day, start_date
- **동작**:
  1. 유효성 검증 (billing_day: 1~31, amount > 0)
  2. 구독 레코드 생성 (is_active: true)
- **billing_day 예외 처리**: 31일로 설정했지만 해당 월이 30일까지인 경우 → 해당 월 마지막 날에 생성

**② 구독 수정**
- **수정 가능 항목**: name, amount, category_id, billing_day
- 다음 결제일부터 변경 사항 적용
- 이미 생성된 거래에는 영향 없음

**③ 구독 해지**
- **동작**:
  1. end_date를 현재 날짜로 설정
  2. is_active를 false로 변경
  3. 해지 시점 이후로는 자동 거래 생성 중단

**④ 구독 목록 조회**
- 활성/비활성 필터링
- 각 구독별 다음 결제 예정일, 누적 결제 금액 표시

**⑤ 스케줄러 동작** (APScheduler)
```
매일 자정(00:00)에 실행:

1. is_active = true인 모든 구독 조회
2. 각 구독에 대해:
   - 오늘 날짜 == billing_day 인지 확인
   - start_date 이후인지 확인
   - 이번 달에 이미 거래가 생성되었는지 확인 (중복 방지)
3. 조건 충족 시 → 지출 거래 자동 생성
   - type: EXPENSE
   - amount: 구독의 amount
   - category_id: 구독의 category_id
   - description: "정기 구독: {구독명}"
   - transaction_date: 오늘 날짜
4. 생성된 거래는 일반 거래와 동일하게 목록에 표시, 수정/삭제 가능
```


> **알림 시스템은 섹션 9 로 메인 spec 으로 승격됨** (코어 기능). 이전 8.3 내용은 9 섹션 참조.

---

## 부록: 코어 vs 확장 정리

| 구분 | 기능 | 우선순위 |
|---|---|---|
| 코어 | 회원 인증 (JWT) | 필수 |
| 코어 | 지출/수입 CRUD | 필수 |
| 코어 | 카테고리 관리 | 필수 |
| 코어 | 통계 | 필수 |
| 코어 | 예산 관리 | 필수 |
| 코어 | 더치페이 정산 | 필수 |
| 코어 | 저축 목표 | 필수 |
| 코어 | 알림 시스템 | 필수 |
| 코어 | CSV Bulk Import | 필수 |
| 확장 | OCR + LLM 자동 분류 | 선택 |
| 확장 | 정기 구독 관리 | 선택 |
| 확장 | 예산 템플릿/추천 | 선택 |
| 확장 | 카테고리 아이콘 커스터마이징 | 선택 |
