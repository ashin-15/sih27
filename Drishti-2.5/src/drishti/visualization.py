from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

from drishti.arrays import ByteArray, FloatArray
from drishti.config import MappingConfig
from drishti.contracts import Mode
from drishti.mapping import MapSnapshot
from drishti.pipeline import FrameResult
from drishti.semantics import CLASS_NAMES
from drishti.temporal import FusedMapView, FusedOccupancy, TerrainFlag, TerrainState


@dataclass(frozen=True)
class CellGeometry:
    centers_m: FloatArray
    sizes_m: FloatArray
    colors: ByteArray


def cell_geometry(snapshot: MapSnapshot) -> CellGeometry:
    low_m = snapshot.observed_min_cm.astype(np.float64) / 100
    high_m = snapshot.observed_max_cm.astype(np.float64) / 100
    centers = np.column_stack([snapshot.centers_xy_m, (low_m + high_m) / 2])
    sizes = np.column_stack([snapshot.size_m, snapshot.size_m, high_m - low_m])
    colors = np.tile(np.array([145, 151, 160], dtype=np.uint8), (len(low_m), 1))
    colors[snapshot.ground_valid] = [71, 185, 160]
    colors[snapshot.obstacle_valid] = [235, 151, 68]
    colors[snapshot.ambiguous] = [208, 111, 214]
    return CellGeometry(centers, sizes, colors)


def _semantic_palette() -> ByteArray:
    return np.array(
        [
            [145, 151, 160],
            [100, 160, 245],
            [210, 125, 70],
            [180, 80, 200],
            [90, 100, 230],
            [80, 200, 220],
            [245, 95, 95],
            [230, 140, 160],
            [210, 90, 130],
            [180, 160, 210],
            [190, 175, 130],
            [220, 125, 210],
            [150, 115, 90],
            [215, 205, 165],
            [185, 140, 100],
            [90, 170, 90],
            [140, 110, 65],
            [140, 185, 105],
            [210, 210, 210],
            [235, 195, 70],
        ],
        dtype=np.uint8,
    )


def semantic_legend_markdown() -> str:
    rows = [
        "# Semantic class legend",
        "",
        "Semantic cell color is the dominant accepted point class, not a point-level label.",
        "",
        "| ID | Class | RGB |",
        "| ---: | --- | --- |",
    ]
    for semantic_id, (class_name, color) in enumerate(
        zip(CLASS_NAMES, _semantic_palette(), strict=True)
    ):
        red, green, blue = color.tolist()
        rows.append(f"| {semantic_id} | {class_name} | {red}, {green}, {blue} |")
    return "\n".join(rows)


def semantic_summary_markdown(result: FrameResult) -> str:
    snapshot = result.snapshot
    class_count = len(CLASS_NAMES)
    point_counts = np.bincount(result.observations.semantic, minlength=class_count)
    cell_counts = np.bincount(snapshot.semantic, minlength=class_count)
    present = np.flatnonzero((point_counts + cell_counts) > 0)
    rows = [
        "## Semantic evidence",
        "",
        "Cell color is the dominant accepted point class, not a point-level label.",
        "",
        "| ID | Class | Accepted points | Cells |",
        "| ---: | --- | ---: | ---: |",
    ]
    rows.extend(
        f"| {semantic_id} | {CLASS_NAMES[semantic_id]} | {point_counts[semantic_id]:,} | "
        f"{cell_counts[semantic_id]:,} |"
        for semantic_id in present
    )
    evidence = snapshot.semantic_evidence
    if len(evidence):
        maximum = np.max(evidence, axis=1, keepdims=True)
        tied_cells = int(np.count_nonzero(np.count_nonzero(evidence == maximum, axis=1) > 1))
    else:
        tied_cells = 0
    conflicts = int(np.count_nonzero(snapshot.semantic_conflict))
    rows.extend(
        [
            "",
            f"Known-class conflicts: {conflicts:,} cells.",
            f"Tied class evidence rendered as unknown: {tied_cells:,} cells.",
        ]
    )
    return "\n".join(rows)


