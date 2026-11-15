import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path
from dotenv import load_dotenv

# Load biến môi trường từ .env
DUONG_DAN_THU_MUC = Path(__file__).resolve().parent
load_dotenv(DUONG_DAN_THU_MUC / ".env")

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
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
    "Hoàng Mai": (20.9734, 105.8504)
}

HINH_ANH_DO_UONG = {
    "CF01": "https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?w=600&auto=format&fit=crop&q=80",
    "CF02": "https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?w=600&auto=format&fit=crop&q=80",
    "CF03": "https://images.unsplash.com/photo-1517256064527-09c73fc73e38?w=600&auto=format&fit=crop&q=80",
    "CF04": "https://images.unsplash.com/photo-1541167760496-1628856ab772?w=600&auto=format&fit=crop&q=80",
    "TS01": "https://images.unsplash.com/photo-1558857563-b37cfb77c570?w=600&auto=format&fit=crop&q=80",
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
    "NE02": "https://images.unsplash.com/photo-1589734747387-9430c6a51d4d?w=600&auto=format&fit=crop&q=80",
    "NE03": "https://images.unsplash.com/photo-1600271886742-f049cd451bba?w=600&auto=format&fit=crop&q=80",
    "TL01": "https://images.unsplash.com/photo-1597481499750-3e6b22637e12?w=600&auto=format&fit=crop&q=80",
    "TL02": "https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?w=600&auto=format&fit=crop&q=80"
}

class ChatRequest(BaseModel):
    message: str
    user_name: Optional[str] = "Kiệt"
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

                    # Bổ sung ảnh đại diện chất lượng cao
                    mon["hinh_anh"] = HINH_ANH_DO_UONG.get(mid, "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=600&auto=format&fit=crop&q=80")

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
async def menu():
    try:
        if not csdl:
            return JSONResponse(status_code=500, content={"error": "Cơ sở dữ liệu không khả dụng"})

        danh_sach = csdl.lay_tat_ca_do_uong()
        for m in danh_sach:
            m["hinh_anh"] = HINH_ANH_DO_UONG.get(m["id"], "https://images.unsplash.com/photo-1551024709-8f23befc6f87?w=600&auto=format&fit=crop&q=80")
        return {"danh_sach_do_uong": danh_sach}
    except Exception as e:
        print(f"Lỗi lấy menu: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/all-shops")
async def all_shops():
    """Lấy toàn bộ 89 chi nhánh quán tại Hà Nội để vẽ lên bản đồ Leaflet Map."""
    try:
        if not csdl:
            return JSONResponse(status_code=500, content={"error": "Cơ sở dữ liệu không khả dụng"})

        conn = csdl.khoi_tao_ket_noi()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ten_quan, thuong_hieu, dia_chi, quan, latitude, longitude, rating, user_ratings_total, link_shopeefood FROM ChiNhanhQuan")
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return {"danh_sach_quan": rows}
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

@app.get("/api/suc-khoe")
async def suc_khoe():
    return {
        "trang_thai": "hoat_dong",
        "mo_hinh": "Gemini 3.5 Flash",
        "ten_bot": "Mijushi",
        "tong_so_quan": 89
    }

if __name__ == "__main__":
    uvicorn.run("Máy Chủ Web:app", host="127.0.0.1", port=8000, reload=True)
