import csv

from kdri import VENDOR_DIR


def test_vendor_files_present_with_expected_row_counts():
    codes = list(csv.DictReader((VENDOR_DIR / "nutrient_codes.csv").open(encoding="utf-8")))
    bands = list(csv.DictReader((VENDOR_DIR / "kdri_standards.csv").open(encoding="utf-8")))
    assert len(codes) == 47
    assert len(bands) == 1052
    assert (VENDOR_DIR / "2025_KDRI_보도자료.pdf").exists()
