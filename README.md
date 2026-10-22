# Existing (legacy) codebase for ApKit4D

This branch (`legacy`) will never be merged into `main`.

I've taken the original codebase and added `uv` to it.

To run the app run `uv run python -m ApKit4D`.

I've not added Qt6 as a dependency. On my system Python accesses the system library. You might have to `uv add PyQt6`.
