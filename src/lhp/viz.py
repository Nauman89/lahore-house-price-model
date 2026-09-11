"""Plot styling for the project's figures. A module, not a script (PLAN §9).

Nothing here analyses anything. It holds the house style — palette, typography, axis
chrome, number formatting and the figure-saving convention — so that a notebook cell is
three lines about the data instead of thirty about matplotlib, and so every figure in the
stage 7 deck already matches every figure in the EDA notebook. Flagged in PLAN §9 as
reusable across projects: nothing below mentions houses, Lahore or prices except the
currency formatter, which is parameterised.

**The palette is adopted, not invented.** The eight categorical hues, the blue sequential
ramp, the blue↔red diverging pair and the chrome tokens come from a validated reference
palette whose ordering was chosen to clear colour-vision-deficiency separation on
*adjacent* pairs. Two rules travel with it and are not negotiable by eye:

* **Fixed order, never cycled.** Series one takes slot one. A ninth series is not a
  ninth colour — it folds into "other", or the chart becomes small multiples.
* **Three slots for all-pairs forms.** Scatter, bubble and small-multiple charts put
  every series beside every other, and past three slots the full set stops clearing the
  separation floor. Bars and lines, where only neighbours touch, may use all eight.

Three of the light-mode hues sit below 3:1 contrast on the light surface, so a chart that
leans on them carries direct labels rather than colour alone. :func:`label_bars` is there
for exactly that.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# --------------------------------------------------------------------------------------
# Palette — adopted from the validated reference instance, light mode
# --------------------------------------------------------------------------------------

#: Categorical hues in their validated order. Index 0 is the first series, always.
CATEGORICAL: tuple[str, ...] = (
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
)

#: How many slots are safe when every series sits beside every other (scatter, bubble,
#: small multiples). Bars and lines compare neighbours only and may use the full eight.
ALL_PAIRS_LIMIT = 3

#: Blue, light to dark. For continuous magnitude — heatmaps, choropleths, bin counts.
SEQUENTIAL: tuple[str, ...] = (
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec",
    "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95",
)

#: For an *ordinal* ramp — discrete ordered marks — start no lighter than this, or the
#: lightest step disappears into the surface.
ORDINAL_FLOOR = 3

#: Two poles that read as opposite, with a neutral midpoint. For signed quantities only:
#: residuals, deviation from a benchmark, above/below a median.
DIVERGING: tuple[str, str, str] = ("#2a78d6", "#f0efec", "#d03b3b")

#: Reserved for state, never for "series 4", and always shipped with a label.
STATUS: dict[str, str] = {
    "good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b",
}

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

#: 16:9 at a size that stays legible when a slide is projected. Two tiers of figure share
#: one geometry: an exploratory chart and a deck chart differ in how much is *said* on
#: them — title, annotation, source line — not in how they are drawn.
FIGSIZE = (10.0, 5.625)
DPI = 200

#: Where a saved figure goes. PLAN §10.
FIGURE_DIR = Path("reports/figures")


def use_house_style() -> None:
    """Apply the house style to every subsequent figure. Call once per notebook.

    Sets the palette as the default property cycle, strips the top and right spines,
    puts a hairline grid behind the marks on the value axis only, and recesses the axis
    chrome so the data is the darkest thing on the page.
    """
    mpl.rcParams.update({
        "figure.figsize": FIGSIZE,
        "figure.dpi": 110,
        "savefig.dpi": DPI,
        "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "axes.prop_cycle": mpl.cycler(color=list(CATEGORICAL)),
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.labelcolor": INK_SECONDARY,
        "axes.titlecolor": INK,
        "axes.titlesize": 13,
        "axes.titleweight": "semibold",
        "axes.titlelocation": "left",
        "axes.titlepad": 10,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": INK_MUTED,
        "ytick.color": INK_MUTED,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.frameon": False,
        "legend.fontsize": 9,
        "legend.labelcolor": INK_SECONDARY,
        "lines.linewidth": 2.0,
        "lines.markersize": 5,
        "font.size": 10,
        "text.color": INK,
    })


def millions(decimals: int = 1, suffix: str = "M") -> FuncFormatter:
    """Axis formatter rendering PKR in millions — 3,700,000 becomes ``3.7M``.

    The project states every price in millions, in the decision log, the reconciliation
    and the deck alike, so one convention travels from cleaning through to the client.
    """
    def render(value: float, _position: int) -> str:
        return f"{value / 1e6:,.{decimals}f}{suffix}"
    return FuncFormatter(render)


def thousands() -> FuncFormatter:
    """Axis formatter with thousands separators, for counts."""
    return FuncFormatter(lambda value, _position: f"{value:,.0f}")


def annotate(
    ax: plt.Axes,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    source: str | None = None,
    grid_axis: str = "y",
) -> plt.Axes:
    """Put the chart's words on it and confine the grid to the value axis.

    The subtitle carries the finding — "DHA phase medians span 61%" — and the title names
    the view. A reader who takes nothing else from the figure should take the subtitle.

    Args:
        ax: The axes to annotate.
        title: Names what is plotted.
        subtitle: One line stating what it shows. This is the sentence that ends up on
            the slide.
        xlabel / ylabel: Axis labels. Omit where the tick labels already say it.
        source: A provenance line set below the axes, e.g. the row count and window.
        grid_axis: ``"y"``, ``"x"`` or ``"both"``. Gridlines belong on the value axis;
            a grid across the category axis is noise.

    Returns:
        The same axes, so calls can chain.
    """
    # Title and subtitle are drawn as axes-relative text rather than through set_title,
    # so the two stack instead of landing on the same baseline. Everything is anchored to
    # the axes, so `bbox_inches="tight"` at save time crops around them.
    if title:
        ax.text(
            0.0, 1.10 if subtitle else 1.02, title, transform=ax.transAxes, ha="left",
            va="bottom", fontsize=13, fontweight="semibold", color=INK,
        )
    if subtitle:
        ax.text(
            0.0, 1.02, subtitle, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=10, color=INK_SECONDARY,
        )
    ax.set_xlabel(xlabel or "")
    ax.set_ylabel(ylabel or "")
    ax.grid(True, axis=grid_axis, color=GRID, linewidth=0.8)
    if grid_axis != "both":
        ax.grid(False, axis="x" if grid_axis == "y" else "y")
    if source:
        # Clear of the tick labels, and clear of the axis label when there is one.
        ax.text(
            0.0, -0.24 if ax.get_xlabel() else -0.13, source, transform=ax.transAxes,
            ha="left", va="top", fontsize=8, color=INK_MUTED,
        )
    return ax


def label_bars(
    ax: plt.Axes,
    *,
    fmt: str = "{:,.0f}",
    only: int | None = None,
    horizontal: bool = False,
) -> None:
    """Write values on bars — selectively, never on every mark by default.

    A number on every bar turns a chart into a table that is harder to read than a table.
    ``only`` labels the n largest and leaves the rest to the axis, which is what a reader
    actually needs: the top of the ranking, and a scale for everything else.

    Args:
        ax: The axes holding the bars.
        fmt: Format string applied to each labelled value.
        only: Label just the n largest bars. ``None`` labels all of them — use it when
            the chart carries few bars, or when the hue needs the relief of a label.
        horizontal: True for barh, where the value runs along x.
    """
    bars = [p for container in ax.containers for p in container]
    values = [(p.get_width() if horizontal else p.get_height()) for p in bars]
    keep = set(range(len(bars)))
    if only is not None and only < len(bars):
        keep = set(sorted(range(len(bars)), key=lambda i: values[i], reverse=True)[:only])

    for index, (patch, value) in enumerate(zip(bars, values, strict=True)):
        if index not in keep:
            continue
        if horizontal:
            x, y, ha, va = patch.get_width(), patch.get_y() + patch.get_height() / 2, "left", "center"
            offset = (4, 0)
        else:
            x, y, ha, va = patch.get_x() + patch.get_width() / 2, patch.get_height(), "center", "bottom"
            offset = (0, 4)
        ax.annotate(
            fmt.format(value), (x, y), textcoords="offset points", xytext=offset,
            ha=ha, va=va, fontsize=9, color=INK_SECONDARY,
        )


def reference_line(ax: plt.Axes, value: float, label: str, *, horizontal: bool = True) -> None:
    """Draw a labelled benchmark — a median, a threshold, an acceptance criterion.

    Recessive by design: a dashed hairline in muted ink, so it reads as the ruler the
    data is measured against rather than as another series.
    """
    draw = ax.axhline if horizontal else ax.axvline
    draw(value, color=INK_MUTED, linestyle="--", linewidth=1.0, zorder=1)
    if horizontal:
        ax.annotate(label, (1.0, value), xycoords=("axes fraction", "data"),
                    textcoords="offset points", xytext=(-4, 4), ha="right", va="bottom",
                    fontsize=9, color=INK_MUTED)
    else:
        ax.annotate(label, (value, 1.0), xycoords=("data", "axes fraction"),
                    textcoords="offset points", xytext=(4, -4), ha="left", va="top",
                    fontsize=9, color=INK_MUTED)


def save(fig: plt.Figure, name: str, *, directory: Path | str = FIGURE_DIR) -> Path:
    """Write a figure to ``reports/figures/<name>.png`` and return the path.

    Deck resolution by default, so a promoted figure needs no re-render — the two tiers
    differ in annotation, not in output quality.
    """
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    return path
