# Exact owned container operations

`ContainerSpec` is the canonical Pydantic launch policy. `Containers.reserve`
prepares an exact name/private label reservation; `create` resolves a local image,
creates once and verifies sandbox readback before returning an identity. `inspect`,
`start`, `wait`, `remove` and `state` act on exact observed ownership. `ReceiptStore`
retains endpoint/reservation/observed identity; it does not fingerprint or persist
the complete launch policy. Ownership and uncertain-create recovery are unchanged.

## Explicit log driver

`ContainerSpec.log_driver` is an optional driver name, without a hardcoded driver
catalogue or a broad log-option API. None/omission preserves previous model/native
payload omission and daemon policy. `log_driver="none"` explicitly requests disabled
container logging. Driver names are ordinary configuration; no credentials or
driver options are introduced.

`Containers.create` converts the supplied name to the SDK's `LogConfig` only at the
native boundary and verifies exact `HostConfig.LogConfig.Type` afterward. A missing,
malformed or mismatched driver fails launch verification before any start. Creation
may already have happened, so it retains the existing CreationUnconfirmedError and
exact ownership cleanup path. It never silently accepts daemon fallback logging.

This capability was found missing while preparing credential-free controls: the
earlier mirror design assumed `logging=none`, but the actual spec could not request
it. No control container was launched to work around that gap. Real Docker controls
remain pending focused review of this addition. Internal regression controls cover
omitted policy, arbitrary driver projection, exact readback and mismatch cleanup;
these controls do not establish real Docker acceptance.
