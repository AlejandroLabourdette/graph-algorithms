# graph-algorithms

Implementations of graph theory algorithms in Python, with graph visualizations rendered by [Graphviz](https://graphviz.org/).

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Graphviz system binaries (`dot`): `brew install graphviz`

## Usage

```sh
uv sync                       # install dependencies
uv run pytest                 # run tests
uv run ruff check .           # lint
uv run ruff format .          # format
```
