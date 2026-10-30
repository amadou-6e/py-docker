"""Internal logging-policy controls; real Docker acceptance remains separate."""

from unittest.mock import Mock

import pytest
from docker.errors import NotFound
from pydantic import ValidationError

from py_docker.containers.models import ContainerReceipt, ContainerSpec
from py_docker.containers.service import Containers
from py_docker.errors import CreationUnconfirmedError
from py_docker.sessions.models import ContainerSession
from py_docker.sessions.service import Sessions
from py_docker.streams.models import StreamLimits


def _runtime(spec, readback):
    """Return real ownership/launch verification over an internal SDK boundary."""
    sdk, image, observed = Mock(), Mock(), Mock()
    image.id = spec.image
    image.attrs = {
        "Config": {"User": "", "WorkingDir": "", "Entrypoint": None, "Cmd": None}
    }
    sdk.images.get.return_value = image
    containers = Containers(sdk, endpoint="unix:///controlled.sock")
    reservation = containers.reserve(spec)
    observed.id = "b" * 64
    observed.attrs = {
        "Id": observed.id,
        "Name": "/owned",
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "PidsLimit": 128,
            "Memory": 1073741824,
            "Init": False,
            "NanoCpus": 0,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "LogConfig": readback,
        },
        "Config": {
            "Labels": reservation.to_private_record()["labels"],
            "OpenStdin": False,
            "Tty": False,
            "User": "",
            "WorkingDir": "",
            "Entrypoint": None,
            "Cmd": None,
        },
    }
    removed = [False]

    def get(_):
        if removed[0]:
            raise NotFound("controlled absent resource")
        return observed

    def remove(**_):
        removed[0] = True

    sdk.containers.get.side_effect = get
    sdk.containers.create.return_value = observed
    observed.remove.side_effect = remove
    return containers, reservation, observed


@pytest.mark.parametrize("driver", [None, "none", "vendor-plugin/driver:tag"])
def test_requested_driver_projection_and_omission_are_exact(driver):
    """Omitted policy leaves native defaults untouched; explicit names have no local catalogue."""
    spec = ContainerSpec(image="sha256:" + "a" * 64, name="owned", log_driver=driver)
    readback = {"Type": driver or "daemon-default", "Config": {}}
    containers, reservation, observed = _runtime(spec, readback)
    identity = containers.create(spec, reservation)
    assert identity.id == observed.id
    options = containers.sdk.containers.create.call_args.kwargs
    assert "log_driver" not in options
    if driver is None:
        assert "log_config" not in options and "log_driver" not in spec.model_dump()
        assert (
            spec.model_dump()
            == ContainerSpec(image=spec.image, name=spec.name).model_dump()
        )
    else:
        assert options["log_config"] == {"Type": driver, "Config": {}}
        assert spec.model_dump()["log_driver"] == driver
        assert ContainerSpec.model_validate(spec.model_dump()).log_driver == driver
    observed.start.assert_not_called()


@pytest.mark.parametrize(
    "readback", [None, {}, {"Type": ""}, {"Type": "json-file"}, "malformed"]
)
def test_driver_readback_mismatch_is_cleaned_before_any_start(tmp_path, readback):
    """A created resource with unconfirmed logging never starts or silently falls back."""
    spec = ContainerSpec(image="sha256:" + "a" * 64, name="owned", log_driver="none")
    containers, reservation, observed = _runtime(spec, readback)
    containers.reserve = Mock(return_value=reservation)
    execution = Mock()
    path = tmp_path.joinpath("logging-receipt.json")
    with pytest.raises(CreationUnconfirmedError) as caught:
        Sessions(containers, execution).open(
            ContainerSession(
                spec=spec,
                limits=StreamLimits(seconds=10, max_bytes=1024),
                receipt_path=path,
            )
        )
    assert caught.value.operation == "verify requested container log driver"
    assert caught.value.receipt == reservation
    assert containers.sdk.containers.create.call_count == 1
    observed.start.assert_not_called()
    execution.attach.assert_not_called()
    observed.remove.assert_called_once_with(force=True, v=False)
    assert not path.exists()


def test_empty_driver_rejected_and_existing_receipt_schema_unchanged():
    """Validate supplied names without adding launch policy to ownership records."""
    with pytest.raises(ValidationError):
        ContainerSpec(image="local", name="owned", log_driver="")
    spec = ContainerSpec(image="sha256:" + "a" * 64, name="owned", log_driver="none")
    containers, reservation, _ = _runtime(spec, {"Type": "none"})
    record = ContainerReceipt(
        reservation=reservation, endpoint=containers.endpoint
    ).to_private_record()
    assert set(record) == {"name", "labels", "endpoint"}
    assert set(reservation.to_private_record()) == {"name", "labels"}
    assert ContainerReceipt.from_private_record(record).reservation == reservation
