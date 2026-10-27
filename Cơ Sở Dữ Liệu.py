"""
Module Quản Lý Cơ Sở Dữ Liệu SQLite cho Chatbot Gợi Ý Đồ Uống.
Lưu trữ danh mục đồ uống, mapping thương hiệu và các chi nhánh quán tại Hà Nội.
"""

import os
import sys
import json
import math
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Đảm bảo mã hóa UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DUONG_DAN_THU_MUC = Path(__file__).resolve().parent
DUONG_DAN_CSDL = DUONG_DAN_THU_MUC / "Cơ Sở Dữ Liệu Đồ Uống.db"


def khoi_tao_ket_noi() -> sqlite3.Connection:
    """Tạo kết nối tới SQLite Database với row_factory dạng Dictionary."""
    conn = sqlite3.connect(str(DUONG_DAN_CSDL))
    conn.row_factory = sqlite3.Row
    return conn


def tinh_khoang_cach_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    """Tính khoảng cách hình cầu giữa 2 tọa độ GPS (kết quả trả về mét)."""
    R = 6371000  # Bán kính Trái Đất (mét)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)


def lay_tat_ca_do_uong() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các món đồ uống."""
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DoUong ORDER BY danh_muc, gia ASC")
    rows = cursor.fetchall()
    conn.close()

    ket_qua = []
    for r in rows:
        d = dict(r)
        d["tam_trang"] = json.loads(d["tam_trang"]) if "tam_trang" in d and d["tam_trang"] else []
        d["thoi_tiet"] = json.loads(d["thoi_tiet"]) if "thoi_tiet" in d and d["thoi_tiet"] else []
        d["topping"] = json.loads(d["topping"]) if "topping" in d and d["topping"] else []
        ket_qua.append(d)
    return ket_qua


def lay_do_uong_theo_danh_muc(danh_muc: str) -> List[Dict[str, Any]]:
    """Lọc đồ uống theo danh mục."""
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DoUong WHERE danh_muc = ? ORDER BY gia ASC", (danh_muc,))
    rows = cursor.fetchall()
    conn.close()

    ket_qua = []
    for r in rows:
        d = dict(r)
        d["tam_trang"] = json.loads(d["tam_trang"]) if "tam_trang" in d and d["tam_trang"] else []
        d["thoi_tiet"] = json.loads(d["thoi_tiet"]) if "thoi_tiet" in d and d["thoi_tiet"] else []
        d["topping"] = json.loads(d["topping"]) if "topping" in d and d["topping"] else []
        ket_qua.append(d)
    return ket_qua


def lay_do_uong_theo_id(mon_id: str) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết của một món theo mã ID."""
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DoUong WHERE id = ?", (mon_id,))
    r = cursor.fetchone()
    conn.close()

    if not r:
        return None
    d = dict(r)
    d["tam_trang"] = json.loads(d["tam_trang"]) if "tam_trang" in d and d["tam_trang"] else []
    d["thoi_tiet"] = json.loads(d["thoi_tiet"]) if "thoi_tiet" in d and d["thoi_tiet"] else []
    d["topping"] = json.loads(d["topping"]) if "topping" in d and d["topping"] else []
    return d


def tim_quan_ban_mon(mon_id: str, user_lat: float = 21.0285, user_lon: float = 105.8542, top_k: int = 2) -> List[Dict[str, Any]]:
    """
    Tìm các quán gần vị trí người dùng nhất có phục vụ món đồ uống được chỉ định.
    Mặc định tọa độ Hồ Gươm: 21.0285, 105.8542 (hoặc Bách Khoa: 21.0056, 105.8433).
    """
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()

    # 1. Lấy danh sách thương hiệu có bán món này
    cursor.execute("SELECT ds_thuong_hieu FROM ThuongHieuDoUong WHERE mon_id = ?", (mon_id,))
    r_th = cursor.fetchone()
    ds_th = json.loads(r_th["ds_thuong_hieu"]) if r_th else []

    if not ds_th:
        cursor.execute("SELECT * FROM ChiNhanhQuan")
        rows = cursor.fetchall()
    else:
        placeholders = ",".join(["?"] * len(ds_th))
        cursor.execute(f"SELECT * FROM ChiNhanhQuan WHERE thuong_hieu IN ({placeholders})", ds_th)
        rows = cursor.fetchall()

    conn.close()

    # 2. Tính khoảng cách thực tế từ vị trí người dùng đến từng quán
    danh_sach_quan = []
    for r in rows:
        q = dict(r)
        kc_met = tinh_khoang_cach_haversine(user_lat, user_lon, q["latitude"], q["longitude"])
        q["khoang_cach_thuc_te_m"] = kc_met
        if kc_met < 1000:
            q["khoang_cach_hien_thi"] = f"{kc_met}m"
        else:
            q["khoang_cach_hien_thi"] = f"{kc_met / 1000:.1f}km"
        danh_sach_quan.append(q)

    # 3. Sắp xếp quán gần nhất
    danh_sach_quan.sort(key=lambda x: x["khoang_cach_thuc_te_m"])
    return danh_sach_quan[:top_k]
