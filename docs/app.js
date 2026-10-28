// Atlas of Joy. Plain d3, no build step.

const LAYERS = [
  ["beyond_wealth", "Happier than wealth predicts"],
  ["together", "People together"],
  ["happiness", "Happiness (World Happiness Report)"],
  ["face", "Faces"],
  ["people", "People"],
  ["smile_given_face", "Smiling, of photos with a face"],
  ["nature", "Nature and water"],
  ["city", "City and streets"],
  ["joy_title", "Happy words in titles"],
  ["brightness", "Brightness"],
  ["warmth", "Colour warmth"],
  ["colourfulness", "Colourfulness"],
];

const LABELS = Object.fromEntries(LAYERS);
Object.assign(LABELS, {
  smile: "Smiles",
  predicted: "Predicted (wealth + people photos)",
  gdp: "GDP per head",
  fun: "Fun and leisure",
  sunset: "Sunsets",
  indoors: "Indoors",
  pets: "Pets",
  food: "Food",
  night: "Night",
  saturation: "Saturation",
});

// one hue, light to dark. grey keeps red free for the highlight.
const RAMP = ["#e6e6e6", "#c8c8c8", "#a8a8a8", "#878787", "#666666", "#444444", "#1f1f1f"];
const RAMP_DARK = ["#4a4a4a", "#636363", "#7d7d7d", "#989898", "#b4b4b4", "#d0d0d0", "#ededed"];

const dark = () => matchMedia("(prefers-color-scheme: dark)").matches;
const pct = (v) => (v == null ? "–" : `${Math.round(v * 100)}%`);
const num = (v, d = 2) => (v == null ? "–" : v.toFixed(d));
const signed = (v) => (v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(2)}`);
const money = (v) => (v == null ? "–" : `$${Math.round(v / 1000)}k`);
function fmt(key, v) {
  if (key === "beyond_wealth") return signed(v);
  if (key === "gdp") return money(v);
  if (["happiness", "predicted", "brightness", "saturation", "warmth", "colourfulness"].includes(key)) return num(v);
  return pct(v);
}

const tip = document.getElementById("tip");
function showTip(e, html) {
  tip.innerHTML = html;
  tip.hidden = false;
  const x = Math.min(e.clientX + 12, innerWidth - tip.offsetWidth - 8);
  tip.style.left = `${x}px`;
  tip.style.top = `${e.clientY + 12}px`;
}
const hideTip = () => (tip.hidden = true);

let selected = null;
const listeners = [];
function select(name) {
  selected = name;
  listeners.forEach((fn) => fn(name));
}

Promise.all([d3.json("data.json"), d3.json("vendor/countries-110m.json")]).then(([data, world]) => {
  const byNum = new Map(data.countries.map((c) => [c.iso_num, c]));
  const byName = new Map(data.countries.map((c) => [c.name, c]));

  header(data);
  map(data, world, byNum);
  countryPanel(byName);
  scatter(data);
  signals(data);
  table(data);

  showdown(data);
  focus(byName);
  reports(data);

  const start = byName.get("Norway") ? "Norway" : data.countries[0].name;
  select(start);
});

function header(data) {
  const s = data.summary;
  const m = s.money_plus_photos;
  const faces = data.signals.find((d) => d.signal === "face");
  document.getElementById("lede").textContent =
    `We looked at ${s.photos.toLocaleString("en")} ordinary Flickr photos taken by locals in ${s.countries} countries. ` +
    `On their own, the photos can't tell a happy country from an unhappy one. But one thing does stand out: ` +
    `where people photograph each other more, countries are happier than their wealth alone would predict.`;

  const items = [
    [`+${Math.round(m.gain * 100)} pts`, `of happiness explained when people photos are added to GDP (${Math.round(m.r2_gdp_only * 100)}% to ${Math.round(m.r2_gdp_plus_people * 100)}%)`, true],
    [num(faces.partial_rho), "correlation of faces in photos with happiness, after taking out wealth"],
    [num(s.cv_rho), "correlation when all 18 photo signals try to predict happiness alone. Nothing."],
    [s.photos.toLocaleString("en"), `photos from ${s.countries} countries, at most 30 per photographer`],
  ];
  d3.select("#stats").selectAll("div").data(items).join("div")
    .attr("class", (d) => (d[2] ? "stat hero" : "stat"))
    .html((d) => `<div class="num">${d[0]}</div><div class="what">${d[1]}</div>`);
}

