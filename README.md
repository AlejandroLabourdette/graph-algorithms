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

### Graphs

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

### Petri nets

A Petri net file has three sections, each started by its keyword alone on a line and given in
any order: `pre`, `post` and `marking`. `pre` and `post` are matrices of non-negative integers
with a row per place and a column per transition: `pre` holds the tokens each transition consumes
from each place and `post` the tokens it produces into it. Each matrix may have a header line of
transition names and may start every row with a place name (names cannot be integers); without
them, places are named `p1..pn` and transitions `t1..tm`. `marking` is one line with the initial
tokens of every place. Blank lines and anything after `#` are ignored.

```text
pre
     t1 t2
a    1  0
b    0  2

post
     t1 t2
a    0  1
b    1  0

marking
1 1
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

Examples in `examples/`:

| File | Graph |
| --- | --- |
| `tarjan.txt` | CLRS figure 22.9 plus a self-loop and an isolated vertex |
| `tarjan2.txt` | Two cycles joined by one edge |
| `tarjan3.txt` | Directed acyclic graph without header (vertices `1..n`), every vertex is its own component |
| `tarjan4.txt` | A single cycle with chords, the whole graph is one component |
| `tarjan5.txt` | Chain of components of different sizes, including a 2-cycle and a self-loop |
| `tarjan6.txt` | Two disconnected parts with multi-letter vertex names |

### Petri net token game

Interactive simulation of a place/transition net (`graph_algorithms.petri.PetriNet`). At each
step it prints the current marking and the enabled transitions (`t` is enabled when every place
holds at least `Pre[p, t]` tokens), renders the net, and asks which transition to fire. Firing
`t` moves to the marking `M - Pre[:, t] + Post[:, t]` and the next step lists the transitions
enabled there. The game ends when you type `q` (or EOF) or when no transition is enabled
(deadlock), and prints the firing sequence.

The rendered net is rewritten at each step: places are circles with their tokens (dots, or a
number above four), enabled transitions are green, disabled ones gray, the last fired transition
has an orange border, and arcs show their weight when it is greater than one.

```sh
uv run petri examples/petri.txt              # rewrites output/petri.svg at each step
uv run petri examples/petri.txt -f png -o output/buffer
```

Examples in `examples/`:

| File | Net |
| --- | --- |
| `petri.txt` | Producer / consumer with a one-slot buffer, runs forever |
| `petri2.txt` | Weighted arcs and a conflict between two transitions sharing a place |
| `petri3.txt` | Two processes taking two resources in opposite order, without names; firing `t1 t4` deadlocks |
| `petri4.txt` | Unbounded queue: `queue` becomes ω first and `done` one level later |
| `petri5.txt` | Bounded buffer with two slots: 2-bounded but not safe, a single cycle |

### Petri net coverability analysis (Karp-Miller)

Non-interactive analysis of a place/transition net (`graph_algorithms.petri_cover`) that uses the
same input files as the token game. It builds the coverability tree, derives the coverability graph
and analyses both, prints a report and renders two images: `<output>_tree.<format>` and
`<output>_graph.<format>`.

```sh
uv run petri_cover examples/petri4.txt          # writes output/petri4_tree.svg and output/petri4_graph.svg
uv run petri_cover examples/petri2.txt -f png -o output/parts
```

- **Coverability tree.** The root is the initial marking and each enabled transition creates a
  child, breadth first. A child whose marking already appears in an earlier node is a
  *duplicate*: it stays in the tree as a leaf and is not expanded, so the tree is always finite.
- **Omegas.** Each new marking is compared with the markings on the path from the root, nearest
  ancestor first. If it covers an ancestor (`>=` in every place) and differs from it, the places
  where it is strictly greater can be pumped without limit and become **ω** (ω + n = ω,
  ω − n = ω, ω ≥ n). The report lists every node that introduces omegas, the ancestor it covers
  and the places.
- **Coverability graph.** The tree with equal markings merged: duplicates become arcs back to the
  node they repeat. Parallel arcs are drawn as one arc labelled with all their transitions.
- **Strongly connected components.** Tarjan's algorithm on the coverability graph, numbered in
  topological order: SCC 1 holds the initial marking and the terminal components come last. Cyclic
  components are drawn as clusters; the report marks terminal components (no arc leaves them) and
  dead markings (no enabled transition).
- **Boundedness.** A place is unbounded when ω appears in it; otherwise its bound is the most
  tokens it holds in any marking. The net is bounded when every place is, and safe when every
  bound is at most 1.

With `-i` (`--interactive`) the tree is built step by step instead: at each step it shows the
current node, the path from the root and the enabled transitions, and you type the one to fire.
The new marking is compared with the path (omegas are announced as they appear) and a marking that
already exists is reported as a duplicate, which is not expanded and sends you back to its parent.
Firing a transition that was already fired from the current node moves to the child that exists
instead of adding another one. Type `r` to go back to the parent and explore another branch, or
`q` to quit; the tree `<output>_tree.<format>` is redrawn at every step, with the current node in
green. On exit it prints the tree built so far and its omegas.

```sh
uv run petri_cover examples/petri.txt -i -f png -o output/buffer
```

In the images, markings with an ω are orange, duplicates are dashed gray leaves labelled with the
node they repeat (`= M3`), dead markings are labelled `dead` and have a red border, and the
initial marking has a thick border.
