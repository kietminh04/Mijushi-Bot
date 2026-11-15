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
from pathlib import Path
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
    "Cầu Giấy": (21.0362, 105.7906)
}

class ChatRequest(BaseModel):
    message: str
    user_name: Optional[str] = "Kiệt"
    location: Optional[str] = "Bách Khoa"

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
                "khu_vuc": ten_khu_vuc
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
        return {"danh_sach_do_uong": danh_sach}
    except Exception as e:
        print(f"Lỗi lấy menu: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/api/quan")
async def quan(mon_id: str, khu_vuc: str = "Bách Khoa"):
    try:
        if not csdl:
            return JSONResponse(status_code=500, content={"error": "Cơ sở dữ liệu không khả dụng"})

        if khu_vuc not in VI_TRI_MAC_DINH:
            khu_vuc = "Bách Khoa"

        lat, lon = VI_TRI_MAC_DINH[khu_vuc]
        danh_sach_quan = csdl.tim_quan_ban_mon(mon_id, lat, lon, top_k=2)

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
        "danh_sach_khu_vuc": ["Bách Khoa", "Hoàn Kiếm", "Vũ Tông Phan", "Đống Đa", "Cầu Giấy"]
    }

@app.get("/api/suc-khoe")
async def suc_khoe():
    return {
        "trang_thai": "hoat_dong",
        "mo_hinh": "Gemini 3.5 Flash",
        "ten_bot": "Mijushi"
    }

if __name__ == "__main__":
    uvicorn.run("Máy Chủ Web:app", host="127.0.0.1", port=8000, reload=True)
