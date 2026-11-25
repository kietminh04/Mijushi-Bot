import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from dotenv import load_dotenv

# Load biến môi trường từ .env
DUONG_DAN_THU_MUC = Path(__file__).resolve().parent
load_dotenv(DUONG_DAN_THU_MUC / ".env")

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import math
import httpx
import uvicorn
from starlette.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import importlib

try:
    tro_ly_module = importlib.import_module("Trợ Lý Gemini")
    tro_ly_gemini = tro_ly_module.tro_ly_gemini
except Exception as e:
    print(f"Lỗi import Trợ Lý Gemini: {e}")
    tro_ly_gemini = None

try:
    csdl_module = importlib.import_module("Cơ Sở Dữ Liệu")
    csdl = csdl_module
except Exception as e:
    print(f"Lỗi import Cơ Sở Dữ Liệu: {e}")
    csdl = None

_bo_may_goi_y_cache = None


def _lay_bo_may_goi_y():
    """Nạp lười Bộ Máy Gợi Ý cục bộ khi Gemini bận hoặc quá tải."""
    global _bo_may_goi_y_cache
    if _bo_may_goi_y_cache is None:
        try:
            bo_may_module = importlib.import_module("Bộ Máy Gợi Ý")
            _bo_may_goi_y_cache = bo_may_module.bo_may_goi_y
        except Exception as e:
            print(f"Lỗi import Bộ Máy Gợi Ý: {e}")
            _bo_may_goi_y_cache = False
    return _bo_may_goi_y_cache if _bo_may_goi_y_cache else None

app = FastAPI(title="Mijushi Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VI_TRI_MAC_DINH = {
    "Bách Khoa": (21.0056, 105.8433),
    "Hoàn Kiếm": (21.0285, 105.8542),
    "Vũ Tông Phan": (20.9961, 105.8172),
    "Đống Đa": (21.0175, 105.8295),
    "Cầu Giấy": (21.0362, 105.7906),
    "Ba Đình": (21.0341, 105.8277),
    "Hai Bà Trưng": (21.0084, 105.8566),
    "Thanh Xuân": (20.9936, 105.8083),
    "Tây Hồ": (21.0601, 105.8252),
    "Hà Đông": (20.9719, 105.7766),
    "Nam Từ Liêm": (21.0181, 105.7725),
    "Long Biên": (21.0378, 105.8856),
    "Hoàng Mai": (20.9734, 105.8504),
    "Bắc Từ Liêm": (21.0431, 105.7686),
    "Gia Lâm": (20.9939, 105.9596),
}

HINH_ANH_DO_UONG = {
    "CF01": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=600&auto=format&fit=crop&q=80",
    "CF02": "https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?w=600&auto=format&fit=crop&q=80",
    "CF03": "https://images.unsplash.com/photo-1517256064527-09c73fc73e38?w=600&auto=format&fit=crop&q=80",
    "CF04": "https://images.unsplash.com/photo-1541167760496-1628856ab772?w=600&auto=format&fit=crop&q=80",
    "TS01": "https://images.unsplash.com/photo-1734770580735-796a00e42cb2?w=600&auto=format&fit=crop&q=80",
    "TS02": "https://images.unsplash.com/photo-1576092768241-dec231879fc3?w=600&auto=format&fit=crop&q=80",
    "TS03": "https://images.unsplash.com/photo-1536256263959-770b48d82b0a?w=600&auto=format&fit=crop&q=80",
    "TS04": "https://images.unsplash.com/photo-1525385133512-2f3bdd039054?w=600&auto=format&fit=crop&q=80",
    "TH01": "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=600&auto=format&fit=crop&q=80",
    "TH02": "https://images.unsplash.com/photo-1513558161293-cdaf765ed2fd?w=600&auto=format&fit=crop&q=80",
    "TH03": "https://images.unsplash.com/photo-1497534446932-c925b458314e?w=600&auto=format&fit=crop&q=80",
    "TH04": "https://images.unsplash.com/photo-1546173159-315724a31696?w=600&auto=format&fit=crop&q=80",
    "DX01": "https://images.unsplash.com/photo-1572490122747-3968b75cc699?w=600&auto=format&fit=crop&q=80",
    "DX02": "https://images.unsplash.com/photo-1577805947697-89e18249d767?w=600&auto=format&fit=crop&q=80",
    "DX03": "https://images.unsplash.com/photo-1589733955941-5eeaf752f6dd?w=600&auto=format&fit=crop&q=80",
    "NE01": "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=600&auto=format&fit=crop&q=80",
    "NE02": "https://images.unsplash.com/photo-1683166263544-e754e85c3e7c?w=600&auto=format&fit=crop&q=80",
    "NE03": "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=600&auto=format&fit=crop&q=80",
    "TL01": "https://images.unsplash.com/photo-1597481499750-3e6b22637e12?w=600&auto=format&fit=crop&q=80",
    "TL02": "https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?w=600&auto=format&fit=crop&q=80"
}

