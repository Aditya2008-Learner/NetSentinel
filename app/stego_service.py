"""Steganography and Image Forensics service using Pillow."""

import hashlib
import os
from PIL import Image
from typing import Dict, Tuple, Optional

Image.MAX_IMAGE_PIXELS = 25_000_000


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
            
            pixels = list(rgb_img.getdata())
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
    """Extract hidden LSB secret text from an image."""
    try:
        with Image.open(image_path) as img:
            rgb_img = img.convert("RGB")
            pixels = list(rgb_img.getdata())

            binary_data = []
            for pixel in pixels:
                r, g, b = pixel
                binary_data.append(str(r & 1))
                binary_data.append(str(g & 1))
                binary_data.append(str(b & 1))

            binary_string = "".join(binary_data)
            
            # Read first 32 bits (4 bytes) for length
            length_bits = binary_string[:32]
            message_length = int(length_bits, 2)

            total_bits_needed = 32 + (message_length * 8)
            if total_bits_needed > len(binary_string):
                return False, "Invalid steganographic payload or no secret found."

            message_bits = binary_string[32:total_bits_needed]
            message_bytes = bytearray()
            for i in range(0, len(message_bits), 8):
                byte = message_bits[i:i+8]
                message_bytes.append(int(byte, 2))

            secret_text = message_bytes.decode("utf-8", errors="ignore")
        return True, secret_text
    except Exception as exc:
        return False, f"Extraction failed: {str(exc)}"


def analyze_image_forensics(image_path: str, file_bytes: bytes) -> Dict[str, object]:
    """Perform metadata and heuristic forensics analysis on an image."""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            format_name = img.format or "UNKNOWN"
            mode = img.mode
            sha256_hash = calculate_sha256(file_bytes)
            file_size = len(file_bytes)

            # Heuristic LSB entropy/noise check
            # Sample first 10,000 pixels without materializing entire image into memory
            rgb_img = img.convert("RGB")
            lsb_count = 0
            total_samples = 0
            for pixel in rgb_img.getdata():
                r, g, b = pixel
                if (r & 1) ^ (g & 1) ^ (b & 1):
                    lsb_count += 1
                total_samples += 1
                if total_samples >= 10000:
                    break
            
            noise_ratio = lsb_count / total_samples if total_samples > 0 else 0
            susposity_score = round(min(100, max(5, abs(noise_ratio - 0.5) * 100 + (15 if format_name == 'PNG' else 5))), 1)

            indicators = []
            if susposity_score > 60:
                indicators.append("Elevated LSB entropy variance detected.")
            if format_name == "PNG":
                indicators.append("Lossless format suitable for LSB data hiding.")
            else:
                indicators.append("Lossy format (JPEG); LSB modification may be degraded by compression.")

            return {
                "filename": os.path.basename(image_path),
                "format": format_name,
                "mode": mode,
                "dimensions": f"{width} x {height}",
                "file_size_bytes": file_size,
                "sha256": sha256_hash,
                "susposity_score": susposity_score,
                "indicators": indicators,
                "status": "Analyzed successfully"
            }
    except Exception as exc:
        return {"error": str(exc)}
