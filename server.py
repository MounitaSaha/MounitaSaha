from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def start_local_server(directory: Path, port: int = 0):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    return server, server.server_address[1]
