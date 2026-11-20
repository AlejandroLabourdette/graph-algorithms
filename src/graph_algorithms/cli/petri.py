"""Command line entry point for the interactive Petri net token game."""

import argparse
from pathlib import Path

from graph_algorithms.petri import PetriNet
from graph_algorithms.render import render_petri_net

QUIT = "q"


def ask_transition(net: PetriNet, enabled: list[str]) -> str | None:
    """Prompt until the user names an enabled transition; None means quit."""
    while True:
        try:
            choice = input(f"Fire transition ({QUIT} to quit): ").strip()
        except EOFError, KeyboardInterrupt:
            print()
            return None
        if choice == QUIT:
            return None
        if choice in enabled:
            return choice
        if choice in net.transitions:
            print(f"  {choice} is not enabled")
        elif choice:
            print(f"  unknown transition {choice!r}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Play the token game on a Petri net: show the enabled transitions of the "
        "current marking, fire the one you choose and render the net with Graphviz at each step."
    )
    parser.add_argument("input", type=Path, help="file with pre, post and marking sections")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path without extension, rewritten at each step (default: output/<input name>)",
    )
    parser.add_argument("-f", "--format", default="svg", choices=["svg", "png", "pdf"])
    args = parser.parse_args(argv)

    net = PetriNet.from_text(args.input.read_text())
    output = args.output or Path("output") / args.input.stem
    marking = net.initial_marking
    fired: list[str] = []

    while True:
        print(f"\nStep {len(fired)}")
        print(
            "  Marking: " + " ".join(f"{p}={n}" for p, n in zip(net.places, marking, strict=True))
        )
        last_fired = fired[-1] if fired else None
        rendered = render_petri_net(net, marking, last_fired).render(
            output, format=args.format, cleanup=True
        )
        print(f"  Net written to {rendered}")

        enabled = net.enabled_transitions(marking)
        if not enabled:
            print("  Deadlock: no transition is enabled")
            break
        print(f"  Enabled transitions: {', '.join(enabled)}")

        transition = ask_transition(net, enabled)
        if transition is None:
            break
        marking = net.fire(marking, transition)
        fired.append(transition)

    print(f"\nFiring sequence: {' '.join(fired) or '(empty)'}")
