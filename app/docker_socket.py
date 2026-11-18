"""
docker_socket.py - Interfaccia minimale al Docker socket Unix senza binari esterni.
Uso: python3 docker_socket.py <azione> <nome_container>
Azioni: start | restart | is_running | exit_code
"""
import socket
import json
import sys


DOCKER_SOCK = "/var/run/docker.sock"


def docker_request(method: str, path: str) -> dict:
    """Esegue una chiamata HTTP al Docker daemon via Unix socket."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(DOCKER_SOCK)
    try:
        request = f"{method} {path} HTTP/1.0\r\nHost: localhost\r\n\r\n"
        sock.sendall(request.encode())

        # Leggo l'intera risposta
        response = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
    finally:
        sock.close()

    # Separo header da body
    _, _, body = response.partition(b"\r\n\r\n")
    body_str = body.decode("utf-8", errors="replace").strip()

    if not body_str:
        return {}
    try:
        return json.loads(body_str)
    except json.JSONDecodeError:
        return {"raw": body_str}


def main():
    if len(sys.argv) < 3:
        print("Uso: python3 docker_socket.py <azione> <container>", file=sys.stderr)
        sys.exit(2)

    action, container = sys.argv[1], sys.argv[2]

    if action == "start":
        docker_request("POST", f"/containers/{container}/start")

    elif action == "restart":
        docker_request("POST", f"/containers/{container}/restart")

    elif action == "is_running":
        data = docker_request("GET", f"/containers/{container}/json")
        running = data.get("State", {}).get("Running", False)
        print("True" if running else "False")

    elif action == "exit_code":
        data = docker_request("GET", f"/containers/{container}/json")
        print(data.get("State", {}).get("ExitCode", -1))

    else:
        print(f"Azione sconosciuta: {action}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
