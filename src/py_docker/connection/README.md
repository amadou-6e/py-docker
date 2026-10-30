# Engine connection boundary

`Client` resolves one endpoint and owns the Docker SDK connection pools. Concrete
`DirectAPIClient` and `DirectDockerClient` remain beside endpoint settings and
resolution so transport behavior is discoverable without session internals.

## Proposed deadline admission (implementation pending)

`RequestBudget` is the canonical Pydantic absolute monotonic deadline and private
create-dispatch witness. `remaining_seconds(now)` refuses expiry and
`timeout_seconds(supplied, configured, now)` clamps this request's scalar timeout.
`RequestDeadlineScope` binds that budget to the actual APIClient object using
`__enter__`/`__exit__`; `current(api)` finds only that object's active scope.
Different clients may nest; same-client nesting is refused, preserving one create
witness. ContextVar bindings are per context and always reset. No shared timeout,
pool or adapter setting is changed.

`DirectAPIClient.send` checks every Engine send, including nested high-level calls,
attach and redirects. Before the first create POST, expiry is a proven no-send;
after admission, uncertainty must retain ownership intent. Client construction,
version negotiation and calls outside a session scope retain existing settings.

This is admission plus socket inactivity timeout control, not a hard wall-clock
deadline: trickling responses and named-pipe busy retries may overrun. No timer,
worker, provider knowledge, credential handling or implicit retry belongs here.