function map(data, world, byNum) {
  const el = document.getElementById("map");
  const width = 960, height = 470;
  const shapes = topojson.feature(world, world.objects.countries).features
    .filter((f) => f.properties.name !== "Antarctica");
  const projection = d3.geoEqualEarth().fitSize([width, height], { type: "FeatureCollection", features: shapes });
  const path = d3.geoPath(projection);

  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  const paths = svg.selectAll("path").data(shapes).join("path")
    .attr("d", path)
    .attr("class", (f) => (byNum.has(f.id) ? "country" : "country empty"))
    .on("mousemove", (e, f) => {
      const c = byNum.get(f.id);
      const key = layer.property("value");
      showTip(e, c ? `<b>${c.name}</b><br>${LABELS[key]}: ${fmt(key, c[key])}<br>${c.photos} photos, ${c.users} people` : `${f.properties.name}<br>not enough local photos`);
    })
    .on("mouseleave", hideTip)
    .on("click", (e, f) => byNum.has(f.id) && select(byNum.get(f.id).name));

  const layer = d3.select("#layer");
  layer.selectAll("option").data(LAYERS).join("option").attr("value", (d) => d[0]).text((d) => d[1]);

  function paint() {
    const key = layer.property("value");
    const values = data.countries.map((c) => c[key]).filter((v) => v != null);
    const scale = d3.scaleQuantile(values, dark() ? RAMP_DARK : RAMP);
    paths.filter(".country:not(.empty)").attr("fill", (f) => {
      const v = byNum.get(f.id)[key];
      return v == null ? null : scale(v);
    }).classed("empty-value", (f) => byNum.get(f.id)[key] == null);
    paths.filter((f) => byNum.has(f.id) && byNum.get(f.id)[key] == null).attr("fill", "var(--none)");

    const q = scale.quantiles();
    const lo = fmt(key, d3.min(values)), hi = fmt(key, d3.max(values));
    d3.select("#legend").html(
      `<span>${lo}</span><span class="ramp">${scale.range().map((c) => `<span style="background:${c}"></span>`).join("")}</span><span>${hi}</span>` +
      `<span class="swatch-none"></span><span>no data</span>`
    );
  }
  layer.on("change", paint);
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", paint);
  paint();

  listeners.push((name) => paths.classed("on", (f) => byNum.get(f.id)?.name === name).filter(".on").raise());
}

function countryPanel(byName) {
  const rows = [
    ["happiness", "Happiness score"],
    ["beyond_wealth", "Beyond what wealth predicts"],
    ["gdp", "GDP per head"],
    ["together", "People together"],
    ["face", "Faces"],
    ["smile_given_face", "Smiling, of faces"],
    ["nature", "Nature and water"],
    ["city", "City and streets"],
    ["joy_title", "Happy words in titles"],
    ["brightness", "Brightness"],
    ["warmth", "Warmth"],
  ];
  listeners.push((name) => {
    const c = byName.get(name);
    if (!c) return;
    document.getElementById("country").innerHTML =
      `<div class="name">${c.name}</div>
       <p class="muted small">${c.photos} photos from ${c.users} local photographers</p>
       <dl>${rows.map(([k, l]) => `<dt>${l}</dt><dd>${fmt(k, c[k])}</dd>`).join("")}</dl>`;

    d3.select("#strip").selectAll("a").data(c.thumbs, (t) => t.id).join("a")
      .attr("href", (t) => t.page)
      .attr("target", "_blank")
      .attr("rel", "noopener")
      .attr("title", (t) => `${t.title || "Untitled"} by ${t.author}`)
      .html((t) => `<img src="thumbs/${t.id}.jpg" alt="${(t.title || "Photo").replace(/"/g, "&quot;")}" loading="lazy">`);
    document.getElementById("strip-note").textContent =
      `${c.thumbs.length} random photos from ${c.name}. Click one to see it on Flickr.`;
  });
}

