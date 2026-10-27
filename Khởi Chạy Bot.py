"""
Khởi Chạy Discord Bot Quán Nước AI (Mijushi).
Gợi ý danh sách tổng hợp nhiều món đồ uống trước (Top 3-4 món) -> Chọn món để xem quán gần nhất.
Chạy 100% trên GPU RTX 4080 (0 token LLM, 0 đồng API).
"""

import os
import sys
import json
import logging
import asyncio
import re
from pathlib import Path
from typing import Optional, List, Dict, Any
import importlib.util

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from aiohttp import web

# Cấu hình UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("MijushiBot")

DUONG_DAN_THU_MUC = Path(__file__).resolve().parent
load_dotenv(DUONG_DAN_THU_MUC / ".env")

def _nap_module(ten_module: str, ten_file: str):
    duong_dan = DUONG_DAN_THU_MUC / ten_file
    spec = importlib.util.spec_from_file_location(ten_module, str(duong_dan))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

csdl = _nap_module("csdl", "Cơ Sở Dữ Liệu.py")
bo_may_goi_y_mod = _nap_module("bo_may_goi_y", "Bộ Máy Gợi Ý.py")
bo_may_goi_y = bo_may_goi_y_mod.bo_may_goi_y

tro_ly_gemini_mod = _nap_module("tro_ly_gemini", "Trợ Lý Gemini.py")
tro_ly_gemini = tro_ly_gemini_mod.tro_ly_gemini

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
GUILD_ID_STR = os.getenv("DISCORD_GUILD_ID", "").strip()
GUILD_ID = int(GUILD_ID_STR) if GUILD_ID_STR.isdigit() else None

VI_TRI_MAC_DINH = {
    "Hoàn Kiếm": (21.0285, 105.8542),
    "Bách Khoa": (21.0056, 105.8433),
    "Vũ Tông Phan": (20.9985, 105.8175),
    "Đống Đa": (21.0142, 105.8335),
    "Cầu Giấy": (21.0345, 105.7950)
}

MAU_SAC = {
    "Cà Phê": 0x8B5A2B,
    "Trà Sữa": 0xD4A373,
    "Trà Hoa Quả": 0xF39C12,
    "Đá Xay": 0x1ABC9C,
    "Nước Ép": 0x2ECC71,
    "Thư Giãn": 0x9B59B6,
    "Chính": 0xE67E22,
    "Thành Công": 0x27AE60
}

EMOJI_DANH_MUC = {
    "Cà Phê": "☕",
    "Trà Sữa": "🧋",
    "Trà Hoa Quả": "🍑",
    "Đá Xay": "🍧",
    "Nước Ép": "🍹",
    "Thư Giãn": "🍵"
}

TU_KHOA_CHAO_HOI = [
    "hi", "hello", "chào", "chao", "alo", "helo", "hey", "ê", "e bot", "ê bot", 
    "yo", "hế lô", "quán nước ơi", "mijushi", "mijushi ơi", "bot ơi", "hello bot",
    "xin chào", "chào bạn", "có ai ở đây không", "hú", "2"
]


