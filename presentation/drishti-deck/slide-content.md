# Drishti-2.5 - four-slide pitch content

Prepared 2026-09-29 for SIH26053 (DRDO, Smart Vehicles). Every number below is either measured
by Drishti in this repository, reported by a named primary source, or marked as a calculation.
Nothing is estimated. Status words on the slides: PROVEN / MEASURED (done and evidenced),
PROPOSED (designed, not built), TEST / VALIDATE (needs prototype, hardware or field work).

Deck pages follow the team deck: 2 Proposed Solution, 3 Technical Approach, 4 Feasibility &
Viability, 5 Impact & Benefits. The editable deck is built by `build.mjs` in this folder.

---

## Slide 2 - Proposed Solution

### Main message
Drishti-2.5 turns each raw LiDAR scan into a compact, labelled 2.5D terrain map: sharp near the
vehicle, lighter far away.

### Exact slide content

**Title:** PROPOSED SOLUTION

**Solution line:** Drishti-2.5 turns every raw LiDAR scan into a compact, labelled 2.5D terrain
map - sharp near the vehicle, lighter far away.

**Problem (left chip):** 3D point clouds are too heavy for real-time use. Flat 2D grids lose
kerbs, ditches and overhangs.

**Visual flow:** RAW LIDAR SCAN (~124k 3D points per scan) → DRISHTI-2.5 (find ground · label
points · build adaptive grid) → 2.5D MAP (height + class in every cell)

**Ring legend (on the visual):** 5 cm cells to 10 m · 10 cm cells to 25 m · 50 cm cells to 100 m

**Capability cards:**

1. **Ground Separation** - Separates ground from everything above it, so terrain height is
   correct.
2. **Point-Level Labels** - Labels each laser point as road, vehicle, person, pole or 15
   other classes.
3. **Foveated 2.5D Grid** - Uses fine 5 cm cells near the vehicle, growing to 50 cm at 100 m.
4. **Obstacle Evidence** - Groups labelled points into obstacles; tracks vehicles and people over
   time.

**Differentiator ribbon:** Every point lands in exactly one cell - no gaps or double counts at
ring boundaries. Unknown stays unknown, never silently marked safe.

**Built for:** DRDO UGV perception teams and autonomy developers.

### Visual structure
- Header, then a one-line solution statement across the top with a small problem chip on the left.
- Dominant visual (middle band): three linked panels, left to right. Left: a scattered-dot point
  cloud. Middle: the Drishti-2.5 block with three mini-steps. Right: a top-down ring diagram
  with a vehicle at the centre and three concentric bands (5 / 10 / 50 cm), labelled "not to scale".
- Bottom: four equal capability cards with line icons, colour-coded to the pipeline stages used
  on slide 3 (orange ground, green labels, gold grid, purple obstacles).
- A thin navy differentiator ribbon beneath the cards.

### Speaker notes
"A LiDAR gives about 124 thousand 3D points every scan. That is too heavy to process at full
detail, but flattening it into a 2D grid throws away the heights that reveal kerbs and ditches.
Drishti-2.5 takes the middle path the problem statement asks for: a 2.5D map that keeps height and
class in every cell, with 5 centimetre cells close to the vehicle and 50 centimetre cells out to
100 metres, like human foveated vision. It separates ground, labels every point with a deep
network, builds the adaptive grid and groups obstacles. Two design rules matter: every point goes
to exactly one cell, so nothing is lost or double counted where rings meet, and anything the system
is unsure about stays marked unknown."