function scatter(data) {
  const rows = data.countries.filter((c) => c.beyond_wealth != null && c.together != null);
  const width = 960, height = 520, margin = { top: 16, right: 24, bottom: 40, left: 48 };
  const x = d3.scaleLinear(d3.extent(rows, (d) => d.together), [margin.left, width - margin.right]).nice();
  const y = d3.scaleLinear(d3.extent(rows, (d) => d.beyond_wealth), [height - margin.bottom, margin.top]).nice();

  const svg = d3.select("#scatter").append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x).ticks(6, "%").tickSize(-(height - margin.top - margin.bottom))).call((g) => g.select(".domain").remove());
  svg.append("g").attr("class", "axis").attr("transform", `translate(${margin.left},0)`)
    .call(d3.axisLeft(y).ticks(6).tickFormat(signed).tickSize(-(width - margin.left - margin.right))).call((g) => g.select(".domain").remove());
  svg.append("line").attr("class", "zero").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y(0)).attr("y2", y(0));
  svg.append("text").attr("class", "axis-title").attr("x", width - margin.right).attr("y", height - 6).attr("text-anchor", "end").text("share of photos with people together →");
  svg.append("text").attr("class", "axis-title").attr("x", margin.left + 4).attr("y", margin.top + 4).attr("dy", "0.7em").text("↑ happier than wealth predicts");

  // least squares line, just to guide the eye
  const mx = d3.mean(rows, (d) => d.together), my = d3.mean(rows, (d) => d.beyond_wealth);
  const slope = d3.sum(rows, (d) => (d.together - mx) * (d.beyond_wealth - my)) / d3.sum(rows, (d) => (d.together - mx) ** 2);
  const [x0, x1] = x.domain();
  svg.append("line").attr("class", "fit")
    .attr("x1", x(x0)).attr("y1", y(my + slope * (x0 - mx)))
    .attr("x2", x(x1)).attr("y2", y(my + slope * (x1 - mx)));

  const g = svg.selectAll("g.pt").data(rows).join("g").attr("class", "pt").style("cursor", "pointer");
  g.append("circle").attr("class", "dot-country").attr("r", 5).attr("cx", (d) => x(d.together)).attr("cy", (d) => y(d.beyond_wealth))
    .attr("stroke", "var(--bg)").attr("stroke-width", 2);
  g.append("circle").attr("r", 12).attr("cx", (d) => x(d.together)).attr("cy", (d) => y(d.beyond_wealth)).attr("fill", "transparent");

  // label only the countries at the edges, plus whichever is selected
  const edge = new Set([
    ...d3.sort(rows, (d) => d.beyond_wealth).slice(0, 3),
    ...d3.sort(rows, (d) => -d.beyond_wealth).slice(0, 3),
    ...d3.sort(rows, (d) => -d.together).slice(0, 3),
  ].map((d) => d.name));
  g.append("text").attr("class", "dot-name").attr("x", (d) => x(d.together) + 9).attr("y", (d) => y(d.beyond_wealth)).attr("dy", "0.35em")
    .text((d) => d.name).attr("display", (d) => (edge.has(d.name) ? null : "none"));

  g.on("mousemove", (e, d) => showTip(e, `<b>${d.name}</b><br>People together ${pct(d.together)}<br>Beyond wealth ${signed(d.beyond_wealth)}<br>Happiness ${num(d.happiness)}, GDP ${money(d.gdp)}`))
    .on("mouseleave", hideTip)
    .on("click", (e, d) => select(d.name));

  listeners.push((name) => {
    g.select(".dot-country").classed("on", (d) => d.name === name);
    g.select("text").classed("on", (d) => d.name === name).attr("display", (d) => (edge.has(d.name) || d.name === name ? null : "none"));
    g.filter((d) => d.name === name).raise();
  });
}

