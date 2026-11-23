"""Configuración del gateway, leída de variables de entorno."""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # A qué servicio va cada prefijo de ruta.
    datasets_url: str = "http://localhost:8001"
    training_url: str = "http://localhost:8002"
    inference_url: str = "http://localhost:8003"
    # Orígenes del cliente web que pueden llamar al gateway (CORS).
    client_origins: tuple[str, ...] = field(default=("http://localhost:5173",))
    # Segundos máximos de espera a un servicio.
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "Settings":
        d = cls()
        origins = os.getenv("CLIENT_ORIGINS")
        return cls(
            datasets_url=os.getenv("DATASETS_URL", d.datasets_url).rstrip("/"),
            training_url=os.getenv("TRAINING_URL", d.training_url).rstrip("/"),
            inference_url=os.getenv("INFERENCE_URL", d.inference_url).rstrip("/"),
            client_origins=tuple(o.strip() for o in origins.split(",") if o.strip())
            if origins
            else d.client_origins,
            timeout=float(os.getenv("UPSTREAM_TIMEOUT", d.timeout)),
        )

    @property
    def routes(self) -> dict[str, str]:
        """Prefijo público -> URL base del servicio dueño."""
        return {
            "datasets": self.datasets_url,
            "jobs": self.training_url,
            "models": self.inference_url,
        }
