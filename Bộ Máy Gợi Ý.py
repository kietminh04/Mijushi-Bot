"""
Bộ Máy Gợi Ý Đồ Uống Thông Minh (Hybrid Recommendation Engine).
Kết hợp Tìm Kiếm Ngữ Nghĩa (Semantic Vector Search) và Bộ Lọc Quy Tắc (Rule-based Intent Matching).
Tận dụng tăng tốc GPU NVIDIA RTX 4080 với PyTorch & SentenceTransformers.
"""

import re
import sys
import math
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import importlib.util

# Đảm bảo mã hóa UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BoMayGoiY")

# Nạp module Cơ Sở Dữ Liệu
DUONG_DAN_THU_MUC = Path(__file__).resolve().parent
spec_csdl = importlib.util.spec_from_file_location("Cơ Sở Dữ Liệu", str(DUONG_DAN_THU_MUC / "Cơ Sở Dữ Liệu.py"))
csdl = importlib.util.module_from_spec(spec_csdl)
spec_csdl.loader.exec_module(csdl)


# ==========================================
# 1. TỪ ĐIỂN TỪ KHÓA Ý ĐỊNH (INTENT DICTIONARY)
# ==========================================
TU_KHOA_QUY_TAC = {
    "nhiet_do_nong": ["nóng", "ấm", "ấm bụng", "ấm áp", "giữ ấm", "ngày lạnh", "mùa đông", "mưa lạnh", "se lạnh", "buốt"],
    "nhiet_do_da": ["đá", "lạnh", "mát", "mát mát", "mát mẻ", "mát lạnh", "tê tái", "giải khát", "mát rượi", "nóng bức", "hè", "oi bức", "cháy da", "khát"],
    "giam_can_healthy": ["giảm cân", "eat clean", "healthy", "thanh lọc", "detox", "ít calo", "ít đường", "không đường", "vóc dáng", "đẹp da", "thải độc"],
    "tinh_tao_caffeine": ["buồn ngủ", "tỉnh táo", "tỉnh", "tập trung", "thức đêm", "deadline", "sáng sớm", "cần tỉnh", "mệt mỏi uể oải", "nạp năng lượng"],
    "khong_caffeine": ["mất ngủ", "khó ngủ", "say cà phê", "không caffeine", "không cafein", "tối muộn", "đêm khuya", "dị ứng cà phê", "tim đập nhanh"],
    "vi_chua": ["chua", "chua chua", "chua thanh", "chua ngọt", "chanh", "cam", "ổi", "mãng cầu", "chanh leo", "giải ngấy"],
    "vi_ngot_beo": ["ngọt", "ngọt ngọt", "béo", "béo ngậy", "ngậy", "kem", "cheese", "phô mai", "trân châu", "sữa tươi", "hảo ngọt", "xả stress"],
    "vi_dang": ["đắng", "đắng đắng", "đậm đà", "cà phê đậm", "chát nhẹ", "mộc", "nguyên chất"],
    "thanh_mat_the": ["thanh mát", "mát", "mát mát", "mát mẻ", "giải nhiệt", "the mát", "bạc hà", "dưa hấu", "cần tây", "trà thảo mộc", "thanh tịnh", "dịu dàng"]
}


# ==========================================
# 2. VECTORIZER NỘI BỘ DỰ PHÒNG (TF-IDF & N-GRAM)
# ==========================================
class TFIDFTextEngine:
    """Bộ vectorizer n-gram TF-IDF thuần Python không phụ thuộc bên ngoài."""

    def __init__(self):
        self.vocabulary = {}
        self.idf = {}
        self.doc_vectors = []
        self.items = []

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = cleaned.split()
        bigrams = [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]
        return tokens + bigrams

    def fit_transform(self, items: List[Dict[str, Any]]):
        self.items = items
        self.vocabulary = {}
        self.idf = {}
        self.doc_vectors = []

        doc_tokens = []
        df_counts = {}

        for item in items:
            corpus_text = f"{item['ten']} {item['danh_muc']} {item['huong_vi']} {item['mo_ta']} " + \
                          " ".join(item.get("tam_trang", [])) + " " + " ".join(item.get("thoi_tiet", []))
            tokens = self._tokenize(corpus_text)
            doc_tokens.append(tokens)

            unique_tokens = set(tokens)
            for t in unique_tokens:
                df_counts[t] = df_counts.get(t, 0) + 1

        n_docs = len(items)
        idx = 0
        for token, count in df_counts.items():
            self.vocabulary[token] = idx
            self.idf[token] = math.log((n_docs + 1) / (count + 1)) + 1.0
            idx += 1

        for tokens in doc_tokens:
            vec = self._vectorize(tokens)
            self.doc_vectors.append(vec)

    def _vectorize(self, tokens: List[str]) -> Dict[int, float]:
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        vec = {}
        norm_sq = 0.0
        for t, count in tf.items():
            if t in self.vocabulary:
                v_idx = self.vocabulary[t]
                val = (1 + math.log(count)) * self.idf[t]
                vec[v_idx] = val
                norm_sq += val * val

        norm = math.sqrt(norm_sq) if norm_sq > 0 else 1.0
        for v_idx in vec:
            vec[v_idx] /= norm
        return vec

    def similarity(self, query: str) -> List[float]:
        q_tokens = self._tokenize(query)
        q_vec = self._vectorize(q_tokens)
        scores = []
        for d_vec in self.doc_vectors:
            dot = sum(q_vec.get(k, 0.0) * d_vec.get(k, 0.0) for k in q_vec if k in d_vec)
            scores.append(dot)
        return scores


