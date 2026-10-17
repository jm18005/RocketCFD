"""Matplotlib canvas embedding and 2D/3D plot helpers for sweep results."""
from __future__ import annotations

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: 21 (registers the 3d projection used below)
from PySide6.QtWidgets import QWidget


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent: QWidget | None = None) -> None:
        self.figure = Figure(figsize=(5, 4))
        super().__init__(self.figure)
        self.setParent(parent)


def draw_line_plot(
    canvas: MplCanvas,
    x: np.ndarray,
    y: np.ndarray,
    xlabel: str,
    ylabel: str,
    yscale: str = "linear",
    annotate_extrema: bool = True,
) -> None:
    canvas.figure.clear()
    axes = canvas.figure.add_subplot()
    axes.plot(x, y, marker="o", markersize=3)
    if yscale == "log":
        axes.set_yscale("log")
    if annotate_extrema and len(y):
        imax, imin = int(np.argmax(y)), int(np.argmin(y))
        axes.plot([x[imax]], [y[imax]], marker="^", color="red", markersize=10)
        axes.annotate(
            f"max {y[imax]:.4g}\n@ {x[imax]:.4g}",
            (x[imax], y[imax]),
            textcoords="offset points",
            xytext=(8, 8),
            color="red",
            fontsize=8,
        )
        axes.plot([x[imin]], [y[imin]], marker="v", color="blue", markersize=10)
        axes.annotate(
            f"min {y[imin]:.4g}\n@ {x[imin]:.4g}",
            (x[imin], y[imin]),
            textcoords="offset points",
            xytext=(8, -18),
            color="blue",
            fontsize=8,
        )
    axes.set_xlabel(xlabel)
    axes.set_ylabel(ylabel)
    axes.grid(True)
    canvas.figure.tight_layout()
    canvas.draw()
