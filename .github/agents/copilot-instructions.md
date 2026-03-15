# CVCutter Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-15

## Active Technologies

- Python 3.11+ (project baseline remains `>=3.11`) + Flet (UI migration target), moviepy/opencv-python/librosa/pydub/scipy/ffmpeg toolchain, google-api-python-client stack, configured AI provider adapter (default: Gemini), `uv`-managed packaging/runtime (002-refactor-concert-tool)

## Project Structure

```text
src/
tests/
```

## Commands

uv run ruff check .
uv run pyright
uv run pytest --cov

## Code Style

Python 3.11+ (project baseline remains `>=3.11`): Follow standard conventions

## Recent Changes

- 002-refactor-concert-tool: Added Python 3.11+ (project baseline remains `>=3.11`) + Flet (UI migration target), moviepy/opencv-python/librosa/pydub/scipy/ffmpeg toolchain, google-api-python-client stack, configured AI provider adapter (default: Gemini), `uv`-managed packaging/runtime

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
