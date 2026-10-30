# Owned interactive container lifecycle

`Sessions.open` persists exact intent, creates, observes immutable identity,
attaches, then starts once. `Session` owns its stream and receipt lock until
creator-thread `close`; generic ownership recovery remains in `ReceiptStore`.
No provider or authentication policy belongs to this package.

## Proposed optional deadline interface (implementation pending)

`open(request, *, deadline=None, cleanup_seconds=None)` keeps today's behavior
when both options are omitted. An explicit absolute monotonic deadline requires
an explicit positive finite cleanup reserve; invalid values fail before locking.
These options do not change `ContainerSession` or the persisted receipt schema.

`SessionDeadline` groups normal `RequestBudget` and cleanup duration;
`from_options` validates the pair and `cleanup_budget(now)` initializes the one
cleanup deadline. `state` and `wait` reuse the normal deadline; partial stream
reads/writes use its absolute cap. `terminate` binds its cleanup scope explicitly
on any thread. `close` reuses that reserve under the termination lock, always
detaches/releases the receipt lock, and stores any cleanup uncertainty for repeat
calls. A binding failure must never mark cleanup confirmed.

Normal scopes exit before failure-cleanup scopes begin. Unknown creates, expired
cleanup, or unverified removal preserve the pending receipt; cleanup uncertainty
overrides the safe primary failure. If termination used the reserve after removal,
close may conservatively retain a receipt for an already absent container.

No Engine send is admitted once its scope expires. Socket inactivity timeouts,
trickling responses and named-pipe connect retries prevent a finite wall-time
guarantee. Closing a client is not proof of aborting daemon work.
