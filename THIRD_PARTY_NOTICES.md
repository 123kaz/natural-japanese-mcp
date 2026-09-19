# Upstream dependency

This project is a thin MCP transport wrapper around:

- Repository: https://github.com/coji/natural-japanese
- Pinned commit: `9a78a42964096da509b8f3e011f0085a5f080151`
- License: MIT

The upstream repository is cloned into the container image without rewriting its
`lint.py` detection logic. Its original license and copyright notices remain
inside the cloned source tree.

The wrapper code in this repository is separately licensed under this
repository's MIT License.
