#!/usr/bin/env python3
"""Local static server for verification. Not product code.

Serves the repo root and stamps every response with the run id and commit.
"""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def end_headers(self):
        self.send_header("X-Verify-App", "procurement-copilot")
        self.send_header("X-Verify-Run", self.server.run_id)
        self.send_header("X-Verify-Commit", self.server.commit)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):
        line = "%s - %s\n" % (self.log_date_time_string(), fmt % args)
        self.server.access_fp.write(line)
        self.server.access_fp.flush()


def main():
    parser = argparse.ArgumentParser(description="Stamp and serve the procurement copilot repo")
    parser.add_argument("--root", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--access-log", required=True)
    args = parser.parse_args()

    access = open(args.access_log, "a", encoding="utf-8", buffering=1)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.run_id = args.run_id
    server.commit = args.commit
    server.access_fp = access
    # Handler reads the directory from the server via the request's directory kw.
    # SimpleHTTPRequestHandler in 3.7+ takes directory on the constructor, so
    # bind it here by wrapping the handler class.
    server.RequestHandlerClass = lambda *a, directory=args.root, **kw: Handler(
        *a, directory=directory, **kw
    )
    print("SERVING http://127.0.0.1:%s/ run=%s commit=%s" % (args.port, args.run_id, args.commit), flush=True)
    try:
        server.serve_forever()
    finally:
        access.close()


if __name__ == "__main__":
    main()
