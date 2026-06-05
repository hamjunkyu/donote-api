import csv
import hashlib
import io
import uuid
from datetime import datetime
from typing import Iterator

from sqlalchemy.orm import Session
from sqlalchemy import or_

from .models import ImportHash
from .schemas import CSVRowData, ImportResult
from app.categories.models import Category
from app.transactions.models import Transaction

def generate_row_hash(user_id: uuid.UUID, row: CSVRowData) -> str:
    """
    명세에 따라 user_id + 날짜 + 금액 + 메모 + 행 번호 조합의 SHA-256 해시를 생성합니다.
    """
    raw_string = f"{user_id}:{row.transaction_date.isoformat()}:{row.amount}:{row.memo}:{row.row_number}"
    return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()

def parse_csv_content(decoded_content: str, result: ImportResult) -> Iterator[CSVRowData]:
    """디코딩된 CSV 내용을 행 단위로 검증해 CSVRowData 제너레이터로 반환한다.

    날짜·금액 형식 오류 행은 result.errors 에 행 번호와 함께 기록하고 건너뛴다
    (한 행이 잘못돼도 전체 import 가 중단되지 않도록).
    """
    reader = csv.DictReader(io.StringIO(decoded_content))

    for index, row in enumerate(reader, start=2):
        amount_str = row.get("금액", "").replace(",", "").strip()
        try:
            amount = float(amount_str) if amount_str else 0.0
        except ValueError:
            result.errors.append(f"Row {index}: 금액 형식 오류 ('{amount_str}')")
            continue

        # 유형: 한글(수입/지출)·영문(INCOME/EXPENSE) 모두 허용 → 영문으로 통일
        type_raw = row.get("유형", "EXPENSE").strip()
        type_value = {"수입": "INCOME", "지출": "EXPENSE"}.get(type_raw, type_raw.upper())

        # 날짜: YYYY-MM-DD 명시적 파싱. 형식 오류 행은 건너뛴다.
        date_str = row.get("날짜", "").strip()
        try:
            transaction_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            result.errors.append(f"Row {index}: 날짜 형식 오류 ('{date_str}', YYYY-MM-DD 필요)")
            continue

        yield CSVRowData(
            row_number=index,
            transaction_date=transaction_date,
            type=type_value,
            category=row.get("카테고리", "").strip(),
            amount=amount,
            memo=row.get("메모", "").strip(),
        )

def process_import_batch(
    db: Session, 
    user_id: uuid.UUID, 
    batch: list[CSVRowData], 
    result: ImportResult,
    category_map: dict
) -> None:
    """단일 배치 데이터에 대한 중복 검사, 해시 저장 및 거래(Transaction) 일괄 등록을 수행합니다."""
    result.total_rows += len(batch)
    
    row_hashes = {}
    for row in batch:
        h = generate_row_hash(user_id, row)
        if h in row_hashes:
            result.duplicate_count += 1
        else:
            row_hashes[h] = row
            
    existing_hashes_query = db.query(ImportHash.hash).filter(
        ImportHash.user_id == user_id,
        ImportHash.hash.in_(row_hashes.keys())
    ).all()
    
    existing_hashes = {r[0] for r in existing_hashes_query}
    new_hashes_to_insert = []
    transactions_to_insert = []
    valid_rows_batch = []

    for row_hash, row in row_hashes.items():
        if row_hash in existing_hashes:
            result.duplicate_count += 1
            continue

        # 금액 검증: 0 이하는 저장하지 않고 오류로 기록 (DB CHECK 제약과 일치).
        if row.amount <= 0:
            result.errors.append(
                f"Row {row.row_number}: 금액은 0보다 커야 합니다 (값: {int(row.amount)})"
            )
            continue

        # 카테고리 텍스트 자동 매칭 ((name, type) 조합). 실패 시 "기타"로 폴백.
        category_id = category_map.get((row.category, row.type))

        if category_id is None:
            category_id = category_map.get(("기타", row.type))

        if category_id is None:
            result.errors.append(
                f"Row {row.row_number}: 카테고리 '{row.category}' 매칭 실패 + 폴백 카테고리 없음"
            )
            continue

        new_hashes_to_insert.append(ImportHash(user_id=user_id, hash=row_hash))
        valid_rows_batch.append(row)
        transactions_to_insert.append(
            Transaction(
                user_id=user_id,
                category_id=category_id,
                type=row.type,
                amount=row.amount,
                transaction_date=row.transaction_date,
                description=row.memo,
            )
        )

    # 해시 + 거래를 한 트랜잭션으로 저장. 실패 시 배치 전체 롤백 (부분 저장 방지).
    try:
        if new_hashes_to_insert:
            db.bulk_save_objects(new_hashes_to_insert)
        if transactions_to_insert:
            db.bulk_save_objects(transactions_to_insert)
        db.commit()
    except Exception:
        db.rollback()
        result.errors.append(
            f"{len(transactions_to_insert)}개 행 저장 중 오류가 발생해 해당 배치가 롤백되었습니다."
        )
        return

    result.valid_rows.extend(valid_rows_batch)
    result.imported_count += len(transactions_to_insert)

def process_csv_import(db: Session, user_id: uuid.UUID, decoded_content: str) -> ImportResult:
    result = ImportResult()
    batch_size = 500
    batch = []

    # 카테고리 자동 매칭을 위한 사용자/시스템 카테고리 맵 구축
    categories = db.query(Category).filter(
        or_(Category.user_id == user_id, Category.user_id == None)
    ).all()
    category_map = {(c.name, c.type): c.id for c in categories}

    for row in parse_csv_content(decoded_content, result):
        batch.append(row)
        if len(batch) >= batch_size:
            process_import_batch(db, user_id, batch, result, category_map)
            batch.clear()

    if batch:
        process_import_batch(db, user_id, batch, result, category_map)

    return result