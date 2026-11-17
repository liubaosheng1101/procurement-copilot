# Verification evidence

This directory is the proof store for `verify-procurement-copilot`.

Each launch creates one subdirectory named with its `VERIFY_RUN_ID`. That subdirectory holds commands, exit metadata, server logs, rendered DOM, screenshots, and downloaded JSON.

`verify.py cleanup` stops the server and browser that run started and deletes `/tmp/procurement-copilot-verify/<run-id>/`. It does not delete anything under this directory.
