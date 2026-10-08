"""Ephemeral synthetic Safari page served only on CI loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import uuid


class SafariFixture:
    def __enter__(self):
        endpoint = "/atode-qa-" + uuid.uuid4().hex
        body = ("<!doctype html><html lang='ja'><meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>あとでやる箱の共有テスト</title>"
                "<h1>ATODE-SAFARI-FIXTURE</h1><p>架空の共有テストです。</p></html>").encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != endpoint:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'")
                self.send_header("X-Robots-Tag", "noindex, nofollow")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        try:
            self.thread.start()
        except BaseException:
            self.server.server_close()
            raise
        self.url = "http://127.0.0.1:" + str(self.server.server_port) + endpoint
        return self

    def __exit__(self, *_):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
