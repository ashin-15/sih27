import pptxgen from "pptxgenjs";

const OUTPUT = "Drishti-2.5-SIH26053.pptx";
const TEAM = "AstroNex";
const HEADING_FONT = "Comic Sans MS";
const BODY_FONT = "Arial";
const W = 13.333;
const M = 0.4;
const FULL = W - 2 * M;

const C = {
  canvas: "F4F4F2",
  navy: "243B53",
  ink: "2E3A48",
  muted: "4A5563",
  white: "FFFFFF",
  green: "2F6B52",
  greenPale: "DCEEDB",
  blue: "2F5FA8",
  bluePale: "DDE8F7",
  orange: "C8742F",
  orangePale: "FBE0C3",
  orangeInk: "6E3408",
  gold: "B08A2E",
  goldPale: "F4E6B4",
  purple: "6A4FA0",
  purplePale: "DDD2F0",
  cream: "F7E7D0",
  pink: "F1C5C5",
  red: "B84747",
  grey: "9AA3AE",
};

const STATUS = {
  proven: { label: "PROVEN", fill: C.green, line: C.green, text: C.white },
  measured: { label: "MEASURED", fill: C.green, line: C.green, text: C.white },
  proposed: { label: "PROPOSED", fill: C.blue, line: C.blue, text: C.white },
  test: { label: "TEST", fill: C.orangePale, line: C.orange, text: C.orangeInk },
  validate: { label: "VALIDATE", fill: C.orangePale, line: C.orange, text: C.orangeInk },
  calculated: { label: "CALCULATED", fill: C.white, line: C.navy, text: C.navy },
};

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE";
pptx.title = "Drishti-2.5 - SIH26053";
pptx.subject = "Adaptive variable-resolution 2.5D LiDAR mapping";
pptx.author = TEAM;

// ---------- shared drawing helpers ----------

const kit = (slide) => {
  const text = (value, opts) =>
    slide.addText(value, { fontFace: BODY_FONT, margin: 0, valign: "top", ...opts });
  const box = (x, y, w, h, fill, opts = {}) =>
    slide.addShape(pptx.ShapeType.roundRect, {
      x, y, w, h, rectRadius: opts.radius ?? 0.12, fill: { color: fill },
      line: { color: opts.line ?? C.navy, width: opts.lineWidth ?? 1.25 },
    });
  const icon = (name, x, y, size) =>
    slide.addImage({ path: `assets/icons/${name}.png`, x, y, w: size, h: size });
  const badge = (name, x, y, d = 0.62, ring = C.navy) => {
    slide.addShape(pptx.ShapeType.ellipse, {
      x, y, w: d, h: d, fill: { color: C.white }, line: { color: ring, width: 1.25 },
    });
    icon(name, x + d * 0.22, y + d * 0.22, d * 0.56);
  };
  const arrow = (x1, y1, x2, y2, width = 1.75, color = C.navy) =>
    slide.addShape(pptx.ShapeType.line, {
      x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
      flipH: x2 < x1, flipV: y2 < y1,
      line: { color, width, endArrowType: "triangle" },
    });
  const line = (x1, y1, x2, y2, color = C.navy, width = 1, dashType = "solid") =>
    slide.addShape(pptx.ShapeType.line, {
      x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
      flipH: x2 < x1, flipV: y2 < y1, line: { color, width, dashType },
    });
  const chip = (status, x, y, w = 0.86) => {
    const s = STATUS[status];
    box(x, y, w, 0.22, s.fill, { line: s.line, lineWidth: 1, radius: 0.06 });
    text(s.label, {
      x, y, w, h: 0.22, fontSize: 8, bold: true, color: s.text,
      align: "center", valign: "middle", charSpacing: 1,
    });
  };
  const pill = (label, x, y, w, h = 0.24, fill = C.white, color = C.navy, fontSize = 9) => {
    box(x, y, w, h, fill, { lineWidth: 0.75, radius: h / 2 });
    text(label, { x, y, w, h, fontSize, color, align: "center", valign: "middle", bold: true });
  };
  return { text, box, icon, badge, arrow, line, chip, pill };
};

const header = (slide, title, subtitle = "") => {
  const { text } = kit(slide);
  slide.background = { color: C.canvas };
  text(TEAM, {
    x: M, y: 0.28, w: 2, h: 0.3, fontSize: 13, fontFace: HEADING_FONT, color: C.navy,
  });
  text(title, {
    x: 2.4, y: 0.14, w: 8.53, h: 0.62, fontSize: 32, bold: true, fontFace: HEADING_FONT,
    color: C.navy, align: "center", valign: "middle",
  });
  if (subtitle) text(subtitle, {
    x: 2.4, y: 0.76, w: 8.53, h: 0.3, fontSize: 14, color: C.green, align: "center",
    italic: true,
  });
  slide.addImage({ path: "assets/sih-2026-logo.png", x: 11.43, y: 0.16, w: 1.5, h: 0.697 });
};

