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

Graphs are plain text adjacency matrices of `0`s and `1`s separated by whitespace: row `u`,
column `v` is `1` when there is an edge `u -> v` (a `1` on the diagonal is a self-loop).
An optional first line names the vertices (at least one name must be non-numeric); without
it, vertices are named `1..n`. Blank lines and anything after `#` are ignored.

```text
# a -> b, b -> a, b -> c
a b c
0 1 0
1 0 1
0 0 0
```

## Algorithms

### Tarjan's strongly connected components

Finds the strongly connected components of a directed graph in O(V + E)
(`graph_algorithms.tarjan.strongly_connected_components`). The rendered graph draws each
component as a labelled, colored cluster; edges between components are dashed.

```sh
uv run tarjan examples/tarjan.txt            # writes output/tarjan.svg
uv run tarjan examples/tarjan.txt -f png -o output/clrs
```