function signals(data) {
  const rows = data.signals;
  const rowH = 28, margin = { top: 24, right: 64, bottom: 8, left: 220 };
  const width = 960, height = margin.top + rows.length * rowH + margin.bottom;
  const x = d3.scaleLinear([-0.6, 0.6], [margin.left, width - margin.right]);
  const y = (i) => margin.top + i * rowH + rowH / 2;

  d3.select("#signals").append("div").attr("class", "key").html(
    `<span><i style="width:16px;height:10px;background:var(--ink)"></i>beyond wealth</span>` +
    `<span><i style="width:8px;height:8px;border-radius:50%;background:var(--ink-3)"></i>plain correlation</span>`
  );
  const svg = d3.select("#signals").append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${margin.top - 8})`)
    .call(d3.axisTop(x).ticks(6).tickSize(-(rows.length * rowH + 8))).call((g) => g.select(".domain").remove());
  svg.append("line").attr("class", "zero").attr("x1", x(0)).attr("x2", x(0)).attr("y1", margin.top - 8).attr("y2", height - margin.bottom);

  const g = svg.selectAll("g.sig").data(rows).join("g").attr("class", "sig");
  g.append("text").attr("class", "sig-label").attr("x", margin.left - 16).attr("y", (d, i) => y(i)).attr("dy", "0.35em").attr("text-anchor", "end").text((d) => LABELS[d.signal] || d.signal);
  g.append("rect")
    .attr("class", (d) => (d.partial_rho < 0 ? "bar neg" : "bar"))
    .attr("x", (d) => Math.min(x(0), x(d.partial_rho)))
    .attr("width", (d) => Math.abs(x(d.partial_rho) - x(0)))
    .attr("y", (d, i) => y(i) - 5).attr("height", 10);
  g.append("circle").attr("class", "raw").attr("r", 4).attr("cx", (d) => x(d.rho)).attr("cy", (d, i) => y(i)).attr("stroke", "var(--bg)").attr("stroke-width", 2);
  g.append("text").attr("class", "sig-value").attr("x", width - margin.right + 12).attr("y", (d, i) => y(i)).attr("dy", "0.35em").text((d) => signed(d.partial_rho));
  g.append("rect").attr("x", 0).attr("width", width).attr("y", (d, i) => y(i) - rowH / 2).attr("height", rowH).attr("fill", "transparent")
    .on("mousemove", (e, d) => showTip(e, `<b>${LABELS[d.signal] || d.signal}</b><br>beyond wealth ${signed(d.partial_rho)} (p ${num(d.partial_p, 3)})<br>plain ${signed(d.rho)}`))
    .on("mouseleave", hideTip);
}

function showdown(data) {
  const sd = data.showdown;
  const blurb = {
    photos_only: "all 18 photo signals",
    people_only: "faces, people, people together",
    money_only: "GDP per head",
    money_people: "GDP + the three people signals",
  };
  const reportsCols = [["happiness", "WHR 2012-14", "what it learned from"], ["whr_2024", "WHR 2024", "ten years later"], ["wvs_happy", "World Values Survey", "\"are you happy?\""]];
  const best = Object.fromEntries(reportsCols.map(([k]) => [k, d3.max(sd.scores, (r) => r[k])]));

  let html = `<div></div>` + reportsCols.map(([, l, sub]) => `<div class="h"><b>${l}</b><br>${sub}</div>`).join("");
  for (const r of sd.scores) {
    html += `<div class="m">${r.model}<small>${blurb[r.key]}</small></div>`;
    for (const [k] of reportsCols) {
      const v = r[k];
      const cls = v === best[k] ? "top" : v < 0.2 ? "low" : "";
      const left = v < 0 ? 50 + v * 50 : 50, width = Math.abs(v) * 50;
      html += `<div><div class="v ${cls}">${signed(v)}</div><div class="bar-track ${cls}"><div class="bar-fill" style="left:${left}%;width:${width}%"></div></div></div>`;
    }
  }
  document.getElementById("showdown").innerHTML = html;

  document.getElementById("verdict").textContent =
    `Photos on their own know nothing. Money on its own knows a lot. Put them together and the photos move ` +
    `${sd.helped} countries closer to their real rank and ${sd.hurt} further away. Country by country, that's a coin flip. ` +
    `The gain comes from a few big wins: Latin American countries that are happier than their money, and southern and eastern European ones that are less happy than theirs.`;

  const item = (d) => {
    const delta = Math.round(d.closer_by);
    return `<li><div><div class="name">${d.country}</div>` +
      `<div class="path">real #${Math.round(d.real)} · money alone #${Math.round(d.money_only)} · money + people #${Math.round(d.money_people)}</div></div>` +
      `<div class="delta ${delta > 0 ? "up" : ""}">${delta > 0 ? "+" : "−"}${Math.abs(delta)}</div></li>`;
  };
  document.getElementById("rescued").innerHTML = sd.rescued.map(item).join("");
  document.getElementById("misled").innerHTML = sd.misled.map(item).join("");
}

