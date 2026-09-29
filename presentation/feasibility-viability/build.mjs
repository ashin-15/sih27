import pptxgen from "pptxgenjs";

const OUTPUT = "Drishti-Feasibility-and-Viability.pptx";
const TEAM = "AstroNex";
const PAGE_NUMBER = "4";
const HEADING_FONT = "Comic Sans MS";
const BODY_FONT = "Arial";

const C = {
  canvas: "F4F4F2",
  navy: "243B53",
  ink: "2E3A48",
  muted: "4A5563",
  green: "2F6B52",
  greenPale: "DCEEDB",
  blue: "2F5FA8",
  bluePale: "DDE8F7",
  orange: "C8742F",
  orangePale: "F6C98F",
  orangeInk: "6E3408",
  white: "FFFFFF",
};

const STATUS = {
  proven: { label: "PROVEN", fill: C.green, line: C.green, text: C.white },
  measured: { label: "MEASURED", fill: C.green, line: C.green, text: C.white },
  proposed: { label: "PROPOSED", fill: C.blue, line: C.blue, text: C.white },
  test: { label: "TEST", fill: C.orangePale, line: C.orange, text: C.orangeInk },
  validate: { label: "VALIDATE", fill: C.orangePale, line: C.orange, text: C.orangeInk },
};

const STEPS = [
  {
    icon: "layers",
    title: "Technical Foundation",
    hook: "Core building blocks already work together.",
    simple:
      "Drishti finds the ground, labels each laser point (road, car, wall...) and builds " +
      "a map that is detailed up close and coarser far away.",
    items: [
      ["proven", "Patchwork++ finds the ground; FRNet labels points - one pipeline."],
      ["measured", "67.55% mIoU label score on 4,071 real driving scans."],
    ],
  },
  {
    icon: "wifi-off",
    title: "Local Operation",
    hook: "Runs offline - no internet or cloud needed.",
    simple:
      "All processing happens on the computer itself, so it can work where there is no " +
      "network, such as remote terrain.",
    items: [
      ["proven", "Recorded LiDAR scans run locally after models are installed."],
      ["test", "Field trials: dust, rain, rough ground and sensor alignment."],
    ],
  },
  {
    icon: "laptop",
    title: "Economic Viability",
    hook: "Low cost: a laptop and free software.",
    simple:
      "We keep building and testing now, and buy special hardware only once the real " +
      "needs are known.",
    items: [
      ["proven", "Runs on an ordinary CPU with no cloud fees or paid APIs."],
      ["validate", "Vehicle hardware cost; licence terms for data and models."],
    ],
  },
  {
    icon: "truck",
    title: "Vehicle Integration",
    hook: "Built in blocks that plug into a vehicle.",
    simple:
      "Each step (read scan → find ground → label points → build map) is its own block, " +
      "so a live sensor feed can be added without rebuilding the rest.",
    items: [
      ["proposed", "ROS 2 adapters (standard robot software link) feed in live LiDAR."],
      ["test", "Vehicle speed, power, memory. Now ~7 s per scan on a laptop."],
    ],
  },
];

const UPGRADES = {
  icon: "git-branch",
  title: "Maintainable Upgrades",
  hook: "Every result can be traced and repeated.",
  simple: "Exact software versions and model files are locked, so anyone can rerun a test.",
  items: [
    ["proven", "Version locks and checkpoint hashes (file fingerprints) record what was tested."],
    ["proposed", "Before each upgrade, rerun all checks and have a named owner approve it."],
  ],
};

