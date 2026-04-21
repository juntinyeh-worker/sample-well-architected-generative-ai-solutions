"""AgentCore wrapper: HTTP 8080 ↔ Kiro CLI ACP (JSON-RPC over stdio, newline-delimited)."""
import subprocess, json, os, threading, queue, logging
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KiroACP:
    def __init__(self):
        self.proc = None
        self.pending = {}
        self.chunks = {}  # rid -> list of text chunks
        self.next_id = 0
        self.lock = threading.Lock()
        self.session_id = None

    def start(self):
        self.proc = subprocess.Popen(
            ["kiro-cli", "acp", "--trust-all-tools"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        logger.info(f"ACP pid={self.proc.pid}")
        self._call("initialize", {"protocolVersion": 1, "clientCapabilities": {}, "clientInfo": {"name": "agentcore", "version": "0.1"}})
        resp = self._call("session/new", {"cwd": "/tmp", "mcpServers": []})
        self.session_id = resp.get("result", {}).get("sessionId", "")
        logger.info(f"Session: {self.session_id}")

    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Auto-approve permissions
            if msg.get("method") == "session/request_permission":
                rid = msg.get("id")
                if rid is not None:
                    opts = msg.get("params", {}).get("options", [])
                    oid = next((o.get("optionId") for o in opts if o.get("kind") == "allow_always"), "allow_always")
                    self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "result": {"outcome": {"outcome": "selected", "optionId": oid}}}) + "\n")
                    self.proc.stdin.flush()
                continue

            # Collect streamed text chunks
            params = msg.get("params", {})
            update = params.get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                text = update.get("content", {}).get("text", "")
                if text:
                    # Add to all active prompt chunk collectors
                    for rid, chunks in self.chunks.items():
                        chunks.append(text)

            # Response with id -> resolve pending
            mid = msg.get("id")
            if mid is not None and mid in self.pending:
                self.pending[mid].put(msg)

    def _call(self, method, params, timeout=120):
        with self.lock:
            self.next_id += 1
            rid = self.next_id
        q = queue.Queue()
        self.pending[rid] = q
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method, "params": params}) + "\n")
        self.proc.stdin.flush()
        try:
            return q.get(timeout=timeout)
        except queue.Empty:
            return {"error": {"message": "timeout"}}
        finally:
            self.pending.pop(rid, None)

    def prompt(self, text):
        if not self.session_id:
            return "No session"
        with self.lock:
            self.next_id += 1
            rid = self.next_id
        q = queue.Queue()
        self.pending[rid] = q
        self.chunks[rid] = []
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rid, "method": "session/prompt", "params": {
            "sessionId": self.session_id,
            "prompt": [{"type": "text", "text": text}],
        }}) + "\n")
        self.proc.stdin.flush()
        try:
            q.get(timeout=120)  # Wait for final response
        except queue.Empty:
            pass
        finally:
            self.pending.pop(rid, None)
        text_chunks = self.chunks.pop(rid, [])
        return "".join(text_chunks) or "(no response)"

    def is_alive(self):
        return self.proc and self.proc.poll() is None


acp = KiroACP()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)))) if int(self.headers.get("Content-Length", 0)) else {}
        if not acp.is_alive():
            acp.start()
        response = acp.prompt(body.get("input", "hello"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"response": response}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok" if acp.is_alive() else "starting"}).encode())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    acp.start()
    logger.info(f"Wrapper on :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
