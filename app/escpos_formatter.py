import base64
import io
import urllib.request
from PIL import Image
import time
from escpos.printer import Network
from escpos.exceptions import BarcodeCodeError

RECEIPT_WIDTH = 32

_QR_EC_LEVELS = {"L": 0, "M": 1, "Q": 2, "H": 3}
_BARCODE_POS = {
    "below": "BELOW",
    "above": "ABOVE",
    "both": "BOTH",
    "off": "OFF",
}


def format_and_print(
    text: str,
    host: str,
    port: int,
    qr_data: str | None = None,
    max_retries: int = 10,
) -> int:
    """Format receipt content and send it to the printer. Returns lines printed."""
    lines = _legacy_to_lines(text, qr_data)
    return format_lines(lines, host, port, max_retries)


def format_lines(lines: list[dict], host: str, port: int, max_retries: int = 10) -> int:
    """Connect to the printer and process structured line objects.
    Ensures printer profile has media width for alignment features.
    Retries on connection errors up to max_retries times with 0.5s pause.
    """
    last_exc = None
    for attempt in range(max_retries):
        printer = None
        try:
            printer = Network(host, port=port)
            # Ensure media width is set so center/right alignment works without warnings
            try:
                # Use printer._profile directly for mutability
                if not hasattr(printer, '_profile') or not isinstance(printer._profile, dict):
                    printer._profile = {}
                profile = printer._profile
                media = profile.setdefault('media', {})
                width = media.setdefault('width', {})
                if not width.get('pixel'):
                    width['pixel'] = 384
            except Exception:
                pass
            lines_printed = process_line_objects(lines, printer)
            printer.close()
            return lines_printed
        except (ConnectionError, TimeoutError) as exc:
            last_exc = exc
            if printer is not None:
                try:
                    printer.close()
                except Exception:
                    pass
            if attempt < max_retries - 1:
                time.sleep(0.5)
                continue
            raise RuntimeError(f"printer connection failed after {max_retries} attempts: {exc}") from exc
        except Exception:
            if printer is not None:
                try:
                    printer.close()
                except Exception:
                    pass
            raise
    raise RuntimeError(f"printer connection failed after {max_retries} attempts: {last_exc}")


def process_line_objects(lines: list[dict], printer) -> int:
    """Execute structured line objects against a printer instance."""
    lines_printed = 0

    for line in lines:
        line_type = line.get("type", "text")
        if line_type == "text":
            lines_printed += _handle_text_line(line, printer)
        elif line_type == "feed":
            lines_printed += _handle_feed_line(line, printer)
        elif line_type == "cut":
            _handle_cut_line(line, printer)
        elif line_type == "qr":
            _handle_qr_line(line, printer)
        elif line_type == "barcode":
            _handle_barcode_line(line, printer)
        elif line_type == "pulse":
            _handle_pulse_line(line, printer)
        elif line_type == "image":
            _handle_image_line(line, printer)
            lines_printed += 1

    return lines_printed


def lines_to_text(lines: list[dict]) -> str:
    """Render structured line objects as plain text for preview."""
    output: list[str] = []

    for line in lines:
        line_type = line.get("type", "text")
        if line_type == "text":
            output.extend(_render_text_preview(line))
        elif line_type == "feed":
            output.extend([""] * line.get("count", 1))
        elif line_type == "cut":
            output.append("═" * RECEIPT_WIDTH)
            output.append("[CUT]")
        elif line_type == "qr":
            data = line.get("data", "")
            preview = data if len(data) <= 32 else f"{data[:32]}..."
            output.append(f"[QR: {preview}]")
        elif line_type == "barcode":
            code = line.get("code", "")
            bc = line.get("bc", "")
            preview = code if len(code) <= 32 else f"{code[:32]}..."
            output.append(f"[BARCODE {bc}: {preview}]")
        elif line_type == "pulse":
            pin = line.get("pin", 0)
            output.append(f"[DRAWER PULSE pin={pin}]")
        elif line_type == "image":
            w = line.get("width", "?")
            h = line.get("height", "?")
            output.append(f"[IMAGE: {w}x{h}]")

    return "\n".join(output)


def _legacy_to_lines(text: str, qr_data: str | None = None) -> list[dict]:
    """Wrap raw text into a structured list preserving user's newlines.
    Each user line becomes a text object (left-aligned). We do NOT rewrap.
    """
    lines: list[dict] = []
    # Split on \n and keep empty lines as empty strings
    for line in text.split("\n"):
        # Ensure trailing newline for each text object (printer expects it)
        lines.append({"type": "text", "text": (line if line.endswith("\n") else line + "\n"), "align": "left"})
    lines.append({"type": "feed", "count": 1})
    if qr_data:
        lines.append({"type": "qr", "data": qr_data})
    return lines


def _handle_text_line(line: dict, printer) -> int:
    set_kwargs: dict = {
        "align": line.get("align", "left"),
        "font": line.get("font", "a"),
        "bold": line.get("bold", False),
        "underline": line.get("underline", 0),
        "double_width": line.get("double_width", False),
        "double_height": line.get("double_height", False),
        "invert": line.get("invert", False),
    }

    if line.get("width") is not None:
        set_kwargs["width"] = line["width"]
    if line.get("height") is not None:
        set_kwargs["height"] = line["height"]
    if line.get("smooth") is not None:
        set_kwargs["smooth"] = line["smooth"]

    printer.set(**set_kwargs)
    printer.text(line["text"])

    newlines = line.get("newlines", 0)
    if newlines:
        printer.ln(count=newlines)

    return 1 + newlines


def _handle_feed_line(line: dict, printer) -> int:
    count = line.get("count", 1)
    printer.ln(count=count)
    return count


