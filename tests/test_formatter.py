from unittest.mock import ANY, MagicMock, patch

import pytest

from app.escpos_formatter import (
    RECEIPT_WIDTH,
    _legacy_to_lines,
    _wrap_text,
    format_and_print,
    format_lines,
    lines_to_text,
    process_line_objects,
)


@pytest.fixture
def mock_printer():
    printer = MagicMock()
    printer.pulse = MagicMock()
    return printer


def test_wrap_text_empty():
    assert _wrap_text("") == []


def test_wrap_text_short():
    assert _wrap_text("hello", width=32) == ["hello"]


def test_wrap_text_exact():
    text = "a" * 32
    assert _wrap_text(text, width=32) == [text]


def test_wrap_text_long():
    text = "one two three four five six seven"
    assert _wrap_text(text, width=20) == [
        "one two three four",
        "five six seven",
    ]


def test_wrap_text_long_word():
    text = "abcdefghij"
    assert _wrap_text(text, width=4) == ["abcd", "efgh", "ij"]


def test_process_text_line(mock_printer):
    lines = [
        {
            "type": "text",
            "text": "Hello",
            "align": "center",
            "bold": True,
            "font": "b",
        }
    ]

    count = process_line_objects(lines, mock_printer)

    mock_printer.set.assert_called_once_with(
        align="center",
        font="b",
        bold=True,
        underline=0,
        double_width=False,
        double_height=False,
        invert=False,
    )
    mock_printer.text.assert_called_once_with("Hello")
    assert count == 1


def test_process_text_line_with_newlines(mock_printer):
    lines = [{"type": "text", "text": "Hi", "newlines": 2}]

    count = process_line_objects(lines, mock_printer)

    mock_printer.ln.assert_called_once_with(count=2)
    assert count == 3


def test_process_feed_line(mock_printer):
    lines = [{"type": "feed", "count": 3}]

    count = process_line_objects(lines, mock_printer)

    mock_printer.ln.assert_called_once_with(count=3)
    assert count == 3


def test_process_cut_line(mock_printer):
    lines = [{"type": "cut", "mode": "part", "feed": 0}]

    process_line_objects(lines, mock_printer)

    mock_printer.cut.assert_called_once_with(mode="PART", feed=False)


def test_process_qr_line(mock_printer):
    lines = [
        {
            "type": "qr",
            "data": "https://example.com",
            "size": 6,
            "center": False,
            "ec": "H",
        }
    ]

    process_line_objects(lines, mock_printer)

    mock_printer.qr.assert_called_once_with(
        "https://example.com",
        size=6,
        center=False,
        ec=3,
    )


def test_process_barcode_line(mock_printer):
    lines = [
        {
            "type": "barcode",
            "code": "1234567890",
            "bc": "CODE128",
            "height": 80,
            "width": 3,
            "pos": "above",
            "font": "b",
        }
    ]

    process_line_objects(lines, mock_printer)

    mock_printer.barcode.assert_called_once_with(
        code="1234567890",
        bc="CODE128",
        height=80,
        width=3,
        pos="ABOVE",
        font="B",
    )


def test_process_pulse_line(mock_printer):
    lines = [{"type": "pulse", "pin": 1}]

    process_line_objects(lines, mock_printer)

    mock_printer.pulse.assert_called_once_with(1)


def test_process_pulse_line_uses_cashdraw_fallback(mock_printer):
    del mock_printer.pulse
    mock_printer.cashdraw = MagicMock()
    lines = [{"type": "pulse", "pin": 0}]

    process_line_objects(lines, mock_printer)

    mock_printer.cashdraw.assert_called_once_with(0)


@patch("app.escpos_formatter.Network")
def test_format_lines_structured(mock_network_class):
    mock_printer = MagicMock()
    mock_printer.pulse = MagicMock()
    mock_network_class.return_value = mock_printer

    structured_lines = [
        {"type": "text", "text": "Receipt\n"},
        {"type": "feed", "count": 1},
        {"type": "cut"},
    ]

    count = format_lines(structured_lines, host="192.168.1.1", port=9100)

    mock_network_class.assert_called_once_with("192.168.1.1", port=9100)
    mock_printer.set.assert_called()
    mock_printer.text.assert_called_once_with("Receipt\n")
    mock_printer.ln.assert_called_once_with(count=1)
    mock_printer.cut.assert_called_once()
    mock_printer.close.assert_called_once()
    assert count == 2


@patch("app.escpos_formatter.Network")
def test_format_lines_connection_error(mock_network_class):
    mock_network_class.side_effect = ConnectionError("connection refused")

    with pytest.raises(RuntimeError, match="printer connection failed"):
        format_lines([{"type": "cut"}], host="host", port=9100)


def test_lines_to_text_text_styles():
    lines = [
        {
            "type": "text",
            "text": "Title",
            "align": "center",
            "bold": True,
            "underline": 1,
            "invert": True,
        }
    ]

    preview = lines_to_text(lines)

    assert "**" in preview
    assert "_" in preview
    assert "[INV:" in preview
    assert "Title" in preview
    assert "             Title" in preview


def test_lines_to_text_feed():
    lines = [{"type": "feed", "count": 2}]

    assert lines_to_text(lines) == "\n"


def test_lines_to_text_cut():
    lines = [{"type": "cut"}]

    preview = lines_to_text(lines)

    assert preview == f"{'═' * RECEIPT_WIDTH}\n[CUT]"


def test_lines_to_text_qr():
    short_data = "https://example.com"
    long_data = "x" * 40

    short_preview = lines_to_text([{"type": "qr", "data": short_data}])
    long_preview = lines_to_text([{"type": "qr", "data": long_data}])

    assert short_preview == f"[QR: {short_data}]"
    assert long_preview == f"[QR: {'x' * 32}...]"


