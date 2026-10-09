"""Read-only Nook/Ollama identity check. No inference, writes, starts or downloads."""
import argparse
import http.client
import json
import sys

MODEL = "qwen2.5:0.5b-instruct-q4_K_M"
DIGEST = "a8b0c51577010a279d933d14c2a8ab4b268079d44c5c8830c0a93900f1827c67"
RUNTIME = "0.30.6"
MAX_BYTES = 64 * 1024


def get_json(port, path):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path, headers={"Accept-Encoding": "identity"})
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(f"127.0.0.1:{port}{path} returned HTTP {response.status}")
        raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise RuntimeError("Readiness response exceeded 64 KiB")
        return json.loads(raw)
    finally:
        connection.close()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-port", type=int, default=8765)
    parser.add_argument("--model-port", type=int, default=11435)
    args = parser.parse_args()
    require(all(1024 <= p <= 65535 for p in (args.app_port, args.model_port)), "Invalid port")
    require(args.model_port not in (11434, args.app_port), "Use a dedicated model port")
    version = get_json(args.model_port, "/api/version")
    require(version.get("version") == RUNTIME, "Runtime differs from accepted Ollama 0.30.6")
    tags = get_json(args.model_port, "/api/tags")
    matches = [m for m in tags.get("models", []) if m.get("name") == MODEL]
    require(len(matches) == 1 and matches[0].get("digest") == DIGEST,
            "Exact model name/digest missing. Do not substitute another tag or bypass the pin.")
    status = get_json(args.app_port, "/api/status")
    chat = status.get("chat", {})
    require(status.get("status") == "ready", "Nook API is not ready")
    require(chat.get("enabled") is True, "Nook general chat is disabled")
    require(chat.get("model") == MODEL and chat.get("expected_digest") == DIGEST,
            "Nook source does not match the accepted model configuration")
    require(chat.get("endpoint") == f"http://127.0.0.1:{args.model_port}",
            "Nook is configured for a different runtime port")
    print(json.dumps({"configuration_and_model_identity_passed": True,
                      "inference_tested": False,
                      "runtime": RUNTIME, "model": MODEL, "digest": DIGEST,
                      "next_step": "Run the three-prompt smoke in the guide."}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, AttributeError, TypeError,
            http.client.HTTPException) as exc:
        print(f"Readiness check failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
