from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import rerun as rr
import rerun.blueprint as rrb

from drishti.arrays import ByteArray, FloatArray
from drishti.contracts import Mode
from drishti.mapping import MapSnapshot
from drishti.pipeline import FrameResult
from drishti.semantics import CLASS_NAMES


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


class RerunView:
    def __init__(self, *, recording_path: Path | None = None, spawn: bool = False) -> None:
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
                            name="Accepted raw points", origin="world", contents=["world/raw/**"]
                        ),
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
        badge = (
            "ORACLE semantics and motion. Mapping evaluation, not autonomous perception."
            if snapshot.mode == Mode.ORACLE
            else "LABEL-FREE geometry. Semantic and motion classes are unknown."
        )
        status = (
            f"# Drishti-2.5\n\n**{badge}**\n\n"
            f"Sequence: {snapshot.sequence} | Frame: {snapshot.frame_id}\n\n"
            f"Pose: {snapshot.pose_source.value} | Ground: {snapshot.ground_method}\n\n"
            "**Single-frame cells. No temporal fusion, tracking, clearance "
            "or passability verdict.**"
            "\n\nPlayback uses dataset time, not measured rendering or processing FPS.\n\n"
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
            + ("No accepted points in this frame." if not len(snapshot.point_count) else "")
        )
        stream.log("status", rr.TextDocument(status, media_type="text/markdown"))
        for name, value in asdict(result.timings).items():
            stream.log(f"timing/{name}", rr.Scalars(value))

    def close(self) -> None:
        self.recording.flush()
        self.recording.disconnect()