# ==========================================
# 3. BỘ MÁY GỢI Ý HYBRID CHÍNH
# ==========================================
class BoMayGoiYDoUong:
    def __init__(self):
        self.ds_do_uong = []
        self.tfidf_engine = TFIDFTextEngine()
        self.embedding_model = None
        self.doc_embeddings = None
        self.co_gpu = False
        self.device = "cpu"

        self._kiem_tra_gpu()
        self.cap_nhat_du_lieu_mon()
        self._khoi_tao_semantic_model()

    def _kiem_tra_gpu(self):
        try:
            import torch
            if torch.cuda.is_available():
                self.co_gpu = True
                self.device = "cuda"
                logger.info(f"Đã kích hoạt tăng tốc GPU: {torch.cuda.get_device_name(0)}")
            else:
                self.device = "cpu"
                logger.info("Chạy suy luận embedding trên CPU.")
        except Exception as e:
            logger.warning(f"Không thể kiểm tra PyTorch CUDA: {e}")

    def cap_nhat_du_lieu_mon(self):
        """Đồng bộ danh sách đồ uống từ CSDL và huấn luyện lại vector không gian."""
        self.ds_do_uong = csdl.lay_tat_ca_do_uong()
        self.tfidf_engine.fit_transform(self.ds_do_uong)
        logger.info(f"Đã nạp {len(self.ds_do_uong)} món vào bộ nhớ đệm Bộ Máy Gợi Ý.")

    def _khoi_tao_semantic_model(self):
        """Thử tải mô hình SentenceTransformer nếu có kết nối mạng hoặc cache."""
        try:
            from sentence_transformers import SentenceTransformer
            # Dùng mô hình đa ngôn ngữ siêu nhẹ và chính xác
            model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            logger.info(f"Đang chuẩn bị SentenceTransformer '{model_name}'...")
            self.embedding_model = SentenceTransformer(model_name, device=self.device)

            texts = [
                f"{item['ten']} danh mục {item['danh_muc']}, hương vị: {item['huong_vi']}. Mô tả: {item['mo_ta']}. "
                f"Tâm trạng: {', '.join(item.get('tam_trang', []))}. Thời tiết: {', '.join(item.get('thoi_tiet', []))}."
                for item in self.ds_do_uong
            ]
            self.doc_embeddings = self.embedding_model.encode(texts, convert_to_tensor=True, device=self.device)
            logger.info("Đã tạo xong Vector Embeddings cho toàn bộ menu đồ uống!")

            # Tạo bộ vector nhận diện ý định giao tiếp vs tìm đồ uống
            self.mau_chit_chat = [
                "xin chào", "chào bạn", "hello", "hiii", "hey bot", "bot ơi", "alo", 
                "bạn là ai", "bạn tên gì", "hôm nay thế nào", "có ai ở đây không", 
                "giúp tôi với", "hướng dẫn sử dụng", "bạn làm được gì", "chán quá",
                "cảm ơn bạn", "tạm biệt", "hế lô", "ê", "yo", "mijushi ơi", "ê bot",
                "hôm nay mệt quá", "tâm sự đi", "chào buổi sáng", "bye"
            ]
            self.mau_tim_do_uong = [
                "tôi muốn uống nước", "gợi ý đồ uống", "thèm trà sữa", "uống gì cho tỉnh ngủ",
                "cà phê đậm vị", "tìm quán nước gần đây", "nước ép thanh mát giải nhiệt",
                "đồ uống ít calo giảm cân", "thèm gì ngọt béo ngậy", "trời lạnh uống gì ấm",
                "uống gì xả stress", "trà hoa cúc thư giãn", "matcha đá xay", "thèm cà phê muối",
                "muốn uống gì đó chua thanh", "nước gì mát lạnh"
            ]
            self.emb_chit_chat = self.embedding_model.encode(self.mau_chit_chat, convert_to_tensor=True, device=self.device)
            self.emb_tim_do_uong = self.embedding_model.encode(self.mau_tim_do_uong, convert_to_tensor=True, device=self.device)
            logger.info("Đã khởi tạo xong bộ Vector Semantic Intent Classifier!")
        except Exception as e:
            logger.info(f"SentenceTransformer chưa sẵn sàng ({e}). Chuyển sang dùng bộ máy TF-IDF N-gram song song.")
            self.embedding_model = None

    def phan_loai_y_dinh(self, query: str) -> Tuple[str, float]:
        """
        Dùng mô hình MLM (SentenceTransformer) để phân loại câu nói là CHIT_CHAT hay TIM_DO_UONG.
        Trả về (nhãn, điểm_tin_cậy).
        """
        q_clean = query.strip()
        if not q_clean or len(q_clean.split()) <= 2 and any(w in q_clean.lower() for w in ["hi", "hello", "alo", "chào", "ê", "helo", "yo"]):
            return "CHIT_CHAT", 1.0

        if hasattr(self, "emb_chit_chat") and self.emb_chit_chat is not None:
            try:
                import torch
                from sentence_transformers import util
                q_emb = self.embedding_model.encode(q_clean, convert_to_tensor=True, device=self.device)
                score_chat = float(torch.max(util.cos_sim(q_emb, self.emb_chit_chat)))
                score_drink = float(torch.max(util.cos_sim(q_emb, self.emb_tim_do_uong)))

                if score_chat >= score_drink or score_drink < 0.40:
                    return "CHIT_CHAT", score_chat
                else:
                    return "TIM_DO_UONG", score_drink
            except Exception as e:
                logger.warning(f"Lỗi phân loại ý định qua embedding: {e}")

        # Fallback từ khóa nếu không có model
        q_lower = q_clean.lower()
        if any(w in q_lower for w in ["chào", "hi", "hello", "bạn là ai", "bạn tên gì", "hôm nay thế nào"]):
            return "CHIT_CHAT", 0.9
        return "TIM_DO_UONG", 0.6

    def _tinh_diem_ngu_nghia(self, query: str) -> List[float]:
        """Tính điểm tương đồng ngữ nghĩa giữa câu hỏi người dùng và từng món đồ uống."""
        if self.embedding_model is not None and self.doc_embeddings is not None:
            try:
                import torch
                from sentence_transformers import util
                q_emb = self.embedding_model.encode(query, convert_to_tensor=True, device=self.device)
                cos_scores = util.cos_sim(q_emb, self.doc_embeddings)[0]
                return cos_scores.cpu().tolist()
            except Exception as e:
                logger.warning(f"Lỗi suy luận embedding, dùng fallback TF-IDF: {e}")

        # Fallback TF-IDF
        return self.tfidf_engine.similarity(query)

    def _phan_tich_y_dinh(self, query: str) -> Dict[str, Any]:
        """Trích xuất các ý định đặc thù từ câu hỏi của người dùng."""
        q_lower = query.lower()
        intents = {}

        for nhan, tu_khoa_list in TU_KHOA_QUY_TAC.items():
            khop = [tk for tk in tu_khoa_list if tk in q_lower]
            intents[nhan] = len(khop) > 0

        # Trích xuất ngân sách nếu có (ví dụ: "dưới 40k", "tầm 50 nghìn")
        gia_match = re.search(r"dưới\s*(\d+)\s*(k|nghìn|ngàn|vnd|đ)?", q_lower)
        if gia_match:
            val = int(gia_match.group(1))
            if val < 1000:
                val *= 1000
            intents["ngan_sach_toi_da"] = val

        return intents

    def _tinh_diem_quy_tac(self, mon: Dict[str, Any], intents: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Tính điểm cộng quy tắc và tạo danh sách lý do phù hợp."""
        bonus = 0.0
        ly_do = []

        # 1. Nhiệt độ
        if intents.get("nhiet_do_nong"):
            if mon["nhiet_do"] in ["Nóng", "Cả hai"]:
                bonus += 0.35
                ly_do.append("Phục vụ ấm nóng xua tan cảm giác lạnh giá")
            else:
                bonus -= 0.3

        if intents.get("nhiet_do_da"):
            if mon["nhiet_do"] in ["Đá", "Cả hai"]:
                bonus += 0.25
                ly_do.append("Mát lạnh sảng khoái giải nhiệt tức thì")

        # 2. Healthy / Giảm cân
        if intents.get("giam_can_healthy"):
            if mon["calo"] <= 120:
                bonus += 0.35
                ly_do.append(f"Ít calo ({mon['calo']} kcal), thuần tự nhiên tốt cho vóc dáng")
            elif mon["calo"] > 250:
                bonus -= 0.25

        # 3. Tỉnh táo vs Không caffeine
        if intents.get("tinh_tao_caffeine"):
            if mon["caffeine"] in ["Cao", "Trung bình"]:
                bonus += 0.35
                ly_do.append(f"Hàm lượng caffeine {mon['caffeine'].lower()} giúp lấy lại tập trung nhanh chóng")

        if intents.get("khong_caffeine"):
            if mon["caffeine"] == "Không":
                bonus += 0.4
                ly_do.append("Hoàn toàn 100% không chứa caffeine, êm dịu không lo mất ngủ")
            elif mon["caffeine"] == "Cao":
                bonus -= 0.5

        # 4. Hương vị
        if intents.get("vi_chua") and ("chua" in mon["huong_vi"].lower() or mon["danh_muc"] in ["Trà Hoa Quả", "Nước Ép"]):
            bonus += 0.25
            ly_do.append("Vị chua ngọt thanh mát kích thích vị giác và chống ngấy")

        if intents.get("vi_ngot_beo") and ("béo" in mon["huong_vi"].lower() or mon["danh_muc"] in ["Trà Sữa", "Đá Xay"]):
            bonus += 0.25
            ly_do.append("Hương vị ngọt ngào, béo thơm hấp dẫn xoa dịu tâm trạng")

        if intents.get("thanh_mat_the") and ("thanh" in mon["huong_vi"].lower() or "bạc hà" in mon["huong_vi"].lower()):
            bonus += 0.25
            ly_do.append("Thanh mát dịu nhẹ, thanh lọc cơ thể")

        # 5. Ngân sách
        if "ngan_sach_toi_da" in intents:
            if mon["gia"] <= intents["ngan_sach_toi_da"]:
                bonus += 0.15
                ly_do.append(f"Giá hợp lý ({mon['gia']:,} VNĐ) vừa vặn ngân sách")
            else:
                bonus -= 0.4

        return bonus, ly_do

    def goi_y(self, cau_hoi: str, so_luong: int = 3, loc_danh_muc: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Phương thức chính: Nhận câu hỏi tự nhiên của người dùng và trả về top món phù hợp nhất.
        """
        if not self.ds_do_uong:
            self.cap_nhat_du_lieu_mon()

        # 1. Tính điểm ngữ nghĩa
        diem_ngu_nghia = self._tinh_diem_ngu_nghia(cau_hoi)

        # 2. Phân tích ý định & Tính điểm quy tắc
        intents = self._phan_tich_y_dinh(cau_hoi)

        danh_sach_ket_qua = []
        for idx, mon in enumerate(self.ds_do_uong):
            if loc_danh_muc and loc_danh_muc.lower() not in mon["danh_muc"].lower():
                continue

            score_semantic = diem_ngu_nghia[idx] if idx < len(diem_ngu_nghia) else 0.0
            bonus_rule, ly_do = self._tinh_diem_quy_tac(mon, intents)

            tong_diem = (score_semantic * 0.6) + (bonus_rule * 0.4)

            # Tự động tạo câu giải thích nếu danh sách lý do trống
            if not ly_do:
                ly_do.append(f"Hợp với gu: {mon['huong_vi']}")

            danh_sach_ket_qua.append({
                "mon": mon,
                "tong_diem": round(tong_diem, 3),
                "diem_ngu_nghia": round(score_semantic, 3),
                "ly_do_goi_y": " • ".join(ly_do[:2])
            })

        # Sắp xếp giảm dần theo tổng điểm
        danh_sach_ket_qua.sort(key=lambda x: x["tong_diem"], reverse=True)
        return danh_sach_ket_qua[:so_luong]


# Khởi tạo singleton instance
bo_may_goi_y = BoMayGoiYDoUong()


if __name__ == "__main__":
    cau_hoi_test = "Hôm nay trời mưa lạnh, tớ đang mệt muốn uống gì đó nóng ấm ngọt ngào không bị mất ngủ"
    print(f"Câu hỏi: '{cau_hoi_test}'\n")
    ket_qua = bo_may_goi_y.goi_y(cau_hoi_test, so_luong=3)
    for i, item in enumerate(ket_qua, 1):
        m = item["mon"]
        print(f"{i}. [{m['id']}] {m['ten']} ({m['gia']:,}đ, {m['calo']} calo, {m['nhiet_do']})")
        print(f"   Điểm phù hợp: {item['tong_diem']}")
        print(f"   Lý do gợi ý: {item['ly_do_goi_y']}")
        print(f"   Hương vị: {m['huong_vi']}\n")
