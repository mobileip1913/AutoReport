"""命令行生成海外电商模拟 Excel"""
from pathlib import Path

from app.services.overseas_sample import RECOMMENDED_MAPPING_GUIDE, create_overseas_ecommerce_excel

if __name__ == "__main__":
    out = Path("sample_data/tiktok_uk_store_20250623.xlsx")
    create_overseas_ecommerce_excel(out)
    print(f"Generated: {out.resolve()}")
    print(RECOMMENDED_MAPPING_GUIDE)
