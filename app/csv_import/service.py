import csv
import hashlib
import io
import uuid
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

def parse_csv_content(decoded_content: str) -> Iterator[CSVRowData]:
    """문자열로 디코딩된 CSV 내용을 읽어 필수 컬럼을 포함한 CSVRowData 제너레이터로 반환합니다."""
    reader = csv.DictReader(io.StringIO(decoded_content))
    
    for index, row in enumerate(reader, start=2):
        amount_str = row.get("금액", "0").replace(",", "").strip()
        try:
            amount = float(amount_str) if amount_str else 0.0
        except ValueError:
            amount = 0.0

        yield CSVRowData(
            row_number=index,
            transaction_date=row.get("날짜", "").strip(),
            type=row.get("유형", "EXPENSE").strip().upper(),
            category=row.get("카테고리", "").strip(),
            amount=amount,
            memo=row.get("메모", "").strip()
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
    
    for row_hash, row in row_hashes.items():
        if row_hash in existing_hashes:
            result.duplicate_count += 1
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

        # 중복이 아닌 유효한 데이터 통과
        new_hashes_to_insert.append(ImportHash(user_id=user_id, hash=row_hash))
        result.valid_rows.append(row)
        result.imported_count += 1

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
        
    # 해시 및 실제 거래 데이터 일괄 DB 삽입
    if new_hashes_to_insert:
        db.bulk_save_objects(new_hashes_to_insert)
    if transactions_to_insert:
        db.bulk_save_objects(transactions_to_insert)
    db.commit()

def process_csv_import(db: Session, user_id: uuid.UUID, row_generator: Iterator[CSVRowData]) -> ImportResult:
    result = ImportResult()
    batch_size = 500
    batch = []
    
    # 카테고리 자동 매칭을 위한 사용자/시스템 카테고리 맵 구축
    categories = db.query(Category).filter(
        or_(Category.user_id == user_id, Category.user_id == None)
    ).all()
    category_map = {(c.name, c.type): c.id for c in categories}
    
    for row in row_generator:
        batch.append(row)
        if len(batch) >= batch_size:
            process_import_batch(db, user_id, batch, result, category_map)
            batch.clear()
            
    if batch:
        process_import_batch(db, user_id, batch, result, category_map)
        
    return result