const NOTES = `Feasibility & Viability - speaker notes

30-second script
"Drishti already works as a replay prototype: it finds the ground, labels every LiDAR point and builds an adaptive map, all on one laptop with no internet. On 4,071 real driving scans the labelling scores 67.55 percent mIoU. It costs little to keep developing, and it is built in separate blocks so a live vehicle sensor can be plugged in through ROS 2. What is not proven yet: field conditions, real-time speed on vehicle hardware, deployment cost and licences. Those are our next tests."

Plain-language glossary
- LiDAR: a laser sensor that measures distance to millions of points around the vehicle.
- mIoU (mean intersection over union): for each class, the overlap between predicted and true points divided by their union, averaged over 19 classes. Higher is better.
- ROS 2: the standard open-source software framework robots use to pass sensor data between programs.
- Checkpoint hash: a fingerprint of the exact model file, so anyone can confirm they use the same model.

Colour cues: green = Proven/Measured, blue = Proposed, orange = Test/Validate. Every cue also carries a text label.

B. Evidence behind the claims

1. The core technologies exist and are integrated.
Patchwork++ has published ground-segmentation research and Python/C++ implementations. FRNet provides published LiDAR semantic-segmentation research and public code. Drishti's own evaluation records the 67.55% result, which measures point semantics, not navigation safety.
Sources: Patchwork++ paper (IROS 2022) https://arxiv.org/abs/2207.11919 and https://github.com/url-kaist/patchwork-plusplus ; FRNet authors' repository https://github.com/Xiangxu-0103/FRNet ; Drishti evaluation docs/research/experiments/0025-t003-full-sequence08.md (E-051, official mIoU 0.6754690443, 4,071 scans, 19 classes).

2. Local execution is demonstrated; field operation remains unverified.
Drishti loads local model files and processes recorded scans without a mandatory remote inference service. SemanticKITTI supplies annotated driving sequences, but benchmark success does not establish performance in defence terrain, adverse weather or live sensor conditions.
Sources: local inference implementation Drishti-2.5/src/drishti/learned.py ; official dataset description https://semantic-kitti.org/dataset.html

3. Prototyping has a practical resource basis; deployment economics remain open.
The existing laptop executes CPU inference. However, the recorded model-stage median is 7,177 ms per scan, so this does not establish real-time embedded deployment. FRNet declares an Apache-2.0 code license; SemanticKITTI declares noncommercial dataset terms. Neither establishes permission for every checkpoint or downstream use.
Sources: CPU measurements docs/research/experiments/0026-t003-cpu-semantic-verification.md (E-052) ; FRNet licensing https://github.com/Xiangxu-0103/FRNet ; dataset terms https://semantic-kitti.org/dataset.html

4. Vehicle integration has an identifiable engineering route.
ROS 2's PointCloud2 message carries point fields, acquisition time and coordinate-frame information. This supports the proposed adapter approach. Drishti still needs live ingestion, calibration, synchronization and target-hardware validation.
Sources: official ROS 2 message definition https://raw.githubusercontent.com/ros2/common_interfaces/rolling/sensor_msgs/msg/PointCloud2.msg ; current interface boundaries docs/interfaces.md

5. Maintenance mechanisms exist; sustained ownership needs definition.
The repository contains dependency locks, source/checkpoint checks and automated validation. These support traceable upgrades. Maintainer ownership, release procedures and support funding remain unresolved.
Sources: verification record docs/research/experiments/0026-t003-cpu-semantic-verification.md ; open items docs/open-items.md

Defence relevance: DRDO explicitly lists AI perception, autonomous navigation and algorithm-validation simulation among UGV technology tasks. This establishes application relevance, not endorsement or procurement commitment.
Source: DRDO UGV technology foresight https://drdo.gov.in/drdo/en/offerings/technology-foresight/ugv`;

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.title = "Feasibility and Viability";
pptx.subject = "Drishti 2.5 - SIH26053";
pptx.author = TEAM;

const slide = pptx.addSlide();
slide.background = { color: C.canvas };

const text = (value, opts) =>
  slide.addText(value, { fontFace: BODY_FONT, margin: 0, valign: "top", ...opts });
const icon = (name, x, y, size) =>
  slide.addImage({ path: `assets/icons/${name}.png`, x, y, w: size, h: size });
const roundBox = (x, y, w, h, fill, line = C.navy, radius = 0.12) =>
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h, rectRadius: radius, fill: { color: fill }, line: { color: line, width: 1.25 },
  });

