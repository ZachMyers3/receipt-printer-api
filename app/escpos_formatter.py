from escpos.printer import Network


def format_and_print(
    text: str,
    host: str,
    port: int,
    qr_data: str | None = None,
) -> int:
    """Format receipt content and send it to the printer. Returns lines printed."""
    try:
        printer = Network(host, port=port)
        lines_printed = 0

        printer.set(align="center", bold=True)
        printer.text("📋 PRINTED TASKS\n")
        lines_printed += 1

        printer.set(align="left", bold=False)
        printer.text("─" * 32 + "\n")
        lines_printed += 1

        for line in _wrap_text(text, width=32):
            printer.text(line + "\n")
            lines_printed += 1

        printer.text("\n")
        lines_printed += 1

        if qr_data is not None:
            printer.qr(qr_data, size=8)

        printer.cut()
        printer.close()
    except (ConnectionError, TimeoutError) as exc:
        raise RuntimeError(f"printer connection failed: {exc}") from exc

    return lines_printed


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