const footer = (slide, page, withLegend) => {
  const { text, box } = kit(slide);
  if (withLegend) {
    let lx = M;
    for (const [status, label] of [
      ["proven", "Proven / Measured"],
      ["proposed", "Proposed"],
      ["test", "Test / Validate"],
    ]) {
      const s = STATUS[status];
      box(lx, 7.15, 0.16, 0.16, s.fill, { line: s.line, lineWidth: 1, radius: 0.03 });
      const w = 0.12 + label.length * 0.068;
      text(label, { x: lx + 0.22, y: 7.12, w, h: 0.22, fontSize: 9, color: C.muted, valign: "middle" });
      lx += 0.22 + w + 0.2;
    }
  }
  text("SMART INDIA HACKATHON 2026  ·  SIH26053", {
    x: 4.17, y: 7.12, w: 5, h: 0.22, fontSize: 9, color: C.muted, align: "center",
    valign: "middle", charSpacing: 2,
  });
  text(String(page), {
    x: W - M - 0.5, y: 7.09, w: 0.5, h: 0.26, fontSize: 12, fontFace: HEADING_FONT,
    color: C.navy, align: "right", valign: "middle",
  });
};

// Deterministic pseudo-random point cloud, denser near the sensor like a real scan.
const pointCloud = (slide, cx, cy, rx, ry, count) => {
  let seed = 26053;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  for (let i = 0; i < count; i += 1) {
    const r = Math.sqrt(rand()) ** 1.8;
    const a = rand() * Math.PI * 2;
    const d = 0.03 + rand() * 0.025;
    slide.addShape(pptx.ShapeType.ellipse, {
      x: cx + Math.cos(a) * r * rx - d / 2, y: cy + Math.sin(a) * r * ry - d / 2, w: d, h: d,
      fill: { color: r < 0.35 ? C.navy : r < 0.7 ? C.blue : "7A93B8" },
      line: { color: C.canvas, width: 0 },
    });
  }
};

const rings = (slide, cx, cy, rOuter) => {
  const bands = [
    [rOuter, C.bluePale],
    [rOuter * 0.62, C.greenPale],
    [rOuter * 0.32, C.goldPale],
  ];
  for (const [r, fill] of bands) {
    slide.addShape(pptx.ShapeType.ellipse, {
      x: cx - r, y: cy - r, w: 2 * r, h: 2 * r, fill: { color: fill },
      line: { color: C.navy, width: 1 },
    });
  }
  slide.addShape(pptx.ShapeType.rect, {
    x: cx - 0.07, y: cy - 0.11, w: 0.14, h: 0.22, fill: { color: C.navy },
    line: { color: C.navy, width: 0 },
  });
};

// ---------- slide 2: proposed solution ----------

