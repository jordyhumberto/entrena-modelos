import httpx
import pytest

from app.config import Settings
from app.main import create_app

SETTINGS = Settings(
    datasets_url="http://datasets",
    training_url="http://training",
    inference_url="http://inference",
)


def make_client(handler):
    """Gateway cuyos servicios son `handler` (función petición -> respuesta)."""
    app = create_app(SETTINGS, transport=httpx.MockTransport(handler))
    return app


async def call(app, method, url, **kw):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://gw") as c:
            return await c.request(method, url, **kw)


async def test_health():
    r = await call(make_client(lambda req: httpx.Response(200)), "GET", "/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@pytest.mark.parametrize("path,expected", [
    ("/datasets", "http://datasets/datasets"),
    ("/datasets/5", "http://datasets/datasets/5"),
    ("/jobs/7", "http://training/jobs/7"),
    ("/models/3/predict", "http://inference/models/3/predict"),
])
async def test_enruta_al_servicio_correcto(path, expected):
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json={"ok": True})

    r = await call(make_client(handler), "GET", path)
    assert r.status_code == 200 and seen["url"] == expected


async def test_reenvia_query_cuerpo_y_metodo():
    seen = {}

    def handler(req):
        seen.update(method=req.method, query=req.url.query.decode(), body=req.content)
        return httpx.Response(201, json={"id": 1})

    r = await call(make_client(handler), "POST", "/jobs?device=gpu", json={"a": 1})
    assert r.status_code == 201 and r.json() == {"id": 1}
    assert seen["method"] == "POST" and seen["query"] == "device=gpu"
    assert b'"a"' in seen["body"]


async def test_propaga_errores_del_servicio():
    r = await call(make_client(lambda req: httpx.Response(404, json={"detail": "no"})),
                   "GET", "/datasets/99")
    assert r.status_code == 404 and r.json() == {"detail": "no"}


async def test_ruta_desconocida_da_404():
    r = await call(make_client(lambda req: httpx.Response(200)), "GET", "/otra-cosa")
    assert r.status_code == 404


async def test_servicio_caido_da_502():
    def handler(req):
        raise httpx.ConnectError("sin conexión")

    r = await call(make_client(handler), "GET", "/datasets")
    assert r.status_code == 502


async def test_timeout_da_504():
    def handler(req):
        raise httpx.ReadTimeout("lento")

    r = await call(make_client(handler), "GET", "/jobs")
    assert r.status_code == 504


async def test_health_services_503_si_alguno_cae():
    def handler(req):
        if req.url.host == "training":
            raise httpx.ConnectError("caído")
        return httpx.Response(200, json={"status": "ok"})

    r = await call(make_client(handler), "GET", "/health/services")
    assert r.status_code == 503
    assert r.json() == {"datasets": "ok", "jobs": "caído", "models": "ok"}


async def test_cors_permite_al_cliente_web():
    r = await call(make_client(lambda req: httpx.Response(200)), "GET", "/health",
                   headers={"Origin": "http://localhost:5173"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_cors_rechaza_otros_origenes():
    r = await call(make_client(lambda req: httpx.Response(200)), "GET", "/health",
                   headers={"Origin": "http://malo.example"})
    assert "access-control-allow-origin" not in r.headers