TERRAIN_COLORS = np.array(
    [
        [120, 124, 132],  # unknown
        [60, 200, 90],  # drivable
        [205, 170, 110],  # non-drivable terrain
        [225, 60, 55],  # obstacle
        [55, 58, 68],  # stale
    ],
    dtype=np.uint8,
)
OCCUPANCY_COLORS = np.array(
    [[120, 124, 132], [225, 60, 55], [70, 150, 235], [55, 58, 68]], dtype=np.uint8
)
CURB_COLOR = [255, 220, 0]
DROP_COLOR = [190, 60, 230]
OVERHANG_COLOR = [0, 230, 230]


def _rgb(color: object) -> str:
    return ", ".join(str(value) for value in np.asarray(color).tolist())


def terrain_legend_markdown() -> str:
    names = ("Unknown", "Drivable", "Non-drivable terrain", "Obstacle", "Stale")
    rows = [
        "# Terrain and occupancy legend",
        "",
        "Fused over the sequence (decision 0011). Evidence only, not a navigation guarantee. "
        "Unknown is never drivable.",
        "",
        "| Terrain state | RGB |",
        "| --- | --- |",
    ]
    rows += [
        f"| {name} | {_rgb(color)} |" for name, color in zip(names, TERRAIN_COLORS, strict=True)
    ]
    rows += [
        f"| Curb edge (neighbour higher than the step limit) | {_rgb(CURB_COLOR)} |",
        f"| Drop edge (neighbour lower than the step limit) | {_rgb(DROP_COLOR)} |",
        f"| Overhang (obstacle above vehicle clearance) | {_rgb(OVERHANG_COLOR)} |",
        "",
        "| Fused occupancy | RGB |",
        "| --- | --- |",
    ]
    rows += [
        f"| {state.name.lower()} | {_rgb(color)} |"
        for state, color in zip(FusedOccupancy, OCCUPANCY_COLORS, strict=True)
    ]
    rows += [
        "",
        "Elevation tab: Kalman ground height, blue (low) to red (high); only cells whose "
        "filter standard deviation is within the validity limit are drawn. Free-space tab: "
        "current-scan observed-free cells in blue over the single-frame geometry.",
    ]
    return "\n".join(rows)


def _height_colors(height_m: FloatArray) -> ByteArray:
    if not len(height_m):
        return np.empty((0, 3), dtype=np.uint8)
    low, high = np.percentile(height_m, [2, 98])
    t = np.clip((height_m - low) / max(float(high - low), 1e-3), 0, 1)
    red = np.clip(1.5 - np.abs(4 * t - 3), 0, 1)
    green = np.clip(1.5 - np.abs(4 * t - 2), 0, 1)
    blue = np.clip(1.5 - np.abs(4 * t - 1), 0, 1)
    return (np.column_stack([red, green, blue]) * 255).astype(np.uint8)


def fused_summary_markdown(fused: FusedMapView) -> str:
    summary = fused.summary
    rows = [
        "## Fused map (temporal fusion, Kalman elevation)",
        "",
        f"Published cells: {summary.published_cells:,} | Fixed allocation: "
        f"{summary.allocated_bytes / 1e6:.1f} MB, constant over the sequence",
        "",
        "| Terrain | Cells |",
        "| --- | ---: |",
    ]
    rows += [
        f"| {state.name.lower().replace('_', '-')} | {count:,} |"
        for state, count in zip(TerrainState, summary.terrain_counts, strict=True)
    ]
    rows += [
        "",
        f"Curb edges: {summary.curb_cells:,} | Drop edges: {summary.drop_cells:,} | "
        f"Overhangs: {summary.overhang_cells:,}",
        "",
        "| Occupancy | Cells |",
        "| --- | ---: |",
    ]
    rows += [
        f"| {state.name.lower()} | {count:,} |"
        for state, count in zip(FusedOccupancy, summary.occupancy_counts, strict=True)
    ]
    return "\n".join(rows)


