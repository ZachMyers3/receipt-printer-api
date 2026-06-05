import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.escpos_formatter import format_and_print

app = FastAPI()

PRINTER_HOST = os.getenv("PRINTER_HOST", "printer")
PRINTER_PORT = int(os.getenv("PRINTER_PORT", "9100"))


class PrintRequest(BaseModel):
    text: str
    qr_data: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/print")
def print_receipt(request: PrintRequest) -> dict[str, str | int]:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")

    try:
        lines = format_and_print(
            text=text,
            host=PRINTER_HOST,
            port=PRINTER_PORT,
            qr_data=request.qr_data,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"status": "sent", "lines": lines}
