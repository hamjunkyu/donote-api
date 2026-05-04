import csv
import hashlib
import io
import uuid
from typing import Iterator

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from .models import ImportHash
from .schemas import CSVRowData, ImportResult


def generate_row_hash(user_id: uuid.UUID, row: CSVRowData) -> str:
    """
    행 데이터를 기반으로 SHA-256 해시를 생성합니다.
    (수정됨): 유지보수와 정확성을 위해 행 번호(row_number)를 해시 기준에서 제외했습니다.
    이제 파일 내 줄 위치가 바뀌어도 날짜, 금액, 메모만 같으면 정확히 중복으로 차단합니다.
    """
    raw_string = f"{user_id}:{row.transaction_date.isoformat()}:{row.amount}:{row.memo}"
    return hashlib.sha256(raw_string.encode("utf-8")).hexdigest()


def parse_csv_content(decoded_content: str) -> Iterator[CSVRowData]:
    """문자열로 디코딩된 CSV 내용을 읽어 CSVRowData 동기 제너레이터로 반환합니다."""
    reader = csv.DictReader(io.StringIO(decoded_content))
    
    for index, row in enumerate(reader, start=2): # 1행은 헤더
        # 금액 데이터에 포함될 수 있는 콤마(,) 제거나 빈 값 처리
        amount_str = row.get("금액", "0").replace(",", "").strip()
        try:
            amount = float(amount_str) if amount_str else 0.0
        except ValueError:
            amount = 0.0

        yield CSVRowData(
            row_number=index,
            transaction_date=row.get("날짜", "").strip(),
            amount=amount,
            memo=row.get("메모", "").strip()
        )


def process_csv_import(
    db: Session, 
    user_id: uuid.UUID, 
    rows: Iterator[CSVRowData], 
    batch_size: int = 1000
) -> ImportResult:
    """CSV 데이터 제너레이터를 받아 청크 단위로 중복 검사 후 DB에 반영합니다."""
    result = ImportResult()
    current_batch: list[CSVRowData] = []
    
    for row in rows:
        current_batch.append(row)
        if len(current_batch) >= batch_size:
            _process_batch(db, user_id, current_batch, result)
            current_batch.clear()
            
    # 남은 데이터 처리
    if current_batch:
        _process_batch(db, user_id, current_batch, result)
        
    return result


def _process_batch(
    db: Session, 
    user_id: uuid.UUID, 
    batch: list[CSVRowData], 
    result: ImportResult
) -> None:
    """단일 배치 데이터에 대한 중복 검사 및 해시 저장 로직을 수행합니다."""
    result.total_rows += len(batch)
    
    row_hashes = {}
    for row in batch:
        h = generate_row_hash(user_id, row)
        # 💡 같은 파일/배치 안에서 이미 처리된 동일 해시가 있다면 즉시 중복 처리
        if h in row_hashes:
            result.duplicate_count += 1
        else:
            row_hashes[h] = row
            
    # 1. DB 일괄 조회 (IN 절 활용)
    existing_hashes_query = db.query(ImportHash.hash).filter(
        ImportHash.user_id == user_id,
        ImportHash.hash.in_(row_hashes.keys())
    ).all()
    
    existing_hashes = {r[0] for r in existing_hashes_query}
    new_hashes_to_insert = []
    
    # 2. DB 중복 필터링
    for row_hash, row in row_hashes.items():
        if row_hash in existing_hashes:
            result.duplicate_count += 1
            continue
            
        new_hashes_to_insert.append(ImportHash(user_id=user_id, hash=row_hash))
        result.valid_rows.append(row)
        result.imported_count += 1
        
    # 3. 새로운 해시 일괄 저장
    if new_hashes_to_insert:
        try:
            db.bulk_save_objects(new_hashes_to_insert)
            db.commit()
        except IntegrityError:
            db.rollback()
            result.errors.append("해시 데이터 저장 중 무결성 제약 조건 위반이 발생했습니다.")
        except Exception as e:
            db.rollback()
            result.errors.append(f"해시 DB 저장 중 예기치 않은 오류가 발생했습니다: {str(e)}")