class RerunView:
    def __init__(
        self,
        *,
        recording_path: Path | None = None,
        spawn: bool = False,
        config: MappingConfig | None = None,
    ) -> None:
        sizes_cm = (MappingConfig() if config is None else config).cell_sizes_cm
        self.cell_sizes_m = np.asarray(sizes_cm, dtype=np.float64) / 100
        if (recording_path is None) == (not spawn):
            raise ValueError("choose exactly one Rerun destination: recording or spawned viewer")
        self.recording = rr.RecordingStream("Drishti-2.5")
        if recording_path is not None:
            self.recording.save(recording_path)
        else:
            self.recording.spawn()
        self.recording.log("world", rr.ViewCoordinates.FLU, static=True)
        self.recording.log(
            "world/semantics",
            rr.AnnotationContext(
                [
                    rr.AnnotationInfo(id=index, label=name, color=color.tolist())
                    for index, (name, color) in enumerate(
                        zip(CLASS_NAMES, _semantic_palette(), strict=True)
                    )
                ]
            ),
            static=True,
        )
        self.recording.log(
            "semantic_legend",
            rr.TextDocument(semantic_legend_markdown(), media_type="text/markdown"),
            static=True,
        )
        self.recording.log(
            "terrain_legend",
            rr.TextDocument(terrain_legend_markdown(), media_type="text/markdown"),
            static=True,
        )
        self.recording.send_blueprint(
            rrb.Blueprint(
                rrb.Horizontal(
                    rrb.Tabs(
                        rrb.Spatial3DView(
                            name="Geometry",
                            origin="world",
                            contents=["world/geometry/**"],
                            eye_controls=rrb.EyeControls3D(
                                position=(0, -70, 70), look_target=(0, 0, 0), eye_up=(0, 0, 1)
                            ),
                        ),
                        rrb.Spatial3DView(
                            name="Top-down",
                            origin="world",
                            contents=["world/geometry/**"],
                            eye_controls=rrb.EyeControls3D(
                                position=(0, 0, 80), look_target=(0, 0, 0), eye_up=(1, 0, 0)
                            ),
                        ),
                        rrb.Spatial3DView(
                            name="Semantics", origin="world", contents=["world/semantics/**"]
                        ),
                        rrb.Spatial3DView(
                            name="Terrain (fused)",
                            origin="world",
                            contents=["world/fused/terrain/**"],
                            eye_controls=rrb.EyeControls3D(
                                position=(0, 0, 80), look_target=(0, 0, 0), eye_up=(1, 0, 0)
                            ),
                        ),
                        rrb.Spatial3DView(
                            name="Occupancy (fused)",
                            origin="world",
                            contents=["world/fused/occupancy/**"],
                            eye_controls=rrb.EyeControls3D(
                                position=(0, 0, 80), look_target=(0, 0, 0), eye_up=(1, 0, 0)
                            ),
                        ),
                        rrb.Spatial3DView(
                            name="Elevation (Kalman)",
                            origin="world",
                            contents=["world/fused/elevation/**"],
                        ),
                        rrb.Spatial3DView(
                            name="Free space (current scan)",
                            origin="world",
                            contents=["world/visibility/**", "world/geometry/cells"],
                            eye_controls=rrb.EyeControls3D(
                                position=(0, 0, 80), look_target=(0, 0, 0), eye_up=(1, 0, 0)
                            ),
                        ),
                        rrb.Spatial3DView(
                            name="Accepted raw points", origin="world", contents=["world/raw/**"]
                        ),
                        rrb.Spatial3DView(
                            name="Estimated motion", origin="world", contents=["world/motion/**"]
                        ),
                        rrb.TextDocumentView(
                            name="Semantic class legend", origin="semantic_legend"
                        ),
                        rrb.TextDocumentView(name="Terrain legend", origin="terrain_legend"),
                    ),
                    rrb.Vertical(
                        rrb.TextDocumentView(name="Evidence and limitations", origin="status"),
                        rrb.TimeSeriesView(name="Processing latency (ms)", origin="timing"),
                        row_shares=[3, 1],
                    ),
                    column_shares=[2, 1],
                ),
                rrb.BlueprintPanel(expanded=False),
                rrb.TimePanel(timeline="dataset_time", playback_speed=1.0),
                auto_layout=False,
                auto_views=False,
            )
        )

    def publish(self, result: FrameResult) -> None:
        snapshot = result.snapshot
        stream = self.recording
        stream.set_time("frame", sequence=snapshot.frame_id)
        stream.set_time("dataset_time", duration=snapshot.timestamp_s)
        geometry = cell_geometry(snapshot)
        stream.log(
            "world/geometry/cells",
            rr.Boxes3D(
                centers=geometry.centers_m,
                sizes=geometry.sizes_m,
                colors=geometry.colors,
                fill_mode=rr.components.FillMode.MajorWireframe,
                radii=rr.Radius.ui_points(0.35),
            ),
        )
        ground = snapshot.ground_valid
        stream.log(
            "world/geometry/ground",
            rr.Boxes3D(
                centers=np.column_stack(
                    [snapshot.centers_xy_m[ground], snapshot.ground_height_cm[ground] / 100]
                ),
                sizes=np.column_stack(
                    [
                        snapshot.size_m[ground],
                        snapshot.size_m[ground],
                        np.zeros(np.count_nonzero(ground)),
                    ]
                ),
                colors=[71, 185, 160],
                fill_mode=rr.components.FillMode.Solid,
            ),
        )
        stream.log(
            "world/semantics/cells",
            rr.Boxes3D(
                centers=geometry.centers_m,
                sizes=geometry.sizes_m,
                colors=_semantic_palette()[snapshot.semantic],
                class_ids=snapshot.semantic,
                fill_mode=rr.components.FillMode.MajorWireframe,
                radii=rr.Radius.ui_points(0.35),
            ),
        )
        stream.log(
            "world/raw/points",
            rr.Points3D(
                result.observations.points_map_m,
                colors=[175, 182, 191],
                radii=0.025,
            ),
        )
        self._publish_visibility(result)
        self._publish_fused(result.fused)
        if result.estimated_motion is not None:
            palette = np.array([[140, 140, 140], [65, 190, 130], [245, 95, 65]], dtype=np.uint8)
            stream.log(
                "world/motion/points",
                rr.Points3D(
                    result.observations.points_map_m,
                    colors=palette[result.estimated_motion.point_state],
                    radii=0.035,
                ),
            )
        if snapshot.mode == Mode.ORACLE:
            badge = "ORACLE semantics and motion. Mapping evaluation, not autonomous perception."
        elif snapshot.mode == Mode.LEARNED:
            badge = "LEARNED point semantics from a checkpoint. Object motion is unknown."
        else:
            badge = "LABEL-FREE geometry. Semantic and motion classes are unknown."
        if result.estimated_motion is not None:
            badge = (
                "LEARNED semantics. Motion is an uncalibrated observed-centre displacement "
                "estimate: grey unknown, green stationary, red moving."
            )
        status = (
            f"# Drishti-2.5\n\n**{badge}**\n\n"
            f"Sequence: {snapshot.sequence} | Frame: {snapshot.frame_id}\n\n"
            f"Pose: {snapshot.pose_source.value} | Ground: {snapshot.ground_method}\n\n"
            + (
                "**Geometry and semantic tabs: single-frame cells. Terrain, occupancy and "
                "elevation tabs: fused sequence map (evidence, not a navigation guarantee).**"
                if result.fused is not None
                else "**Single-frame cells. No temporal fusion, clearance or passability verdict.**"
            )
            + "\n\nPlayback uses dataset time, not measured rendering or processing FPS.\n\n"
            "Deskew unavailable: scans have no point timestamps.\n\n"
            "Teal: supported ground. Orange: nonground return. Gray: unclassified. "
            "Purple: conflicting ground heights. Boxes show observed height envelopes, "
            "not solid occupied volumes or free-space proofs.\n\n"
            f"Cells: {len(snapshot.point_count):,} | Snapshot arrays: {snapshot.array_bytes:,} B"
            " (not process memory)\n\n"
            f"Accepted: {result.accounting.accepted_points:,} / {result.accounting.input_points:,}"
            f" | Projection collisions retained: {result.accounting.projection_collisions:,}\n\n"
            f"Invalid geometry: {result.accounting.invalid_geometry:,} | "
            f"Outside ROI: {result.accounting.outside_roi:,} | "
            f"Outside height: {result.accounting.outside_height:,}\n\n"
            f"Invalid intensity: {result.accounting.invalid_intensity:,}\n\n"
            f"{semantic_summary_markdown(result)}\n\n"
            + (f"{fused_summary_markdown(result.fused)}\n\n" if result.fused is not None else "")
            + ("No accepted points in this frame." if not len(snapshot.point_count) else "")
        )
        stream.log("status", rr.TextDocument(status, media_type="text/markdown"))
        for name, value in asdict(result.timings).items():
            if value is not None:
                stream.log(f"timing/{name}", rr.Scalars(value))

    def _publish_visibility(self, result: FrameResult) -> None:
        visibility = result.visibility
        if visibility is None:
            return
        size = self.cell_sizes_m[visibility.free_level]
        centers = (visibility.free_indices + 0.5) * size[:, None]
        snapshot = result.snapshot
        height = (
            float(np.median(snapshot.ground_height_cm[snapshot.ground_valid])) / 100
            if np.any(snapshot.ground_valid)
            else 0.0
        )
        self.recording.log(
            "world/visibility/free",
            rr.Boxes3D(
                centers=np.column_stack([centers, np.full(len(centers), height)]),
                sizes=np.column_stack([size, size, np.zeros(len(size))]),
                colors=OCCUPANCY_COLORS[FusedOccupancy.FREE],
                fill_mode=rr.components.FillMode.Solid,
            ),
        )

    def _publish_fused(self, fused: FusedMapView | None) -> None:
        if fused is None:
            return
        stream = self.recording
        size = fused.size_m
        ground_z = fused.ground_height_m
        flat = np.column_stack([size, size, np.zeros(len(size))])
        floor = np.column_stack([fused.centers_xy_m, ground_z])
        stream.log(
            "world/fused/terrain/cells",
            rr.Boxes3D(
                centers=floor,
                sizes=flat,
                colors=TERRAIN_COLORS[fused.terrain],
                fill_mode=rr.components.FillMode.Solid,
            ),
        )
        for name, flag, color in (
            ("curb", TerrainFlag.CURB, CURB_COLOR),
            ("drop", TerrainFlag.DROP, DROP_COLOR),
            ("overhang", TerrainFlag.OVERHANG, OVERHANG_COLOR),
        ):
            mask = (fused.flags & flag) > 0
            stream.log(
                f"world/fused/terrain/{name}",
                rr.Points3D(
                    np.column_stack([fused.centers_xy_m[mask], ground_z[mask] + 0.05]),
                    colors=color,
                    radii=np.maximum(size[mask] * 0.6, 0.05),
                ),
            )
        obstacle = fused.terrain == TerrainState.OBSTACLE
        low = fused.obstacle_low_m[obstacle]
        high = np.maximum(fused.obstacle_high_m[obstacle], low + 0.05)
        stream.log(
            "world/fused/terrain/obstacles",
            rr.Boxes3D(
                centers=np.column_stack([fused.centers_xy_m[obstacle], (low + high) / 2]),
                sizes=np.column_stack([size[obstacle], size[obstacle], high - low]),
                colors=TERRAIN_COLORS[TerrainState.OBSTACLE],
                fill_mode=rr.components.FillMode.MajorWireframe,
            ),
        )
        stream.log(
            "world/fused/occupancy/cells",
            rr.Boxes3D(
                centers=floor,
                sizes=flat,
                colors=OCCUPANCY_COLORS[fused.occupancy],
                fill_mode=rr.components.FillMode.Solid,
            ),
        )
        valid = fused.ground_valid
        stream.log(
            "world/fused/elevation/ground",
            rr.Boxes3D(
                centers=floor[valid],
                sizes=flat[valid],
                colors=_height_colors(ground_z[valid]),
                fill_mode=rr.components.FillMode.Solid,
            ),
        )

    def flush(self) -> None:
        self.recording.flush()

    def close(self) -> None:
        self.flush()
        self.recording.disconnect()
