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

## API Reference

The API allows for two ways of printing: **Simple Text** (for quick messages) and **Structured Lines** (for full design control).

### 1. Simple Text Printing
Used for quick updates or simple lists.

**Endpoint:** `POST /print`

**Example Request:**
```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy milk\nCall dentist\nWalk dog"}'
```

**Parameters:**
- `text` (string): The text to print. Newlines (`\n`) are preserved.
- `qr_data` (string, optional): If provided, a QR code containing this data will be printed at the end of the text.
- `max_retries` (int, optional): Number of connection attempts (default: 10).

---

### 2. Structured Lines Printing
Used for professional layouts, branding, and precise control. You pass an array of "line objects," where each object defines a specific printing action.

**Endpoint:** `POST /print`

**Comprehensive Example:**
```json
{
  "max_retries": 10,
  "lines": [
    {
      "type": "image",
      "data": "https://example.com/logo.png",
      "width": 300,
      "center": true,
      "dither": true
    },
    {
      "type": "text",
      "text": "OFFICIAL RECEIPT",
      "align": "center",
      "bold": true,
      "double_height": true
    },
    {
      "type": "text",
      "text": "--------------------------------",
      "align": "center"
    },
    {
      "type": "text",
      "text": "Item: Coffee Bean Roast - $15.00",
      "align": "left",
      "bold": false
    },
    {
      "type": "text",
      "text": "TOTAL: $15.00",
      "align": "right",
      "bold": true,
      "underline": 1
    },
    {
      "type": "feed",
      "count": 2
    },
    {
      "type": "qr",
      "data": "https://example.com/order/123",
      "size": 6,
      "center": true,
      "ec": "M"
    },
    {
      "type": "barcode",
      "code": "1234567890",
      "bc": "CODE128",
      "height": 80,
      "pos": "below",
      "font": "a"
    },
    {
      "type": "pulse",
      "pin": 2
    },
    {
      "type": "cut",
      "mode": "full",
      "feed": true
    }
  ]
}
```

### Parameter Breakdown by Line Type

#### `text` (Default)
Controls standard text output.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `text` | string | `""` | The text content to print. |
| `align` | string | `"left"` | Alignment: `"left"`, `"center"`, or `"right"`. |
| `font` | string | `"a"` | Font selector (e.g., `"a"`, `"b"`). |
| `bold` | boolean | `false` | Enable bold text. |
| `underline` | int | `0` | Underline mode. |
| `double_width` | boolean | `false` | Expand character width. |
| `double_height`| boolean | `false` | Expand character height. |
| `invert` | boolean | `false` | Inverted (white text on black background). |
| `width` | int | `null` | Fixed character width. |
| `height` | int | `null` | Fixed character height. |
| `newlines` | int | `0` | Number of extra line feeds after this text. |

#### `image`
Prints graphics. Supports URLs or Base64 data URLs.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `data` | string | **Req** | URL (`https://...`) or data URL (`data:image/...;base64,...`). |
| `width` | int | `384` | Max width in pixels. |
| `height` | int | `null` | Max height in pixels. |
| `center` | boolean | `false` | Center image on the paper. |
| `dither` | boolean | `false` | Use Floyd-Steinberg dithering for better grayscale. |
| `keep_aspect` | boolean | `true` | Preserve image aspect ratio when resizing. |

#### `qr`
Prints a QR code.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `data` | string | **Req** | The content of the QR code. |
| `size` | int | `8` | Size of the QR module. |
| `center` | boolean | `false` | Center the QR code. |
| `ec` | string/int | `1` | Error Correction: `"L"` (0), `"M"` (1), `"Q"` (2), `"H"` (3). |

#### `barcode`
Prints a standard barcode.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `code` | string | **Req** | The barcode value. |
| `bc` | string | **Req** | Barcode type (e.g., `"CODE128"`, `"EAN13"`). |
| `height` | int | `100` | Height of the barcode in dots. |
| `width` | int | `2` | Width of the barcode modules. |
| `pos` | string | `"below"` | Text position: `"above"`, `"below"`, `"both"`, or `"off"`. |
| `font` | string | `"a"` | Font for the human-readable text. |

#### `feed`
Advances the paper.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `count` | int | `1` | Number of lines to feed. |

#### `cut`
Triggers the printer's paper cutter.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `mode` | string | `"full"` | Cut mode: `"full"` or `"part"`. |
| `feed` | bool/int | `3` | Feed amount before cutting. |

#### `pulse`
Opens the cash drawer or triggers a pin.
| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `pin` | int | `0` | The pin number to pulse. |

---

### Other Endpoints

#### `POST /preview`
Renders the receipt as a plain-text string without sending it to the physical printer. Great for debugging layouts.
- **Request Body:** Same as `/print`.
- **Response:** `{ "preview": "Rendered text representation..." }`

#### `GET /health`
Check if the service is running.
- **Response:** `{ "status": "ok" }`

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

## Hardware Notes

- **QR codes:** Large sizes or high error correction may cause some printers to reset. Recommended: `size` 1–2, error correction `L`.
- **Images:** Keep width ≤ 384 px. Large images are automatically resized; if the printer runs out of memory, further reduce dimensions.
- **Retries:** `max_retries` controls connection retry attempts (default 10).

## Development

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## License

MIT