const slideSolution = () => {
  const slide = pptx.addSlide();
  const { text, box, badge, arrow, pill } = kit(slide);
  header(slide, "PROPOSED SOLUTION", "Foveated 2.5D LiDAR mapping for autonomous ground vehicles");

  box(M, 1.2, 3.55, 1.0, "FBEDED", { line: C.red });
  text("THE PROBLEM", { x: M + 0.2, y: 1.3, w: 3.2, h: 0.24, fontSize: 10, bold: true, color: C.red, charSpacing: 1 });
  text("3D point clouds are too heavy for real time. Flat 2D grids lose kerbs, ditches and overhangs.", {
    x: M + 0.2, y: 1.55, w: 3.2, h: 0.6, fontSize: 11, color: C.ink,
  });
  box(4.15, 1.2, W - M - 4.15, 1.0, C.white, { lineWidth: 1.75 });
  text("OUR SOLUTION", { x: 4.35, y: 1.3, w: 3, h: 0.24, fontSize: 10, bold: true, color: C.green, charSpacing: 1 });
  text(
    [
      { text: "Drishti-2.5 turns every raw LiDAR scan into a compact, labelled 2.5D terrain map", options: { bold: true, color: C.navy } },
      { text: " - sharp near the vehicle, lighter far away.", options: { color: C.ink } },
    ],
    { x: 4.35, y: 1.55, w: W - M - 4.55, h: 0.6, fontSize: 15 },
  );

  // Dominant visual: input -> Drishti-2.5 -> output
  const vy = 2.42;
  const vh = 2.3;
  box(M, vy, 3.3, vh, C.bluePale);
  text("RAW LIDAR SCAN", { x: M, y: vy + 0.12, w: 3.3, h: 0.28, fontSize: 12, bold: true, color: C.navy, align: "center", fontFace: HEADING_FONT });
  pointCloud(slide, M + 1.65, vy + 1.18, 1.38, 0.64, 260);
  text("~124k 3D points every scan", { x: M, y: vy + vh - 0.36, w: 3.3, h: 0.24, fontSize: 10.5, color: C.ink, align: "center", italic: true });
  arrow(M + 3.35, vy + vh / 2, 4.3, vy + vh / 2, 2.25);

  const bx = 4.35;
  const bw = 3.95;
  box(bx, vy, bw, vh, C.white, { lineWidth: 1.75 });
  text("DRISHTI-2.5", { x: bx, y: vy + 0.12, w: bw, h: 0.32, fontSize: 16, bold: true, color: C.navy, align: "center", fontFace: HEADING_FONT });
  [
    ["1  Find the ground", C.orangePale],
    ["2  Label every point", C.greenPale],
    ["3  Build the adaptive grid", C.goldPale],
    ["4  Group obstacles", C.purplePale],
  ].forEach(([label, fill], i) => {
    box(bx + 0.35, vy + 0.55 + i * 0.41, bw - 0.7, 0.33, fill, { lineWidth: 1, radius: 0.08 });
    text(label, { x: bx + 0.55, y: vy + 0.55 + i * 0.41, w: bw - 1.1, h: 0.33, fontSize: 11.5, bold: true, color: C.navy, valign: "middle" });
  });
  arrow(bx + bw + 0.05, vy + vh / 2, 8.85, vy + vh / 2, 2.25);

  const ox = 8.9;
  const ow = W - M - ox;
  box(ox, vy, ow, vh, C.white, { lineWidth: 1.75 });
  text("2.5D MAP OUTPUT", { x: ox, y: vy + 0.12, w: ow, h: 0.28, fontSize: 12, bold: true, color: C.navy, align: "center", fontFace: HEADING_FONT });
  rings(slide, ox + 1.08, vy + 1.2, 0.78);
  [
    [C.goldPale, "5 cm cells", "to 10 m"],
    [C.greenPale, "10 cm cells", "to 25 m"],
    [C.bluePale, "50 cm cells", "to 100 m"],
  ].forEach(([fill, a, b], i) => {
    const ly = vy + 0.62 + i * 0.44;
    box(ox + 2.08, ly + 0.04, 0.26, 0.26, fill, { lineWidth: 1, radius: 0.05 });
    text([{ text: a, options: { bold: true, breakLine: true } }, { text: b }], {
      x: ox + 2.44, y: ly, w: 1.5, h: 0.4, fontSize: 10, color: C.ink,
    });
  });
  text("Height + class in every cell · not to scale", { x: ox, y: vy + vh - 0.36, w: ow, h: 0.24, fontSize: 10.5, color: C.ink, align: "center", italic: true });

  // Capability cards
  const cy = 4.92;
  const ch = 1.62;
  const cw = (FULL - 3 * 0.2) / 4;
  [
    ["mountain", "Ground Separation", "Separates ground from everything above it, so terrain height is correct.", "Patchwork++", C.orangePale],
    ["tags", "Point-Level Labels", "Labels each laser point as road, vehicle, person, pole or 15 other classes.", "FRNet · 19 classes", C.greenPale],
    ["grid-3x3", "Foveated 2.5D Grid", "Uses fine 5 cm cells near the vehicle, growing to 50 cm at 100 m.", "Integer ring lattice", C.goldPale],
    ["boxes", "Obstacle Evidence", "Groups labelled points into obstacles; tracks vehicles and people over time.", "Candidates + track IDs", C.purplePale],
  ].forEach(([ic, title, body, tag, fill], i) => {
    const x = M + i * (cw + 0.2);
    box(x, cy, cw, ch, fill);
    badge(ic, x + 0.16, cy + 0.14, 0.52);
    text(title, { x: x + 0.78, y: cy + 0.14, w: cw - 0.9, h: 0.52, fontSize: 13.5, bold: true, color: C.navy, valign: "middle" });
    text(body, { x: x + 0.18, y: cy + 0.72, w: cw - 0.36, h: 0.56, fontSize: 10.5, color: C.ink });
    pill(tag, x + 0.18, cy + ch - 0.29, cw - 0.36, 0.2, C.white, C.navy, 8.5);
  });

  box(M, 6.68, FULL, 0.34, C.navy, { line: C.navy, radius: 0.08 });
  text(
    [
      { text: "What makes it different:  ", options: { bold: true, color: C.goldPale } },
      { text: "every point lands in exactly one cell - no gaps or double counts at ring edges. Unknown stays unknown, never silently marked safe.", options: { color: C.white } },
    ],
    { x: M + 0.2, y: 6.68, w: FULL - 0.4, h: 0.34, fontSize: 10.5, valign: "middle" },
  );
  footer(slide, 2, false);
  slide.addNotes(NOTES.solution);
};

// ---------- slide 3: technical approach ----------