function focus(byName) {
  document.querySelectorAll(".focus").forEach((el) => {
    const c = byName.get(el.dataset.country);
    if (!c) return;
    const facts = [
      [`#${c.whr_2024_rank}`, "in the 2024 report"],
      [`#${c.predicted_rank}`, "where the model puts it"],
      [pct(c.together), "of photos show people together"],
    ];
    el.querySelector(".facts").innerHTML = facts.map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join("");
    el.querySelector(".mini-strip").innerHTML = c.thumbs.slice(0, 8)
      .map((t) => `<a href="${t.page}" target="_blank" rel="noopener" title="${(t.title || "Untitled").replace(/"/g, "&quot;")} by ${t.author}"><img src="thumbs/${t.id}.jpg" alt="" loading="lazy"></a>`).join("");
    el.style.cursor = "pointer";
    el.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      select(c.name);
      document.getElementById("country").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function reports(data) {
  const t = d3.select("#reports");
  t.append("thead").append("tr").selectAll("th")
    .data(["Report", "Countries", "Model (GDP + people photos)", "GDP only"]).join("th").text((d) => d);
  t.append("tbody").selectAll("tr").data(data.compare).join("tr").html((r) =>
    `<td>${r.report}</td><td>${r.countries}</td>` +
    `<td class="${r.photos_model > r.gdp_only ? "best" : ""}">${num(r.photos_model)}</td>` +
    `<td class="${r.gdp_only >= r.photos_model ? "best" : ""}">${num(r.gdp_only)}</td>`);
  document.getElementById("reports-note").textContent =
    "Rank correlation between each prediction and each report. Bold marks the better of the two. " +
    "The photos help on the data they learned from, but the edge doesn't carry over to the newer report or the other survey.";

  const rows = data.countries.filter((c) => c.whr_2024_rank != null && c.predicted_rank != null)
    .sort((a, b) => a.whr_2024_rank - b.whr_2024_rank);
  const rowH = 16, margin = { top: 24, right: 16, bottom: 8, left: 150 };
  const width = 960, height = margin.top + rows.length * rowH + margin.bottom;
  const x = d3.scaleLinear([1, d3.max(rows, (d) => Math.max(d.predicted_rank, d.whr_2024_rank))], [margin.left, width - margin.right]);
  const y = (i) => margin.top + i * rowH + rowH / 2;

  const svg = d3.select("#ranks").append("svg").attr("viewBox", `0 0 ${width} ${height}`);
  svg.append("g").attr("class", "axis").attr("transform", `translate(0,${margin.top - 8})`)
    .call(d3.axisTop(x).tickValues([1, 10, 20, 30, 40, 50, 60]).tickFormat((d) => `#${d}`).tickSize(-(rows.length * rowH + 8)))
    .call((g) => g.select(".domain").remove());

  const g = svg.selectAll("g.row").data(rows).join("g").attr("class", "row").style("cursor", "pointer");
  g.append("rect").attr("x", 0).attr("width", width).attr("y", (d, i) => y(i) - rowH / 2).attr("height", rowH).attr("fill", "transparent");
  g.append("text").attr("class", "row-label").attr("x", margin.left - 12).attr("y", (d, i) => y(i)).attr("dy", "0.35em").attr("text-anchor", "end").text((d) => d.name);
  g.append("line").attr("class", "link").attr("x1", (d) => x(d.whr_2024_rank)).attr("x2", (d) => x(d.predicted_rank)).attr("y1", (d, i) => y(i)).attr("y2", (d, i) => y(i));
  g.filter((d) => d.wvs_happy_rank != null).append("circle").attr("class", "dot-wvs").attr("r", 3.5).attr("cx", (d) => x(d.wvs_happy_rank)).attr("cy", (d, i) => y(i) - 0);
  g.append("circle").attr("class", "dot-whr").attr("r", 4).attr("cx", (d) => x(d.whr_2024_rank)).attr("cy", (d, i) => y(i));
  g.append("circle").attr("class", "dot-pred").attr("r", 4).attr("cx", (d) => x(d.predicted_rank)).attr("cy", (d, i) => y(i));
  g.on("mousemove", (e, d) => showTip(e, `<b>${d.name}</b><br>Model #${d.predicted_rank}<br>WHR 2024 #${d.whr_2024_rank}<br>World Values Survey ${d.wvs_happy_rank ? "#" + d.wvs_happy_rank : "–"}`))
    .on("mouseleave", hideTip)
    .on("click", (e, d) => select(d.name));

  listeners.push((name) => g.select("text").classed("on", (d) => d.name === name));
}

function table(data) {
  const cols = ["name", "photos", "users", "happiness", "gdp", "beyond_wealth", "together", "face", "people", "smile_given_face", "nature", "city", "joy_title", "brightness", "warmth"];
  const head = { name: "Country", photos: "Photos", users: "People" };
  const t = d3.select("#table");
  t.append("thead").append("tr").selectAll("th").data(cols).join("th").text((c) => head[c] || LABELS[c]);
  t.append("tbody").selectAll("tr").data([...data.countries].sort((a, b) => d3.ascending(a.name, b.name))).join("tr")
    .selectAll("td").data((c) => cols.map((k) => [k, c[k]])).join("td")
    .text(([k, v]) => (k === "name" || k === "photos" || k === "users" ? v : fmt(k, v)));
}
