from types import SimpleNamespace

from docker_db.docker.manager import ContainerManager


class _FakeContainer:
    def __init__(self, name: str, ports: dict | None = None, status: str = "running"):
        self.name = name
        self.status = status
        self.attrs = {
            "State": {"Running": status == "running", "Status": status},
            "NetworkSettings": {"Ports": ports or {}},
        }

    def reload(self):
        return self


class _FlowManager(ContainerManager):
    def __init__(self):
        self.config = SimpleNamespace(
            database="db",
            volume_path=None,
            container_name="test-container",
            port=5432,
            retries=1,
            delay=0,
            init_script=None,
        )
        self.client = None
        self.initial_container = _FakeContainer("initial")
        self.recreated_container = _FakeContainer("recreated")
        self.created_db_container = None
        self.calls = []

    @property
    def connection(self):
        return None

    def _build_image(self, force: bool = False):
        self.calls.append("build_image")

    def _create_container(self, force: bool = False, exists_ok: bool = True):
        self.calls.append("create_container")
        return self.initial_container

    def _start_container(self, container=None, force: bool = False, running_ok: bool = True, retry: bool = True):
        self.calls.append("start_container")
        return self.recreated_container

    def _create_db(self, db_name: str, container=None):
        self.calls.append("create_db")
        self.created_db_container = container
        return container

    def test_connection(self):
        self.calls.append("test_connection")

    def _get_environment_vars(self):
        return {}

    def _get_volume_mounts(self):
        return []

    def _get_port_mappings(self):
        return {}

    def _get_healthcheck(self):
        return {}


class _ValidateBindingsManager(ContainerManager):
    def __init__(self):
        self.config = SimpleNamespace(
            container_name="test-container",
            port=5432,
            retries=1,
            delay=0,
            init_script=None,
        )
        self.client = None
        self.recreated_container = _FakeContainer(
            "recreated",
            ports={"5432/tcp": [{"HostPort": "5432"}]},
        )
        self.calls = []
        self.start_kwargs = None

    @property
    def connection(self):
        return None

    def stop_db(self, container=None, force: bool = False):
        self.calls.append("stop_db")
        return container

    def _remove_container(self, container=None):
        self.calls.append("remove_container")
        return container

    def _create_container(self, force: bool = False, exists_ok: bool = True):
        self.calls.append("create_container")
        return self.recreated_container

    def _start_container(self, container=None, force: bool = False, running_ok: bool = True, retry: bool = True):
        self.calls.append("start_container")
        self.start_kwargs = {
            "container": container,
            "force": force,
            "running_ok": running_ok,
            "retry": retry,
        }
        return self.recreated_container

    def _get_environment_vars(self):
        return {}

    def _get_volume_mounts(self):
        return []

    def _get_port_mappings(self):
        return {"5432/tcp": 5432}

    def _get_healthcheck(self):
        return {}

    def _create_db(self, db_name: str, container=None):
        return container


def test_create_db_passes_latest_container_to_create_db():
    manager = _FlowManager()

    container = manager.create_db()

    assert container is manager.recreated_container
    assert manager.created_db_container is manager.recreated_container
    assert manager.calls == [
        "build_image",
        "create_container",
        "start_container",
        "test_connection",
        "create_db",
    ]


def test_start_db_returns_latest_container():
    manager = _FlowManager()

    container = manager.start_db(container=manager.initial_container)

    assert container is manager.recreated_container


def test_validate_port_bindings_recreates_on_conflict_and_returns_new_container():
    manager = _ValidateBindingsManager()
    stale_container = _FakeContainer("stale", ports={"5432/tcp": None})

    container = manager._validate_port_bindings(stale_container, retry=True)

    assert container is manager.recreated_container
    assert manager.calls == ["stop_db", "remove_container", "create_container", "start_container"]
    assert manager.start_kwargs is not None
    assert manager.start_kwargs["container"] is manager.recreated_container
    assert manager.start_kwargs["force"] is True
    assert manager.start_kwargs["running_ok"] is False
    assert manager.start_kwargs["retry"] is False