const slideApproach = () => {
  const slide = pptx.addSlide();
  const { text, box, badge, arrow, line, chip, pill } = kit(slide);
  header(slide, "TECHNICAL APPROACH", "One pipeline: raw scan in → labelled 2.5D map out");

  const stages = [
    ["radar", "Scan Input", "Reads each scan with time and pose; rejects invalid points.", "64-beam LiDAR replay · ROS 2 proposed", C.bluePale],
    ["mountain", "Ground Segmentation", "Fits local ground patches to split ground from everything above.", "Patchwork++ · IROS 2022", C.orangePale],
    ["tags", "Semantic Labels", "Deep network gives each point one of 19 classes; unknown kept.", "FRNet · IEEE TIP 2025", C.greenPale],
    ["grid-3x3", "Adaptive 2.5D Grid", "Places every point in exactly one ring cell by integer index.", "5 / 10 / 50 cm rings", C.goldPale],
    ["boxes", "Obstacle Evidence", "Clusters labelled points; keeps vehicle and person IDs across frames.", "Candidates + track IDs", C.purplePale],
    ["monitor", "Map & Dashboard", "Publishes a read-only map, audit record and colour-coded 3D view.", "Map snapshot · Rerun", C.bluePale],
  ];
  const gap = 0.3;
  const nw = (FULL - 5 * gap) / 6;
  const ny = 1.62;
  const nh = 2.72;
  const nx = (i) => M + i * (nw + gap);

  const lane = (label, i0, i1, color) => {
    const x0 = nx(i0);
    const x1 = nx(i1) + nw;
    line(x0, 1.36, x1, 1.36, color, 1.5);
    pill(label, (x0 + x1) / 2 - 0.55, 1.24, 1.1, 0.24, C.canvas, color, 9);
  };
  lane("IN", 0, 0, C.blue);
  lane("PROCESS", 1, 4, C.green);
  lane("OUT", 5, 5, C.blue);

  stages.forEach(([ic, title, body, tech, fill], i) => {
    const x = nx(i);
    box(x, ny, nw, nh, fill);
    text(String(i + 1), { x: x + 0.12, y: ny + 0.1, w: 0.3, h: 0.3, fontSize: 14, bold: true, color: C.navy, fontFace: HEADING_FONT });
    badge(ic, x + nw / 2 - 0.3, ny + 0.14, 0.6);
    text(title, { x: x + 0.1, y: ny + 0.82, w: nw - 0.2, h: 0.5, fontSize: 13, bold: true, color: C.navy, align: "center", valign: "middle" });
    text(body, { x: x + 0.14, y: ny + 1.36, w: nw - 0.28, h: 0.8, fontSize: 10.5, color: C.ink, align: "center" });
    box(x + 0.1, ny + nh - 0.52, nw - 0.2, 0.42, C.white, { lineWidth: 0.75, radius: 0.08 });
    text(tech, { x: x + 0.14, y: ny + nh - 0.52, w: nw - 0.28, h: 0.42, fontSize: 8.5, bold: true, color: C.navy, align: "center", valign: "middle" });
    if (i < stages.length - 1) arrow(x + nw + 0.03, ny + nh / 2, x + nw + gap - 0.03, ny + nh / 2, 2);
  });

  // What each cell stores
  const by = 4.58;
  const bh = 2.4;
  const lw = 6.95;
  box(M, by, lw, bh, C.white);
  text("WHAT EACH 2.5D CELL STORES", { x: M + 0.25, y: by + 0.15, w: 5, h: 0.3, fontSize: 12, bold: true, color: C.navy, fontFace: HEADING_FONT });
  // side-view sketch of one cell
  const sx = M + 0.3;
  const sy = by + 0.62;
  slide.addShape(pptx.ShapeType.rect, { x: sx, y: sy + 1.14, w: 2.1, h: 0.3, fill: { color: C.orangePale }, line: { color: C.navy, width: 1 } });
  slide.addShape(pptx.ShapeType.rect, { x: sx + 1.15, y: sy + 0.18, w: 0.5, h: 0.96, fill: { color: C.purplePale }, line: { color: C.navy, width: 1 } });
  line(sx, sy + 0.02, sx, sy + 1.44, C.navy, 1, "dash");
  line(sx + 2.1, sy + 0.02, sx + 2.1, sy + 1.44, C.navy, 1, "dash");
  text("ground height", { x: sx, y: sy + 1.46, w: 2.1, h: 0.2, fontSize: 8.5, color: C.muted, align: "center" });
  text("obstacle\nheight span", { x: sx + 0.05, y: sy + 0.3, w: 1.05, h: 0.4, fontSize: 8.5, color: C.muted, align: "right" });
  text("one cell", { x: sx, y: sy - 0.16, w: 2.1, h: 0.18, fontSize: 8.5, italic: true, color: C.muted, align: "center" });
  const fields = [
    ["Ground height", C.orangePale],
    ["Obstacle height span", C.purplePale],
    ["Class evidence (19)", C.greenPale],
    ["Point count", C.bluePale],
    ["Intensity", C.bluePale],
    ["Ambiguity flag", "FBEDED"],
  ];
  fields.forEach(([label, fill], i) => {
    const col = i % 2;
    const row = Math.floor(i / 2);
    pill(label, M + 2.75 + col * 2.0, by + 0.66 + row * 0.44, 1.85, 0.32, fill, C.navy, 9.5);
  });
  text("Heights in integer centimetres. Every accepted point is counted once.", {
    x: M + 2.75, y: by + 2.0, w: 3.95, h: 0.3, fontSize: 9, italic: true, color: C.muted,
  });

  const rx = M + lw + 0.22;
  const rw = W - M - rx;
  box(rx, by, rw, bh, C.bluePale);
  slide.addImage({ path: "assets/icons/cpu.png", x: rx + 0.22, y: by + 0.15, w: 0.32, h: 0.32 });
  text("COMPUTE TODAY", { x: rx + 0.62, y: by + 0.15, w: 3, h: 0.32, fontSize: 12, bold: true, color: C.navy, fontFace: HEADING_FONT, valign: "middle" });
  text("Laptop CPU · fully offline · no cloud", { x: rx + 2.55, y: by + 0.15, w: rw - 2.75, h: 0.32, fontSize: 9.5, italic: true, color: C.muted, align: "right", valign: "middle" });
  [
    ["measured", "Geometry path: median 83 ms per scan over 1,000 scans."],
    ["measured", "FRNet on CPU: ~7.2 s per scan, so a GPU is required."],
    ["proposed", "NVIDIA GPU path (coded, not yet validated) and ROS 2 live input."],
  ].forEach(([status, body], i) => {
    const y = by + 0.66 + i * 0.52;
    chip(status, rx + 0.22, y + 0.02);
    text(body, { x: rx + 1.2, y, w: rw - 1.4, h: 0.46, fontSize: 10.5, color: C.ink });
  });
  footer(slide, 3, true);
  slide.addNotes(NOTES.approach);
};

