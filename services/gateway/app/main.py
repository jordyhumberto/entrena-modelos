"""Gateway: punto de entrada único. No tiene lógica de negocio, solo reenvía."""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings

# Cabeceras que no se deben copiar tal cual entre petición y respuesta.
_SKIP_REQUEST = {"host", "connection", "keep-alive", "transfer-encoding"}
_SKIP_RESPONSE = {"content-length", "content-encoding", "transfer-encoding", "connection"}
_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]


def create_app(
    settings: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Crea la app. `transport` permite simular los servicios en las pruebas."""
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(timeout=settings.timeout, transport=transport) as client:
            app.state.http = client
            yield

    app = FastAPI(title="entrena-modelos gateway", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.client_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/services")
    async def health_services(response: Response) -> dict:
        """Pregunta a cada servicio si está vivo."""
        result: dict[str, str] = {}
        for name, base in settings.routes.items():
            try:
                r = await app.state.http.get(f"{base}/health")
                result[name] = "ok" if r.is_success else f"error {r.status_code}"
            except httpx.HTTPError:
                result[name] = "caído"
        if any(v != "ok" for v in result.values()):
            response.status_code = 503
        return result

    @app.api_route("/{prefix}", methods=_METHODS)
    @app.api_route("/{prefix}/{path:path}", methods=_METHODS)
    async def proxy(request: Request, prefix: str, path: str = "") -> Response:
        base = settings.routes.get(prefix)
        if base is None:
            return Response(status_code=404, content=b'{"detail":"Ruta no encontrada"}',
                            media_type="application/json")

        url = f"{base}/{prefix}" + (f"/{path}" if path else "")
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _SKIP_REQUEST}
        try:
            upstream = await app.state.http.send(
                app.state.http.build_request(
                    request.method,
                    url,
                    params=request.query_params,
                    headers=headers,
                    content=request.stream(),  # sin cargar el archivo entero en memoria
                )
            )
        except httpx.TimeoutException:
            return Response(status_code=504, content=b'{"detail":"El servicio tard\xc3\xb3 demasiado"}',
                            media_type="application/json")
        except httpx.HTTPError:
            return Response(status_code=502, content=b'{"detail":"Servicio no disponible"}',
                            media_type="application/json")

        out = {k: v for k, v in upstream.headers.items() if k.lower() not in _SKIP_RESPONSE}
        return Response(content=upstream.content, status_code=upstream.status_code, headers=out)

    return app


app = create_app()
