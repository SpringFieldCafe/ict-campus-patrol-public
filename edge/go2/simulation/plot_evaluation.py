"""Optional report figure; Matplotlib is not a simulation/runtime dependency."""

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Plot saved reports and real trajectories"
    )
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--final", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="Output basename, without suffix"
    )
    args = parser.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Circle, Rectangle

    reports = [
        json.loads(path.read_text())
        for path in (args.reference, args.candidate, args.final)
    ]
    root = args.final.parent
    figure, (spatial, bars) = plt.subplots(
        1, 2, figsize=(13, 4.5), gridspec_kw={"width_ratios": [2, 1]}
    )
    layout = ET.parse(
        Path(__file__).parent / "src/mujoco_sim/assets/go2/walls.xml"
    ).getroot()
    for geom in layout.findall("worldbody/geom"):
        if geom.get("type") != "box":
            continue
        x, y, _ = map(float, geom.get("pos").split())
        hx, hy, _ = map(float, geom.get("size").split())
        spatial.add_patch(
            Rectangle(
                (x - hx, y - hy),
                2 * hx,
                2 * hy,
                facecolor="#8a633d",
                edgecolor="#4c3520",
                zorder=4,
            )
        )
    for result in reports[-1]["results"]:
        case = result["case"]
        if case["scene"] != "staggered_walls":
            continue
        path = root / case["id"] / "simulation.jsonl"
        positions = [
            json.loads(line)["position_xy"] for line in path.read_text().splitlines()
        ]
        color = "#14806d" if result["state"] == "SUCCEEDED" else "#cb5148"
        spatial.plot(
            [p[0] for p in positions],
            [p[1] for p in positions],
            color=color,
            alpha=0.65,
            linewidth=1,
        )
        if result["state"] != "SUCCEEDED":
            spatial.scatter(*positions[-1], color=color, marker="x", s=35, zorder=6)
    route = next(
        r["case"]["waypoints"]
        for r in reports[-1]["results"]
        if r["case"]["route_id"] == "checkpoints-walls"
        and r["case"]["variant"] == "center"
    )
    for index, point in enumerate(route):
        spatial.add_patch(
            Circle(
                (point["x"], point["y"]),
                point["radius"],
                facecolor="#4295c4",
                alpha=0.1,
                edgecolor="#2378ad",
            )
        )
        spatial.scatter(point["x"], point["y"], color="#2378ad", s=22, zorder=5)
        spatial.text(point["x"], 0.55, f"CP{index + 1}", ha="center", fontsize=9)
    spatial.scatter(0, 0, color="#243b52", marker="*", s=80, zorder=5)
    spatial.set(
        title="Final setting: all 15 wall trials (base trajectories)",
        xlabel="World x (m)",
        ylabel="World y (m)",
    )
    spatial.set_aspect("equal")
    spatial.set_xlim(-0.4, 8.8)
    spatial.set_ylim(-2, 2)
    spatial.grid(alpha=0.15)
    spatial.legend(
        handles=[
            Line2D([0], [0], color="#14806d", label="Completed 3/3"),
            Line2D([0], [0], color="#cb5148", label="Collision (includes leg contact)"),
        ],
        loc="lower right",
        fontsize=8,
    )
    groups = [r["by_scene"]["staggered_walls"] for r in reports]
    counts = [g["states"]["SUCCEEDED"] for g in groups]
    totals = [g["trials"] for g in groups]
    bars.bar(
        range(3),
        [100 * n / total for n, total in zip(counts, totals)],
        color=["#4a8296", "#be8a52", "#14806d"],
        width=0.6,
    )
    for index, (count, total) in enumerate(zip(counts, totals)):
        bars.text(index, 100 * count / total + 2, f"{count}/{total}", ha="center")
    bars.set_xticks(
        range(3), ["Reference\n0.18 m/s", "Candidate\n0.40 m/s", "Final\n0.18 m/s"]
    )
    bars.set(title="Wall success rate (%)", ylim=(0, 110))
    bars.grid(axis="y", alpha=0.15)
    figure.suptitle(
        "MuJoCo only: fixed walls, 3 target variants x 5 starting poses", fontsize=12
    )
    figure.tight_layout()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".svg"):
        figure.savefig(args.output.with_suffix(suffix), dpi=170, bbox_inches="tight")
        if suffix == ".svg":
            path = args.output.with_suffix(suffix)
            path.write_text(
                "\n".join(line.rstrip() for line in path.read_text().splitlines())
                + "\n"
            )
    plt.close(figure)


if __name__ == "__main__":
    main()
