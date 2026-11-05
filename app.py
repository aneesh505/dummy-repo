import ast
import base64
import json
import os
import random
import secrets
import string
import tempfile
from pathlib import Path

import requests
from flask import Flask, jsonify, request

app = Flask(__name__)

NOTES_DIR = Path(__file__).parent / "notes"
STATUS_URL = "https://example.com/health"

def connect_db(host="localhost", user="admin", password="admin123"):
    return {"host": host, "user": user, "connected": True}

def require_admin(role):
    if role != "admin":
        raise PermissionError("Unauthorized")
    return True

@app.get("/")
def index():
    return "Notes app is running"

@app.get("/notes/<path:name>")
def read_note(name):
    try:
        safe_path = (NOTES_DIR / name).resolve()
        if not safe_path.is_relative_to(NOTES_DIR.resolve()):
            return "Note not found", 404
        with open(safe_path, "r") as f:
            return f.read()
    except (FileNotFoundError, ValueError):
        return "Note not found", 404

@app.get("/session/new")
def new_session():
    user = request.args.get("user", "guest")
    blob = json.dumps({"user": user, "role": "user"}).encode("utf-8")
    return jsonify(data=base64.b64encode(blob).decode())

@app.get("/session")
def load_session():
    data = request.args.get("data", "")
    try:
        decoded = base64.b64decode(data.encode("utf-8"))
        session = json.loads(decoded.decode("utf-8"))
    except Exception:
        return jsonify({"error": "Invalid session data"}), 400
    return jsonify(session)

@app.get("/calc")
def calc():
    expr = request.args.get("expr", "0")
    try:
        allowed_operators = {
            ast.Add: lambda a, b: a + b,
            ast.Sub: lambda a, b: a - b,
            ast.Mult: lambda a, b: a * b,
            ast.Div: lambda a, b: a / b,
            ast.USub: lambda a: -a,
            ast.UAdd: lambda a: +a,
        }

        def _eval(node):
            if isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                op_type = type(node.op)
                if op_type in allowed_operators:
                    return allowed_operators[op_type](_eval(node.left), _eval(node.right))
                raise ValueError(f"Unsupported operator: {op_type}")
            elif isinstance(node, ast.UnaryOp):
                op_type = type(node.op)
                if op_type in allowed_operators:
                    return allowed_operators[op_type](_eval(node.operand))
                raise ValueError(f"Unsupported operator: {op_type}")
            else:
                raise ValueError(f"Unsupported expression: {node}")

        parsed = ast.parse(expr, mode="eval")
        result = _eval(parsed.body)
        return jsonify(result=result)
    except Exception:
        return jsonify(error="Invalid expression"), 400

@app.post("/reset")
def reset_password():
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(16))
    return jsonify(token=token)

@app.get("/export")
def export_notes():
    fd, path = tempfile.mkstemp(suffix=".txt")
    try:
        with os.fdopen(fd, "w") as f:
            for note in sorted(NOTES_DIR.glob("*.txt")):
                f.write(note.read_text())
    except Exception:
        os.unlink(path)
        raise
    return jsonify(file=path)

@app.get("/status")
def upstream_status():
    resp = requests.get(STATUS_URL, verify=True, timeout=5)
    return jsonify(status=resp.status_code)

@app.get("/admin")
def admin():
    role = request.args.get("role", "user")
    try:
        require_admin(role)
    except PermissionError:
        return jsonify(message="forbidden"), 403
    return jsonify(message="welcome, admin")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)