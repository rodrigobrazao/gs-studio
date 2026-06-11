/* GS Studio — vanilla JS frontend */
(() => {
  const $  = (s, r=document) => r.querySelector(s);
  const $$ = (s, r=document) => [...r.querySelectorAll(s)];

  const state = {
    videoPath: "",
    videoInfo: null,
    deps: [],
    runActive: false,
    phaseStart: {},
  };

  // ─────────────────────────────── Tabs / nav highlight
  const sections = $$("section.panel");
  const navLinks = $$(".topnav a");
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        const id = e.target.id;
        navLinks.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${id}`));
      }
    });
  }, { rootMargin: "-40% 0px -50% 0px" });
  sections.forEach((s) => observer.observe(s));

  // ─────────────────────────────── Slider value labels
  const bindVal = (id, valId, fmt = (v) => v) => {
    const el = $(`#${id}`), val = $(`#${valId}`);
    if (!el || !val) return;
    const upd = () => val.textContent = fmt(el.value);
    el.addEventListener("input", upd); upd();
  };
  bindVal("fps", "val-fps");
  bindVal("max-frames", "val-max-frames");
  bindVal("total-steps", "val-steps", v => Number(v).toLocaleString("pt-PT"));
  bindVal("max-splats", "val-splats", v => Number(v).toLocaleString("pt-PT").replace(/\./g, " "));
  bindVal("growth-stop", "val-growth", v => Number(v).toLocaleString("pt-PT"));
  bindVal("export-every", "val-export", v => Number(v).toLocaleString("pt-PT"));
  bindVal("hdri-samples", "val-hdri-samples");

  // ─────────────────────────────── Presets
  const presets = {
    fast:     { steps: 10000, splats: 1000000, growth:  7000, sh: 1 },
    balanced: { steps: 30000, splats: 4000000, growth: 15000, sh: 3 },
    hq:       { steps: 50000, splats: 6000000, growth: 25000, sh: 3 },
  };
  $$(".preset").forEach((b) => {
    b.addEventListener("click", () => {
      $$(".preset").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      const p = presets[b.dataset.preset];
      $("#total-steps").value = p.steps;       $("#total-steps").dispatchEvent(new Event("input"));
      $("#max-splats").value = p.splats;       $("#max-splats").dispatchEvent(new Event("input"));
      $("#growth-stop").value = p.growth;      $("#growth-stop").dispatchEvent(new Event("input"));
      const shRadio = document.querySelector(`input[name="sh"][value="${p.sh}"]`);
      if (shRadio) shRadio.checked = true;
    });
  });

  // ─────────────────────────────── Project name from video
  $("#video-path").addEventListener("change", () => {
    const v = $("#video-path").value.trim();
    if (v && !$("#project-name").value) {
      const base = v.split("/").pop().replace(/\.[^.]+$/, "");
      $("#project-name").value = base + "_v01";
    }
    refreshScenedirPreview();
    if (v) validatePathAndEstimate(v);
  });
  $("#project-name").addEventListener("input", refreshScenedirPreview);
  $("#output-root").addEventListener("input", refreshScenedirPreview);

  function refreshScenedirPreview() {
    const root = $("#output-root").value || "~/Desktop";
    const name = $("#project-name").value || "<nome>";
    $("#scenedir-preview").textContent = `${root}/${name}/`;
  }
  refreshScenedirPreview();

  // ─────────────────────────────── Drag & drop
  const drop = $("#drop-zone");
  ["dragover", "dragenter"].forEach(ev => drop.addEventListener(ev, (e) => {
    e.preventDefault(); drop.classList.add("over");
  }));
  ["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, () => drop.classList.remove("over")));
  drop.addEventListener("drop", async (e) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (!file) return;
    // Em macOS, drag-and-drop expõe file.path em Electron mas não no browser puro.
    // Aqui fazemos upload (o backend prefere caminhos locais via /api/upload-path).
    await uploadFile(file);
  });
  $("#file-input").addEventListener("change", async (e) => {
    const f = e.target.files[0]; if (f) await uploadFile(f);
  });
  $("[data-action='pick-file']").addEventListener("click", () => $("#file-input").click());

  async function uploadFile(file) {
    $("#video-info").textContent = `A carregar ${file.name}…`;
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/upload", { method: "POST", body: fd });
    const j = await r.json();
    $("#video-path").value = j.path;
    state.videoPath = j.path;
    state.videoInfo = j;
    $("#video-info").textContent = `${j.name} · ${humanSize(j.size)}`;
    if (!$("#project-name").value) {
      $("#project-name").value = j.name.replace(/\.[^.]+$/, "") + "_v01";
      refreshScenedirPreview();
    }
    estimateFrames();
  }

  async function validatePathAndEstimate(path) {
    try {
      const fd = new FormData(); fd.append("path", path);
      const r = await fetch("/api/upload-path", { method: "POST", body: fd });
      if (!r.ok) { $("#video-info").textContent = "⚠️ caminho não encontrado"; return; }
      const j = await r.json();
      state.videoPath = j.path;
      $("#video-info").textContent = `${j.name} · ${humanSize(j.size)}`;
      estimateFrames();
    } catch (e) { /* ignore */ }
  }

  async function estimateFrames() {
    if (!state.videoPath) return;
    const r = await fetch("/api/estimate-frames", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_path: state.videoPath,
        fps: +$("#fps").value,
        max_frames: +$("#max-frames").value,
      }),
    });
    if (!r.ok) return;
    const j = await r.json();
    $("#estimate").innerHTML =
      `${j.duration_s}s de vídeo · ~${j.extracted_raw} frames extraídos · ` +
      `<strong>~${j.selected_estimate}</strong> seleccionados`;
  }
  $("#fps").addEventListener("input", debounce(estimateFrames, 250));
  $("#max-frames").addEventListener("input", debounce(estimateFrames, 250));

  // ─────────────────────────────── Deps
  async function loadDeps() {
    $("#deps-table").innerHTML = `<div class="deps-loading">A verificar…</div>`;
    const r = await fetch("/api/deps");
    const j = await r.json();
    state.deps = j.deps;
    renderDeps();
  }
  function renderDeps() {
    const html = state.deps.map(d => `
      <div class="dep-row">
        <div class="dep-status ${d.found ? "ok" : ""}"></div>
        <div>
          <div class="dep-label">${d.label}</div>
          <div class="muted small">${d.kind === "python" ? "Python module" : d.kind === "binary" ? "Binário" : "Pasta"} · <code>${d.check}</code></div>
        </div>
        <div class="dep-version">${d.version || "—"}</div>
        ${d.found
          ? `<button class="btn small ghost" disabled>Instalado</button>`
          : `<button class="btn small" data-install="${d.name}">Instalar</button>`}
      </div>
    `).join("");
    $("#deps-table").innerHTML = html || `<div class="deps-loading">Nada para mostrar</div>`;
    $$("[data-install]").forEach(b => b.addEventListener("click", () => installDep(b.dataset.install)));
  }
  $("[data-action='check-deps']").addEventListener("click", loadDeps);
  $("[data-action='install-all']").addEventListener("click", async () => {
    for (const d of state.deps.filter(x => !x.found)) {
      await installDep(d.name);
    }
    loadDeps();
  });
  async function installDep(name) {
    return new Promise((resolve) => {
      const ws = new WebSocket(`ws://${location.host}/ws/install/${name}`);
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data);
        if (ev.type === "log") appendLog(`[install:${name}] ${ev.line}`);
        if (ev.type === "end") { appendLog(`[install:${name}] terminou (rc=${ev.rc})`, "phase"); ws.close(); resolve(); }
        if (ev.type === "error") { appendLog(`[install:${name}] ${ev.message}`, "err"); ws.close(); resolve(); }
      };
      ws.onclose = () => resolve();
    });
  }

  // ─────────────────────────────── Build config + Run
  function buildConfig() {
    const sh = +(document.querySelector('input[name="sh"]:checked')?.value || 3);
    const matcher = document.querySelector('input[name="matcher"]:checked')?.value || "sequential";
    const inputKind = document.querySelector('input[name="input-kind"]:checked')?.value || "perspective";
    return {
      project_name: $("#project-name").value.trim() || "projecto",
      video_path: state.videoPath || $("#video-path").value.trim(),
      output_root: $("#output-root").value.trim() || "~/Desktop",
      frames: {
        fps: +$("#fps").value,
        max_frames: +$("#max-frames").value,
        selection: $("#selection").value,
      },
      colmap: {
        camera_model: $("#camera-model").value,
        single_camera: $("#single-camera").checked,
        matcher,
        input_kind: inputKind,
      },
      brush: {
        total_steps: +$("#total-steps").value,
        max_splats: +$("#max-splats").value,
        growth_stop_iter: +$("#growth-stop").value,
        sh_degree: sh,
        max_resolution: $("#max-res").value ? +$("#max-res").value : null,
        export_every: +$("#export-every").value,
      },
      output: {
        auto_open_supersplat: $("#auto-open").checked,
        keep_intermediate_plys: $("#keep-intermediate").checked,
        keep_database: $("#keep-db").checked,
        backup_sparse: $("#backup-sparse").checked,
      },
    };
  }

  $("[data-action='start']").addEventListener("click", async () => {
    const cfg = buildConfig();
    if (!cfg.video_path) { alert("Escolhe um vídeo primeiro."); return; }
    if (!cfg.project_name) { alert("Define o nome do projecto."); return; }

    clearLog();
    resetPhases();
    setRunActive(true);

    const r = await fetch("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    });
    if (!r.ok) {
      const j = await r.json().catch(() => ({}));
      appendLog(`Erro ao iniciar: ${j.detail || r.status}`, "err");
      setRunActive(false);
      return;
    }
    connectRunSocket();
    document.querySelector("#panel-run").scrollIntoView({ behavior: "smooth" });
  });

  $("[data-action='cancel']").addEventListener("click", async () => {
    await fetch("/api/cancel", { method: "POST" });
    appendLog("⚠️ Cancelamento pedido", "phase");
  });

  function setRunActive(on) {
    state.runActive = on;
    $("[data-action='start']").disabled = on;
    $("[data-action='cancel']").disabled = !on;
  }

  function resetPhases() {
    $$(".phase").forEach(p => {
      p.classList.remove("running", "done", "error");
      p.querySelector(".phase-fill").style.width = "0%";
      p.querySelector(".phase-meta").textContent = "—";
    });
  }

  function connectRunSocket() {
    const ws = new WebSocket(`ws://${location.host}/ws/run`);
    ws.onmessage = (m) => handleRunEvent(JSON.parse(m.data));
    ws.onclose = () => { /* server desligou ou run terminou */ };
  }

  function handleRunEvent(ev) {
    if (ev.type === "start") {
      appendLog(`▶︎ Pipeline iniciado · ${ev.config.project_name}`, "phase");
    } else if (ev.type === "phase") {
      const el = document.querySelector(`.phase[data-phase="${ev.phase}"]`);
      if (!el) return;
      if (ev.status === "start") {
        el.classList.add("running");
        state.phaseStart[ev.phase] = Date.now();
        el.querySelector(".phase-meta").textContent = "a correr…";
        appendLog(`── ${ev.phase.toUpperCase()} ──`, "phase");
      } else if (ev.status === "done") {
        el.classList.remove("running"); el.classList.add("done");
        el.querySelector(".phase-fill").style.width = "100%";
        const dt = (Date.now() - (state.phaseStart[ev.phase] || Date.now())) / 1000;
        el.querySelector(".phase-meta").textContent = `${dt.toFixed(1)} s`;
      } else if (ev.status === "error") {
        el.classList.remove("running"); el.classList.add("error");
        el.querySelector(".phase-meta").textContent = `falhou (rc=${ev.rc ?? "?"})`;
      }
    } else if (ev.type === "log") {
      appendLog(`[${ev.phase}] ${ev.line}`);
      bumpProgress(ev.phase, ev.line);
    } else if (ev.type === "cmd") {
      appendLog(`$ ${ev.cmd}`, "cmd");
    } else if (ev.type === "error") {
      appendLog(`ERRO: ${ev.message}`, "err");
    } else if (ev.type === "end") {
      setRunActive(false);
      if (ev.status === "done") {
        appendLog(`✓ Concluído em ${(ev.elapsed_s || 0).toFixed(1)} s`, "phase");
        if (ev.final_ply) appendLog(`📦 ${ev.final_ply}`, "phase");
      } else {
        appendLog(`✗ Terminou com estado: ${ev.status}`, "err");
      }
      loadHistory();
    }
  }

  function bumpProgress(phase, line) {
    if (phase !== "brush") return;
    const m = line.match(/step\s+(\d+)\s*\/\s*(\d+)/i);
    if (!m) return;
    const pct = Math.min(100, Math.round((+m[1] / +m[2]) * 100));
    const el = document.querySelector(`.phase[data-phase="brush"] .phase-fill`);
    if (el) el.style.width = pct + "%";
    const meta = document.querySelector(`.phase[data-phase="brush"] .phase-meta`);
    if (meta) meta.textContent = `${pct}% · step ${m[1]}/${m[2]}`;
  }

  // ─────────────────────────────── Log
  function appendLog(line, cls) {
    const log = $("#log");
    const span = document.createElement("span");
    if (cls) span.className = `l-${cls}`;
    span.textContent = line + "\n";
    log.appendChild(span);
    if ($("#autoscroll").checked) log.scrollTop = log.scrollHeight;
  }
  function clearLog() { $("#log").textContent = ""; }

  // ─────────────────────────────── History
  async function loadHistory() {
    const r = await fetch("/api/projects");
    const j = await r.json();
    const html = j.projects.map(p => `
      <div class="history-item">
        <div>
          <div class="h-name">${p.name}</div>
          <div class="h-meta">${p.modified ? new Date(p.modified).toLocaleString("pt-PT") : "—"} · ${p.n_frames || 0} frames · ${p.final_ply_size_mb ? p.final_ply_size_mb + " MB" : "sem .ply"}</div>
        </div>
        <div class="h-meta">${p.scenedir}</div>
        <div class="h-actions">
          ${p.final_ply ? `<button class="btn small" data-open-ss="${p.final_ply}">superspl.at</button>` : ""}
          <button class="btn small ghost" data-reveal="${p.scenedir}">Finder</button>
        </div>
      </div>
    `).join("");
    $("#history-list").innerHTML = html || `<div class="muted small">Sem projectos ainda.</div>`;
    $$("[data-reveal]").forEach(b => b.addEventListener("click", async () => {
      const fd = new FormData(); fd.append("path", b.dataset.reveal);
      await fetch("/api/reveal", { method: "POST", body: fd });
    }));
    $$("[data-open-ss]").forEach(b => b.addEventListener("click", async () => {
      const fd = new FormData(); fd.append("path", b.dataset.openSs);
      await fetch("/api/open-supersplat", { method: "POST", body: fd });
    }));
    // popular dropdown de export-blender
    const sel = $("#export-project");
    if (sel) {
      sel.innerHTML = `<option value="">— escolhe um projecto —</option>` +
        j.projects
          .filter(p => p.final_ply)
          .map(p => `<option value="${p.scenedir}">${p.name} · ${p.final_ply_size_mb || "?"} MB</option>`)
          .join("");
    }
  }
  $("[data-action='refresh-history']").addEventListener("click", loadHistory);

  $("[data-action='discover-projects']")?.addEventListener("click", async (e) => {
    const btn = e.target;
    const original = btn.textContent;
    btn.disabled = true; btn.textContent = "…";
    try {
      const r = await fetch("/api/projects/discover", { method: "POST" });
      const j = await r.json();
      btn.textContent = `✓ ${j.count}`;
      await loadHistory();
    } catch (err) {
      btn.textContent = "✗";
      console.error(err);
    }
    setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 2000);
  });

  // ─────────────────────────────── Blender integration
  async function loadBlenderStatus() {
    const r = await fetch("/api/blender/status");
    const j = await r.json();
    const el = $("#blender-status");
    if (!el) return;
    if (j.installed) {
      el.innerHTML = `✓ Blender instalado · add-ons em <code>${j.version_dir.replace(/^.*Blender\//, "Blender/")}</code>`;
    } else {
      el.innerHTML = `⚠️ Blender não encontrado em /Applications/Blender.app`;
    }
  }

  $("[data-action='install-blender-addons']")?.addEventListener("click", async (e) => {
    const btn = e.target;
    const original = btn.textContent;
    btn.disabled = true; btn.textContent = "A instalar…";
    try {
      const r = await fetch("/api/blender/install-addons", { method: "POST" });
      const j = await r.json();
      const ok = j.install_results.every(x => x.ok);
      btn.textContent = ok ? "✓ Instalados" : "✗ Erros — ver consola";
      console.log("Blender addons install:", j);
      if (j.enable_result?.log) console.log("Enable log:\n" + j.enable_result.log);
      setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 3500);
    } catch (err) {
      btn.textContent = "✗ Erro";
      console.error(err);
      setTimeout(() => { btn.textContent = original; btn.disabled = false; }, 3500);
    }
  });

  $("[data-action='render-hdri']")?.addEventListener("click", async (e) => {
    const scenedir = $("#export-project").value;
    if (!scenedir) { alert("Escolhe um projecto primeiro."); return; }
    const btn = e.target;
    const log = $("#hdri-log");
    log.classList.remove("hidden");
    log.textContent = "A renderizar HDRI (Cycles 4k pode demorar 2–10 min)…\n";
    btn.disabled = true; btn.textContent = "A renderizar…";
    const engine = document.querySelector('input[name="hdri-engine"]:checked')?.value || "cycles";
    try {
      const r = await fetch("/api/blender/render-hdri", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scenedir,
          resolution: $("#hdri-resolution").value,
          engine,
          samples: +$("#hdri-samples").value,
          position: $("#hdri-position").value.trim() || "auto",
        }),
      });
      const j = await r.json();
      log.textContent += (j.log || "") + "\n";
      if (j.ok && j.exr) {
        log.textContent += `\n✓ HDRI gerado: ${j.exr} (${j.size_mb} MB)`;
        btn.textContent = "✓ Pronto";
        const fd = new FormData(); fd.append("path", j.exr);
        fetch("/api/reveal", { method: "POST", body: fd });
      } else {
        btn.textContent = "✗ Falhou";
        log.textContent += `\n✗ Erro: ${j.error || "desconhecido"}`;
      }
    } catch (err) {
      log.textContent += `\n✗ Erro: ${err}`;
      btn.textContent = "✗ Falhou";
    }
    setTimeout(() => { btn.textContent = "Renderizar HDRI"; btn.disabled = false; }, 4000);
  });

  $("[data-action='export-blender']")?.addEventListener("click", async (e) => {
    const scenedir = $("#export-project").value;
    if (!scenedir) { alert("Escolhe um projecto primeiro."); return; }
    const btn = e.target;
    const log = $("#export-log");
    log.classList.remove("hidden");
    log.textContent = "A gerar .blend (pode demorar 30–60s no primeiro arranque do Blender)…\n";
    btn.disabled = true; btn.textContent = "A gerar…";
    try {
      const r = await fetch("/api/blender/export", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenedir }),
      });
      const j = await r.json();
      log.textContent += (j.log || "") + "\n";
      if (j.ok && j.blend) {
        log.textContent += `\n✓ .blend criado: ${j.blend}`;
        btn.textContent = "✓ Pronto";
        // abre no Finder o ficheiro
        const fd = new FormData(); fd.append("path", j.blend);
        fetch("/api/reveal", { method: "POST", body: fd });
      } else {
        btn.textContent = "✗ Falhou";
        log.textContent += `\n✗ Erro: ${j.error || "desconhecido"}`;
      }
    } catch (err) {
      log.textContent += `\n✗ Erro: ${err}`;
      btn.textContent = "✗ Falhou";
    }
    setTimeout(() => { btn.textContent = "Gerar .blend"; btn.disabled = false; }, 4000);
  });

  // ─────────────────────────────── Helpers
  function humanSize(b) {
    if (b < 1024) return `${b} B`;
    if (b < 1024 ** 2) return `${(b/1024).toFixed(1)} KB`;
    if (b < 1024 ** 3) return `${(b/1024/1024).toFixed(1)} MB`;
    return `${(b/1024/1024/1024).toFixed(2)} GB`;
  }
  function debounce(fn, ms) {
    let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
  }

  // ─────────────────────────────── Boot
  loadDeps();
  loadHistory();
  loadBlenderStatus();
})();
