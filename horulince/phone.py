"""Assistente de conexão e teste, sem carregar modelos para testar a câmera."""
import time

from .sources import LatestStream, validate_phone_url


def phone_source(value=None):
    if value:
        return validate_phone_url(value)
    print("No iPhone: abra o app transmissor em modo RTSP, inicie a câmera e mantenha o app aberto.")
    print("Conecte iPhone e computador à mesma rede Wi-Fi.")
    return validate_phone_url(input("Cole a URL de transmissão exibida no iPhone: "))


def camera_test(source, seconds=10, show=False):
    import cv2
    if not 1 <= seconds <= 60:
        raise ValueError("Duração do teste deve estar entre 1 e 60 segundos")
    capture = LatestStream(validate_phone_url(source))
    count = 0
    shape = None
    started = None
    try:
        if not capture.isOpened():
            raise RuntimeError("Sem imagem. Confira URL, permissão de rede local, Wi-Fi e app em primeiro plano.")
        started = time.monotonic()
        while time.monotonic() - started < seconds:
            ok, image = capture.read()
            if not ok:
                raise RuntimeError(capture.failure or "A transmissão foi interrompida")
            count += 1
            shape = image.shape[:2]
            if show:
                cv2.imshow("Horulince - teste do iPhone (Q para sair)", image)
                if cv2.waitKey(1) & 0xff == ord("q"):
                    break
        elapsed = time.monotonic() - started
        return {"resultado": "conectado", "quadros_recebidos": count, "largura": shape[1], "altura": shape[0], "quadros_recebidos_por_segundo": round(count / elapsed, 2) if elapsed else None, "reconexoes": capture.reconnections, "nota": "Teste de recepção; não mede desempenho de detecção ou OCR."}
    finally:
        capture.release()
        if show:
            cv2.destroyAllWindows()
