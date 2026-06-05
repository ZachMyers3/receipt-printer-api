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

### POST /print

```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Buy milk\nCall dentist\nWalk dog"}'
```

### With QR code

```bash
curl -X POST http://localhost:8000/print \
  -H "Content-Type: application/json" \
  -d '{"text": "Scan me for details", "qr_data": "https://example.com"}'
```

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

## Development

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## License

MIT