// ---------- slide 4: feasibility & viability ----------

const slideFeasibility = () => {
  const slide = pptx.addSlide();
  const { text, box, badge, chip, line } = kit(slide);
  header(slide, "FEASIBILITY AND VIABILITY", "Working replay prototype. A staged path to field deployment.");

  const cards = [
    {
      icon: "badge-check", title: "Technical Feasibility",
      hook: "Every stage already runs end to end on real LiDAR data.",
      items: [["proven", "Patchwork++ and FRNet are published, open and integrated."]],
      big: "67.55%", cap: "mIoU on 4,071 held-out scans (authors report 68.7%)",
    },
    {
      icon: "wifi-off", title: "Operational Feasibility",
      hook: "Runs fully offline on the vehicle's own computer.",
      items: [["proven", "No cloud or network needed at runtime."], ["test", "Dust, rain, off-road terrain, live sensor, calibration."]],
      big: "69.1%", cap: "mIoU within 20 m; 15.7% beyond 50 m",
    },
    {
      icon: "laptop", title: "Economic Viability",
      hook: "Prototype needs a laptop and open software, not new rigs.",
      items: [["proven", "Open-source stack, public data, no paid APIs."], ["validate", "Vehicle GPU cost; dataset and model licences."]],
      big: "33.6%", cap: "smaller per-scan map than uniform 5 cm (measured)",
    },
    {
      icon: "scaling", title: "Scalability",
      hook: "Rings, radii and sensors change by config, not code.",
      items: [["proven", "Grid rings set in a validated config file."], ["proposed", "ROS 2 adapter for other LiDARs; GPU path."]],
      big: "~31×", cap: "fewer cells than uniform 5 cm at full 100 m (calculated)",
    },
  ];
  const top = 1.24;
  const ch = 5.68;
  const cgap = 0.15;
  const lwTotal = 8.05;
  const cw = (lwTotal - 3 * cgap) / 4;
  cards.forEach((c, i) => {
    const x = M + i * (cw + cgap);
    const iw = cw - 0.28;
    box(x, top, cw, ch, C.greenPale);
    badge(c.icon, x + cw / 2 - 0.3, top + 0.16, 0.6, C.green);
    text(c.title, { x: x + 0.1, y: top + 0.82, w: cw - 0.2, h: 0.5, fontSize: 13, bold: true, color: C.navy, align: "center", valign: "middle" });
    text(c.hook, { x: x + 0.14, y: top + 1.36, w: iw, h: 0.66, fontSize: 10.5, bold: true, color: C.green, align: "center" });
    line(x + 0.3, top + 2.1, x + cw - 0.3, top + 2.1, C.green, 0.75, "dash");
    c.items.forEach(([status, body], j) => {
      const y = top + 2.24 + j * 0.9;
      chip(status, x + 0.14, y);
      text(body, { x: x + 0.14, y: y + 0.27, w: iw, h: 0.58, fontSize: 10, color: C.ink });
    });
    const ey = top + ch - 1.22;
    box(x + 0.12, ey, cw - 0.24, 1.08, C.white, { line: C.green, lineWidth: 1, radius: 0.08 });
    text(c.big, { x: x + 0.12, y: ey + 0.08, w: cw - 0.24, h: 0.42, fontSize: 22, bold: true, color: C.green, align: "center", valign: "middle" });
    text(c.cap, { x: x + 0.2, y: ey + 0.5, w: cw - 0.4, h: 0.52, fontSize: 8.5, color: C.muted, align: "center" });
  });

  const rx = M + lwTotal + 0.2;
  const rw = W - M - rx;
  const cardHead = (ic, title, y) => {
    slide.addImage({ path: `assets/icons/${ic}.png`, x: rx + 0.2, y: y + 0.14, w: 0.32, h: 0.32 });
    text(title, { x: rx + 0.6, y: y + 0.13, w: rw - 0.8, h: 0.34, fontSize: 14, bold: true, color: C.navy, valign: "middle" });
  };

  const ly = top;
  const lh = 1.6;
  box(rx, ly, rw, lh, C.bluePale);
  cardHead("git-branch", "Long-Term Viability", ly);
  text("Every result is pinned, hashed and repeatable.", { x: rx + 0.2, y: ly + 0.52, w: rw - 0.4, h: 0.24, fontSize: 10.5, bold: true, color: C.blue });
  [
    ["proven", "87 automated tests, locked dependencies, checkpoint SHA-256."],
    ["proposed", "Regression gates and named maintainers per release."],
  ].forEach(([status, body], j) => {
    const y = ly + 0.84 + j * 0.36;
    chip(status, rx + 0.2, y);
    text(body, { x: rx + 1.16, y: y - 0.02, w: rw - 1.34, h: 0.34, fontSize: 9.5, color: C.ink, valign: "middle" });
  });

  const py = ly + lh + 0.14;
  const ph = 2.72;
  box(rx, py, rw, ph, C.bluePale);
  cardHead("route", "Path to Field", py);
  const steps = [
    ["Prototype", "Real-data replay, all stages", C.green, "done"],
    ["Validation", "Held-out metrics, GPU timing", C.blue, "now"],
    ["Field Trial", "Live sensor, terrain, weather", C.orange, "next"],
    ["Deployment", "Vehicle integration via ROS 2", C.grey, "later"],
  ];
  const sx = rx + 0.42;
  steps.forEach(([name, desc, color, state], i) => {
    const y = py + 0.64 + i * 0.5;
    if (i < steps.length - 1) line(sx, y + 0.2, sx, y + 0.7, C.navy, 1.25);
    slide.addShape(pptx.ShapeType.ellipse, {
      x: sx - 0.14, y: y + 0.06, w: 0.28, h: 0.28,
      fill: { color: state === "done" ? color : C.white }, line: { color, width: 2 },
    });
    text([{ text: `${name}  `, options: { bold: true, color: C.navy } }, { text: desc, options: { color: C.ink } }], {
      x: sx + 0.28, y: y, w: rw - 1.9, h: 0.4, fontSize: 10, valign: "middle",
    });
    if (state === "now") {
      box(rx + rw - 1.12, y + 0.07, 0.92, 0.26, C.blue, { line: C.blue, radius: 0.06 });
      text("WE ARE HERE", { x: rx + rw - 1.12, y: y + 0.07, w: 0.92, h: 0.26, fontSize: 7.5, bold: true, color: C.white, align: "center", valign: "middle", charSpacing: 1 });
    } else {
      text(state.toUpperCase(), { x: rx + rw - 1.12, y: y + 0.07, w: 0.92, h: 0.26, fontSize: 8, bold: true, color, align: "right", valign: "middle", charSpacing: 1 });
    }
  });

  const dy = py + ph + 0.14;
  const dh = top + ch - dy;
  box(rx, dy, rw, dh, C.bluePale);
  cardHead("shield-check", "Defence Fit", dy);
  text(
    [
      { text: "DRDO VRDE lists AI-based perception and AI-algorithm validation among UGV technology tasks.", options: { breakLine: true } },
      { text: "Relevance only, not endorsement.", options: { italic: true, color: C.muted } },
    ],
    { x: rx + 0.2, y: dy + 0.5, w: rw - 0.4, h: dh - 0.56, fontSize: 10, color: C.ink },
  );
  footer(slide, 4, true);
  slide.addNotes(NOTES.feasibility);
};

