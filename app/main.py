import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.escpos_formatter import (
    _legacy_to_lines,
    format_and_print,
    format_lines,
    lines_to_text,
)

app = FastAPI()

PRINTER_HOST = os.getenv("PRINTER_HOST", "printer")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))


class LineObject(BaseModel):
    type: str = "text"
    text: str | None = None
    align: str | None = None
    font: str | None = None
    bold: bool | None = None
    underline: int | None = None
    double_width: bool | None = None
    double_height: bool | None = None
    invert: bool | None = None
    width: int | None = None
    height: int | None = None
    smooth: bool | None = None
    newlines: int | None = None
    count: int | None = None
    mode: str | None = None
    feed: int | bool | None = None
    data: str | None = None
    size: int | None = None
    center: bool | None = None
    ec: str | None = None
    code: str | None = None
    bc: str | None = None
    height_bc: int | None = None
    width_bc: int | None = None
    pos: str | None = None
    font_bc: str | None = None
    pin: int | None = None


class PrintRequest(BaseModel):
    text: str | None = None
    qr_data: str | None = None
    lines: list[LineObject] | None = None
    max_retries: int | None = None


def _line_object_to_dict(line: LineObject) -> dict:
    data = line.model_dump(exclude_none=True)
    if data.get("type") == "barcode":
        if "height_bc" in data:
            data["height"] = data.pop("height_bc")
        if "width_bc" in data:
            data["width"] = data.pop("width_bc")
        if "font_bc" in data:
            data["font"] = data.pop("font_bc")
    return data


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/print")
def print_receipt(request: PrintRequest) -> dict[str, str | int]:
    if request.lines:
        raw_lines = [_line_object_to_dict(line) for line in request.lines]
        max_retries = request.max_retries if request.max_retries is not None else 10
        try:
            count = format_lines(raw_lines, host=PRINTER_HOST, port=PRINTER_PORT, max_retries=max_retries)
        except RuntimeError as exc:
            if "Invalid barcode:" in str(exc):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"status": "sent", "lines": count}

    if request.text:
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="text must not be empty")
        max_retries = request.max_retries if request.max_retries is not None else 10
        try:
            count = format_and_print(
                text=text,
                host=PRINTER_HOST,
                port=PRINTER_PORT,
                qr_data=request.qr_data,
                max_retries=max_retries,
            )
        except RuntimeError as exc:
            if "Invalid barcode:" in str(exc):
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        return {"status": "sent", "lines": count}

    raise HTTPException(status_code=400, detail="text or lines required")


@app.post("/preview")
def preview_receipt(request: PrintRequest) -> dict[str, str]:
    """Render the receipt as text without printing."""
    if request.lines:
        raw_lines = [_line_object_to_dict(line) for line in request.lines]
        text = lines_to_text(raw_lines)
    elif request.text:
        text = request.text.strip()
        if not text:
            raise HTTPException(status_code=400, detail="text must not be empty")
        raw_lines = _legacy_to_lines(text, request.qr_data)
        text = lines_to_text(raw_lines)
    else:
        raise HTTPException(status_code=400, detail="text or lines required")

    return {"preview": text}
