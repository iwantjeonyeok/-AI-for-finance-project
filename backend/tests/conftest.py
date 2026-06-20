import os
import sys
from pathlib import Path

# 테스트는 항상 DEMO_MODE 로 (외부 API 불필요)
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_bl_portfolio.db")

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
