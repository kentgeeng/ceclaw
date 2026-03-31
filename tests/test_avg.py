"""
測試 avg.py 模組
"""

import os
import tempfile
import pytest
import sys

# 將 avg.py 所在目錄加入路徑
sys.path.insert(0, '/home/zoe_ai')
from avg import read_csv_and_calculate_average


class TestReadCsvAndCalculateAverage:
    """測試 read_csv_and_calculate_average 函式"""
    
    def test_basic_average(self, tmp_path):
        """測試基本平均值計算"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("1\n2\n3\n4\n5\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg == 3.0
        assert count == 5
    
    def test_with_header(self, tmp_path):
        """測試有標題列的 CSV"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("header\n10\n20\n30\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg == 20.0
        assert count == 3
    
    def test_multiple_columns(self, tmp_path):
        """測試多欄位 CSV"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("name,value\nA,10\nB,20\nC,30\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 1)
        
        assert avg == 20.0
        assert count == 3
    
    def test_empty_file(self, tmp_path):
        """測試空檔案"""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg is None
        assert count == 0
    
    def test_single_value(self, tmp_path):
        """測試單一數值"""
        csv_file = tmp_path / "single.csv"
        csv_file.write_text("42\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg == 42.0
        assert count == 1
    
    def test_decimal_values(self, tmp_path):
        """測試小數值"""
        csv_file = tmp_path / "decimal.csv"
        csv_file.write_text("1.5\n2.5\n3.5\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg == 2.5
        assert count == 3
    
    def test_negative_values(self, tmp_path):
        """測試負數"""
        csv_file = tmp_path / "negative.csv"
        csv_file.write_text("-10\n0\n10\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg == 0.0
        assert count == 3
    
    def test_invalid_values_skipped(self, tmp_path):
        """測試跳過無法轉換的值"""
        csv_file = tmp_path / "mixed.csv"
        csv_file.write_text("10\ninvalid\n20\n")
        
        avg, count = read_csv_and_calculate_average(str(csv_file), 0)
        
        assert avg == 15.0
        assert count == 2