const chip = (status, x, y, w = 0.86) => {
  const s = STATUS[status];
  slide.addShape(pptx.ShapeType.roundRect, {
    x, y, w, h: 0.22, rectRadius: 0.06, fill: { color: s.fill }, line: { color: s.line, width: 1 },
  });
  text(s.label, {
    x, y, w, h: 0.22, fontSize: 8, bold: true, color: s.text,
    align: "center", valign: "middle", charSpacing: 1,
  });
};

const CHIP_W = 0.86;
const statusRow = ([status, body], x, y, w) => {
  chip(status, x, y + 0.01, CHIP_W);
  text(body, { x: x + CHIP_W + 0.12, y, w: w - CHIP_W - 0.12, h: 0.46, fontSize: 10, color: C.ink });
};

const iconBadge = (name, x, y, color) => {
  slide.addShape(pptx.ShapeType.ellipse, {
    x, y, w: 0.66, h: 0.66, fill: { color: C.white }, line: { color, width: 1.25 },
  });
  icon(name, x + 0.15, y + 0.15, 0.36);
};

// Header: team (left), marker-style title (centre), SIH logo (right).
text(TEAM, { x: 0.4, y: 0.28, w: 2, h: 0.3, fontSize: 13, fontFace: HEADING_FONT, color: C.navy });
text("FEASIBILITY AND VIABILITY", {
  x: 2.4, y: 0.14, w: 8.53, h: 0.62, fontSize: 32, bold: true, fontFace: HEADING_FONT,
  color: C.navy, align: "center", valign: "middle",
});
text("Working replay prototype. A staged path to field deployment.", {
  x: 2.4, y: 0.76, w: 8.53, h: 0.3, fontSize: 14, color: C.green, align: "center", italic: true,
});
slide.addImage({ path: "assets/sih-2026-logo.png", x: 11.43, y: 0.16, w: 1.5, h: 0.697 });

// Left column: four green feasibility steps joined by a downward flow.
const LX = 0.4;
const LW = 7.95;
const TOP = 1.3;
const STEP_H = 1.26;
const STEP_GAP = 0.18;
const SPLIT = 4.45;

STEPS.forEach((step, i) => {
  const y = TOP + i * (STEP_H + STEP_GAP);
  roundBox(LX, y, LW, STEP_H, C.greenPale);
  iconBadge(step.icon, LX + 0.2, y + 0.16, C.green);
  text(String(i + 1).padStart(2, "0"), {
    x: LX + 0.2, y: y + 0.88, w: 0.66, h: 0.24, fontSize: 11, bold: true,
    fontFace: HEADING_FONT, color: C.green, align: "center",
  });
  const tx = LX + 1.05;
  const tw = SPLIT - 1.2;
  text(step.title, { x: tx, y: y + 0.1, w: tw, h: 0.3, fontSize: 15, bold: true, color: C.navy });
  text(step.hook, { x: tx, y: y + 0.4, w: tw, h: 0.24, fontSize: 11, bold: true, color: C.green });
  text(step.simple, { x: tx, y: y + 0.67, w: tw, h: 0.52, fontSize: 10, color: C.muted });
  slide.addShape(pptx.ShapeType.line, {
    x: LX + SPLIT, y: y + 0.14, w: 0, h: STEP_H - 0.28,
    line: { color: C.green, width: 0.75, dashType: "dash" },
  });
  const sx = LX + SPLIT + 0.18;
  const sw = LW - SPLIT - 0.3;
  step.items.forEach((item, j) => statusRow(item, sx, y + 0.16 + j * 0.54, sw));
  if (i < STEPS.length - 1) {
    slide.addShape(pptx.ShapeType.line, {
      x: LX + 0.53, y: y + STEP_H, w: 0, h: STEP_GAP,
      line: { color: C.navy, width: 1.5, endArrowType: "triangle" },
    });
  }
});

// Right column: stacked blue validation cards.
const RX = 8.6;
const RW = 12.93 - RX;
const cardHeader = (name, title, x, y) => {
  icon(name, x + 0.2, y + 0.14, 0.34);
  text(title, { x: x + 0.64, y: y + 0.14, w: RW - 0.8, h: 0.34, fontSize: 15, bold: true,
    color: C.navy, valign: "middle" });
};