ANH_MAC_DINH = "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=600&auto=format&fit=crop&q=80"
NOMINATIM_USER_AGENT = "Mijushi-Drink-Assistant/1.0"
HANOI_VIEWBOX = "105.60,21.25,106.05,20.80"


def gan_hinh_anh_do_uong(mon: Dict[str, Any]) -> Dict[str, Any]:
    """Bổ sung ảnh đồ uống mặc định nếu DB chưa có trường hinh_anh."""
    if not mon.get("hinh_anh"):
        mon["hinh_anh"] = HINH_ANH_DO_UONG.get(mon.get("id", ""), ANH_MAC_DINH)
    return mon


def _lay_tong_so_quan() -> int:
    """Truy vấn động tổng số chi nhánh quán từ SQLite."""
    if not csdl:
        return 0
    conn = None
    try:
        conn = csdl.khoi_tao_ket_noi()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM ChiNhanhQuan")
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except Exception as e:
        print(f"Lỗi đếm số quán: {e}")
        return 0
    finally:
        if conn is not None:
            conn.close()


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Tính khoảng cách Haversine giữa hai tọa độ (mét)."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _fallback_geocode(query: str) -> List[Dict[str, Any]]:
    """Dự phòng tìm kiếm cục bộ theo khu vực và địa chỉ quán trong SQLite khi API ngoài gián đoạn."""
    q_lower = query.lower()
    matches: List[Dict[str, Any]] = []
    for khu_vuc, (lat, lon) in VI_TRI_MAC_DINH.items():
        if khu_vuc.lower() in q_lower or q_lower in khu_vuc.lower():
            matches.append({"ten": f"{khu_vuc}, Hà Nội", "lat": float(lat), "lon": float(lon)})

    if csdl and len(matches) < 6:
        conn = None
        try:
            conn = csdl.khoi_tao_ket_noi()
            cursor = conn.cursor()
            like_pat = f"%{query}%"
            cursor.execute(
                "SELECT ten_quan, dia_chi, latitude, longitude FROM ChiNhanhQuan "
                "WHERE ten_quan LIKE ? OR dia_chi LIKE ? OR quan LIKE ? LIMIT ?",
                (like_pat, like_pat, like_pat, 6 - len(matches)),
            )
            for r in cursor.fetchall():
                matches.append({
                    "ten": f"{r['ten_quan']} - {r['dia_chi']}",
                    "lat": float(r["latitude"]),
                    "lon": float(r["longitude"]),
                })
        except Exception as e:
            print(f"Lỗi fallback geocode SQLite: {e}")
        finally:
            if conn is not None:
                conn.close()
    return matches


def _format_photon_address(props: Dict[str, Any], max_parts: int = 5) -> str:
    """Định dạng địa chỉ tiếng Việt gọn từ properties của Photon (OSM)."""
    parts: List[str] = []
    name = str(props.get("name") or "").strip()
    street = str(props.get("street") or "").strip()
    housenumber = str(props.get("housenumber") or "").strip()

    if name:
        parts.append(name)
    if street:
        street_full = f"{housenumber} {street}".strip() if housenumber else street
        if street.lower() not in name.lower():
            parts.append(street_full)

    for key in ("locality", "district", "city", "state"):
        val = str(props.get(key) or "").strip()
        if val and all(val.lower() != p.lower() for p in parts):
            parts.append(val)

    return ", ".join(parts[:max_parts])