def test_lines_to_text_barcode():
    lines = [{"type": "barcode", "code": "1234567890", "bc": "CODE128"}]

    assert lines_to_text(lines) == "[BARCODE CODE128: 1234567890]"


def test_lines_to_text_pulse():
    lines = [{"type": "pulse", "pin": 2}]

    assert lines_to_text(lines) == "[DRAWER PULSE pin=2]"


def test_lines_to_text_mixed_receipt():
    lines = [
        {"type": "text", "text": "Store Name", "align": "center", "bold": True},
        {"type": "feed", "count": 1},
        {"type": "qr", "data": "https://pay.example.com"},
        {"type": "barcode", "code": "999", "bc": "EAN13"},
        {"type": "pulse", "pin": 0},
        {"type": "cut"},
    ]

    preview = lines_to_text(lines)
    lines_out = preview.split("\n")

    assert any("Store Name" in line for line in lines_out)
    assert "[QR: https://pay.example.com]" in lines_out
    assert "[BARCODE EAN13: 999]" in lines_out
    assert "[DRAWER PULSE pin=0]" in lines_out
    assert "[CUT]" in lines_out


def test_lines_to_text_legacy_preview():
    lines = _legacy_to_lines("hello world", qr_data="https://example.com")
    preview = lines_to_text(lines)

    # Legacy format now simplified: no header, no cut
    assert "hello world" in preview
    assert "[QR: https://example.com]" in preview
    assert "[CUT]" not in preview


@patch("app.escpos_formatter.Network")
def test_format_and_print_success(mock_network_class):
    mock_printer = MagicMock()
    mock_network_class.return_value = mock_printer

    lines = format_and_print("hello world", host="192.168.1.1", port=9100)

    mock_network_class.assert_called_once_with("192.168.1.1", port=9100)
    mock_printer.set.assert_called()
    mock_printer.text.assert_called()
    # Legacy format no longer includes cut
    mock_printer.cut.assert_not_called()
    mock_printer.close.assert_called_once()

    text_calls = [call[0][0] for call in mock_printer.text.call_args_list]
    assert "hello world\n" in text_calls
    assert lines > 0


@patch("app.escpos_formatter.Network")
def test_format_and_print_with_qr(mock_network_class):
    mock_printer = MagicMock()
    mock_network_class.return_value = mock_printer

    format_and_print(
        "test",
        host="host",
        port=9100,
        qr_data="https://example.com",
    )

    mock_printer.qr.assert_called_once_with("https://example.com", size=8)


@patch("app.escpos_formatter.Network")
def test_format_and_print_connection_error(mock_network_class):
    mock_network_class.side_effect = ConnectionError("connection refused")

    with pytest.raises(RuntimeError, match="printer connection failed"):
        format_and_print("test", host="host", port=9100)


# Image support tests
@patch("app.escpos_formatter.Image")
@patch("app.escpos_formatter.base64.b64decode")
@patch("app.escpos_formatter.urllib.request.urlopen")
@patch("app.escpos_formatter.Network")
def test_process_image_line_success(mock_network_class, mock_urlopen, mock_b64decode, mock_image_module, mock_printer):
    # Prepare mock image
    mock_img = MagicMock()
    mock_img.size = (100, 50)
    mock_img.convert.return_value = mock_img
    mock_img.resize.return_value = mock_img
    mock_image_module.open.return_value = mock_img

    # Base64 data URL
    b64_str = "data:image/png;base64,ABC"
    mock_b64decode.return_value = b"fakebytes"

    lines = [
        {
            "type": "image",
            "data": b64_str,
            "width": 200,
            "height": 100,
            "center": True,
            "dither": False,
            "keep_aspect": False,
        }
    ]

    count = process_line_objects(lines, mock_printer)

    mock_image_module.open.assert_called_once()
    mock_img.convert.assert_called_once_with("1")
    mock_img.resize.assert_called_once_with((200, 100), ANY)
    mock_printer.image.assert_called_once_with(
        mock_img,
        impl="bitImageRaster",
        high_density_vertical=True,
        high_density_horizontal=True,
        center=True,
        fragment_height=960,
    )
    assert count == 1


@patch("app.escpos_formatter.Image")
@patch("app.escpos_formatter.base64.b64decode")
@patch("app.escpos_formatter.Network")
def test_process_image_line_aspect_ratio_resize(mock_network_class, mock_b64decode, mock_image_module, mock_printer):
    # Original image 400x300
    mock_img = MagicMock()
    mock_img.size = (400, 300)
    mock_img.convert.return_value = mock_img
    mock_img.resize.return_value = mock_img
    mock_image_module.open.return_value = mock_img

    mock_b64decode.return_value = b"fakebytes"

    lines = [{
        "type": "image",
        "data": "data:image/png;base64,ABC",
        "width": 200,  # only width given, aspect preserved
    }]

    process_line_objects(lines, mock_printer)

    # Expect height scaled proportionally: 200 * (300/400) = 150
    mock_img.resize.assert_called_once_with((200, 150), ANY)


@patch("app.escpos_formatter.Image")
@patch("app.escpos_formatter.base64.b64decode")
@patch("app.escpos_formatter.Network")
def test_process_image_line_invalid_data_raises(mock_network_class, mock_b64decode, mock_image_module, mock_printer):
    # Simulate missing data
    lines = [{"type": "image", "data": ""}]

    with pytest.raises(RuntimeError, match="Image data missing"):
        process_line_objects(lines, mock_printer)

    # Simulate unsupported format
    lines = [{"type": "image", "data": "ftp://unsupported.com/img.png"}]
    with pytest.raises(RuntimeError, match="Unsupported image data format"):
        process_line_objects(lines, mock_printer)
