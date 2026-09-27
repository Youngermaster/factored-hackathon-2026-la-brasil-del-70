"""Small, unstyled matplotlib figures for ``docs/analysis/figures/`` (PNG, fixed size and resolution, no
embedded software or date metadata, so a rerun on the same data writes the same bytes)."""

from pathlib import Path
from typing import Any

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt

from bank_data.analysis.config import WORKFLOWS

FIGURE_NAMES: tuple[str, ...] = (
    "monthly-volume.png",
    "hour-of-day.png",
    "day-of-week.png",
    "error-contact-lag.png",
    "scores.png",
)
_SIZE = (7.0, 3.6)
_DPI = 100
_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _save(figure: Any, path: Path) -> None:
    figure.tight_layout()
    figure.savefig(path, dpi=_DPI, format="png", metadata={"Software": None})
    plt.close(figure)


def _shares(values: list[int]) -> list[float]:
    total = sum(values)
    return [value / total if total else 0.0 for value in values]


def write_figures(results: dict[str, Any], directory: Path) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 8})
    paths = [directory / name for name in FIGURE_NAMES]

    trend = results["trend"]
    figure, axis = plt.subplots(figsize=_SIZE)
    for workflow in WORKFLOWS:
        axis.plot(trend["months"], trend["workflows"][workflow]["monthly"], label=workflow)
    ticks = list(range(0, len(trend["months"]), 6))
    axis.set_xticks(ticks, [trend["months"][index] for index in ticks])
    axis.set_ylabel("Contacts per month")
    axis.set_title("Contacts per workflow and month (primary mapping; partial first and last months)")
    axis.legend()
    _save(figure, paths[0])

    patterns = results["patterns"]["workflows"]
    figure, axis = plt.subplots(figsize=_SIZE)
    for workflow in WORKFLOWS:
        axis.plot(range(24), _shares(patterns[workflow]["hour_of_day"]), marker=".", label=workflow)
    axis.set_xticks(range(0, 24, 2))
    axis.set_xlabel("Local hour of day (customer country)")
    axis.set_ylabel("Share of the workflow's interactions")
    axis.set_title("Interactions by local hour of day")
    axis.legend()
    _save(figure, paths[1])

    figure, axis = plt.subplots(figsize=_SIZE)
    width = 0.2
    for index, workflow in enumerate(WORKFLOWS):
        positions = [day + (index - 1.5) * width for day in range(7)]
        axis.bar(positions, _shares(patterns[workflow]["weekday"]), width=width, label=workflow)
    axis.set_xticks(range(7), list(_WEEKDAYS))
    axis.set_ylabel("Share of the workflow's interactions")
    axis.set_title("Interactions by local day of week")
    axis.legend()
    _save(figure, paths[2])

    lag = results["lag"]
    figure, axis = plt.subplots(figsize=_SIZE)
    hours = list(range(len(lag["error"]["histogram"])))
    for label in ("error", "baseline"):
        events = lag[label]["events"] or 1
        axis.step(hours, [value / events for value in lag[label]["histogram"]], where="post", label=f"{label} events")
    axis.set_xlabel("Hours from the digital event to the next contact (same customer)")
    axis.set_ylabel("Share of events")
    axis.set_title("Contact after a digital event, errors against a 5% sample of other events (association only)")
    axis.legend()
    _save(figure, paths[3])

    primary = results["scores"]["scenarios"]["primary"]
    ranges = results["scores"]["sensitivity"]["ranges"]
    figure, axis = plt.subplots(figsize=_SIZE)
    names = list(reversed(primary["ranking"]))
    scores = [primary["scores"][name] for name in names]
    errors = [
        [score - ranges[name]["score_min"] for name, score in zip(names, scores, strict=True)],
        [ranges[name]["score_max"] - score for name, score in zip(names, scores, strict=True)],
    ]
    axis.barh(names, scores, xerr=errors, capsize=3)
    axis.set_xlim(0, 100)
    axis.set_xlabel("Weighted score (0 to 100); whiskers: weight sensitivity range")
    axis.set_title("Pre-registered workflow scores (primary mapping)")
    _save(figure, paths[4])
    return paths
