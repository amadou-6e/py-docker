# One-shot owned container jobs

`Jobs.run(job, *, cancelled=None)` collects one binary result using the existing
`Sessions.open` lifecycle; `recover(receipt_path)` reconciles its exact journal.
Jobs compose sessions and never duplicate create/attach/start/cleanup behavior.

## Proposed optional deadline forwarding (implementation pending)

`run` will accept keyword-only `deadline=None, cleanup_seconds=None`, forwarded
unchanged to `Sessions.open`. Omission preserves current behavior and schemas.
An already requested cancellation retains its existing precedence over option
validation. Cancellation still overrides a normal Docker failure when requested;
cleanup uncertainty retains its stronger outcome guarantee. The session README
defines admission/inactivity limits and residual wall-time uncertainty.
