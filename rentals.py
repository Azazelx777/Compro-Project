"""
pack/unpack และ CRUD สำหรับ rentals.dat
เชื่อมโยง books.dat และ members.dat เข้าด้วยกัน
"""
import math
import struct

import storage
import books
import members
from config import (
    RENTALS_FILE,
    RENTAL_FORMAT,
    RENTAL_SIZE,
    STATUS_DELETED,
    STATUS_BORROWING,
    STATUS_RETURNED,
    DEFAULT_RENT_DAYS,
    FINE_PER_DAY,
)

SECONDS_PER_DAY = 86400


def pack_rental(rent_id, book_id, member_id, rent_date, due_date, return_date, fine_amount, status):
    return struct.pack(
        RENTAL_FORMAT,
        int(rent_id),
        int(book_id),
        int(member_id),
        int(rent_date),
        int(due_date),
        int(return_date),
        float(fine_amount),
        int(status),
    )


def unpack_rental(raw):
    (rent_id, book_id, member_id, rent_date, due_date,
     return_date, fine_amount, status) = struct.unpack(RENTAL_FORMAT, raw)

    return {
        "rent_id": rent_id,
        "book_id": book_id,
        "member_id": member_id,
        "rent_date": rent_date,
        "due_date": due_date,
        "return_date": return_date,
        "fine_amount": fine_amount,
        "status": status,
    }


def _rewrite(index, record, **changes):
    data = {**record, **changes}
    raw = pack_rental(
        data["rent_id"],
        data["book_id"],
        data["member_id"],
        data["rent_date"],
        data["due_date"],
        data["return_date"],
        data["fine_amount"],
        data["status"],
    )
    storage.overwrite_record_at_index(RENTALS_FILE, RENTAL_SIZE, index, raw)


def _find(rent_id):
    storage.ensure_file(RENTALS_FILE)
    index, record = storage.find_index_by_id(
        RENTALS_FILE, RENTAL_SIZE, unpack_rental, "rent_id", rent_id
    )
    if record is None or record["status"] == STATUS_DELETED:
        return -1, None
    return index, record


def add(book_id, member_id, rent_days=DEFAULT_RENT_DAYS):
    rent_days = int(rent_days)
    if rent_days <= 0:
        raise ValueError("rent_days ต้องมากกว่า 0")

    if books.get(book_id) is None:
        raise ValueError(f"ไม่พบหนังสือรหัส {book_id}")
    if members.get(member_id) is None:
        raise ValueError(f"ไม่พบสมาชิกรหัส {member_id}")

    if not books.decrement_stock(book_id):
        raise ValueError(f"หนังสือรหัส {book_id} ไม่มีเล่มว่างให้เช่า")

    try:
        storage.ensure_file(RENTALS_FILE)
        new_id = storage.next_id(RENTALS_FILE, RENTAL_SIZE, unpack_rental, "rent_id")
        now = storage.now_ts()

        raw = pack_rental(
            rent_id=new_id,
            book_id=book_id,
            member_id=member_id,
            rent_date=now,
            due_date=now + rent_days * SECONDS_PER_DAY,
            return_date=0,
            fine_amount=0.0,
            status=STATUS_BORROWING,
        )
        storage.append_record(RENTALS_FILE, raw)
    except Exception:
        books.increment_stock(book_id)
        raise

    return new_id


def return_book(rent_id):
    index, record = _find(rent_id)
    if record is None:
        raise ValueError(f"ไม่พบรายการเช่ารหัส {rent_id}")
    if record["status"] == STATUS_RETURNED:
        raise ValueError(f"รายการเช่ารหัส {rent_id} คืนหนังสือไปแล้ว")

    now = storage.now_ts()
    fine = 0.0
    if now > record["due_date"]:
        days_late = math.ceil((now - record["due_date"]) / SECONDS_PER_DAY)
        fine = days_late * FINE_PER_DAY

    _rewrite(index, record, return_date=now, fine_amount=fine, status=STATUS_RETURNED)
    books.increment_stock(record["book_id"])

    return float(fine)


def delete(rent_id):
    index, record = _find(rent_id)
    if record is None:
        return False

    if record["status"] == STATUS_BORROWING:
        books.increment_stock(record["book_id"])

    _rewrite(index, record, status=STATUS_DELETED)
    return True


def list_all(status=None):
    storage.ensure_file(RENTALS_FILE)
    records = storage.read_all(RENTALS_FILE, RENTAL_SIZE, unpack_rental)

    if status is None:
        return [r for r in records if r["status"] != STATUS_DELETED]
    return [r for r in records if r["status"] == status]


def stats():
    storage.ensure_file(RENTALS_FILE)
    all_records = storage.read_all(RENTALS_FILE, RENTAL_SIZE, unpack_rental)
    active = [r for r in all_records if r["status"] != STATUS_DELETED]

    now = storage.now_ts()
    borrowing = [r for r in active if r["status"] == STATUS_BORROWING]
    returned = [r for r in active if r["status"] == STATUS_RETURNED]

    return {
        "total_rentals": len(active),
        "total_active_rentals": len(borrowing),
        "returned": len(returned),
        "deleted": len(all_records) - len(active),
        "total_fine_collected": sum(r["fine_amount"] for r in returned),
        "overdue_rentals": sum(1 for r in borrowing if r["due_date"] < now),
    }