### Evidence
| Claim | Source |
| --- | --- |
| Heavy 3D processing and 2D height loss is the stated problem; 5 cm within 10 m and 50 cm to 100 m are the suggested cells | `SIH26053.md` (official problem statement) |
| ~124k points per scan | MEASURED: mean 123,558 accepted points over 20 sequence 08 scans, [experiment 0031](../../docs/research/experiments/0031-adaptive-vs-uniform-grid.md) |
| 5/10/50 cm rings to 10/25/100 m | `Drishti-2.5/configs/default.toml` |
| 19 classes | SemanticKITTI learning classes; [experiment 0025](../../docs/research/experiments/0025-t003-full-sequence08.md) |
| Exactly-one-cell ownership, integer indices, unknown never becomes a class | `Drishti-2.5/AGENTS.md` contracts, `docs/interfaces.md`, unit tests (87 passed, `docs/testing.md`) |
| Obstacle candidates and cross-frame track IDs | Experiments [0028](../../docs/research/experiments/0028-t004-saved-prediction-eval.md) and [0030](../../docs/research/experiments/0030-t005-association-eval.md) |

---

## Slide 3 - Technical Approach

### Main message
One shared pipeline carries a raw scan to a labelled 2.5D map and obstacle evidence, and every
stage is already running and measured.

### Exact slide content

**Title:** TECHNICAL APPROACH

**Subtitle:** One pipeline: raw scan in → labelled 2.5D map out

**Pipeline (IN → PROCESS → OUT):**

| # | Stage | What it does | Technology |
| --- | --- | --- | --- |
| 1 | Scan Input | Reads each scan with time and pose; rejects invalid points. | 64-beam LiDAR replay · ROS 2 input proposed |
| 2 | Ground Segmentation | Fits local ground patches to split ground from everything above. | Patchwork++ (IROS 2022) |
| 3 | Semantic Labels | Deep network gives each point one of 19 classes; unknown kept. | FRNet (IEEE TIP 2025), pinned checkpoint |
| 4 | Adaptive 2.5D Grid | Places every point in exactly one ring cell by integer index. | 5 / 10 / 50 cm rings |
| 5 | Obstacle Evidence | Clusters labelled points; keeps vehicle and person IDs across frames. | Candidates + track IDs |
| 6 | Map & Dashboard | Publishes a read-only map, audit record and colour-coded 3D view. | Rerun viewer |

**Each cell stores:** ground height · obstacle height span · class evidence · point count ·
intensity · ambiguity flag

**Compute today (laptop CPU, offline):**
- MEASURED: geometry path median 83 ms per scan over 1,000 scans.
- MEASURED: FRNet on CPU ~7.2 s per scan, so a GPU is required.
- PROPOSED: NVIDIA GPU path (coded, not yet validated) and ROS 2 live input.

### Visual structure
- A single horizontal six-stage pipeline across the slide, rounded pastel nodes, navy arrows,
  one colour per category: blue input, orange geometry, green learning, gold grid, purple
  obstacles, blue output. Each node: number, icon, 2-3 word title, one line, technology tag.
- Three small lane labels above: IN (stage 1), PROCESS (stages 2-5), OUT (stage 6).
- Lower left: "Each cell stores" chip row, a stylised cell card.
- Lower right: "Compute today" card with status chips.

### Speaker notes
"Here is the pipeline. A scan comes in with its timestamp and pose, and invalid points are
rejected. Patchwork++, a published ground-segmentation method, splits ground from everything
above it. FRNet, a published LiDAR segmentation network, labels every point with one of 19 classes;
anything it cannot classify stays unknown. The adaptive grid then puts every point into exactly one
cell using integer indices, so rings never overlap. Labelled points are grouped into obstacles, and
vehicles and people keep an ID across frames. Out comes a read-only map snapshot and a colour-coded
3D view. Everything runs offline on a laptop CPU today. The geometry path takes a median 83
milliseconds a scan; the neural network takes about 7 seconds on CPU, so real-time use needs a GPU.
We have coded a GPU path but not yet validated it on NVIDIA hardware."

