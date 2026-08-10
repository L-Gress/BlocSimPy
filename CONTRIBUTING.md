# Contributing to BlocSimPy

Thanks for considering a contribution! This is a small hobby project, so the process is
intentionally lightweight.

## Getting set up

```bash
git clone https://github.com/L-Gress/BlocSimPy.git
cd BlocSimPy
pip install -r requirements-dev.txt
pytest tests/
```

## Adding a new block

Most new block *kinds* need no GUI code at all:

1. Create `engine/blocks/your_block.py` with a class subclassing `BlockModel`
   (see `engine/blocks/gain.py` for a minimal example, or `engine/blocks/saturation.py`
   for one with a parameter dialog).
2. Set a `BLOCK_INFO` dict (`description`, `parameters`, `formula`, `usage`, `category`) — the
   `category` determines which group it appears under in the palette.
3. Import it and add it to `BLOCK_REGISTRY` in `engine/blocks/__init__.py`.
4. Add tests under `tests/` mirroring the existing `test_blocks_*.py` files.

That's it — the block automatically shows up in the palette, saves/loads, and works inside
subsystems. Only override `get_editor_dialog()` if the generic parameter form isn't enough
(dynamic port counts, matrix input, etc.).

## Running tests

```bash
pytest tests/
```

The suite is almost entirely Qt-free (tests `engine/` directly); a couple of tests that need
real `UIBlock`/`UIConnection` objects run headlessly via `QT_QPA_PLATFORM=offscreen`.

## Pull requests

- Keep PRs focused — one change per PR is easier to review than a grab-bag.
- Add or update tests for behavior changes.
- Run `pytest tests/` before opening the PR.

## Reporting bugs

Open an issue with: what you did, what you expected, what happened instead, and (if it's a
simulation/diagram issue) the `.json` diagram file if you're able to share it.