// ---------- slide 5: impact & benefits ----------

const slideImpact = () => {
  const slide = pptx.addSlide();
  const { text, box, arrow } = kit(slide);
  header(slide, "IMPACT AND BENEFITS");

  // [icon, accent, card fill, header fill, title, bullets]; a bullet is [claim, caveat?].
  const cards = [
    ["trending-up", "C0392B", "FDF3F2", "F8DCD8", "Economic", [
      ["33.6% less map data per scan than a uniform 5 cm grid (measured)."],
      ["Smaller maps suit lower-cost embedded computers", "hardware to validate"],
      ["One reusable pipeline avoids rebuilding perception per platform."],
      ["Height evidence may reduce terrain-related vehicle damage", "field trials needed"],
    ]],
    ["leaf", "3F7D5A", "F2F8F3", "DCEEDB", "Environmental", [
      ["Less map data to store and process for every scan."],
      ["Lower compute load can reduce power draw", "not yet measured"],
      ["Could extend battery operating time", "to validate on a vehicle"],
      ["Runs offline: no cloud servers or data transfer."],
    ]],
    ["cog", "2F5FA8", "F1F5FC", "DDE8F7", "Strategic / Indigenization", [
      ["Team-owned pipeline Indian engineers can audit, retrain and extend."],
      ["Aligns with DRDO VRDE's listed AI perception and validation tasks."],
      ["Config-driven grid fits many vehicle platforms", "ROS 2 adapter proposed"],
      ["Dual-use: defence UGVs and civilian autonomous mobility."],
    ]],
    ["hard-hat", "D0671F", "FEF5EE", "FBE0C3", "Field Operators & Reconnaissance UGVs", [
      ["5 cm cells within 10 m keep near-field height detail where kerbs, mounds and trenches appear."],
      ["Colour-coded map with flagged uncertain cells supports operator awareness in rough terrain", "field trials needed"],
    ]],
    ["graduation-cap", "6A4FA0", "F6F3FB", "E6DEF5", "Robotics Researchers & Students", [
      ["No need to rebuild mapping and evaluation code for each experiment."],
      ["Reusable mapping core with hashed runs and official scoring supports adaptive perception, semantic mapping and navigation research."],
    ]],
    ["users", "2A8C8C", "EFF7F7", "D5ECEC", "Civilian Autonomous Mobility", [
      ["Road vehicles meet potholes, pedestrians and unexpected obstacles."],
      ["Tested on real urban driving scans: labels people, vehicles and poles, with height per cell."],
      ["Adaptive detail lowers map data, which may make perception more affordable", "cost not estimated"],
    ]],
  ];

  const gap = 0.36;
  const cw = (FULL - 2 * gap) / 3;
  const ch = 2.72;
  const rowY = [1.16, 4.06];
  const FONT_PT = 10.5;
  const LINE_IN = (FONT_PT * 1.18) / 72;
  const charsPerLine = (widthIn) => Math.floor(widthIn / (FONT_PT * 0.0062));
  const lineCount = (value, widthIn) => {
    const limit = charsPerLine(widthIn);
    let lines = 1;
    let used = 0;
    for (const word of value.split(" ")) {
      const need = used === 0 ? word.length : used + 1 + word.length;
      if (need > limit && used > 0) {
        lines += 1;
        used = word.length;
      } else {
        used = need;
      }
    }
    return lines;
  };

  cards.forEach(([ic, accent, fill, headFill, title, bullets], i) => {
    const col = i % 3;
    const x = M + col * (cw + gap);
    const y = rowY[Math.floor(i / 3)];
    box(x, y, cw, ch, fill, { line: accent, lineWidth: 1.5 });
    box(x + 0.14, y + 0.14, cw - 0.28, 0.62, headFill, { line: headFill, lineWidth: 0.5, radius: 0.1 });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: x + 0.2, y: y + 0.13, w: 0.64, h: 0.64, fill: { color: C.white }, line: { color: accent, width: 1.75 },
    });
    slide.addImage({ path: `assets/icons/${ic}-${accent}.png`, x: x + 0.34, y: y + 0.27, w: 0.36, h: 0.36 });
    text(title, {
      x: x + 0.96, y: y + 0.14, w: cw - 1.14, h: 0.62, fontSize: title.length > 26 ? 13.5 : 15,
      bold: true, color: C.navy, valign: "middle",
    });

    const bx = x + 0.44;
    const bw = cw - 0.62;
    let by = y + 0.94;
    for (const [claim, caveat] of bullets) {
      const full = caveat ? `${claim} (${caveat}).` : claim;
      const h = lineCount(full, bw) * LINE_IN;
      slide.addShape(pptx.ShapeType.ellipse, {
        x: bx - 0.21, y: by + 0.055, w: 0.09, h: 0.09, fill: { color: accent }, line: { color: accent, width: 0 },
      });
      const runs = [{ text: claim, options: { color: C.ink } }];
      if (caveat) runs.push({ text: ` (${caveat}).`, options: { color: accent, italic: true } });
      text(runs, { x: bx, y: by, w: bw, h: h + 0.02, fontSize: FONT_PT, lineSpacingMultiple: 1.0 });
      by += h + 0.1;
    }
    if (col < 2 && i < 3) arrow(x + cw + 0.05, y + ch / 2, x + cw + gap - 0.05, y + ch / 2, 1.75);
  });

  text("Benefits describe mechanisms already built. Items in italics, and field outcomes such as safety and mission time, still need validation.", {
    x: M, y: 6.86, w: FULL, h: 0.22, fontSize: 9.5, italic: true, color: C.muted, align: "center",
  });
  footer(slide, 5, false);
  slide.addNotes(NOTES.impact);
};

