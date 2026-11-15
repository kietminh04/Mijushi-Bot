import sys
import os
from pathlib import Path

# Thêm thư mục gốc dự án vào sys.path
DUONG_DAN_GOC = Path(__file__).resolve().parent.parent
if str(DUONG_DAN_GOC) not in sys.path:
    sys.path.insert(0, str(DUONG_DAN_GOC))

import importlib

# Nạp ứng dụng FastAPI từ Máy Chủ Web
may_chu = importlib.import_module("Máy Chủ Web")
app = may_chu.app
