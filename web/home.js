// The plotipus page: tabs, colour theme, the gallery (gallery.json, written by build.py from docs/options.md),
// the style viewer and the famous plots.

const $ = (id) => document.getElementById(id);
const escape = (text) => text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

// ------------------------------------------------------------------ tabs

function show() {
  // #usage opens a tab; an anchor inside a tab (#before-after) opens its tab and scrolls to it
  const hash = location.hash.slice(1), target = hash ? document.getElementById(hash) : null;
  const pages = [...document.querySelectorAll("[data-page]")].map((el) => el.dataset.page);
  const tab = pages.includes(hash) ? hash : target?.closest("[data-page]")?.dataset.page || "overview";
  document.querySelectorAll("[data-page]").forEach((el) => { el.hidden = el.dataset.page !== tab; });
  document.querySelectorAll("nav.tabs a").forEach((a) => {
    a.classList.toggle("active", a.dataset.tab === tab);
    if (a.dataset.tab === tab) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  });
  if (target && !pages.includes(hash)) target.scrollIntoView();
  else window.scrollTo(0, 0);
}

// ------------------------------------------------------------------ theme

const THEME_ICONS = {
  system: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  light: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  dark: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
};

function setupTheme() {
  const modes = ["system", "light", "dark"], button = $("theme");
  let mode = "system";
  try { mode = localStorage.getItem("plotipus-theme") || "system"; } catch { /* storage may be unavailable */ }
  if (!modes.includes(mode)) mode = "system";
  const apply = () => {
    if (mode === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", mode);
    button.innerHTML = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8"
      stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${THEME_ICONS[mode]}</svg>`;
    button.title = `Colour theme: ${mode} (click to change)`;
    button.setAttribute("aria-label", button.title);
  };
  button.addEventListener("click", () => {
    mode = modes[(modes.indexOf(mode) + 1) % modes.length];
    try { localStorage.setItem("plotipus-theme", mode); } catch { /* ignore */ }
    apply();
  });
  apply();
}

// ------------------------------------------------------------------ segmented controls, copy buttons

function segmented(element, name, options, selected, onChange) {
  element.innerHTML = options.map(([value, label]) =>
    `<label><input type="radio" name="${name}" value="${escape(value)}"${value === selected ? " checked" : ""}><span>${escape(label)}</span></label>`).join("");
  element.addEventListener("change", (event) => onChange(event.target.value));
}

function setupCopy() {
  document.addEventListener("click", async (event) => {
    const button = event.target.closest("button.copy");
    if (!button) return;
    try {
      await navigator.clipboard.writeText(button.parentElement.querySelector("code").textContent);
      button.textContent = "Copied";
    } catch { button.textContent = "Select and copy"; }
    setTimeout(() => { button.textContent = "Copy"; }, 1500);
  });
}

// ------------------------------------------------------------------ gallery

// What each task of the gallery (web/build.py TASKS) covers, shown under its heading.
const TASK_TEXT = {
  "Data and simulation": "Measured points against simulated histograms, with their uncertainties.",
  "Fits and residuals": "Fits stored with the data: curves, components, parameters, pulls, residuals and ratios.",
  "Searches and significance": "Stacked backgrounds and signal, S/√B, yields per region and signal windows.",
  "Likelihood and Bayesian": "Δχ² confidence regions and posterior corner plots: credible regions, marginals, profiles and priors.",
  "Detector performance": "Resolution and response: binned estimators, 2D histograms and scatter plots.",
  "Comparisons and presentation": "One value per category, palettes and number formatting.",
};
const MEDIA = [["slides", "Slides"], ["paper", "Paper column"]];

function dataTable(data) {
  if (!data) return "";
  const head = data.columns.map((c) => `<th>${escape(c)}</th>`).join("");
  const rows = data.rows.map((row) => `<tr>${row.map((v) => `<td>${escape(v)}</td>`).join("")}</tr>`).join("");
  const count = data.shown < data.total ? `${data.rows.length} of the ${data.shown} rows drawn (${data.total} in the file)`
    : `${data.rows.length} of ${data.total} rows`;
  return `<div class="recipe"><span class="step-name">The data</span> <code>${escape(data.file)}</code>
      <span class="hint">${count}</span></div>
    <div class="table-wrap data"><table><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table></div>`;
}

function card(figure, medium) {
  const src = medium === "paper" && figure.paper ? figure.paper : figure.image;
  const toggle = figure.paper ? `<span class="card-medium" role="group" aria-label="Medium">${MEDIA.map(([value, label]) =>
    `<button type="button" data-medium="${value}" aria-pressed="${src === (value === "paper" ? figure.paper : figure.image)}">${label}</button>`).join("")}</span>` : "";
  const docs = figure.docs ? `<p class="hint"><a href="${figure.docs}" target="_blank" rel="noopener">${figure.section
    ? `Options reference: ${escape(figure.section)}` : "Options reference"}</a></p>` : "";
  return `
    <article class="card finding${figure.wide ? " wide" : ""}" data-image="${figure.image}" data-paper="${figure.paper || ""}">
      <span class="chips-b"><span class="chip kind">${figure.kind}</span>${toggle}</span>
      <p><b>${escape(figure.title)}</b></p>
      <a class="fig" href="${src}" target="_blank" rel="noopener"><img loading="lazy" src="${src}" alt="${escape(figure.alt)}"></a>
      ${dataTable(figure.data)}
      <div class="recipe"><span class="step-name">The command</span></div>
      <pre class="wrap"><button class="copy" type="button">Copy</button><code>${escape(figure.command)}</code></pre>
      ${docs}
    </article>`;
}

async function setupGallery() {
  let gallery;
  try {
    const response = await fetch("gallery.json");
    if (!response.ok) throw new Error(response.status);
    gallery = await response.json();
  } catch {
    $("gallery-status").textContent = "The gallery could not be loaded (gallery.json is written by web/build.py).";
    return;
  }
  const { tasks, figures } = gallery;
  const state = { task: "all", medium: "slides" };
  const draw = () => {
    const shown = tasks.filter((task) => state.task === "all" || task === state.task);
    const count = figures.filter((f) => shown.includes(f.task)).length;
    $("gallery-status").textContent = `${count} of ${figures.length} figures`;
    $("gallery-cards").innerHTML = shown.map((task) => {
      const cards = figures.filter((f) => f.task === task);
      if (!cards.length) return "";
      return `<section class="task"><h2 class="section-title">${escape(task)}</h2>
        ${TASK_TEXT[task] ? `<p class="hint">${escape(TASK_TEXT[task])}</p>` : ""}
        <div class="findings">${cards.map((f) => card(f, state.medium)).join("")}</div></section>`;
    }).join("");
  };
  // One card's medium, without redrawing the others.
  $("gallery-cards").addEventListener("click", (event) => {
    const button = event.target.closest(".card-medium button");
    if (!button) return;
    const article = button.closest("article");
    const src = button.dataset.medium === "paper" ? article.dataset.paper : article.dataset.image;
    article.querySelector("img").src = src;
    article.querySelector("a.fig").href = src;
    article.querySelectorAll(".card-medium button").forEach((b) => b.setAttribute("aria-pressed", String(b === button)));
  });
  segmented($("task-filter"), "task", [["all", "All"], ...tasks.map((t) => [t, t])], state.task, (v) => { state.task = v; draw(); });
  segmented($("medium-pick"), "medium", MEDIA, state.medium, (v) => { state.medium = v; draw(); });
  draw();
}

// ------------------------------------------------------------------ style viewer

const STYLES = [
  ["slides", "Ticks in on four sides, no grid, frameless legends, Petroff-10 colours. 8 × 5.84 in, 14 pt sans. The default."],
  ["slides-dark", "The same on #1b1d22, with lightened twins of the darkest colours. 8 × 5.84 in, 14 pt sans."],
  ["paper", "No titles (the caption is the title). A 3.4 in column, 8 pt Computer Modern; save as PDF."],
  ["paper-dark", "The paper column on the dark theme, for posters and dark-mode preprint readers."],
  ["open", "L-shaped frame, ticks out, a faint y grid: for the web. 8 in at 96 dpi, 12 pt sans."],
  ["open-dark", "The web style on the dark theme."],
  ["classic", "plotipus before the redesign, kept so that old figures can be redrawn as they were. 8 × 6 in."],
];
const EXAMPLES = [
  ["01_hue_style", "Hue and style"], ["02_ratio", "Ratio"], ["03_stacked_significance", "Stack"], ["04_data_stack", "Data on a stack"],
  ["05_binned_std", "Binned"], ["06_hist2d", "2D histogram"], ["07_contour", "Contours"], ["08_fit", "Fit"],
];

function setupStyles() {
  const state = { style: "slides", example: "02_ratio" };
  const draw = () => {
    const look = STYLES.find(([name]) => name === state.style)[1], example = EXAMPLES.find(([name]) => name === state.example)[1];
    $("style-image").src = `images/styles/${state.style}/${state.example}.png`;
    $("style-image").alt = `The "${example}" example figure in the ${state.style} style`;
    $("style-name").textContent = state.style;
    $("style-look").textContent = look;
  };
  segmented($("style-pick"), "style", STYLES.map(([name]) => [name, name]), state.style, (value) => { state.style = value; draw(); });
  segmented($("example-pick"), "example", EXAMPLES, state.example, (value) => { state.example = value; draw(); });
  draw();
}

// ------------------------------------------------------------------ famous plots

// image, title, source, link, data ("real" | "extracted"), what the command shows
const FAMOUS = [
  ["higgs-diphoton", "H→γγ", "ATLAS 2012", "https://arxiv.org/abs/1207.7214", "extracted",
    "Data, the signal + background fit and the background, with data − background below: a stored column as the lower panel, its model curves included.",
    "Diphoton mass spectrum with the Higgs boson bump, a signal plus background fit and the data minus background"],
  ["four-lepton", "H→ZZ*→4ℓ", "CMS 2012", "https://arxiv.org/abs/1207.7235", "extracted",
    "Data over stacked Z+X, ZZ and signal, with Garwood bars from the counts, a CMS header and the K_D > 0.5 selection as an inset.",
    "Four-lepton mass: data points over stacked Z+X, ZZ and Higgs signal histograms"],
  ["local-p0", "Local p₀", "ATLAS 2012", "https://arxiv.org/abs/1207.7214", "extracted",
    "Observed and expected p₀ on a log axis, the ±1σ band in its own colour, and σ lines labelled outside the frame.",
    "Local p-value against the Higgs mass, observed and expected with a ±1σ band and σ lines"],
  ["brazil-band", "Brazil band", "ATLAS 2012", "https://arxiv.org/abs/1207.7214", "extracted",
    "Observed and expected 95% CL limits with nested ±1σ and ±2σ bands from two error columns of the expected row.",
    "Observed and expected 95% CL limits on the signal strength with green and yellow ±1σ/±2σ bands"],
  ["z-lineshape", "Z lineshape", "LEP 2006", "https://arxiv.org/abs/hep-ex/0509008", "extracted",
    "The hadronic cross section at the Z peak against two, three and four neutrino species; errors drawn ×10 and labelled so.",
    "Hadronic cross section at the Z peak with curves for two, three and four neutrino species"],
  ["kamland", "Neutrino oscillation", "KamLAND 2008", "https://arxiv.org/abs/0801.4589", "extracted",
    "Survival probability against L₀/E with x error bars from each point's bin, over the oscillation expectation as a step.",
    "Reactor antineutrino survival probability against L/E with the oscillation expectation"],
  ["omega-contours", "Ω_M–Ω_Λ", "Riess et al. 1998 (Union2.1)", "https://arxiv.org/abs/astro-ph/9805201", "real",
    "Confidence regions from a Δχ² grid of 580 supernovae, with labelled levels, reference lines and a shaded excluded region.",
    "Confidence regions in the matter and dark-energy densities with deceleration and geometry lines"],
  ["hubble-1929", "The expanding Universe", "Hubble 1929", "https://doi.org/10.1073/pnas.15.3.168", "real",
    "24 nebulae and 9 groups from Hubble's Table 1 with his two fitted lines, on his grid: a marker per series and no legend.",
    "Velocity against distance of 24 nebulae and 9 groups with Hubble's two fitted lines on his grid"],
  ["hr-diagram", "HR diagram", "Gaia DR2 2018", "https://arxiv.org/abs/1804.09378", "real",
    "66 million stars as a 2D histogram on a square-root colour scale, the sparsest bins in black.",
    "Hertzsprung-Russell diagram of 66 million Gaia DR2 stars on a square-root colour scale"],
  ["keeling", "Keeling curve", "NOAA GML", "https://gml.noaa.gov/ccgg/trends/", "real",
    "Monthly CO₂ at Mauna Loa since 1958 with the deseasonalised trend, and the seasonal cycle as an inset with its own command.",
    "Monthly atmospheric CO2 at Mauna Loa since 1958 with the deseasonalised trend"],
  ["hockey-stick", "Hockey stick", "Mann, Bradley & Hughes 1999", "https://doi.org/10.1029/1999GL900070", "real",
    "A thousand years of Northern Hemisphere temperature with its uncertainty band, the legend below the axes and an arrow at 1998.",
    "Northern Hemisphere temperature reconstruction since AD 1000 with its uncertainty band and the instrumental record"],
  ["ngc3198", "Dark halo of NGC 3198", "van Albada et al. 1985 (SPARC)", "https://ui.adsabs.harvard.edu/abs/1985ApJ...295..305V", "real",
    "A flat rotation curve explained by disk, gas and a fitted dark halo: one line style per component.",
    "Rotation curve of the galaxy NGC 3198: flat HI data explained by disk, gas and dark halo components"],
];

function setupFamous() {
  $("famous-cards").innerHTML = FAMOUS.map(([image, title, source, link, data, text, alt]) => `
    <article class="card finding">
      <span class="chips-b"><span class="chip ${data}">${data === "real" ? "real data" : "extracted"}</span></span>
      <p><b>${title}.</b> ${text}
        <a href="${link}" target="_blank" rel="noopener">${escape(source)}</a></p>
      <a class="fig" href="images/famous/${image}.png" target="_blank" rel="noopener"><img loading="lazy" src="images/famous/${image}.png" width="1050" height="810" alt="${escape(alt)}"></a>
    </article>`).join("");
}

setupTheme();
setupCopy();
setupStyles();
setupFamous();
show();
addEventListener("hashchange", show);
setupGallery().then(() => { if (location.hash === "#gallery") show(); });
