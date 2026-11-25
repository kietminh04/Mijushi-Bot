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


def _giai_ma_json_list(raw_val: Any) -> List[str]:
    """Giải mã an toàn chuỗi JSON mảng thành Python list."""
    if not raw_val:
        return []
    if isinstance(raw_val, list):
        return raw_val
    try:
        parsed = json.loads(raw_val)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _chuan_hoa_do_uong(row: sqlite3.Row) -> Dict[str, Any]:
    """Chuẩn hóa một bản ghi đồ uống từ SQLite sang dict đầy đủ."""
    d = dict(row)
    d["tam_trang"] = _giai_ma_json_list(d.get("tam_trang"))
    d["thoi_tiet"] = _giai_ma_json_list(d.get("thoi_tiet"))
    d["topping"] = _giai_ma_json_list(d.get("topping"))
    d["mua_goi_y"] = _giai_ma_json_list(d.get("mua_goi_y"))
    return d


def lay_tat_ca_do_uong() -> List[Dict[str, Any]]:
    """Lấy danh sách tất cả các món đồ uống."""
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DoUong ORDER BY thuong_hieu, danh_muc, gia ASC")
    rows = cursor.fetchall()
    conn.close()
    return [_chuan_hoa_do_uong(r) for r in rows]


def lay_do_uong_theo_danh_muc(danh_muc: str) -> List[Dict[str, Any]]:
    """Lọc đồ uống theo danh mục."""
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DoUong WHERE danh_muc = ? ORDER BY gia ASC", (danh_muc,))
    rows = cursor.fetchall()
    conn.close()
    return [_chuan_hoa_do_uong(r) for r in rows]


def lay_do_uong_theo_id(mon_id: str) -> Optional[Dict[str, Any]]:
    """Lấy thông tin chi tiết của một món theo mã ID."""
    conn = khoi_tao_ket_noi()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM DoUong WHERE id = ?", (mon_id,))
    r = cursor.fetchone()
    conn.close()
    return _chuan_hoa_do_uong(r) if r else None


def lay_tuy_chon_thuong_hieu(thuong_hieu: str = "KOI Thé") -> Dict[str, Any]:
    """Lấy bảng mức đá, mức đường, topping và gợi ý theo mùa từ SQLite."""
    ket_qua: Dict[str, Any] = {"muc_da": [], "muc_duong": [], "topping": [], "goi_y_theo_mua": []}
    conn = khoi_tao_ket_noi()
    try:
        cursor = conn.cursor()
        for loai, key in (("ICE", "muc_da"), ("SUGAR", "muc_duong")):
            try:
                rows = cursor.execute(
                    "SELECT ma_tuy_chon, ten_tieng_viet FROM TuyChonPhaChe WHERE thuong_hieu = ? AND loai = ? ORDER BY thu_tu ASC",
                    (thuong_hieu, loai),
                ).fetchall()
                ket_qua[key] = [dict(r) for r in rows]
            except Exception:
                pass
        try:
            rows = cursor.execute(
                "SELECT ten_topping, ten_tieng_anh, phu_thu_s, phu_thu_m, phu_thu_l FROM ToppingDoUong WHERE thuong_hieu = ? ORDER BY id ASC",
                (thuong_hieu,),
            ).fetchall()
            ket_qua["topping"] = [dict(r) for r in rows]
        except Exception:
            pass
        try:
            rows = cursor.execute(
                "SELECT mua, nhu_cau, nhom_uu_tien, mon_vi_du, cau_tra_loi_mau, luu_y FROM GoiYTheoMua WHERE thuong_hieu = ? ORDER BY id ASC",
                (thuong_hieu,),
            ).fetchall()
            ket_qua["goi_y_theo_mua"] = [dict(r) for r in rows]
        except Exception:
            pass
    finally:
        conn.close()
    return ket_qua


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
        if not rows:
            cursor.execute("SELECT * FROM ChiNhanhQuan")
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
