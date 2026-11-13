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

## Input format

Graphs are plain text edge lists: one directed edge `u v` per line. A line with a single
token declares an isolated vertex; blank lines and anything after `#` are ignored.

## Algorithms

### Tarjan's strongly connected components

Finds the strongly connected components of a directed graph in O(V + E)
(`graph_algorithms.tarjan.strongly_connected_components`). The rendered graph draws each
component as a labelled, colored cluster; edges between components are dashed.

```sh
uv run tarjan examples/tarjan.txt            # writes output/tarjan.svg
uv run tarjan examples/tarjan.txt -f png -o output/clrs
```
