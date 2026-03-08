# Ollama

Ollama is a local inference runtime that runs large language models and embedding models on your machine. `py-dockerdb` manages the Ollama container lifecycle and optionally pulls a model on startup.

## Install

```bash
pip install py-dockerdb[ollama]
```

This installs `py-dockerdb` together with `tqdm`.

## Minimal example

```python
from docker_db import OllamaConfig, OllamaDB

config = OllamaConfig(
    model="llama3.2",
    pull_model_on_create=True,   # pull the model when start_db() runs
)

db = OllamaDB(config)
db.start_db()

# Use the REST API directly
import requests
response = requests.post(
    f"{db.connection_string()}/api/generate",
    json={"model": "llama3.2", "prompt": "Hello", "stream": False},
)
print(response.json()["response"])

db.stop_db()
```

Pull and list models after startup:

```python
with OllamaDB(config) as db:
    db.pull_model("nomic-embed-text")
    models = db.list_models()
    print([m["name"] for m in models])
```

## Connection details

| Item | Value |
|---|---|
| Protocol | HTTP REST |
| Default port | `11434` |
| Connection string | `http://127.0.0.1:11434` |
| Python client | `requests.Session` |

```python
url = db.connection_string()   # "http://127.0.0.1:11434"
```

## Config reference

| Field | Type | Default | Description |
|---|---|---|---|
| `model` | `str \| None` | `None` | Model name to pull (e.g. `"llama3.2"`) |
| `pull_model_on_create` | `bool` | `False` | Pull `model` automatically during `start_db()` |
| `port` | `int` | `11434` | Port |
| `host` | `str` | `"127.0.0.1"` | Hostname |
| `project_name` | `str` | `"docker_db"` | Container name prefix |
| `retries` | `int` | `10` | Connection retry attempts |
| `delay` | `int` | `3` | Seconds between retries |
| `env_vars` | `dict` | `{}` | Extra environment variables |
| `image_name` | `str` | `"ollama/ollama:latest"` | Docker image |

## Additional methods

### `pull_model(model)`

Pull a model by name from the Ollama library. Blocks until the download is complete (timeout 600 s).

```python
db.pull_model("mistral")
```

### `list_models()`

Return a list of locally available models as dictionaries.

```python
models = db.list_models()
# [{"name": "llama3.2:latest", "size": 2019393189, ...}, ...]
```

## Notes

- Model downloads can be large (several gigabytes). Set `pull_model_on_create=False` if you want to control when the download happens.
- The `volume_path` is bind-mounted to `/root/.ollama`, so downloaded models persist across container restarts.
- For GPU inference, pass `OLLAMA_GPU_LAYERS` (or similar) via `env_vars`.