const mY = TOP;
const mH = 1.82;
roundBox(RX, mY, RW, mH, C.bluePale);
cardHeader("target", "Measured Result", RX, mY);
chip("measured", RX + RW - 1.06, mY + 0.2);
text("67.55%", {
  x: RX + 0.2, y: mY + 0.55, w: 1.75, h: 0.55, fontSize: 32, bold: true, color: C.blue,
  valign: "middle",
});
text("mIoU on 4,071 real driving scans", {
  x: RX + 1.95, y: mY + 0.55, w: RW - 2.15, h: 0.55, fontSize: 12, bold: true, color: C.navy,
  valign: "middle",
});
text("How well each laser point's label matches the human-marked truth, averaged over 19 classes.", {
  x: RX + 0.2, y: mY + 1.14, w: RW - 0.4, h: 0.36, fontSize: 10, color: C.ink,
});
text("Drishti eval E-051 · SemanticKITTI seq 08 · labels only, not a safety measure", {
  x: RX + 0.2, y: mY + mH - 0.27, w: RW - 0.4, h: 0.18, fontSize: 8, italic: true, color: C.muted,
});

const uY = mY + mH + 0.16;
const uH = 2.18;
roundBox(RX, uY, RW, uH, C.bluePale);
cardHeader(UPGRADES.icon, `05  ${UPGRADES.title}`, RX, uY);
text(UPGRADES.hook, {
  x: RX + 0.2, y: uY + 0.54, w: RW - 0.4, h: 0.24, fontSize: 11.5, bold: true, color: C.blue,
});
text(UPGRADES.simple, {
  x: RX + 0.2, y: uY + 0.8, w: RW - 0.4, h: 0.36, fontSize: 10, color: C.muted,
});
UPGRADES.items.forEach((item, j) => statusRow(item, RX + 0.2, uY + 1.22 + j * 0.48, RW - 0.4));

const dY = uY + uH + 0.16;
const dH = TOP + 4 * STEP_H + 3 * STEP_GAP - dY;
roundBox(RX, dY, RW, dH, C.bluePale);
cardHeader("shield-check", "Why It Matters for Defence", RX, dY);
text(
  [
    {
      text:
        "DRDO lists AI perception, autonomous navigation and algorithm-validation " +
        "simulation as UGV technology tasks.",
      options: { breakLine: true },
    },
    { text: "Relevance only, not endorsement or procurement.", options: { italic: true, color: C.muted } },
  ],
  { x: RX + 0.2, y: dY + 0.54, w: RW - 0.4, h: dH - 0.62, fontSize: 10, color: C.ink,
    paraSpaceAfter: 3 },
);

// Footer: status legend (left), event (centre), page number (right).
const legend = [
  ["proven", "Proven / Measured"],
  ["proposed", "Proposed"],
  ["test", "Test / Validate"],
];
let lx = 0.4;
for (const [status, label] of legend) {
  const s = STATUS[status];
  slide.addShape(pptx.ShapeType.roundRect, {
    x: lx, y: 7.13, w: 0.16, h: 0.16, rectRadius: 0.03,
    fill: { color: s.fill }, line: { color: s.line, width: 1 },
  });
  const w = 0.12 + label.length * 0.068;
  text(label, { x: lx + 0.22, y: 7.1, w, h: 0.22, fontSize: 9, color: C.muted, valign: "middle" });
  lx += 0.22 + w + 0.2;
}
text("SMART INDIA HACKATHON 2026", {
  x: 4.67, y: 7.1, w: 4, h: 0.22, fontSize: 9, color: C.muted, align: "center",
  valign: "middle", charSpacing: 2,
});
text(PAGE_NUMBER, {
  x: 12.43, y: 7.07, w: 0.5, h: 0.26, fontSize: 12, fontFace: HEADING_FONT, color: C.navy,
  align: "right", valign: "middle",
});

slide.addNotes(NOTES);

await pptx.writeFile({ fileName: OUTPUT });
console.log(`wrote ${OUTPUT}`);
