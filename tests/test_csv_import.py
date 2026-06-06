import uuid

from app.categories.models import Category
from app.csv_import.service import process_csv_import


def _seed_categories(db, user_id):
    """CSV 매칭/폴백에 필요한 카테고리를 해당 사용자 소유로 시드한다.

    시스템 카테고리는 lifespan 에서 영속 시드될 수 있어 (user_id, name, type)
    유니크 제약과 충돌하므로, 테스트마다 새로 생성되는 user 소유로 만든다.
    """
    for name, type_ in [("식비", "EXPENSE"), ("기타", "EXPENSE")]:
        db.add(Category(id=uuid.uuid4(), user_id=user_id, name=name, type=type_))
    db.commit()


def test_csv_import_skips_non_positive_amount(db, test_user):
    """금액이 0 이하인 행은 저장하지 않고 errors 에 기록한다 (DB CHECK 제약과 일치)."""
    _seed_categories(db, test_user.id)
    csv_content = (
        "날짜,유형,카테고리,금액,메모\n"
        "2026-01-01,지출,식비,9000,점심\n"
        "2026-01-02,지출,식비,0,영원\n"
        "2026-01-03,지출,식비,-500,음수\n"
    )

    result = process_csv_import(db, test_user.id, csv_content)

    assert result.imported_count == 1
    assert len(result.errors) == 2
    assert all("0보다 커야" in e for e in result.errors)


def test_csv_import_skips_invalid_date(db, test_user):
    """날짜 형식 오류 행은 건너뛰고 나머지 행은 정상 import 된다."""
    _seed_categories(db, test_user.id)
    csv_content = (
        "날짜,유형,카테고리,금액,메모\n"
        "2026-01-01,지출,식비,9000,정상\n"
        "2026/01/02,지출,식비,8000,날짜형식오류\n"
    )

    result = process_csv_import(db, test_user.id, csv_content)

    assert result.imported_count == 1
    assert any("날짜 형식 오류" in e for e in result.errors)


def test_csv_import_total_rows_counts_all_data_rows(db, test_user):
    """total_rows 는 형식 오류로 건너뛴 행을 포함한 전체 데이터 행 수다."""
    _seed_categories(db, test_user.id)
    csv_content = (
        "날짜,유형,카테고리,금액,메모\n"
        "2026-01-01,지출,식비,9000,정상\n"
        "2026/01/02,지출,식비,8000,날짜오류\n"
        "2026-01-03,지출,식비,abc,금액오류\n"
    )

    result = process_csv_import(db, test_user.id, csv_content)

    assert result.total_rows == 3      # 3개 데이터 행 전부 집계 (형식 오류 포함)
    assert result.imported_count == 1  # 정상 1건만 저장
    assert len(result.errors) == 2     # 날짜·금액 형식 오류 2건


def test_csv_import_category_fallback_to_etc(db, test_user):
    """매칭되지 않는 카테고리는 동일 type 의 '기타'로 폴백되어 import 된다."""
    _seed_categories(db, test_user.id)
    csv_content = (
        "날짜,유형,카테고리,금액,메모\n"
        "2026-01-01,지출,존재하지않는카테고리,5000,폴백\n"
    )

    result = process_csv_import(db, test_user.id, csv_content)

    assert result.imported_count == 1
    assert result.errors == []