def _handle_cut_line(line: dict, printer) -> None:
    mode = str(line.get("mode", "full")).upper()
    if mode not in {"FULL", "PART"}:
        mode = "FULL"

    feed = line.get("feed", 3)
    feed_bool = bool(feed) if isinstance(feed, int) else feed
    printer.cut(mode=mode, feed=feed_bool)


def _handle_qr_line(line: dict, printer) -> None:
    kwargs: dict = {"size": line.get("size", 8)}
    if "center" in line:
        kwargs["center"] = line["center"]
    if "ec" in line:
        ec = line["ec"]
        kwargs["ec"] = (
            _QR_EC_LEVELS.get(ec.upper(), 1) if isinstance(ec, str) else ec
        )

    printer.qr(line["data"], **kwargs)


def _handle_barcode_line(line: dict, printer) -> None:
    try:
        pos = _BARCODE_POS.get(str(line.get("pos", "below")).lower(), "BELOW")
        font = str(line.get("font", "a")).upper()
        printer.barcode(
            code=line["code"],
            bc=line["bc"],
            height=line.get("height", 100),
            width=line.get("width", 2),
            pos=pos,
            font=font,
        )
    except BarcodeCodeError as exc:
        raise RuntimeError(f"Invalid barcode: {exc}") from exc


def _handle_pulse_line(line: dict, printer) -> None:
    pin = line.get("pin", 0)
    drawer = getattr(printer, "pulse", getattr(printer, "cashdraw"))
    drawer(pin)


def _handle_image_line(line: dict, printer) -> None:
    """Render an image to the printer.
    Supports URL or base64 data URL input. Converts to 1-bit, resizes, and prints.
    """
    data = line.get("data")
    if not data:
        raise RuntimeError("Image data missing")

    try:
        # Load image
        if data.startswith("http://") or data.startswith("https://"):
            with urllib.request.urlopen(data, timeout=10) as resp:
                img_bytes = resp.read()
            img = Image.open(io.BytesIO(img_bytes))
        elif data.startswith("data:image/"):
            # Data URL: format "data:image/png;base64,...."
            # Extract base64 part after the first comma
            _, b64_data = data.split(",", 1)
            img_bytes = base64.b64decode(b64_data)
            img = Image.open(io.BytesIO(img_bytes))
        else:
            raise RuntimeError("Unsupported image data format; must be URL or data:image/base64")

        # Convert to 1-bit
        dither = line.get("dither", False)
        if dither:
            img = img.convert("1", dither=Image.FLOYDSTEINBERG)
        else:
            img = img.convert("1")

        # Determine target size
        max_w = line.get("width")
        max_h = line.get("height")
        # Default width if not provided
        if max_w is None and max_h is None:
            max_w = 384
        orig_w, orig_h = img.size
        new_w, new_h = orig_w, orig_h

        keep_aspect = line.get("keep_aspect", True)

        if max_w is not None and max_h is not None:
            if keep_aspect:
                ratio = min(max_w / orig_w, max_h / orig_h)
            else:
                ratio_w = max_w / orig_w
                ratio_h = max_h / orig_h
                # Use the smaller to ensure within bounds? Actually we want exact fit; but if keep_aspect False, we'll force dimensions exactly
                new_w = max_w
                new_h = max_h
                ratio = None
        elif max_w is not None:
            ratio = max_w / orig_w
        elif max_h is not None:
            ratio = max_h / orig_h
        else:
            ratio = 384 / orig_w

        if ratio is not None:
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)

        # Ensure at least 1 pixel
        new_w = max(1, new_w)
        new_h = max(1, new_h)

        if new_w != orig_w or new_h != orig_h:
            img = img.resize((new_w, new_h), Image.LANCZOS)

        # Print image
        printer.image(
            img,
            impl="bitImageRaster",
            high_density_vertical=True,
            high_density_horizontal=True,
            center=line.get("center", False),
            fragment_height=960,
        )
    except Exception as e:
        raise RuntimeError(f"Image processing failed: {e}") from e


def _render_text_preview(line: dict) -> list[str]:
    text = line.get("text", "").rstrip("\n")
    if not text:
        return [""]

    align = line.get("align", "left")
    rendered: list[str] = []

    for wrapped in _wrap_text(text, width=RECEIPT_WIDTH):
        aligned = _align_text(wrapped, align, RECEIPT_WIDTH)
        rendered.append(_apply_text_styles(aligned, line))

    newlines = line.get("newlines", 0)
    rendered.extend([""] * newlines)
    return rendered


def _align_text(text: str, align: str, width: int) -> str:
    if len(text) >= width:
        return text[:width]

    padding = width - len(text)
    if align == "center":
        left_pad = padding // 2
        return (" " * left_pad) + text
    if align == "right":
        return (" " * padding) + text
    return text


def _apply_text_styles(text: str, line: dict) -> str:
    styled = text
    if line.get("double_width") or line.get("double_height"):
        styled = f"#{styled}#"
    if line.get("bold"):
        styled = f"**{styled}**"
    if line.get("underline"):
        styled = f"_{styled}_"
    if line.get("invert"):
        styled = f"[INV:{styled}]"
    return styled


def _wrap_text(text: str, width: int = 32) -> list[str]:
    """Wrap text to width, respecting word boundaries."""
    if not text:
        return []

    words = text.split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        if not current_line:
            if len(word) <= width:
                current_line = word
            else:
                while len(word) > width:
                    lines.append(word[:width])
                    word = word[width:]
                current_line = word
        elif len(current_line) + 1 + len(word) <= width:
            current_line += " " + word
        else:
            lines.append(current_line)
            if len(word) <= width:
                current_line = word
            else:
                while len(word) > width:
                    lines.append(word[:width])
                    word = word[width:]
                current_line = word

    if current_line:
        lines.append(current_line)

    return lines
