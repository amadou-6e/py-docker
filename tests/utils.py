import os
import shutil
import platform
import docker
import time
from pathlib import Path


def nuke_dir(path: Path):
    if not path.exists():
        return

    # Best-effort chmod pass for local cleanup.
    for root, dirs, files in os.walk(path, topdown=False):
        for name in files:
            try:
                os.chmod(os.path.join(root, name), 0o777)
            except Exception:
                pass
        for name in dirs:
            try:
                os.chmod(os.path.join(root, name), 0o777)
            except Exception:
                pass

    shutil.rmtree(path, ignore_errors=True)
    if not path.exists():
        return

    # CI/Linux fallback: remove root-owned bind-mount artifacts via Docker as root.
    if platform.system() != "Windows":
        try:
            client = docker.from_env()
            client.containers.run(
                "alpine:3.20",
                command='sh -lc "rm -rf /target/* /target/.[!.]* /target/..?* || true"',
                remove=True,
                volumes={str(path): {"bind": "/target", "mode": "rw"}},
            )
        except Exception:
            pass

    shutil.rmtree(path, ignore_errors=True)
    if path.exists():
        cmd = f'rmdir /s /q "{path}"' if platform.system() == "Windows" else f'rm -rf "{path}"'
        os.system(cmd)


def clear_port(port: int, container_prefix: str, timeout: int = 60):
    client = docker.from_env()
    start = time.time()

    while True:
        if time.time() - start > timeout:
            raise TimeoutError(f"Timed out while clearing port {port}")

        port_still_in_use = False
        containers = client.containers.list()  # running only

        for container in containers:
            container.reload()
            ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            if f"{port}/tcp" in ports and ports[f"{port}/tcp"] is not None:
                if container.name.startswith(container_prefix):
                    container.stop(timeout=5)
                else:
                    port_still_in_use = True

        if not port_still_in_use:
            break

        time.sleep(0.5)

    time.sleep(1)
