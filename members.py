"""
pack/unpack และ CRUD สำหรับ members.dat
"""
import re
import struct

import storage
from config import (
    MEMBERS_FILE,
    MEMBER_FORMAT,
    MEMBER_SIZE,
    STATUS_ACTIVE,
    STATUS_DELETED,
)

# ---------------------------------------------------------------------------
# pack / unpack
# ---------------------------------------------------------------------------
def pack_member(member_id, name, phone, join_date, status):
    """แปลงข้อมูลสมาชิกเป็น bytes ขนาดคงที่"""

    name_size, phone_size = _string_field_sizes()

    return struct.pack(
        MEMBER_FORMAT,
        member_id,
        storage.encode_str(name, name_size),
        storage.encode_str(phone, phone_size),
        join_date,
        status,
    )


def unpack_member(raw):
    """แปลง bytes กลับเป็น dict ข้อมูลสมาชิก"""

    member_id, name_raw, phone_raw, join_date, status = struct.unpack(
        MEMBER_FORMAT,
        raw
    )

    return {
        "member_id": member_id,
        "name": storage.decode_str(name_raw),
        "phone": storage.decode_str(phone_raw),
        "join_date": join_date,
        "status": status,
    }


def _string_field_sizes():
    """ดึงขนาดฟิลด์ name/phone จาก MEMBER_FORMAT ใน config.py"""

    sizes = [int(n) for n in re.findall(r"(\d+)s", MEMBER_FORMAT)]
    return sizes[0], sizes[1]

def add(name, phone):
    """เพิ่มสมาชิกใหม่ -> คืน member_id"""

    if not name or not phone:
        raise ValueError("name และ phone ห้ามว่าง")

    storage.ensure_file(MEMBERS_FILE)

    new_id = storage.next_id(
        MEMBERS_FILE,
        MEMBER_SIZE,
        unpack_member,
        "member_id"
    )

    raw = pack_member(
        member_id=new_id,
        name=name,
        phone=phone,
        join_date=storage.now_ts(),
        status=STATUS_ACTIVE,
    )

    storage.append_record(MEMBERS_FILE, raw)

    return new_id


def get(member_id):
    """คืนข้อมูลสมาชิกถ้าพบและยังไม่ถูกลบ"""

    storage.ensure_file(MEMBERS_FILE)

    index, record = storage.find_index_by_id(
        MEMBERS_FILE,
        MEMBER_SIZE,
        unpack_member,
        "member_id",
        member_id
    )

    if index == -1 or record["status"] == STATUS_DELETED:
        return None

    return record


def update(member_id, name=None, phone=None):
    """แก้ไขข้อมูลสมาชิก -> True/False"""

    storage.ensure_file(MEMBERS_FILE)

    index, record = storage.find_index_by_id(
        MEMBERS_FILE,
        MEMBER_SIZE,
        unpack_member,
        "member_id",
        member_id
    )

    if record is None or record["status"] == STATUS_DELETED:
        return False

    if name is not None:
        record["name"] = name

    if phone is not None:
        record["phone"] = phone

    raw = pack_member(
        member_id=record["member_id"],
        name=record["name"],
        phone=record["phone"],
        join_date=record["join_date"],
        status=record["status"],
    )

    storage.overwrite_record_at_index(
        MEMBERS_FILE,
        MEMBER_SIZE,
        index,
        raw
    )

    return True


def delete(member_id):
    """Soft-delete สมาชิก -> True/False"""

    storage.ensure_file(MEMBERS_FILE)

    index, record = storage.find_index_by_id(
        MEMBERS_FILE,
        MEMBER_SIZE,
        unpack_member,
        "member_id",
        member_id
    )

    if record is None or record["status"] == STATUS_DELETED:
        return False

    raw = pack_member(
        member_id=record["member_id"],
        name=record["name"],
        phone=record["phone"],
        join_date=record["join_date"],
        status=STATUS_DELETED,
    )

    storage.overwrite_record_at_index(
        MEMBERS_FILE,
        MEMBER_SIZE,
        index,
        raw
    )

    return True

def list_all(active_only=True):
    """คืนรายการสมาชิกทั้งหมด"""

    storage.ensure_file(MEMBERS_FILE)

    records = storage.read_all(
        MEMBERS_FILE,
        MEMBER_SIZE,
        unpack_member
    )

    if active_only:
        return [r for r in records if r["status"] != STATUS_DELETED]

    return records
