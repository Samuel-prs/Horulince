"""Teste opcional com MJPEG real em loopback; não precisa de iPhone."""
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@unittest.skipUnless(os.environ.get("HORULINCE_TEST_STREAM") == "1", "Ative HORULINCE_TEST_STREAM=1 para testar a rede local e OpenCV")
class StreamIntegrationTests(unittest.TestCase):
    def test_real_opencv_receives_local_mjpeg(self):
        import cv2
        import numpy as np
        from horulince.sources import LatestStream

        image = np.full((240, 320, 3), (20, 80, 200), dtype=np.uint8)
        encoded, jpeg = cv2.imencode(".jpg", image)
        self.assertTrue(encoded)
        content = jpeg.tobytes()
        stop = threading.Event()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    while not stop.is_set():
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(content)).encode("ascii") + b"\r\n\r\n" + content + b"\r\n")
                        self.wfile.flush()
                        stop.wait(.03)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        capture = None
        try:
            capture = LatestStream(f"http://127.0.0.1:{server.server_port}/video")
            self.assertTrue(capture.isOpened())
            ok, received = capture.read()
            self.assertTrue(ok)
            self.assertEqual(received.shape, (240, 320, 3))
        finally:
            if capture is not None:
                capture.release()
            stop.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
        self.assertFalse(capture.thread.is_alive())
