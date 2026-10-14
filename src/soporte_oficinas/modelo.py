"""Contrato del modelo de lenguaje y modelo guionizado para las pruebas."""

from typing import Protocol


class Modelo(Protocol):
    """Cualquier modelo que, dado un prompt de sistema y mensajes, devuelve texto."""

    def generar(self, sistema: str, mensajes: list[dict]) -> str: ...


class ScriptedModel:
    """Devuelve respuestas fijadas de antemano, en orden. Solo para pruebas."""

    def __init__(self, respuestas: list[str]) -> None:
        self._respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def generar(self, sistema: str, mensajes: list[dict]) -> str:
        """Registra la llamada y devuelve la siguiente respuesta del guion."""
        self.llamadas.append({"sistema": sistema, "mensajes": list(mensajes)})
        if not self._respuestas:
            raise RuntimeError("ScriptedModel: no quedan respuestas en el guion")
        return self._respuestas.pop(0)
