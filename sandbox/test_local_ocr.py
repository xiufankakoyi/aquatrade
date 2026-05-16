"""
测试本地 OCR (RapidOCR)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR


def test_local_ocr():
    """测试本地 OCR"""
    
    print("测试 RapidOCR 本地 OCR...")
    
    test_image_path = os.path.join(os.path.dirname(__file__), "test_image.png")
    
    if not os.path.exists(test_image_path):
        print("创建测试图片...")
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', (400, 200), color='white')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        draw.text((50, 50), "Hello World", fill='black', font=font)
        draw.text((50, 100), "测试中文识别", fill='black', font=font)
        
        img.save(test_image_path)
        print(f"测试图片已保存: {test_image_path}")
    
    print(f"\n读取图片: {test_image_path}")
    img = cv2.imread(test_image_path)
    
    if img is None:
        print("❌ 无法读取图片")
        return False
    
    print(f"图片尺寸: {img.shape}")
    
    print("\n开始 OCR 识别...")
    rapid_ocr = RapidOCR()
    result, elapse = rapid_ocr(img)
    
    print(f"\n识别耗时: {elapse}")
    print(f"结果类型: {type(result)}")
    
    if result is None or len(result) == 0:
        print("未识别到文字")
        return False
    
    print(f"\n识别结果 ({len(result)} 行):")
    print("-" * 50)
    
    for i, item in enumerate(result, 1):
        print(f"Item {i}: {item}")
        if len(item) >= 2:
            text = item[1]
            confidence = item[2] if len(item) > 2 else "N/A"
            print(f"  文字: {text}")
            print(f"  置信度: {confidence}")
    
    print("-" * 50)
    print("\n✅ 本地 OCR 测试成功!")
    return True


if __name__ == "__main__":
    test_local_ocr()
