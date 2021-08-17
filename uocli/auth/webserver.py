from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

AUTHORIZATION_CODE = None


class TerminateHTTPServer(Exception):
    """
    Custom exception class that can stop the event loop
    so that we can gracefully terminate the http server
    """

    # I've spent a good hour trying to figure out why I'm not
    # able to handle this exception in run method.
    # For now, I'll raise KeyboardInterrupt but need to investigate
    # this further
    def __init__(self):
        raise KeyboardInterrupt


class WebServer(BaseHTTPRequestHandler):

    def _set_response(self, code):
        self.send_response(code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        global AUTHORIZATION_CODE
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        AUTHORIZATION_CODE = query_params.get("code", None)
        self._set_response(code=200)
        if AUTHORIZATION_CODE:
            self.wfile.write(f"Authentication Successful. You can close this tab now".encode('utf-8'))
            raise TerminateHTTPServer

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        self.send_error(405)


def get_authorization_code(server_class=HTTPServer, handler_class=WebServer, port=8239):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    return AUTHORIZATION_CODE[0]