// ---------- speaker notes ----------

const NOTES = {
  solution: `PROPOSED SOLUTION - speaker notes

Main message: Drishti-2.5 turns each raw LiDAR scan into a compact, labelled 2.5D terrain map, sharp near the vehicle and lighter far away.

Say: "A LiDAR gives about 124 thousand 3D points every scan. That is too heavy to process at full detail, but flattening it into a 2D grid throws away the heights that reveal kerbs and ditches. Drishti-2.5 takes the middle path the problem statement asks for: a 2.5D map that keeps height and class in every cell, with 5 centimetre cells close to the vehicle and 50 centimetre cells out to 100 metres, like human foveated vision. It separates ground, labels every point with a deep network, builds the adaptive grid and groups obstacles. Two design rules matter: every point goes to exactly one cell, so nothing is lost or double counted where rings meet, and anything the system is unsure about stays marked unknown."

Evidence
- Problem and suggested 5 cm / 10 m and 50 cm / 100 m cells: SIH26053 problem statement (DRDO).
- ~124k points per scan: measured mean 123,558 accepted points over 20 SemanticKITTI sequence 08 scans (docs/research/experiments/0031-adaptive-vs-uniform-grid.md).
- Rings 5/10/50 cm to 10/25/100 m: Drishti-2.5/configs/default.toml.
- Exactly-one-cell ownership, unknown never turned into a class: Drishti-2.5 contracts (docs/interfaces.md) and unit tests (87 passed, docs/testing.md).
- Obstacle candidates and track IDs: experiments 0028 and 0030. Velocity is not estimated.`,
  approach: `TECHNICAL APPROACH - speaker notes

Main message: one shared pipeline carries a raw scan to a labelled 2.5D map and obstacle evidence, and every stage is already running and measured.

Say: "A scan comes in with its timestamp and pose, and invalid points are rejected. Patchwork++, a published ground-segmentation method, splits ground from everything above it. FRNet, a published LiDAR segmentation network, labels every point with one of 19 classes; anything it cannot classify stays unknown. The adaptive grid then puts every point into exactly one cell using integer indices, so rings never overlap. Labelled points are grouped into obstacles, and vehicles and people keep an ID across frames. Out comes a read-only map snapshot and a colour-coded 3D view. Everything runs offline on a laptop CPU today. The geometry path takes a median 83 milliseconds per scan; the neural network takes about 7 seconds on CPU, so real-time use needs a GPU. We have coded a GPU path but not yet validated it on NVIDIA hardware."

Evidence
- Patchwork++: Lee, Lim, Myung, IROS 2022, https://arxiv.org/abs/2207.11919 ; code https://github.com/url-kaist/patchwork-plusplus
- FRNet: IEEE Transactions on Image Processing 2025, Apache-2.0 code and SemanticKITTI weights, https://github.com/Xiangxu-0103/FRNet ; checkpoint pinned by SHA-256 (experiment 0025).
- Cell fields: Drishti-2.5/src/drishti/mapping.py (MapSnapshot).
- Geometry path median 83.13 ms over 1,000 sequence 08 scans, geometric mode without the model (E-044, experiment 0019). 28 of 1,000 scans exceeded 100 ms.
- FRNet CPU p50 7,177 ms per scan (E-052, experiment 0026).
- CUDA path integrated with no GPU parity or timing result (docs/open-items.md, O-001).
- ROS 2 PointCloud2 carries point fields, timestamp and frame ID: https://raw.githubusercontent.com/ros2/common_interfaces/rolling/sensor_msgs/msg/PointCloud2.msg`,
  feasibility: `FEASIBILITY AND VIABILITY - speaker notes

Main message: the prototype already runs on real data with open tools; the remaining steps to the field are named, measurable and in order.

Say: "Is it practical? Technically, yes: every stage runs end to end on real LiDAR data today. On all 4,071 scans of the standard held-out sequence, the labelling scores 67.55 percent mIoU, close to the 68.7 percent the FRNet authors report. Operationally, it needs no network. It is strongest near the vehicle, 69 percent within 20 metres, and weak beyond 50 metres, which is why the grid is coarse there and why field trials come next. Economically, the prototype needs only a laptop and open software, and the adaptive grid stored 33.6 percent less map data per scan than a uniform 5 centimetre grid. Ring sizes and sensors are configuration, and every result is hashed and repeatable. We are between prototype and validation. The next gates are GPU timing, live sensor input and field trials in dust, rain and rough terrain."

Evidence
- 67.55% mIoU (0.6754690443) and 92.28% labelled accuracy, 4,071 sequence 08 scans, official evaluator (E-051, experiment 0025). The run joins a 793-scan prefix and a 3,278-scan continuation.
- FRNet authors report 68.7% SemanticKITTI validation mIoU under their conditions: https://github.com/Xiangxu-0103/FRNet
- Sequence 08 is the official validation split: semantic-kitti-api config/semantic-kitti.yaml, https://github.com/PRBonn/semantic-kitti-api
- Range results 69.1% (0-20 m), 54.3% (20-50 m), 15.7% (50 m+): experiment 0025.
- 33.6% fewer cells and snapshot bytes than uniform 5 cm, 20 scans, single frame, logical payload (E-058, experiment 0031).
- ~31x fewer cells at full 100 m coverage is a design calculation (12,566,371 vs 408,407 cells), not a measurement.
- SemanticKITTI is CC BY-NC-SA (non-commercial): https://semantic-kitti.org/dataset.html
- 87 tests passed, locked uv.lock, checkpoint SHA-256: docs/testing.md, experiment 0025.
- DRDO VRDE UGV tasks include "AI Based Perception for Autonomous Driving" and "Simulation software for AI algorithms validation": https://drdo.gov.in/drdo/en/offerings/technology-foresight/ugv (checked 2026-09-29).`,
  impact: `IMPACT AND BENEFITS - speaker notes

Main message: if Drishti-2.5 works in the field, six groups gain: lower cost and compute, lower energy use, indigenous capability, field operators, researchers and civilian mobility.

Say: "What changes if this works? Economically, the adaptive grid already stores 33.6 percent less map data per scan than a uniform 5 centimetre grid, which points toward cheaper embedded computers, though we still have to validate that on hardware. Less compute can also mean less power and longer battery life; we have not measured that yet, and the slide says so in italics. Strategically, it is a team-owned pipeline that Indian engineers can audit and retrain, aligned with the AI perception and validation tasks DRDO's VRDE lists for unmanned ground vehicles. For field operators, 5 centimetre cells near the vehicle keep the height detail where kerbs, mounds and trenches appear, and uncertain cells are flagged rather than shown as safe. Researchers get a reusable mapping core with repeatable, hashed evaluation. And the same approach applies to civilian vehicles: we have tested it on real urban driving scans. Anything in italics still needs field or hardware validation."

Evidence
- 33.6% less map data per scan: E-058, docs/research/experiments/0031-adaptive-vs-uniform-grid.md (20 sequence 08 scans, single-frame logical payload).
- 5 cm cells within 10 m: Drishti-2.5/configs/default.toml.
- Per-cell ground height, obstacle height span, class evidence and ambiguity flags: Drishti-2.5/src/drishti/mapping.py.
- Runs offline with local models: Drishti-2.5/src/drishti/learned.py; E-052.
- Hashed runs and official scoring: experiment 0025 (checkpoint SHA-256, pinned official SemanticKITTI evaluator).
- Urban driving data: SemanticKITTI is built on KITTI odometry driving sequences, https://semantic-kitti.org/dataset.html
- VRDE UGV tasks "AI Based Perception for Autonomous Driving" and "Simulation software for AI algorithms validation": https://drdo.gov.in/drdo/en/offerings/technology-foresight/ugv
- NOT measured: power draw, battery time, embedded hardware cost, vehicle damage, operator workload, mine detection. Mines are deliberately not claimed.`,
};

slideSolution();
slideApproach();
slideFeasibility();
slideImpact();

await pptx.writeFile({ fileName: OUTPUT });
console.log(`wrote ${OUTPUT}`);
