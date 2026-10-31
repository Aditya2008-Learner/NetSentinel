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
    lsb_count = 0
    total_samples = 0
    for pixel in _iter_pixel_tuples(rgb_img):
        r, g, b = pixel
        if (r & 1) ^ (g & 1) ^ (b & 1):
            lsb_count += 1
        total_samples += 1
        if total_samples >= 10000:
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

            pixels = _get_pixel_tuples(rgb_img)

            # Flatten all channel bits into a generator or list
            all_bits = []
            for r, g, b in pixels:
                all_bits.append(r & 1)
                all_bits.append(g & 1)
                all_bits.append(b & 1)

            if len(all_bits) < 32:
                return False, "No hidden message found or invalid payload length"

            length_bits = all_bits[:32]
            try:
                length = int("".join(str(b) for b in length_bits), 2)
            except ValueError:
                return False, "No hidden message found or invalid payload length"

            if length <= 0 or length > 1_000_000 or (32 + length * 8) > len(all_bits):
                return False, "No hidden message found or invalid payload length"

            message_bits = all_bits[32 : 32 + length * 8]
            message_bytes = bytearray()
            for i in range(0, len(message_bits), 8):
                byte_bits = message_bits[i : i + 8]
                if len(byte_bits) < 8:
                    break
                current_byte = 0
                for b in byte_bits:
                    current_byte = (current_byte << 1) | b
                message_bytes.append(current_byte)

            if len(message_bytes) != length:
                return False, "No hidden message found or invalid payload length"

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
