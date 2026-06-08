# Receipt Printer API

A Docker-based FastAPI service that accepts arbitrary text and sends it to a network-connected thermal receipt printer via TCP port 9100 using ESC/POS commands.

## Hardware

- Any ESC/POS-compatible thermal receipt printer with Ethernet (TCP/IP)
- Recommended: Xprinter XP-Q200 (USB+LAN model) ~$50
- 80mm thermal paper (32 chars wide)
- BPA-free paper strongly recommended

## Quick Start

```bash
cp .env.example .env   # Edit with your printer IP
docker compose up --build
```

## API

### POST /print (simple text)

```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy milk\nCall dentist\nWalk dog"}'
```

### With QR code (simple)

```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Scan me for details", "qr_data": "https://example.com"}'
```

### Structured lines (full control)
Use the `lines` array for fine-grained styling, barcodes, cuts, and images.

```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{
    "lines": [
      { "type": "text", "text": "Store", "align": "center", "bold": true },
      { "type": "feed", "count": 1 },
      { "type": "qr", "data": "https://example.com", "size": 6 },
      { "type": "barcode", "code": "1234567890", "bc": "CODE128" },
      { "type": "cut" }
    ]
  }'
```

#### Image line
Print logos or graphics. Accepts a URL or base64 data URL. Auto‑scales to printer width (default 384 px).

```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{
    "lines": [
      { 
        "type": "image",
        "data": "https://example.com/logo.png",
        "width": 300,
        "center": true,
        "dither": true
      },
      { "type": "text", "text": "Thank you!" }
    ]
  }'
```

Image object fields:
- `data` (string, required): URL (`http(s)://…`) or base64 data URL (`data:image/...;base64,…`)
- `width` (int, optional): max width in pixels (default 384)
- `height` (int, optional): max height in pixels (preserves aspect if only one bound is given)
- `center` (bool, optional): center the image (default false)
- `dither` (bool, optional): Floyd‑Steinberg dithering for better quality on 1‑bit printers
- `keep_aspect` (bool, optional): preserve aspect ratio when resizing (default true)

### Preview (no printing)

```bash
curl -X POST http://localhost:8000/preview \
  -H "Content-Type: application/json" \
  -d '{"lines": [{ "type": "image", "width": 200, "height": 100 }]}'
```
Returns `{ "preview": "[IMAGE: 200x100]" }` for images.

### GET /health

```bash
curl http://localhost:8000/health
# {"status": "ok"}
```

## Receipt Layout

```
   📋 PRINTED TASKS
   ────────────────────────────────
   Buy milk
   Call dentist
   Walk dog

   [QR code, optional]
   [paper cut]
```

## Home Assistant Integration

```yaml
rest_command:
  print_tasks:
    url: "http://PRINTER_API_IP:8000/print"
    method: POST
    content_type: "application/json"
    payload: '{"text": "{{ text }}"}'

automation:
  - alias: "Print morning tasks"
    trigger:
      platform: time
      at: "07:00:00"
    action:
      service: rest_command.print_tasks
      data:
        text: "Morning Routine:\n- Take meds\n- Feed animals\n- Start coffee"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRINTER_HOST` | `printer` | Printer IP or hostname |
| `PRINTER_PORT` | `9100` | TCP port (standard ESC/POS) |

## Notes

- **QR codes:** Large sizes or high error correction may cause some printers to reset. Recommended: `size` 1–2, error correction `L`. The service retries automatically on connection resets (default 10 attempts).
- **Images:** Keep width ≤ 384 px. Large images are automatically resized; if the printer runs out of memory, further reduce dimensions.
- **Retries:** `max_retries` controls connection retry attempts (default 10). Invalid barcode data returns `400` immediately; no retries.

## Development

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## License

MIT
