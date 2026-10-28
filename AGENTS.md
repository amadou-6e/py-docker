# Package instructions

Preserve the database history in amadou-6e/pydocker-db. This repository now
builds the general py-docker distribution and imports as py_docker.

Keep feature-owned models.py/settings.py/errors.py; implementation files define
classes or standalone functions, never both. Prefer methods for owned behavior.
Never expose credentials, raw daemon errors or command output in exceptions.
No implicit pull/build/recreate/prune. Destructive operations require exact
resource identity and ownership verification. Document uncertain outcomes.

Commit and push coherent checkpoints. Claude review is required before merge
or publication; reuse the parent workspace reviewer session. Unit fixtures
do not establish real Docker/agent acceptance. Publish only reviewed artifacts
after packaging and real integration checks, without exposing upload keys.
