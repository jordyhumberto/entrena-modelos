# gateway

Punto de entrada único del cliente web. No tiene lógica de negocio: reenvía cada petición al servicio dueño.

| Ruta pública | Servicio | Variable |
|---|---|---|
| `/datasets/...` | datasets-service | `DATASETS_URL` (def. `http://localhost:8001`) |
| `/jobs/...` | training-service | `TRAINING_URL` (def. `http://localhost:8002`) |
| `/models/...` | inference-service | `INFERENCE_URL` (def. `http://localhost:8003`) |

Otras variables: `CLIENT_ORIGINS` (CORS, def. `http://localhost:5173`), `UPSTREAM_TIMEOUT` (segundos, def. 30).

Endpoints propios: `GET /health` y `GET /health/services` (503 si algún servicio no responde).
Si un servicio está caído responde 502; si tarda demasiado, 504.

## Uso local (Python 3.12)

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # en Linux/Mac: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --port 8000 --reload
.venv/Scripts/python -m pytest
```