# ==========================================
# VIEW GỢI Ý MỚI: DANH SÁCH NHIỀU MÓN TRƯỚC -> CHỌN MÓN XEM QUÁN SAU
# ==========================================
class DropdownChonMonDeXemQuan(discord.ui.Select):
    def __init__(self, danh_sach_goi_y: List[Dict[str, Any]], cha: "ViewGoiYDanhSach"):
        self.cha = cha
        options = []
        for idx, item in enumerate(danh_sach_goi_y[:4]):
            m = item["mon"]
            emoji = EMOJI_DANH_MUC.get(m["danh_muc"], "🥤")
            label = f"{idx + 1}. {m['ten'][:40]}"
            desc = f"~{m['gia']:,}đ | {m['calo']} kcal | {m['huong_vi'][:45]}"
            options.append(discord.SelectOption(label=label, value=str(idx), emoji=emoji, description=desc))

        super().__init__(placeholder="👉 Bấm vào đây để chọn món xem quán gần nhất...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.cha.user_id:
            await interaction.response.send_message("Vui lòng gửi câu hỏi của riêng bạn nhé!", ephemeral=True)
            return

        idx = int(self.values[0])
        embed_chi_tiet, view_chi_tiet = self.cha.tao_embed_chi_tiet_quan(idx)
        await interaction.response.edit_message(embed=embed_chi_tiet, view=view_chi_tiet)


class ViewGoiYDanhSach(discord.ui.View):
    def __init__(self, danh_sach_goi_y: List[Dict[str, Any]], user_id: int, cau_hoi: str, toa_do_user: tuple = (21.0056, 105.8433), ten_khu_vuc: str = "Bách Khoa"):
        super().__init__(timeout=300)
        self.danh_sach_goi_y = danh_sach_goi_y
        self.user_id = user_id
        self.cau_hoi = cau_hoi
        self.toa_do_user = toa_do_user
        self.ten_khu_vuc = ten_khu_vuc
        self.add_item(DropdownChonMonDeXemQuan(danh_sach_goi_y, self))

    def tao_embed_danh_sach(self) -> discord.Embed:
        """Tạo bảng danh sách tổng hợp Top 4 món phù hợp nhất."""
        embed = discord.Embed(
            title=f"🍹 Gợi Ý Đồ Uống Chuẩn Gu Cho Bạn",
            description=f"Dựa trên yêu cầu: *\"{self.cau_hoi}\"*\nMình đã phân tích và chọn ra **Top 4 món hợp nhất** dưới đây:\n",
            color=MAU_SAC["Chính"]
        )

        for idx, item in enumerate(self.danh_sach_goi_y[:4], 1):
            m = item["mon"]
            emoji = EMOJI_DANH_MUC.get(m["danh_muc"], "🥤")
            phan_tram = int(item["tong_diem"] * 100)

            tieu_de = f"{emoji} **{idx}. {m['ten']}** — `~{m['gia']:,} VNĐ`"
            noi_dung = (
                f"• **Điểm phù hợp**: `{phan_tram}%` | **Nhiệt độ**: `{m['nhiet_do']}` | **Calo**: `{m['calo']} kcal`\n"
                f"• **Lý do chọn**: *{item['ly_do_goi_y']}*\n"
                f"• **Hương vị**: {m['huong_vi']}"
            )
            embed.add_field(name=tieu_de, value=noi_dung, inline=False)

        embed.set_footer(text=f"Khu vực ưu tiên: {self.ten_khu_vuc} • Chọn món bên dưới để định vị quán gần nhất nhé!")
        return embed

    def tao_embed_chi_tiet_quan(self, idx: int):
        """Tạo Embed chi tiết vị trí các quán gần nhất cho món đã chọn."""
        item = self.danh_sach_goi_y[idx]
        m = item["mon"]
        emoji = EMOJI_DANH_MUC.get(m["danh_muc"], "🥤")
        mau = MAU_SAC.get(m["danh_muc"], MAU_SAC["Chính"])

        embed = discord.Embed(
            title=f"{emoji} Quán Gần Bạn Nhất Bán: {m['ten']}",
            description=f"*{m['mo_ta']}*",
            color=mau
        )

        embed.add_field(name="💰 Giá tham khảo", value=f"`~{m['gia']:,} VNĐ`", inline=True)
        embed.add_field(name="🔥 Calo", value=f"`{m['calo']} kcal`", inline=True)
        embed.add_field(name="⚡ Caffeine", value=f"`{m['caffeine']}`", inline=True)

        ds_quan = csdl.tim_quan_ban_mon(m["id"], self.toa_do_user[0], self.toa_do_user[1], top_k=2)
        if ds_quan:
            thong_tin_quan = []
            for i, q in enumerate(ds_quan, 1):
                thong_tin_quan.append(
                    f"**{i}. {q['ten_quan']}**\n"
                    f"📍 Cách {self.ten_khu_vuc}: `{q['khoang_cach_hien_thi']}` • ⭐ `{q['rating']}/5` ({q['user_ratings_total']} đánh giá)\n"
                    f"🏠 *{q['dia_chi']}*"
                )
            embed.add_field(
                name=f"📍 Các Quán Gần Nhất (Quanh {self.ten_khu_vuc})",
                value="\n\n".join(thong_tin_quan),
                inline=False
            )

        # View chi tiết với nút quay lại và nút ShopeeFood
        view_chi_tiet = ViewChiTietMon(self, ds_quan)
        return embed, view_chi_tiet


class ViewChiTietMon(discord.ui.View):
    def __init__(self, cha: ViewGoiYDanhSach, ds_quan: List[Dict[str, Any]]):
        super().__init__(timeout=180)
        self.cha = cha
        
        # Nút ShopeeFood nếu có quán
        if ds_quan:
            quan_nhat = ds_quan[0]
            link_sp = quan_nhat.get("link_shopeefood") or "https://shopeefood.vn"
            btn_shopee = discord.ui.Button(
                label=f"🛵 Mở {quan_nhat['thuong_hieu']} ({quan_nhat['khoang_cach_hien_thi']})",
                url=link_sp,
                style=discord.ButtonStyle.link
            )
            self.add_item(btn_shopee)

    @discord.ui.button(label="Quay lại danh sách món", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def nut_quay_lai(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.cha.user_id:
            await interaction.response.send_message("Vui lòng gửi câu hỏi của riêng bạn nhé!", ephemeral=True)
            return

        embed_danh_sach = self.cha.tao_embed_danh_sach()
        await interaction.response.edit_message(embed=embed_danh_sach, view=self.cha)


# ==========================================
# KHỞI TẠO BOT & SỰ KIỆN TỰ ĐỘNG TẠO KÊNH
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


async def tu_dong_tao_kenh_huong_dan(guild: discord.Guild):
    ten_kenh = "chỉ-dẫn-gọi-nước"
    kenh_ton_tai = discord.utils.get(guild.text_channels, name=ten_kenh)

    if not kenh_ton_tai:
        try:
            kenh_moi = await guild.create_text_channel(
                name=ten_kenh,
                topic="Kênh hướng dẫn sử dụng và tương tác tự nhiên với Mijushi"
            )
            embed = discord.Embed(
                title="🍹 CHÀO MỪNG BẠN ĐẾN VỚI MIJUSHI!",
                description=(
                    "Hệ thống AI thông minh giúp bạn chọn đồ uống chuẩn gu theo tâm trạng, "
                    "thời tiết và tự động định vị các quán gần bạn nhất có bán món đó!\n\n"
                    "### 💬 2 CÁCH DÙNG SIÊU DỄ DÀNG:\n"
                    "**1. Trò Chuyện Tự Nhiên (Không Cần Gõ Lệnh)**:\n"
                    "• Trong kênh này hoặc nhắn tin riêng (DM) với Bot, bạn chỉ cần gõ bất cứ câu nào:\n"
                    "  👉 *\"Trời mưa lạnh thèm gì ngọt ấm béo ngậy\"*\n"
                    "  👉 *\"Nay buồn ngủ quá cần ly cà phê đậm vị giải nhiệt\"*\n"
                    "  👉 *\"Thèm trà đào thanh mát ít calo quanh Bách Khoa\"*\n\n"
                    "**2. Hoặc Dùng Lệnh Slash Bất Cứ Đâu**:\n"
                    "• Gõ `/goi-y` $\\rightarrow$ Nhập cảm xúc & chọn khu vực.\n"
                    "• Gõ `/menu` $\\rightarrow$ Xem danh sách toàn bộ các món hot nhất.\n"
                ),
                color=MAU_SAC["Chính"]
            )
            embed.set_footer(text="Bot chạy bằng GPU NVIDIA RTX 4080 • Phản hồi trong 0.1 giây!")
            tin_nhan = await kenh_moi.send(embed=embed)
            await tin_nhan.pin()
            logger.info(f"Đã tự động tạo kênh #{ten_kenh} trên server {guild.name}")
        except Exception as e:
            logger.warning(f"Không thể tự tạo kênh #{ten_kenh}: {e}")


async def _trang_chu_web(request):
    return web.Response(
        text="🍹 Mijushi Bot is Running 24/7!\nConnected to Discord Gateway & Google Gemini AI.",
        content_type="text/plain"
    )

async def _khoi_dong_web_server():
    """Khởi động web server mini để Render nhận diện port và UptimeRobot ping 24/7."""
    try:
        port_str = os.getenv("PORT", "10000")
        port = int(port_str) if port_str.isdigit() else 10000
        app = web.Application()
        app.router.add_get("/", _trang_chu_web)
        app.router.add_get("/health", _trang_chu_web)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Đã mở Web Server mini tại cổng {port} để Render kết nối 24/7!")
    except Exception as e:
        logger.warning(f"Không thể khởi động Web Server mini: {e}")

@bot.event
async def on_ready():
    logger.info(f"Đã đăng nhập thành công bot: {bot.user.name} (ID: {bot.user.id})")
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Đã đồng bộ {len(synced)} Slash Commands vào Guild {GUILD_ID}!")
        else:
            synced = await bot.tree.sync()
            logger.info(f"Đã đồng bộ {len(synced)} Slash Commands toàn cầu.")
    except Exception as e:
        logger.error(f"Lỗi khi đồng bộ Slash Commands: {e}")

    for g in bot.guilds:
        await tu_dong_tao_kenh_huong_dan(g)

    activity = discord.Activity(type=discord.ActivityType.listening, name="Bạn muốn uống gì? Cứ nhắn tin tự nhiên nha!")
    await bot.change_presence(activity=activity)

    # Kích hoạt web server mini cho Render
    await _khoi_dong_web_server()


@bot.event
async def on_guild_join(guild: discord.Guild):
    await tu_dong_tao_kenh_huong_dan(guild)


# ==========================================
# XỬ LÝ CHAT TỰ NHIÊN & GUARDRAILS (COOLDOWN)
# ==========================================
THOI_GIAN_CHAT_CUOI: Dict[int, float] = {}
COOLDOWN_GIAY = 3.0

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    la_kenh_rieng = isinstance(message.channel, discord.DMChannel)
    la_kenh_chi_dan = getattr(message.channel, "name", "") == "chỉ-dẫn-gọi-nước"
    duoc_tag = bot.user.mentioned_in(message) and not message.mention_everyone

    if la_kenh_rieng or la_kenh_chi_dan or duoc_tag:
        clean_text = message.clean_content.replace(f"@{bot.user.name}", "").strip()
        text_lower = clean_text.lower().strip()

        if not clean_text:
            return

        # GUARDRAIL 1: CHỐNG SPAM & BẢO VỆ RATE LIMIT (COOLDOWN)
        loop = asyncio.get_event_loop()
        now = loop.time()
        user_id = message.author.id
        last_time = THOI_GIAN_CHAT_CUOI.get(user_id, 0)

        if now - last_time < COOLDOWN_GIAY:
            await message.reply("Chờ xíu nha, Mijushi đang tìm đồ uống nè! Mình là chỗ gợi ý đồ uống chứ đâu phải quán bán nước đâu mà bấm lẹ dữ dị nè 🍹")
            return

        THOI_GIAN_CHAT_CUOI[user_id] = now

        async with message.channel.typing():
            # 1. GỬI TỚI GEMINI PHÂN TÍCH Ý ĐỊNH & SINH LỜI ĐÁP
            ten_user = message.author.display_name or "bạn"
            phan_tich = tro_ly_gemini.xu_ly_tin_nhan(clean_text, ten_user)

            loai_y_dinh = phan_tich.get("loai")

            # A. Trường hợp CHIT_CHAT (Chào hỏi, hỏi thăm, tán gẫu)
            if loai_y_dinh == "CHIT_CHAT":
                loi_dap = phan_tich.get("phan_hoi")
                if loi_dap:
                    await message.reply(loi_dap)
                    return

            # B. Trường hợp GOI_Y_DO_UONG (Muốn tìm món, thèm nước, theo tâm trạng)
            elif loai_y_dinh == "GOI_Y_DO_UONG":
                kv_phat_hien = phan_tich.get("khu_vuc")
                khu_vuc = "Bách Khoa"
                if kv_phat_hien:
                    for kv in VI_TRI_MAC_DINH.keys():
                        if kv.lower() in kv_phat_hien.lower():
                            khu_vuc = kv
                            break
                else:
                    for kv in VI_TRI_MAC_DINH.keys():
                        if kv.lower() in text_lower:
                            khu_vuc = kv
                            break

                toa_do = VI_TRI_MAC_DINH[khu_vuc]
                tu_khoa = phan_tich.get("tu_khoa_khau_vi") or clean_text
                ket_qua = bo_may_goi_y.goi_y(cau_hoi=tu_khoa, so_luong=5)

                if ket_qua:
                    view = ViewGoiYDanhSach(
                        danh_sach_goi_y=ket_qua,
                        user_id=message.author.id,
                        cau_hoi=clean_text,
                        toa_do_user=toa_do,
                        ten_khu_vuc=khu_vuc
                    )
                    embed = view.tao_embed_danh_sach()
                    loi_nhan = phan_tich.get("loi_nhan", "")
                    noi_dung = f"✨ *{loi_nhan}*" if loi_nhan else None
                    await message.reply(content=noi_dung, embed=embed, view=view)
                    return

            # C. FALLBACK CỤC BỘ (Nếu Gemini bận hoặc mất mạng)
            logger.info("Chuyển sang cơ chế phân loại Semantic Intent Classifier cục bộ...")
            y_dinh_local, _ = bo_may_goi_y.phan_loai_y_dinh(clean_text)

            if y_dinh_local == "CHIT_CHAT":
                embed_chao = discord.Embed(
                    title="👋 Chào bạn! Mình là Mijushi đây nè 🍹",
                    description=(
                        "Hôm nay bạn đang cảm thấy thế nào?\n\n"
                        "• Cần một ly **Cà phê đậm vị** để tỉnh táo làm việc/học tập?\n"
                        "• Hay một ly **Trà sữa béo ngậy** để nạp năng lượng xả stress?\n"
                        "• Hoặc **Nước ép / Trà hoa quả thanh mát** giải nhiệt vóc dáng?\n\n"
                        "👉 *Bạn cứ gõ tự nhiên cảm giác của bạn (kèm khu vực quanh Hà Nội nếu muốn), mình sẽ lọc ngay danh sách món chân ái cho bạn nhé!*"
                    ),
                    color=MAU_SAC["Chính"]
                )
                embed_chao.set_footer(text="Ví dụ: 'trời mưa lạnh thèm gì ngọt ấm béo ngậy quanh Bách Khoa'")
                await message.reply(embed=embed_chao)
                return

            khu_vuc = "Bách Khoa"
            for kv in VI_TRI_MAC_DINH.keys():
                if kv.lower() in text_lower:
                    khu_vuc = kv
                    break

            toa_do = VI_TRI_MAC_DINH[khu_vuc]
            ket_qua = bo_may_goi_y.goi_y(cau_hoi=clean_text, so_luong=5)

            if not ket_qua or ket_qua[0]["tong_diem"] < 0.28:
                await message.reply(
                    "Mình chưa bắt được đúng gu của bạn lắm! Bạn thử miêu tả cụ thể hơn xíu xem đang thèm vị gì nhé "
                    "(ví dụ: *'thèm gì chua thanh mát quanh Bách Khoa'*, *'cà phê muối đậm đà'*, *'trà ô long nướng béo ngậy ít đá'*)..."
                )
                return

            view = ViewGoiYDanhSach(
                danh_sach_goi_y=ket_qua,
                user_id=message.author.id,
                cau_hoi=clean_text,
                toa_do_user=toa_do,
                ten_khu_vuc=khu_vuc
            )
            embed = view.tao_embed_danh_sach()
            await message.reply(embed=embed, view=view)

    await bot.process_commands(message)


# ==========================================
# LỆNH SLASH
# ==========================================
@bot.tree.command(name="goi-y", description="Gợi ý đồ uống chuẩn gu và tìm quán gần nhất đang bán.")
@app_commands.describe(
    mo_ta="Mô tả cảm giác, tâm trạng hoặc khẩu vị bạn muốn (ví dụ: mưa lạnh thèm gì ngọt ấm)",
    khu_vuc="Khu vực của bạn tại Hà Nội để tìm quán gần nhất"
)
@app_commands.choices(khu_vuc=[
    app_commands.Choice(name="Bách Khoa (HUST / Hai Bà Trưng)", value="Bách Khoa"),
    app_commands.Choice(name="Hoàn Kiếm (Hồ Gươm / Phố Cổ)", value="Hoàn Kiếm"),
    app_commands.Choice(name="Vũ Tông Phan (Thanh Xuân / Royal City)", value="Vũ Tông Phan"),
    app_commands.Choice(name="Đống Đa (Xã Đàn / Chùa Bộc)", value="Đống Đa"),
    app_commands.Choice(name="Cầu Giấy", value="Cầu Giấy")
])
async def cmd_goi_y(interaction: discord.Interaction, mo_ta: str, khu_vuc: Optional[app_commands.Choice[str]] = None):
    await interaction.response.defer()

    ten_kv = khu_vuc.value if khu_vuc else "Bách Khoa"
    toa_do = VI_TRI_MAC_DINH.get(ten_kv, VI_TRI_MAC_DINH["Bách Khoa"])

    ket_qua = bo_may_goi_y.goi_y(cau_hoi=mo_ta, so_luong=5)
    if not ket_qua:
        await interaction.followup.send("Rất tiếc, mình chưa tìm thấy món phù hợp. Bạn hãy thử miêu tả cách khác nhé!")
        return

    view = ViewGoiYDanhSach(
        danh_sach_goi_y=ket_qua,
        user_id=interaction.user.id,
        cau_hoi=mo_ta,
        toa_do_user=toa_do,
        ten_khu_vuc=ten_kv
    )
    embed = view.tao_embed_danh_sach()
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="menu", description="Xem menu các món đồ uống nổi bật.")
async def cmd_menu(interaction: discord.Interaction):
    ds_mon = csdl.lay_tat_ca_do_uong()
    embed = discord.Embed(
        title="🍹 Danh Mục Đồ Uống Khám Phá Cùng Mijushi",
        description="Chào mừng bạn đến với Mijushi! Dưới đây là các nhóm món nổi bật:",
        color=MAU_SAC["Chính"]
    )
    for dm in ["Cà Phê", "Trà Sữa", "Trà Hoa Quả", "Đá Xay", "Nước Ép", "Thư Giãn"]:
        mon_dm = [m for m in ds_mon if m["danh_muc"] == dm]
        ds_ten = ", ".join([f"**{m['ten']}**" for m in mon_dm[:3]])
        embed.add_field(name=f"{EMOJI_DANH_MUC.get(dm, '🥤')} {dm} ({len(mon_dm)} món)", value=ds_ten, inline=False)

    embed.set_footer(text="Bạn có thể chat tự nhiên câu bất kỳ để Mijushi tư vấn món nhé!")
    await interaction.response.send_message(embed=embed)


def chay_bot():
    if not DISCORD_BOT_TOKEN:
        print("\n⚠️ CẢNH BÁO: CHƯA CẤU HÌNH DISCORD_BOT_TOKEN!\n")
        return

    print("🚀 Đang khởi động Discord Bot Mijushi (Top List View)...")
    bot.run(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    chay_bot()
