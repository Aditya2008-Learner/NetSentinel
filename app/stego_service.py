"""Steganography and Image Forensics service using Pillow."""

import hashlib
import io
import os
from PIL import Image
from typing import Dict, Tuple, Optional, Any

Image.MAX_IMAGE_PIXELS = 4_000_000


def _get_pixel_tuples(img: Image.Image):
    if hasattr(img, "get_flattened_data"):
        return list(img.get_flattened_data())
    return list(img.getdata())


def _iter_pixel_tuples(img: Image.Image):
    if hasattr(img, "get_flattened_data"):
        return iter(img.get_flattened_data())
    return iter(img.getdata())


def calculate_sha256(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def embed_secret_in_image(image_path: str, secret_text: str, output_path: str) -> Tuple[bool, str]:
    """Embed secret text into an image using LSB steganography."""
    try:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            width, height = rgb_img.size
            max_bytes = (width * height * 3) // 8 - 4  # 4 bytes for length prefix

            # Convert secret text to bytes with length prefix
            secret_bytes = secret_text.encode("utf-8")
            length_prefix = len(secret_bytes).to_bytes(4, byteorder="big")
            payload = length_prefix + secret_bytes

            if len(payload) > max_bytes:
                return False, f"Payload too large for image capacity ({len(payload)} bytes > max {max_bytes} bytes)"

            # Convert payload to binary string
            binary_payload = "".join(format(byte, "08b") for byte in payload)
            
            pixels = _get_pixel_tuples(rgb_img)
            new_pixels = []
            data_index = 0
            data_len = len(binary_payload)

            for pixel in pixels:
                r, g, b = pixel
                if data_index < data_len:
                    r = (r & ~1) | int(binary_payload[data_index])
                    data_index += 1
                if data_index < data_len:
                    g = (g & ~1) | int(binary_payload[data_index])
                    data_index += 1
                if data_index < data_len:
                    b = (b & ~1) | int(binary_payload[data_index])
                    data_index += 1
                new_pixels.append((r, g, b))

            encoded_img = Image.new(rgb_img.mode, rgb_img.size)
            encoded_img.putdata(new_pixels)
            encoded_img.save(output_path, "PNG")
        return True, "Secret embedded successfully"
    except Exception as exc:
        return False, str(exc)


def extract_secret_from_image(image_path: str) -> Tuple[bool, str]:
    """Extract hidden LSB secret text from an image file path."""
    try:
        with open(image_path, "rb") as f:
            return extract_secret_from_bytes(f.read())
    except Exception as exc:
        return False, f"Extraction failed: {str(exc)}"


def analyze_image_forensics(image_path: str, file_bytes: bytes) -> Dict[str, object]:
    """Perform metadata and heuristic forensics analysis on an image."""
    try:
        with Image.open(image_path) as img:
            return _analyze_image_forensics_pil(img, file_bytes, os.path.basename(image_path))
    except Exception as exc:
        return {"error": str(exc)}


def _analyze_image_forensics_pil(img: Image.Image, file_bytes: bytes, filename: str) -> Dict[str, object]:
    width, height = img.size
    format_name = img.format or "UNKNOWN"
    mode = img.mode
    sha256_hash = calculate_sha256(file_bytes)
    file_size = len(file_bytes)

    rgb_img = img.convert("RGB")
    total_pixels = width * height
    target_samples = 10000
    step = max(1, total_pixels // target_samples) if total_pixels > 0 else 1

    lsb_count = 0
    total_samples = 0
    for idx, pixel in enumerate(_iter_pixel_tuples(rgb_img)):
        if idx % step == 0:
            r, g, b = pixel
            if (r & 1) ^ (g & 1) ^ (b & 1):
                lsb_count += 1
            total_samples += 1
            if total_samples >= target_samples:
                break
    
    noise_ratio = lsb_count / total_samples if total_samples > 0 else 0
    entropy_factor = max(0.0, 1.0 - 2.0 * abs(noise_ratio - 0.5))
    susposity_score = round(min(100.0, max(5.0, (entropy_factor * 80.0) + (15.0 if format_name == 'PNG' else 5.0))), 1)

    indicators = []
    if noise_ratio >= 0.42 and noise_ratio <= 0.58:
        indicators.append("High LSB bit-plane entropy approaching random distribution (characteristic of steganographic payload).")
    else:
        indicators.append("Natural LSB spatial correlation observed (typical for non-steganographic imagery).")

    if format_name == "PNG":
        indicators.append("Lossless format suitable for LSB data hiding.")
    else:
        indicators.append("Lossy format (JPEG); LSB modification may be degraded by compression.")

    return {
        "filename": filename,
        "format": format_name,
        "mode": mode,
        "dimensions": f"{width} x {height}",
        "file_size_bytes": file_size,
        "sha256": sha256_hash,
        "susposity_score": susposity_score,
        "suspicion_score": susposity_score,
        "indicators": indicators,
        "status": "Analyzed successfully"
    }


def extract_secret_from_bytes(file_bytes: bytes) -> Tuple[bool, str]:
    """Extract hidden LSB secret text from image bytes directly."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            rgb_img = img.convert("RGB")
            width, height = rgb_img.size
            total_pixels = width * height
            total_bits = total_pixels * 3

            if total_bits < 32:
                return False, "No hidden message found or invalid payload length"

            def _bit_stream():
                for r, g, b in _iter_pixel_tuples(rgb_img):
                    yield r & 1
                    yield g & 1
                    yield b & 1

            stream = _bit_stream()

            length = 0
            for _ in range(32):
                length = (length << 1) | next(stream)

            if length <= 0 or length > 1_000_000 or (32 + length * 8) > total_bits:
                return False, "No hidden message found or invalid payload length"

            message_bytes = bytearray()
            for _ in range(length):
                byte_val = 0
                for _ in range(8):
                    byte_val = (byte_val << 1) | next(stream)
                message_bytes.append(byte_val)

            decoded_text = message_bytes.decode("utf-8", errors="replace")
            return True, decoded_text
    except Exception as exc:
        return False, f"Extraction failed: {str(exc)}"



def analyze_image_forensics_from_bytes(file_bytes: bytes, filename: str = "image.png") -> Dict[str, Any]:
    """Perform forensics analysis directly from image bytes."""
    try:
        with Image.open(io.BytesIO(file_bytes)) as img:
            return _analyze_image_forensics_pil(img, file_bytes, filename)
    except Exception as exc:
        return {"error": str(exc)}
