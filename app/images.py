"""Xử lý ảnh sản phẩm tải lên: kiểm tra đúng là ảnh, xoay theo EXIF, thu nhỏ và nén lại thành JPEG.

Nén lại (thay vì lưu nguyên file) giúp: ảnh nhỏ (~100–200 KB) nên CSDL và băng thông nhẹ,
bỏ siêu dữ liệu EXIF (có thể chứa vị trí GPS), và loại bỏ nội dung lạ được giấu trong file.
"""
import io

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}
MAX_SIDE = 1000          # cạnh dài nhất sau khi thu nhỏ (px)
MAX_UPLOAD_MB = 5
Image.MAX_IMAGE_PIXELS = 40_000_000  # chặn "bom giải nén" (ảnh rất nhỏ nhưng kích thước pixel khổng lồ)


class ImageError(ValueError):
    pass


def process_upload(raw: bytes) -> tuple[bytes, str]:
    """Trả về (dữ liệu JPEG, content type). Báo ImageError nếu file không phải ảnh hợp lệ."""
    if not raw:
        raise ImageError("File ảnh trống.")
    if len(raw) > MAX_UPLOAD_MB * 1024 * 1024:
        raise ImageError(f"Ảnh quá lớn (tối đa {MAX_UPLOAD_MB} MB).")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ALLOWED_FORMATS:
            raise ImageError("Chỉ nhận ảnh JPG, PNG, WebP hoặc GIF.")
        img.load()
        img = ImageOps.exif_transpose(img)
    except ImageError:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError,
            SyntaxError, ValueError):
        raise ImageError("File không phải ảnh hợp lệ hoặc bị hỏng.") from None

    img.thumbnail((MAX_SIDE, MAX_SIDE))
    if img.mode in ("RGBA", "LA", "P"):
        # JPEG không có nền trong suốt: đặt lên nền trắng
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, "white")
        bg.paste(img, mask=img.getchannel("A"))
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True, progressive=True)
    return out.getvalue(), "image/jpeg"
