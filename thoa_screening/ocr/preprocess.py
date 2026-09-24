"""
OCR Preprocessing Utilities.

Uses OpenCV to deskew, denoise, and threshold images to improve Tesseract accuracy.
"""
import math
import numpy as np
import cv2
from PIL import Image

def deskew(image: np.ndarray) -> np.ndarray:
    """
    Deskew the image using minAreaRect on contours.
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
        
    # Invert the image (text needs to be white, background black for minAreaRect)
    gray = cv2.bitwise_not(gray)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # Get all non-zero pixel coordinates
    coords = np.column_stack(np.where(thresh > 0))
    if coords.size == 0:
        return image
        
    # Compute minimum bounding rectangle
    angle = cv2.minAreaRect(coords)[-1]
    
    # minAreaRect returns angle in [-90, 0)
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
        
    # If the angle is suspiciously large, don't rotate
    if abs(angle) > 15:
        return image
        
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    return rotated

def preprocess_for_ocr(pil_img: Image.Image) -> Image.Image:
    """
    Preprocess a PIL image for OCR.
    1. Convert to grayscale.
    2. Denoise.
    3. Adaptive Thresholding (Binarization).
    4. Deskew.
    """
    # Convert PIL to cv2
    img = np.array(pil_img)
    if len(img.shape) == 3 and img.shape[2] == 3: # RGB
        # Convert RGB to BGR for cv2
        img = img[:, :, ::-1]
        
    # 1. Grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
        
    # 2. Denoise
    # We use median blur for salt-and-pepper noise removal
    denoised = cv2.medianBlur(gray, 3)
    
    # 3. Adaptive Thresholding (helps with uneven lighting)
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    # 4. Deskew
    deskewed = deskew(binary)
    
    # Convert back to PIL
    return Image.fromarray(deskewed)