### Evidence
| Claim | Source |
| --- | --- |
| Patchwork++ ground segmentation, IROS 2022, open code | [arXiv 2207.11919](https://arxiv.org/abs/2207.11919); [repository](https://github.com/url-kaist/patchwork-plusplus) |
| FRNet, IEEE TIP 2025, Apache-2.0 code, SemanticKITTI weights | [FRNet authors' repository](https://github.com/Xiangxu-0103/FRNet) |
| Checkpoint pinned by SHA-256 | [experiment 0025](../../docs/research/experiments/0025-t003-full-sequence08.md) |
| Cell fields | `Drishti-2.5/src/drishti/mapping.py` (`MapSnapshot`) |
| Geometry path median 83.13 ms, 1,000 sequence 08 scans | E-044, [experiment 0019](../../docs/research/experiments/0019-paced-inprocess-screen.md); geometric mode only, no model |
| FRNet CPU p50 7,177 ms per scan | E-052, [experiment 0026](../../docs/research/experiments/0026-t003-cpu-semantic-verification.md) |
| CUDA path coded, no GPU parity/timing | `docs/open-items.md` O-001 |
| ROS 2 PointCloud2 carries fields, stamp and frame | [official message definition](https://raw.githubusercontent.com/ros2/common_interfaces/rolling/sensor_msgs/msg/PointCloud2.msg) |

---

## Slide 4 - Feasibility & Viability

### Main message
The prototype already runs on real data with open tools; the remaining steps to the field are
named, measurable and in order.

### Exact slide content

**Title:** FEASIBILITY AND VIABILITY

**Subtitle:** Working replay prototype. A staged path to field deployment.

**Four green cards:**

1. **Technical Feasibility** - Every stage already runs end to end on real LiDAR data.
   - PROVEN: Patchwork++ and FRNet are published, open and integrated.
   - Evidence: **67.55% mIoU** on 4,071 held-out scans (authors report 68.7%).
2. **Operational Feasibility** - Runs fully offline on the vehicle's own computer.
   - PROVEN: no cloud or network at runtime.
   - TEST: dust, rain, off-road terrain, live sensor and calibration.
   - Evidence: **69.1% mIoU within 20 m**, 15.7% beyond 50 m.
3. **Economic Viability** - Prototype needs a laptop and open software, not new rigs.
   - PROVEN: open-source stack, public data, no paid APIs.
   - VALIDATE: vehicle GPU cost; dataset and model licence terms.
   - Evidence: **33.6% smaller** per-scan map than a uniform 5 cm grid.
4. **Scalability** - Rings, radii and sensors change by config, not code.
   - PROVEN: grid rings set in a validated config file.
   - PROPOSED: ROS 2 adapter for other LiDARs; GPU path.
   - Evidence: **~31× fewer cells** than uniform 5 cm at full 100 m coverage (calculated).

**Blue stack:**

- **Long-Term Viability** - Every result is pinned, hashed and repeatable.
  - PROVEN: 87 automated tests, locked dependencies, checkpoint SHA-256.
  - PROPOSED: regression gates and named maintainers for each release.
- **Path to Field** - PROTOTYPE (done: real-data replay) → VALIDATION (now: held-out metrics,
  GPU timing) → FIELD TRIAL (next: live sensor, terrain, weather) → DEPLOYMENT (vehicle
  integration). Marker: "We are here" between Prototype and Validation.
- **Defence Fit** - DRDO VRDE lists AI-based perception and AI-algorithm validation among UGV
  technology tasks. Relevance only, not endorsement.

### Visual structure
- Follows the team deck page 4: four tall green cards on the left (icon, heading, bold hook,
  status rows, one highlighted evidence number at the bottom), stacked blue cards on the right.
- The "Path to Field" card is a vertical four-step maturity ladder with a "We are here" marker.
- Footer legend for the three status colours.

### Speaker notes
"Is it practical? Technically, yes: every stage runs end to end on real LiDAR data today. On all
4,071 scans of the standard held-out sequence, the labelling scores 67.55 percent mIoU, close to
the 68.7 percent the FRNet authors report. Operationally, it needs no network. It is strongest near
the vehicle, 69 percent within 20 metres, and weak beyond 50 metres, which is why the grid is
coarse there and why field trials come next. Economically, the prototype needs only a laptop and
open software, and the adaptive grid stored 33.6 percent less map data per scan than a uniform
5 centimetre grid. Ring sizes and sensors are configuration, and every result is hashed and
repeatable. We are between prototype and validation. The next gates are GPU timing, live sensor
input and field trials in dust, rain and rough terrain."

### Evidence
| Claim | Source |
| --- | --- |
| 67.55% mIoU (0.6754690443), 4,071 sequence 08 scans, 19 classes, 92.28% labelled accuracy | E-051, [experiment 0025](../../docs/research/experiments/0025-t003-full-sequence08.md) |
| FRNet authors report 68.7% SemanticKITTI val mIoU | [FRNet repository](https://github.com/Xiangxu-0103/FRNet) results table (authors' conditions) |
| Sequence 08 is the labelled held-out validation sequence | Labels for 00-10 are public ([dataset page](https://semantic-kitti.org/dataset.html)); the official API split config assigns 08 to validation ([semantic-kitti-api](https://github.com/PRBonn/semantic-kitti-api), `config/semantic-kitti.yaml`); [experiment 0025](../../docs/research/experiments/0025-t003-full-sequence08.md) |
| 69.1% within 20 m, 54.3% at 20-50 m, 15.7% beyond 50 m | [experiment 0025](../../docs/research/experiments/0025-t003-full-sequence08.md) range table |
| No mandatory cloud or network at runtime | `Drishti-2.5/src/drishti/learned.py`; E-052 |
| 33.6% fewer cells and bytes, 20 scans | E-058, [experiment 0031](../../docs/research/experiments/0031-adaptive-vs-uniform-grid.md) |
| ~31× fewer cells at full coverage | DESIGN CALCULATION in experiment 0031: 12,566,371 vs 408,407 cells |
| SemanticKITTI is CC BY-NC-SA (non-commercial) | [dataset page](https://semantic-kitti.org/dataset.html) |
| 87 tests passed, checkpoint SHA-256, locked `uv.lock` | `docs/testing.md`; experiment 0025 |
| DRDO VRDE tasks: "AI Based Perception for Autonomous Driving", "Simulation software for AI algorithms validation", "Data Set Generation for UGV application" | [DRDO UGV technology foresight](https://drdo.gov.in/drdo/en/offerings/technology-foresight/ugv), checked 2026-09-29 |

---

## Slide 5 - Impact & Benefits

### Main message
If Drishti-2.5 works in the field, six groups gain, and each benefit is tied to a mechanism
already built or clearly marked as still to validate.

### Exact slide content

**Title:** IMPACT AND BENEFITS

Top row (linked by arrows): Economic → Environmental → Strategic / Indigenization.
Bottom row: Field Operators & Reconnaissance UGVs · Robotics Researchers & Students · Civilian
Autonomous Mobility. Caveats in italics.

1. **Economic**
   - 33.6% less map data per scan than a uniform 5 cm grid (measured).
   - Smaller maps suit lower-cost embedded computers *(hardware to validate)*.
   - One reusable pipeline avoids rebuilding perception per platform.
   - Height evidence may reduce terrain-related vehicle damage *(field trials needed)*.
2. **Environmental**
   - Less map data to store and process for every scan.
   - Lower compute load can reduce power draw *(not yet measured)*.
   - Could extend battery operating time *(to validate on a vehicle)*.
   - Runs offline: no cloud servers or data transfer.
3. **Strategic / Indigenization**
   - Team-owned pipeline Indian engineers can audit, retrain and extend.
   - Aligns with DRDO VRDE's listed AI perception and validation tasks.
   - Config-driven grid fits many vehicle platforms *(ROS 2 adapter proposed)*.
   - Dual-use: defence UGVs and civilian autonomous mobility.
4. **Field Operators & Reconnaissance UGVs**
   - 5 cm cells within 10 m keep near-field height detail where kerbs, mounds and trenches appear.
   - Colour-coded map with flagged uncertain cells supports operator awareness in rough terrain
     *(field trials needed)*.
5. **Robotics Researchers & Students**
   - No need to rebuild mapping and evaluation code for each experiment.
   - Reusable mapping core with hashed runs and official scoring supports adaptive perception,
     semantic mapping and navigation research.
6. **Civilian Autonomous Mobility**
   - Road vehicles meet potholes, pedestrians and unexpected obstacles.
   - Tested on real urban driving scans: labels people, vehicles and poles, with height per cell.
   - Adaptive detail lowers map data, which may make perception more affordable
     *(cost not estimated)*.

**Honesty line:** Benefits describe mechanisms already built. Items in italics, and field
outcomes such as safety and mission time, still need validation.

### Visual structure
- Follows the supplied reference: a 2 × 3 grid of rounded cards, each with its own accent colour
  (red, green, blue on top; orange, purple, teal below), a tinted header strip, a circled line
  icon and matching coloured bullets. Arrows link the three top cards.
- Caveats are italic in the card's accent colour, so judges can see at a glance what is proven.

### Changes from the reference, and why
- "Lower-cost embedded hardware", "lower power", "longer battery" and "reduced vehicle damage"
  are kept but marked as still to validate: none has been measured.
- "Reduced thermal-management requirements" was dropped: no evidence.
- "Mines" was removed from the field-operator card: Drishti has no mine data or detector.
- "Reduces dependence on foreign perception software" became "team-owned pipeline Indian engineers
  can audit, retrain and extend": the pipeline uses open components from overseas authors
  (Patchwork++, FRNet), so the stronger claim would be inaccurate.
- "Lowers the risk of vehicle immobilization" was dropped: not measured.
- "Robotics Researches" corrected to "Robotics Researchers".

### Speaker notes
"What changes if this works? Economically, the adaptive grid already stores 33.6 percent less map
data per scan than a uniform 5 centimetre grid, which points toward cheaper embedded computers,
though we still have to validate that on hardware. Less compute can also mean less power and
longer battery life; we have not measured that yet, and the slide says so in italics.
Strategically, it is a team-owned pipeline that Indian engineers can audit and retrain, aligned
with the AI perception and validation tasks DRDO's VRDE lists for unmanned ground vehicles. For
field operators, 5 centimetre cells near the vehicle keep the height detail where kerbs, mounds and
trenches appear, and uncertain cells are flagged rather than shown as safe. Researchers get a
reusable mapping core with repeatable, hashed evaluation. And the same approach applies to civilian
vehicles: we have tested it on real urban driving scans. Anything in italics still needs field or
hardware validation."

### Evidence
| Claim | Source |
| --- | --- |
| 33.6% less map data per scan | E-058, [experiment 0031](../../docs/research/experiments/0031-adaptive-vs-uniform-grid.md) |
| 5 cm cells within 10 m | `Drishti-2.5/configs/default.toml` |
| Per-cell height, class evidence, ambiguity flags | `Drishti-2.5/src/drishti/mapping.py` |
| Runs offline | `Drishti-2.5/src/drishti/learned.py`; E-052 |
| Hashed runs and official scoring | [experiment 0025](../../docs/research/experiments/0025-t003-full-sequence08.md) |
| Real urban driving scans | SemanticKITTI, built on KITTI odometry sequences, [dataset page](https://semantic-kitti.org/dataset.html) |
| VRDE task list | [DRDO UGV technology foresight](https://drdo.gov.in/drdo/en/offerings/technology-foresight/ugv) |
| Not measured: power, battery, hardware cost, vehicle damage, operator workload | Listed in evidence gaps below |

---

## 1. Overall story

**Problem → Foveated 2.5D map → Running, measured pipeline → Staged path to the field →
Terrain detail where it matters.**

## 2. Judge takeaway

"Drishti-2.5 already turns real LiDAR into a compact, labelled 2.5D terrain map."

## 3. Likely judge questions

| # | Question | Answer with |
| --- | --- | --- |
| 1 | Is this real-time? | Not yet, and we say so. Geometry path median 83 ms per scan on a laptop CPU (1,000 scans); FRNet is ~7.2 s on CPU. FRNet authors report 29.1 FPS under their own (GPU) conditions, not ours. Our CUDA path is coded but unvalidated. Next gate: 100 ms on an NVIDIA host. |
| 2 | How accurate is it, and on what data? | 67.55% mIoU and 92.28% labelled-point accuracy on all 4,071 held-out sequence 08 scans, official evaluator. Authors report 68.7%. By range: 69.1% within 20 m, 15.7% beyond 50 m. |
| 3 | You used a pretrained model. What is your innovation? | The contribution is the variable-resolution 2.5D engine and its contracts: integer ring lattice with exactly-one-cell ownership, point accounting that conserves every point, unknown kept distinct, obstacle evidence and one shared, auditable path. The model is a replaceable stage. |
| 4 | Does it detect objects well? | Panoptic baseline PQ 0.587 over 19 classes; car 0.90, person 0.76. Weaknesses: motorcyclist 0.00 and far objects (8 of 30 eligible 50 m+ segments). Tracking baseline: 69 ID switches over 200 frames. These are baselines, not acceptance. |
| 5 | What memory saving did you prove? | 33.6% fewer stored cells and bytes than a uniform 5 cm grid on 20 scans (single frame, logical payload). Full-coverage calculation: ~31× fewer cells. We have not yet compared against a 3D voxel map or measured process memory. |
| 6 | What hardware does a vehicle need? | Today: a laptop CPU for replay. For real time, an NVIDIA GPU is needed for the network; exact module, power and cost are not yet measured. LiDAR: tested only on SemanticKITTI's 64-beam data. |
| 7 | Will it work off-road, in dust or rain? | Not yet shown. SemanticKITTI is urban and suburban driving. Field trials for terrain, weather and calibration are the planned next stage. Patchwork++ adapts its ground parameters online, which helps but is not proof. |
| 8 | How will it connect to a real vehicle? | Proposed ROS 2 adapter: PointCloud2 already carries point fields, timestamp and frame ID. Calibration, time sync and live-ingest contracts must be defined and tested first. |
| 9 | How is this better than existing tools like elevation mapping or 3D occupancy maps? | Uniform elevation maps spend the same cell size everywhere; 3D voxel maps keep height but at large memory. Drishti keeps per-cell height and semantic evidence with range-adaptive cells and exactly-one-cell ownership. A head-to-head benchmark is not yet done. |
| 10 | Can you use this commercially or in defence? | FRNet code is Apache-2.0; SemanticKITTI data is CC BY-NC-SA (non-commercial). Checkpoint weight terms need confirmation, and deployment would need retraining on permitted, preferably Indian terrain data. |

## 4. Evidence gaps (not hidden)

| Gap | Needs | Current status |
| --- | --- | --- |
| Complete-path 100 ms real-time | Performance benchmarking on an NVIDIA host | NOT VERIFIED; CPU learned path ~7.2 s per scan |
| GPU path correctness and speed | Hardware validation | CUDA code integrated, no GPU parity or timing |
| Off-road, dust, rain, night | Field testing with a live sensor | NOT VERIFIED; only SemanticKITTI driving data |
| Other LiDARs (16/32/128 beam) | Dataset and hardware validation | NOT VERIFIED; 64-beam only |
| Live input, calibration, time sync | Prototype testing, ROS 2 adapter | PROPOSED; no live ingest exists |
| Kerbs, potholes, overhangs as obstacles | Independent annotated dataset | Contract tests only; no held-out recall |
| Temporal map fusion across frames | Prototype and validation | Single-frame maps only |
| Motion and velocity | Prototype and validation | Track IDs only; velocity unknown |
| Free space and navigation safety | Prototype, validation, field testing | Not claimed; evidence-only output |
| Memory versus a 3D voxel map; process memory | Performance benchmarking | Only 2.5D uniform baseline, 20 scans, logical payload |
| Deployment hardware cost, power and battery time | Cost estimation, hardware validation | UNKNOWN; impact slide marks these in italics |
| Dataset and checkpoint rights for deployment | Licence review | SemanticKITTI non-commercial; weight terms unconfirmed |
| Continuous 4,071-scan state | Validation | Score combines two engine runs (793 + 3,278 scans) |
