import json
import re
import webbrowser
import traceback
import subprocess
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import quote

from config import OUTPUT_DIR
from menu_ui import render_menu_page
from pipeline_runner import run_from_csv


def _guess_content_type(path):
    suffix = Path(path).suffix.lower()
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
    }.get(suffix, "application/octet-stream")


def _parse_multipart(body, content_type):
    boundary_match = re.search(r'boundary=([^;]+)', content_type)
    if not boundary_match:
        raise ValueError("Missing multipart boundary")

    boundary = boundary_match.group(1).strip().strip('"')
    delimiter = ("--" + boundary).encode("utf-8")
    parts = body.split(delimiter)
    fields = {}

    for raw_part in parts:
        part = raw_part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        headers_blob, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue

        headers = {}
        for header_line in headers_blob.split(b"\r\n"):
            if b":" not in header_line:
                continue
            key, value = header_line.split(b":", 1)
            headers[key.decode("utf-8", errors="ignore").strip().lower()] = value.decode("utf-8", errors="ignore").strip()

        disposition = headers.get("content-disposition", "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        field_name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match:
            fields[field_name] = {
                "filename": filename_match.group(1),
                "content": content.rstrip(b"\r\n"),
                "headers": headers,
            }
        else:
            fields[field_name] = content.decode("utf-8", errors="ignore").rstrip("\r\n")

    return fields


class LauncherServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, directory):
        super().__init__(server_address, RequestHandlerClass)
        self.directory = Path(directory)
        self.base_url = None


class LauncherRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            html = render_menu_page(self.server.base_url)
            self._send_html(html)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/start":
            self._send_json({"error": "Not found"}, status=404)
            return

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send_json({"error": "Expected multipart form data"}, status=400)
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length)
        try:
            form = _parse_multipart(body, content_type)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, status=400)
            return

        csv_field = form.get("source_csv")
        if not isinstance(csv_field, dict) or not csv_field.get("content"):
            self._send_json({"error": "CSV upload missing"}, status=400)
            return

        overrides_text = form.get("config_overrides", "{}")
        try:
            overrides = json.loads(overrides_text)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid config overrides"}, status=400)
            return

        upload_dir = OUTPUT_DIR / "launcher_uploads" / Path(self.path).stem
        upload_dir.mkdir(parents=True, exist_ok=True)
        original_name = Path(csv_field.get("filename") or "uploaded.csv").name or "uploaded.csv"
        source_path = upload_dir / original_name
        with source_path.open("wb") as handle:
            handle.write(csv_field["content"])

        try:
            result = run_from_csv(source_path, overrides=overrides)
        except Exception as exc:
            error_text = traceback.format_exc()
            print(error_text)
            self._send_json({"error": str(exc), "traceback": error_text}, status=500)
            return

        result_path = Path(result["result_path"]).resolve()
        try:
            relative_result = result_path.relative_to(self.server.directory.resolve())
            result_url = "/" + quote(relative_result.as_posix()) + f"?run={result['run_id']}"
        except ValueError:
            result_url = result_path.as_uri()
        self._send_json(
            {
                "result_url": result_url,
                "title": "Processed Sphere",
                "message": f"{result['source_row_count']} rows processed from {source_path.name}",
                "source_file": str(source_path),
                "run_id": result["run_id"],
            }
        )


def start_launcher_server(host="127.0.0.1", port=0, directory=None):
    directory = directory or Path(__file__).resolve().parent
    handler = partial(LauncherRequestHandler, directory=str(directory))
    server = LauncherServer((host, port), handler, directory=directory)
    port = server.server_address[1]
    server.base_url = f"http://{host}:{port}"
    return server


def run_launcher():
    server = start_launcher_server()
    webbrowser.open(server.base_url + "/")
    try:
        server.serve_forever()
    finally:
        server.server_close()


def launch_launcher_detached():
    script_path = Path(__file__).resolve()
    creationflags = 0
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP

    subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=str(script_path.parent),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
    )


if __name__ == "__main__":
    run_launcher()