async def _query_nominatim_geocode(search_query: str, raw_query: str, has_hanoi: bool) -> List[Dict[str, Any]]:
    params = {
        "q": search_query,
        "format": "jsonv2",
        "countrycodes": "vn",
        "viewbox": HANOI_VIEWBOX,
        "bounded": 0,
        "limit": 6,
        "addressdetails": 1,
    }
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
        "Accept-Language": "vi,en",
    }
    async with httpx.AsyncClient(timeout=2.5) as client:
        resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
        resp.raise_for_status()
        items = resp.json()

        if not items and not has_hanoi:
            params["q"] = raw_query
            resp = await client.get("https://nominatim.openstreetmap.org/search", params=params, headers=headers)
            resp.raise_for_status()
            items = resp.json()

    results: List[Dict[str, Any]] = []
    for item in items:
        try:
            results.append({
                "ten": item.get("display_name", raw_query),
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return results


async def _query_photon_geocode(search_query: str, raw_query: str, has_hanoi: bool) -> List[Dict[str, Any]]:
    headers = {"User-Agent": NOMINATIM_USER_AGENT}
    async with httpx.AsyncClient(timeout=5.0) as client:
        params = {"q": search_query, "limit": 8, "lat": 21.0285, "lon": 105.8542}
        resp = await client.get("https://photon.komoot.io/api/", params=params, headers=headers)
        resp.raise_for_status()
        features = resp.json().get("features") or []

        if not features and not has_hanoi:
            params["q"] = raw_query
            resp = await client.get("https://photon.komoot.io/api/", params=params, headers=headers)
            resp.raise_for_status()
            features = resp.json().get("features") or []

    vn_features = [
        f for f in features
        if (f.get("properties") or {}).get("countrycode", "").upper() == "VN"
    ]
    selected = vn_features if vn_features else features

    results: List[Dict[str, Any]] = []
    for feat in selected[:6]:
        try:
            coords = feat["geometry"]["coordinates"]
            props = feat.get("properties") or {}
            ten = _format_photon_address(props, max_parts=5) or raw_query
            results.append({
                "ten": ten,
                "lat": float(coords[1]),
                "lon": float(coords[0]),
            })
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    return results


def _fallback_reverse_geocode(lat: float, lon: float) -> str:
    """Dự phòng tạo địa chỉ ngắn gọn theo khu vực gần nhất tại Hà Nội."""
    nearest_name = None
    nearest_dist = float("inf")
    for khu_vuc, (k_lat, k_lon) in VI_TRI_MAC_DINH.items():
        dist = _haversine_meters(lat, lon, k_lat, k_lon)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_name = khu_vuc
    if nearest_name and nearest_dist <= 5000:
        return f"Khu vực {nearest_name}, Hà Nội"
    return f"Vị trí ({lat:.4f}, {lon:.4f})"


def _format_short_vietnamese_address(data: Dict[str, Any]) -> str:
    """Định dạng địa chỉ tiếng Việt ngắn gọn, dễ đọc từ kết quả Nominatim reverse."""
    addr = data.get("address") or {}
    parts: List[str] = []

    road = addr.get("road") or addr.get("pedestrian") or addr.get("footway") or addr.get("path")
    house_number = addr.get("house_number")
    if house_number and road:
        parts.append(f"{house_number} {road}")
    elif road:
        parts.append(road)
    elif data.get("name"):
        parts.append(str(data["name"]))

    for key in ("quarter", "neighbourhood", "suburb", "village", "hamlet"):
        val = addr.get(key)
        if val and val not in parts:
            parts.append(val)
            break

    for key in ("city_district", "district", "town", "county"):
        val = addr.get(key)
        if val and val not in parts:
            parts.append(val)
            break

    city = addr.get("city") or addr.get("state")
    if city and city not in parts:
        parts.append(city)

    if parts:
        return ", ".join(parts[:4])

    display_name = str(data.get("display_name") or "").strip()
    if display_name:
        segments = [seg.strip() for seg in display_name.split(",") if seg.strip()]
        return ", ".join(segments[:3])
    return ""

class ChatRequest(BaseModel):
    message: str
    user_name: Optional[str] = "bạn"
    location: Optional[str] = "Bách Khoa"
    lat: Optional[float] = None
    lon: Optional[float] = None

giao_dien_path = DUONG_DAN_THU_MUC / "Giao Diện"
if giao_dien_path.exists():
    app.mount("/static", StaticFiles(directory=str(giao_dien_path)), name="static")

@app.get("/")
async def root():
    trang_chu_path = giao_dien_path / "Trang Chủ.html"
    if trang_chu_path.exists():
        return FileResponse(str(trang_chu_path))
    return {"thong_bao": "Mijushi Web API đang hoạt động"}

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        if not tro_ly_gemini:
            return JSONResponse(
                status_code=500,
                content={
                    "loai": "FALLBACK",
                    "reply": "Mijushi đang đồng bộ kết nối não bộ Gemini AI, bạn vui lòng thử lại sau vài giây nhé!"
                }
            )

        phan_tich = tro_ly_gemini.xu_ly_tin_nhan(req.message, req.user_name)
        loai = phan_tich.get("loai", "FALLBACK")

        # Fallback sang Bộ Máy Gợi Ý cục bộ (Vector Search + Rule) nếu Gemini 503/429
        if loai == "FALLBACK":
            bo_may_goi_y = _lay_bo_may_goi_y()
            if bo_may_goi_y is not None:
                y_dinh, _ = bo_may_goi_y.phan_loai_y_dinh(req.message)
                if y_dinh == "CHIT_CHAT":
                    phan_tich = {
                        "loai": "CHIT_CHAT",
                        "phan_hoi": f"Chào {req.user_name}! Mình là Mijushi 🍹 Bạn đang muốn tìm trà sữa KOI Thé, cà phê hay đồ uống thanh mát quanh khu vực nào ở Hà Nội nhỉ?"
                    }
                else:
                    goi_y_local = bo_may_goi_y.goi_y(req.message, so_luong=4)
                    phan_tich = {
                        "loai": "GOI_Y_DO_UONG",
                        "loi_nhan": "Dưới đây là những món hợp gu nhất mình lọc từ menu dựa trên yêu cầu của bạn nè:",
                        "danh_sach_id_mon": [item["mon"]["id"] for item in goi_y_local],
                        "ly_do_chon": {item["mon"]["id"]: item["ly_do_goi_y"] for item in goi_y_local},
                        "khu_vuc": req.location,
                    }
                loai = phan_tich["loai"]

        if loai == "CHIT_CHAT":
            return {
                "loai": "CHIT_CHAT",
                "reply": phan_tich.get("phan_hoi", "")
            }

        elif loai == "GOI_Y_DO_UONG":
            if not csdl:
                return JSONResponse(
                    status_code=500,
                    content={
                        "loai": "FALLBACK",
                        "reply": "Hệ thống cơ sở dữ liệu chưa sẵn sàng, vui lòng thử lại sau!"
                    }
                )

            # Xác định vị trí và tọa độ người dùng (Hỗ trợ định vị GPS)
            if req.lat is not None and req.lon is not None:
                lat, lon = req.lat, req.lon
                ten_khu_vuc = req.location or "Vị trí GPS của bạn"
            else:
                ten_khu_vuc = req.location or phan_tich.get("khu_vuc", "Bách Khoa")
                if ten_khu_vuc not in VI_TRI_MAC_DINH:
                    ten_khu_vuc = "Bách Khoa"
                lat, lon = VI_TRI_MAC_DINH[ten_khu_vuc]

            danh_sach_id_mon = phan_tich.get("danh_sach_id_mon", [])[:4]
            danh_sach_mon = []

            for mid in danh_sach_id_mon:
                try:
                    mon = csdl.lay_do_uong_theo_id(mid)
                    if not mon:
                        continue

                    # Bổ sung ảnh đại diện chất lượng cao (không ghi đè nếu DB đã có)
                    gan_hinh_anh_do_uong(mon)

                    # Tìm quán gần nhất từ database GPS
                    quan_gan_nhat = csdl.tim_quan_ban_mon(mid, lat, lon, top_k=2)
                    ly_do = phan_tich.get("ly_do_chon", {}).get(mid, "")

                    danh_sach_mon.append({
                        "mon": mon,
                        "ly_do": ly_do,
                        "quan_gan_nhat": quan_gan_nhat
                    })
                except Exception:
                    continue

            return {
                "loai": "GOI_Y_DO_UONG",
                "loi_nhan": phan_tich.get("loi_nhan", ""),
                "danh_sach_mon": danh_sach_mon,
                "khu_vuc": ten_khu_vuc,
                "toa_do_hien_tai": {"lat": lat, "lon": lon}
            }

        else:
            return {
                "loai": "FALLBACK",
                "reply": "Mijushi đang đồng bộ kết nối não bộ Gemini AI, bạn vui lòng thử lại sau vài giây nhé!"
            }

    except Exception as e:
        print(f"Lỗi xử lý chat: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "loai": "FALLBACK",
                "reply": "Mijushi đang đồng bộ kết nối não bộ Gemini AI, bạn vui lòng thử lại sau vài giây nhé!"
            }
        )

@app.get("/api/menu")
async def menu(thuong_hieu: Optional[str] = Query(None, description="Lọc theo tên chuỗi cửa hàng")):
    try:
        if not csdl:
            return JSONResponse(status_code=500, content={"error": "Cơ sở dữ liệu không khả dụng"})

        tat_ca = csdl.lay_tat_ca_do_uong()
        for m in tat_ca:
            gan_hinh_anh_do_uong(m)

        # Thống kê số món & số chi nhánh theo từng chuỗi từ SQLite
        brand_counts: Dict[str, int] = {}
        for m in tat_ca:
            th = m.get("thuong_hieu") or "Hệ thống"
            brand_counts[th] = brand_counts.get(th, 0) + 1

        shop_counts: Dict[str, int] = {}
        conn = csdl.khoi_tao_ket_noi()
        try:
            for r in conn.execute("SELECT thuong_hieu, COUNT(*) AS cnt FROM ChiNhanhQuan GROUP BY thuong_hieu"):
                shop_counts[r["thuong_hieu"]] = int(r["cnt"])
        finally:
            conn.close()

        danh_sach_chuoi = [
            {"thuong_hieu": th, "so_mon": cnt, "so_chi_nhanh": shop_counts.get(th, 0)}
            for th, cnt in sorted(brand_counts.items(), key=lambda kv: (-shop_counts.get(kv[0], 0), -kv[1], kv[0]))
        ]

        danh_sach_loc = (
            [m for m in tat_ca if (m.get("thuong_hieu") or "").lower() == thuong_hieu.strip().lower()]
            if thuong_hieu and thuong_hieu.strip() and thuong_hieu.strip().lower() != "all"
            else tat_ca
        )

        tuy_chon_koi = csdl.lay_tuy_chon_thuong_hieu("KOI Thé") if hasattr(csdl, "lay_tuy_chon_thuong_hieu") else {}
        return {
            "danh_sach_do_uong": danh_sach_loc,
            "tong_so_mon": len(tat_ca),
            "danh_sach_chuoi": danh_sach_chuoi,
            "tuy_chon_koi_the": tuy_chon_koi,
        }
    except Exception as e:
        print(f"Lỗi lấy menu: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/all-shops")
async def all_shops():
    """Lấy toàn bộ chi nhánh quán tại Hà Nội từ SQLite để vẽ lên bản đồ Leaflet Map."""
    try:
        if not csdl:
            return JSONResponse(status_code=500, content={"error": "Cơ sở dữ liệu không khả dụng"})

        conn = csdl.khoi_tao_ket_noi()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ten_quan, thuong_hieu, dia_chi, quan, latitude, longitude, rating, user_ratings_total, link_shopeefood FROM ChiNhanhQuan")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {"danh_sach_quan": rows, "tong_so_quan": len(rows)}
    except Exception as e:
        print(f"Lỗi lấy danh sách quán: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/quan")
async def quan(mon_id: str, khu_vuc: str = "Bách Khoa", lat: Optional[float] = None, lon: Optional[float] = None):
    try:
        if not csdl:
            return JSONResponse(status_code=500, content={"error": "Cơ sở dữ liệu không khả dụng"})

        if lat is not None and lon is not None:
            user_lat, user_lon = lat, lon
        else:
            if khu_vuc not in VI_TRI_MAC_DINH:
                khu_vuc = "Bách Khoa"
            user_lat, user_lon = VI_TRI_MAC_DINH[khu_vuc]

        danh_sach_quan = csdl.tim_quan_ban_mon(mon_id, user_lat, user_lon, top_k=2)

        return {
            "mon_id": mon_id,
            "khu_vuc": khu_vuc,
            "danh_sach_quan": danh_sach_quan
        }
    except Exception as e:
        print(f"Lỗi tìm quán: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/locations")
async def locations():
    return {
        "danh_sach_khu_vuc": list(VI_TRI_MAC_DINH.keys()),
        "toa_do": VI_TRI_MAC_DINH
    }

@app.get("/api/geocode")
async def geocode(q: str = Query("", description="Địa chỉ hoặc địa điểm cần tìm tại Hà Nội")):
    """Tìm kiếm địa điểm tại Hà Nội/Việt Nam qua OpenStreetMap Nominatim và Photon fallback."""
    query = q.strip()
    if not query:
        return []

    lower_q = query.lower()
    has_hanoi = any(kw in lower_q for kw in ("hà nội", "ha noi", "hanoi"))
    search_query = query if has_hanoi else f"{query}, Hà Nội"

    for provider_name, fetcher in (
        ("Nominatim", _query_nominatim_geocode),
        ("Photon", _query_photon_geocode),
    ):
        try:
            results = await fetcher(search_query, query, has_hanoi)
            if results:
                return results
        except Exception as e:
            print(f"Lỗi geocode {provider_name} ({query}): {e}")

    return _fallback_geocode(query)

@app.get("/api/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(..., description="Vĩ độ"),
    lon: float = Query(..., description="Kinh độ"),
):
    """Chuyển đổi tọa độ trên bản đồ thành địa chỉ tiếng Việt ngắn gọn (Nominatim + Photon fallback)."""
    headers = {
        "User-Agent": NOMINATIM_USER_AGENT,
        "Accept-Language": "vi,en",
    }

    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            resp = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2", "addressdetails": 1, "zoom": 18},
                headers=headers,
            )
            resp.raise_for_status()
            dia_chi = _format_short_vietnamese_address(resp.json())
            if dia_chi:
                return {"dia_chi": dia_chi, "lat": lat, "lon": lon}
    except Exception as e:
        print(f"Lỗi reverse-geocode Nominatim ({lat}, {lon}): {e}")

    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://photon.komoot.io/reverse",
                params={"lat": lat, "lon": lon},
                headers={"User-Agent": NOMINATIM_USER_AGENT},
            )
            resp.raise_for_status()
            features = resp.json().get("features") or []
            if features:
                dia_chi = _format_photon_address(features[0].get("properties") or {}, max_parts=4)
                if dia_chi:
                    return {"dia_chi": dia_chi, "lat": lat, "lon": lon}
    except Exception as e:
        print(f"Lỗi reverse-geocode Photon ({lat}, {lon}): {e}")

    return {"dia_chi": _fallback_reverse_geocode(lat, lon), "lat": lat, "lon": lon}

@app.get("/api/suc-khoe")
async def suc_khoe():
    tong_mon = len(csdl.lay_tat_ca_do_uong()) if csdl else 0
    return {
        "trang_thai": "hoat_dong",
        "mo_hinh": "Gemini 3.5 Flash",
        "ten_bot": "Mijushi",
        "tong_so_quan": _lay_tong_so_quan(),
        "tong_so_mon": tong_mon,
    }

if __name__ == "__main__":
    uvicorn.run("Máy Chủ Web:app", host="127.0.0.1", port=8000, reload=True)
