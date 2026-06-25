"use strict";

const form = document.getElementById("search-form");
const input = document.getElementById("q");
const statusEl = document.getElementById("status");
const result = document.getElementById("result");

function show(el) { el.hidden = false; }
function hide(el) { el.hidden = true; }

function setStatus(msg, isError) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", !!isError);
  show(statusEl);
}

function render(data) {
  hide(statusEl);

  document.getElementById("airport-name").textContent =
    data.airport.name + (data.airport.city ? ` — ${data.airport.city}` : "");

  const codes = [data.airport.icao, data.airport.iata].filter(Boolean).join(" / ");
  document.getElementById("airport-codes").textContent = codes;

  document.getElementById("raw").textContent = data.raw;
  document.getElementById("summary").textContent = data.summary || "";

  const ul = document.getElementById("plain");
  ul.innerHTML = "";
  (data.plain || []).forEach((line) => {
    const li = document.createElement("li");
    li.textContent = line;
    ul.appendChild(li);
  });

  renderAlternatives(data.alternatives);
  show(result);
}

function renderAlternatives(alts) {
  const wrap = document.getElementById("alt-wrap");
  const span = document.getElementById("alternatives");
  span.innerHTML = "";
  if (!alts || !alts.length) { hide(wrap); return; }
  alts.forEach((a) => {
    const link = document.createElement("span");
    link.className = "alt-link";
    link.textContent = `${a.name} (${a.icao})`;
    link.addEventListener("click", () => lookup(a.icao));
    span.appendChild(link);
  });
  show(wrap);
}

async function lookup(query) {
  hide(result);
  setStatus("Fetching latest METAR…", false);
  try {
    const resp = await fetch(`/api/metar?q=${encodeURIComponent(query)}`);
    const data = await resp.json();
    if (!resp.ok) {
      setStatus(data.error || "Something went wrong.", true);
      return;
    }
    render(data);
  } catch (err) {
    setStatus("Network error — could not reach the server.", true);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (q) lookup(q);
});

document.querySelectorAll(".chip").forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.dataset.q;
    lookup(chip.dataset.q);
  });
});
