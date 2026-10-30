"""Fontes locais e câmera IP com fila de um quadro e reconexão limitada."""
from dataclasses import dataclass
import math
import threading
import time
from urllib.parse import urlsplit


def is_network(source):
    return isinstance(source, str) and urlsplit(source).scheme.lower() in {"rtsp", "rtsps", "http", "https"}


def validate_phone_url(value):
    value = value.strip()
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        raise ValueError("Endereço inválido. Copie a URL de transmissão exibida no app.") from None
    if parsed.scheme.lower() not in {"rtsp", "rtsps", "http", "https"} or not parsed.hostname or (port is not None and port < 1):
        raise ValueError("Use a URL RTSP ou HTTP/MJPEG completa exibida no app do iPhone.")
    return value


def open_network(source):
    import cv2
    # Os timeouts são definidos na abertura; set() posterior não é suportado.
    return cv2.VideoCapture(source, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000])


@dataclass(frozen=True)
class Packet:
    sequence: int
    generation: int
    captured: float
    image: object


class LatestStream:
    """Lê a rede continuamente, descartando quadros antigos antes da inferência.

    A thread é a única dona do VideoCapture; release() sinaliza e aguarda os
    timeouts do backend. Nunca entrega o último quadro de uma conexão anterior.
    """

    def __init__(self, source, factory=None, retries=3, read_timeout=22.0, max_age=1.5, retry_delay=.5):
        self.source = source
        self.factory = factory or open_network
        self.retries = retries
        self.read_timeout = read_timeout
        self.max_age = max_age
        self.retry_delay = retry_delay
        self.condition = threading.Condition()
        self.stop = threading.Event()
        self.packet = None
        self.delivered = 0
        self.delivered_generation = 0
        self.generation = 0
        self.reconnections = 0
        self.sequence = 0
        self.failed = False
        self.failure = None
        self.initialized = threading.Event()
        self.fps = 30.0
        self.thread = threading.Thread(target=self._worker, name="horulince-camera", daemon=True)
        self.thread.start()

    def _worker(self):
        capture = None
        consecutive_failures = 0
        try:
            while not self.stop.is_set():
                if capture is None:
                    capture = self.factory(self.source)
                    if not capture.isOpened():
                        capture.release()
                        capture = None
                        consecutive_failures += 1
                    else:
                        # CAP_PROP_FPS = 5; evita importar OpenCV nos testes.
                        fps = capture.get(5)
                        self.fps = fps if math.isfinite(fps) and 0 < fps < 1000 else 30.0
                if capture is not None:
                    if self.stop.is_set():
                        break
                    ok, image = capture.read()
                    if ok:
                        consecutive_failures = 0
                        with self.condition:
                            self.sequence += 1
                            self.packet = Packet(self.sequence, self.generation, time.monotonic(), image)
                            self.initialized.set()
                            self.condition.notify_all()
                        continue
                    capture.release()
                    capture = None
                    consecutive_failures += 1
                with self.condition:
                    self.packet = None
                    self.generation += 1
                    self.condition.notify_all()
                if consecutive_failures > self.retries:
                    self.failure = "Transmissão indisponível após as tentativas de reconexão"
                    break
                self.reconnections += 1
                if self.stop.wait(self.retry_delay):
                    break
        except Exception:
            # URLs podem conter senhas: mensagem pública nunca repete a exceção.
            self.failure = "Falha ao receber vídeo da câmera de rede"
        finally:
            if capture is not None:
                capture.release()
            with self.condition:
                self.failed = True
                self.packet = None
                self.initialized.set()
                self.condition.notify_all()

    def isOpened(self):
        self.initialized.wait(self.read_timeout)
        with self.condition:
            return not self.failed and self.packet is not None

    def get(self, prop):
        return self.fps if prop == 5 else 0

    def read(self):
        deadline = time.monotonic() + self.read_timeout
        with self.condition:
            while not self.failed and not self.stop.is_set():
                packet = self.packet
                if packet is not None and packet.sequence > self.delivered and time.monotonic() - packet.captured <= self.max_age:
                    self.delivered = packet.sequence
                    self.delivered_generation = packet.generation
                    return True, packet.image.copy()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.failure = "Tempo esgotado esperando uma imagem atual da câmera"
                    return False, None
                self.condition.wait(remaining)
        return False, None

    def release(self):
        self.stop.set()
        with self.condition:
            self.condition.notify_all()
        self.thread.join(timeout=6)


def open_source(source):
    if is_network(source):
        return LatestStream(source)
    import cv2
    return cv2.VideoCapture(source)
