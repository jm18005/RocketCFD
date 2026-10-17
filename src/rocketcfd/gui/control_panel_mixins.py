"""Control-panel behavior shared by the main window's reference/sweep-status controls."""
from __future__ import annotations

import numpy as np
from PySide6.QtWidgets import QFileDialog

from rocketcfd.flow import SEA_LEVEL_TEMPERATURE, FlowCondition
from rocketcfd.gas import speed_of_sound
from rocketcfd.geometry import frontal_area
from rocketcfd.gui.viewport import panel_mesh_to_polydata, render_reference_scene


class ReferenceControlsMixin:
    """Subclasses must define _apply_extra_overlays() -- any additional overlay (a
    geometry bounding box, a mesh domain preview, ...) drawn on top of the base scene."""

    def show_reference_scene(self, direction_unit: np.ndarray | None = None) -> None:
        self.view_tabs.setCurrentIndex(0)
        mesh_polydata = panel_mesh_to_polydata(self.panel_mesh) if self.panel_mesh is not None else None
        render_reference_scene(
            self.plotter,
            self._moment_reference(),
            mesh_polydata,
            direction_unit,
            wind_speed=self.wind_speed_spin.value(),
            wind_direction_deg=self.wind_direction_spin.value(),
            wind_elevation_deg=self.wind_elevation_spin.value(),
            vehicle_speed=self._current_flow_speed(),
        )
        self._apply_extra_overlays()

    def _reference_overlay_active(self) -> bool:
        return self.show_coords_checkbox.isChecked() or self.show_flow_checkbox.isChecked() or self.show_wind_checkbox.isChecked()

    def _current_flow_direction_unit(self) -> np.ndarray:
        try:
            alpha_axis = self.rows["alpha_deg"].axis()
            beta_axis = self.rows["beta_deg"].axis()
        except ValueError:
            alpha_axis = beta_axis = None
        alpha_deg = float(alpha_axis.values[0]) if alpha_axis is not None else 0.0
        beta_deg = float(beta_axis.values[0]) if beta_axis is not None else 0.0
        condition = FlowCondition(name="preview", velocity=1.0, alpha_deg=alpha_deg, beta_deg=beta_deg)
        return condition.direction_unit()

    def _current_flow_speed(self) -> float:
        if self.mach_input_checkbox.isChecked():
            try:
                mach_axis = self.rows["mach"].axis()
                temperature_axis = self.rows["temperature"].axis()
            except ValueError:
                return 0.0
            if mach_axis is None:
                return 0.0
            temperature = float(temperature_axis.values[0]) if temperature_axis is not None else SEA_LEVEL_TEMPERATURE
            return float(mach_axis.values[0]) * speed_of_sound(temperature)
        try:
            velocity_axis = self.rows["velocity"].axis()
        except ValueError:
            return 0.0
        return float(velocity_axis.values[0]) if velocity_axis is not None else 0.0

    def _moment_reference(self) -> np.ndarray:
        return np.array([self.ref_x_spin.value(), self.ref_y_spin.value(), self.ref_z_spin.value()])

    def _on_ref_dims_override_toggled(self, checked: bool) -> None:  # noqa: 21 (Qt slot signature)
        self.ref_area_spin.setEnabled(checked)
        self.ref_length_spin.setEnabled(checked)
        self._update_auto_reference_dims()

    def _update_auto_reference_dims(self) -> None:
        if self.panel_mesh is None or self.ref_dims_override_checkbox.isChecked():
            return
        direction = self._current_flow_direction_unit()
        area = frontal_area(self.panel_mesh, direction)
        length = 2.0 * np.sqrt(area / np.pi) if area > 0.0 else 1.0
        self.ref_area_spin.setValue(area)
        self.ref_length_spin.setValue(length)

    def _reference_overrides(self) -> tuple[float | None, float | None]:
        if not self.ref_dims_override_checkbox.isChecked():
            return None, None
        return self.ref_area_spin.value(), self.ref_length_spin.value()


class SweepStatusMixin:
    """Subclasses must define _export_case_results_csv(path, case_results)."""

    def _on_sweep_failed(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self._residual_timer.stop()
        self._live_case_log = None
        self.geometry_status_label.setText(f"Run failed: {message}")

    def _on_export_csv(self, checked: bool = False) -> None:  # noqa: 21 (Qt slot signature)
        if not self.case_results:
            self.geometry_status_label.setText("No results to export yet -- run a case first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export aerotable to CSV", "aerotable.csv", "CSV files (*.csv)")
        if not path:
            return
        self._export_case_results_csv(path, self.case_results)
        self.geometry_status_label.setText(f"Exported {len(self.case_results)} case(s) to {path}.")
