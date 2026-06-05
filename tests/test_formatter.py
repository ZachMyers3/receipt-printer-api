from unittest.mock import MagicMock, patch

import pytest

from app.escpos_formatter import _wrap_text, format_and_print


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


@patch("app.escpos_formatter.Network")
def test_format_and_print_success(mock_network_class):
    mock_printer = MagicMock()
    mock_network_class.return_value = mock_printer

    lines = format_and_print("hello world", host="192.168.1.1", port=9100)

    mock_network_class.assert_called_once_with("192.168.1.1", port=9100)
    mock_printer.set.assert_called()
    mock_printer.text.assert_called()
    mock_printer.cut.assert_called_once()
    mock_printer.close.assert_called_once()

    text_calls = [call[0][0] for call in mock_printer.text.call_args_list]
    assert "📋 PRINTED TASKS\n" in text_calls
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
