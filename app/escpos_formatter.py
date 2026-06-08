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
) -> int:
    """Format receipt content and send it to the printer. Returns lines printed."""
    lines = _legacy_to_lines(text, qr_data)
    return format_lines(lines, host, port)


def format_lines(lines: list[dict], host: str, port: int) -> int:
    """Connect to the printer and process structured line objects.
    Ensures printer profile has media width for alignment features.
    """
    try:
        printer = Network(host, port=port)
        # Ensure media width is set so center/right alignment works without warnings
        try:
            profile = getattr(printer, '_profile', None)
            if profile is not None and isinstance(profile, dict):
                if not profile.get('media', {}).get('width', {}).get('pixel'):
                    profile.setdefault('media', {})['width'] = {'pixel': 384}
        except Exception:
            # If profile manipulation fails, continue - alignment may not be perfect
            pass
        lines_printed = process_line_objects(lines, printer)
        printer.close()
    except (ConnectionError, TimeoutError) as exc:
        raise RuntimeError(f"printer connection failed: {exc}") from exc

    return lines_printed


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
