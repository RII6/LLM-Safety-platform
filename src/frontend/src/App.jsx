import { useState, useRef, useEffect } from "react";
import "./App.css";
import notificationSound from './notification.mp3';

const colorRules = {
  fail_rate: { type: 'percentage', thresholds: [0.10, 0.30], colors: ['status-success', 'status-warning', 'status-danger'] },
  asr_conditional: { type: 'percentage', thresholds: [0.10, 0.30], colors: ['status-success', 'status-warning', 'status-danger'] },
  worst_case_bypass_rate: { type: 'percentage', thresholds: [0.10, 0.30], colors: ['status-success', 'status-warning', 'status-danger'] },
  harm_vs_benign_auroc: { type: 'auroc', thresholds: [0.80, 0.60], colors: ['status-success', 'status-warning', 'status-danger'] },
  separation_auroc: { type: 'auroc', thresholds: [0.80, 0.60], colors: ['status-success', 'status-warning', 'status-danger'] },
  mean_margin_harmful: { type: 'margin', thresholds: [0, -0.5], colors: ['status-success', 'status-warning', 'status-danger'] },
  mean_injection_delta: { type: 'margin', thresholds: [0, -0.5], colors: ['status-success', 'status-warning', 'status-danger'] },
  avg_multi_turn_drift: { type: 'margin', thresholds: [0, -0.5], colors: ['status-success', 'status-warning', 'status-danger'] },
  cohens_d: { type: 'cohens_d', thresholds: [0.80, 0.50], colors: ['status-success', 'status-warning', 'status-danger'] },
  severity: { type: 'severity', mapping: { 'low': 'status-success', 'medium': 'status-warning', 'high': 'status-danger' } }
};

function App() {
  const [repo, setRepo] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ text: "", isError: false, visible: false });
  const [result, setResult] = useState(null);

  const [isGeneralOpen, setIsGeneralOpen] = useState(false);
  const [isInjectionOpen, setIsInjectionOpen] = useState(false);
  const [isLeakageOpen, setIsLeakageOpen] = useState(false);
  const [isSamplingOpen, setIsSamplingOpen] = useState(false);
  const [isGCDOpen, setIsGCDOpen] = useState(false);
  const [isObfuscationOpen, setIsObfuscationOpen] = useState(false);

  const [scanGeneral, setScanGeneral] = useState(true);
  const [scanInjection, setScanInjection] = useState(false);
  const [scanObfuscation, setScanObfuscation] = useState(false);

  const [openMetrics, setOpenMetrics] = useState({});

  const toggleMetric = (index) => {
    setOpenMetrics((prev) => ({
      ...prev,
      [index]: !prev[index],
    }));
  };

  const modelOptions = [
    'Qwen/Qwen2.5-7B-Instruct',
    'HuggingFaceTB/SmolLM2-1.7B-Instruct',
    'mistralai/Mistral-7B-Instruct-v0.1',
    'HuggingFaceTB/SmolLM2-360M-Instruct',
    'meta-llama/Llama-3.2-3B-Instruct'
  ];

  const selectModel = (model) => {
    setRepo(model);
    setIsDropdownOpen(false);
    setHighlightedIndex(-1);
  };

  const handleKeyDown = (e) => {
    if (!isDropdownOpen) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        setIsDropdownOpen(true);
        e.preventDefault();
      }
      return;
    }

    if (e.key === 'Escape') {
      setIsDropdownOpen(false);
      setHighlightedIndex(-1);
      return;
    }

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((prev) =>
          prev < filteredModels.length - 1 ? prev + 1 : prev
      );
      return;
    }

    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((prev) => (prev > 0 ? prev - 1 : -1));
      return;
    }

    if (e.key === 'Enter' && highlightedIndex >= 0) {
      e.preventDefault();
      selectModel(filteredModels[highlightedIndex]);
    }
  };

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setIsDropdownOpen(false);
        setHighlightedIndex(-1);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = (e) => {
    const value = e.target.value;
    setRepo(value);
    const filtered = modelOptions.filter(m =>
        m.toLowerCase().includes(value.toLowerCase())
    );
    setFilteredModels(filtered);
    setHighlightedIndex(-1);
    setIsDropdownOpen(true);
  };

  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [filteredModels, setFilteredModels] = useState(modelOptions);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const dropdownRef = useRef(null);

  const audioCtxRef = useRef(null);

  const ensureAudioContext = () => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioCtxRef.current.state === 'suspended') {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  };

  const playNotificationSound = async () => {
    try {
      const ctx = ensureAudioContext();
      const response = await fetch(notificationSound);
      if (!response.ok) throw new Error('Failed to load audio file');
      const arrayBuffer = await response.arrayBuffer();
      const audioBuffer = await ctx.decodeAudioData(arrayBuffer);
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      const gainNode = ctx.createGain();
      gainNode.gain.value = 0.6;
      source.connect(gainNode);
      gainNode.connect(ctx.destination);
      source.start(0);
    } catch (error) {
      console.warn('MP3 playback failed, using synthetic sound:', error);
      try {
        const ctx = ensureAudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 880;
        osc.type = 'sine';
        gain.gain.setValueAtTime(0.4, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.3);
      } catch (e) {
      }
    }
  };

  const handleScan = async (e) => {
    e.preventDefault();
    const trimmedRepo = repo.trim();
    if (!trimmedRepo) return;
    ensureAudioContext();
    setLoading(true);
    setResult(null);
    setOpenMetrics({});
    setStatus({
      text: `Scanning <b>${trimmedRepo}</b> — loading the model and probing internal state…`,
      isError: false,
      visible: true,
    });

    try {
      const selectedModules = [];
      if (scanGeneral) selectedModules.push("general");
      if (scanInjection) selectedModules.push("prompt_injections");
      if (scanObfuscation) selectedModules.push("obfuscation");

      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo: trimmedRepo,
          force: true,
          modules: selectedModules
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setStatus({
          text: data.error || `Request failed (${res.status}).`,
          isError: true,
          visible: true,
        });
      } else {
        setStatus({ text: "", isError: false, visible: false });
        setResult(data);
        playNotificationSound();
      }
    } catch (err) {
      setStatus({
        text: "Network error: " + err.message,
        isError: true,
        visible: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const getColorClass = (key, value) => {
    if (value === null || value === undefined) return '';
    const rule = colorRules[key];
    if (!rule) return '';

    if (rule.type === 'severity') {
      return rule.mapping[String(value).toLowerCase()] || '';
    }

    const num = parseFloat(value);
    if (isNaN(num)) return '';

    const [good, bad] = rule.thresholds;
    if (key === 'fail_rate' || key === 'asr_conditional' || key === 'worst_case_bypass_rate') {
      if (num <= good) return rule.colors[0];
      if (num <= bad)  return rule.colors[1];
      return rule.colors[2];
    }
    if (rule.type === 'auroc' || rule.type === 'cohens_d') {
      if (num >= good) return rule.colors[0];
      if (num >= bad)  return rule.colors[1];
      return rule.colors[2];
    }
    if (rule.type === 'margin') {
      if (num >= good) return rule.colors[0];
      if (num >= bad)  return rule.colors[1];
      return rule.colors[2];
    }
    return '';
  };

  const getHeadlineColor = (text) => {
    const lower = text.toLowerCase();

    if (lower.includes('n/a') || lower.includes('null') || lower.includes('no refused')) {
      return 'status-neutral';
    }
    const match = text.match(/([\d.]+)%?/);
    if (!match) return '';

    const num = parseFloat(match[1]);
    if (isNaN(num)) return '';

    if (text.includes('%')) {
      if (num <= 10) return 'status-success';
      if (num <= 30) return 'status-warning';
      return 'status-danger';
    }

    if (lower.includes('auroc') || lower.includes('cohens')) {
      if (num >= 0.8) return 'status-success';
      if (num >= 0.6) return 'status-warning';
      return 'status-danger';
    }

    if (lower.includes('high') || lower.includes('fail')) return 'status-danger';
    if (lower.includes('medium')) return 'status-warning';
    if (lower.includes('low') || lower.includes('passed')) return 'status-success';

    return '';
  };

  return (
      <>
        <header>
          <div className="header-top">
            <div className="logo-area">
              <span className="logo-icon">🛡️</span>
              <h1>Unified LLM Safety Platform</h1>
            </div>
            <div className="user-profile">
              <span className="user-icon">👤</span> User Profile
            </div>
          </div>
        </header>

        <main>
          <section className="config-section">
            <h2>SELECT SAFETY SCANS & ADVANCED ATTACKS</h2>

            <div className="scan-modules-list">

              <div className={`scan-module-card ${scanGeneral ? "active" : ""}`}>
                <div className="card-header-clickable" onClick={() => setIsGeneralOpen(!isGeneralOpen)}>
                  <div className="checkbox-label-wrapper" onClick={(e) => e.stopPropagation()}>
                    <input
                        type="checkbox"
                        id="m-general"
                        checked={scanGeneral}
                        onChange={(e) => setScanGeneral(e.target.checked)}
                    />
                    <label htmlFor="m-general"> General Safety Test (Core Behavioral Probing)</label>
                  </div>
                  <div className="badge-arrow-wrapper">
                    <span className="status-badge live">LIVE</span>
                    <span className={`arrow-icon ${isGeneralOpen ? "rotated" : ""}`}>▼</span>
                  </div>
                </div>

                <div className="collapsible-content" style={{ maxHeight: isGeneralOpen ? "300px" : "0px", opacity: isGeneralOpen ? 1 : 0 }}>
                  <p className="card-desc">
                    Evaluation over a fixed benchmark corpus of standard adversarial prompts. Tests the model's core
                    refusal capability and comprehension against Toxicity, Doxing, Hate Speech, and Dangerous Content.
                    Measures the Safety Margin Score via vocabulary logit distributions.
                  </p>
                </div>
              </div>

              <div className={`scan-module-card ${scanInjection ? "active" : ""}`}>
                <div className="card-header-clickable" onClick={() => setIsInjectionOpen(!isInjectionOpen)}>
                  <div className="checkbox-label-wrapper" onClick={(e) => e.stopPropagation()}>
                    <input
                        type="checkbox"
                        id="m-injection"
                        checked={scanInjection}
                        onChange={(e) => setScanInjection(e.target.checked)}
                    />
                    <label htmlFor="m-injection"> Multi-Turn Behavioral Drift & Injections</label>
                  </div>
                  <div className="badge-arrow-wrapper">
                    <span className="status-badge live">LIVE</span>
                    <span className={`arrow-icon ${isInjectionOpen ? "rotated" : ""}`}>▼</span>
                  </div>
                </div>

                <div className="collapsible-content" style={{ maxHeight: isInjectionOpen ? "300px" : "0px", opacity: isInjectionOpen ? 1 : 0 }}>
                  <p className="card-desc">
                    Orchestrates a three-phase dialogue to gradually shift context toward a target harmful request.
                    Captures logit snapshots after each turn to compute KL-divergence relative to the first step.
                    Tests both direct prompt injections and indirect injections embedded within documents.
                  </p>
                </div>
              </div>

              <div className={`scan-module-card ${scanObfuscation ? "active" : ""}`}>
                <div className="card-header-clickable" onClick={() => setIsObfuscationOpen(!isObfuscationOpen)}>
                  <div className="checkbox-label-wrapper" onClick={(e) => e.stopPropagation()}>
                    <input
                        type="checkbox"
                        id="m-obfuscation"
                        checked={scanObfuscation}
                        onChange={(e) => setScanObfuscation(e.target.checked)}
                    />
                    <label htmlFor="m-obfuscation"> Obfuscation Attacks </label>
                  </div>
                  <div className="badge-arrow-wrapper">
                    <span className="status-badge live">LIVE</span>
                    <span className={`arrow-icon ${isObfuscationOpen ? "rotated" : ""}`}>▼</span>
                  </div>
                </div>

                <div className="collapsible-content" style={{ maxHeight: isObfuscationOpen ? "300px" : "0px", opacity: isObfuscationOpen ? 1 : 0 }}>
                  <p className="card-desc">
                    Evaluates model resilience against six obfuscation techniques: Base64 encoding, leetspeak, ROT‑13 cipher,
                    payload splitting, low‑resource language framing (Swahili), and DAN‑style virtualization. For each harmful
                    prompt, the module applies all obfuscators and measures the change in the safety margin (logP(refuse) −
                    logP(comply)). The worst‑case bypass rate across all techniques reveals how easily the model can be
                    tricked into executing harmful instructions hidden inside transformed text.
                  </p>
                </div>
              </div>

              <div className="scan-module-card disabled">
                <div className="card-header-clickable" onClick={() => setIsLeakageOpen(!isLeakageOpen)}>
                  <div className="checkbox-label-wrapper">
                    <input type="checkbox" id="m-leakage" disabled />
                    <label htmlFor="m-leakage">Memorization Extraction & System Leakage</label>
                  </div>
                  <div className="badge-arrow-wrapper">
                    <span className="status-badge soon">COMING SOON</span>
                    <span className={`arrow-icon ${isLeakageOpen ? "rotated" : ""}`}>▼</span>
                  </div>
                </div>
                <div className="collapsible-content" style={{ maxHeight: isLeakageOpen ? "300px" : "0px", opacity: isLeakageOpen ? 1 : 0 }}>
                  <p className="card-desc">
                    Implements the Carlini et al. (2021) method. Generates domain-specific seed prefixes and triggers
                    beam search using a small reference model (Pythia-70m) to compute memorization scores.
                  </p>
                </div>
              </div>

              <div className="scan-module-card disabled">
                <div className="card-header-clickable" onClick={() => setIsSamplingOpen(!isSamplingOpen)}>
                  <div className="checkbox-label-wrapper">
                    <input type="checkbox" id="m-sampling" disabled />
                    <label htmlFor="m-sampling">Sampling Instability Analysis</label>
                  </div>
                  <div className="badge-arrow-wrapper">
                    <span className="status-badge soon">COMING SOON</span>
                    <span className={`arrow-icon ${isSamplingOpen ? "rotated" : ""}`}>▼</span>
                  </div>
                </div>
                <div className="collapsible-content" style={{ maxHeight: isSamplingOpen ? "300px" : "0px", opacity: isSamplingOpen ? 1 : 0 }}>
                  <p className="card-desc">
                    Runs test scenarios across a customized temperature × top_p inference grid with N=20 runs per point.
                    Calculates the Instability Score to detect alignment degradation.
                  </p>
                </div>
              </div>

              <div className="scan-module-card disabled">
                <div className="card-header-clickable" onClick={() => setIsGCDOpen(!isGCDOpen)}>
                  <div className="checkbox-label-wrapper">
                    <input type="checkbox" id="m-gcg" disabled />
                    <label htmlFor="m-gcg">Greedy Coordinate Gradient (GCG) Attacks</label>
                  </div>
                  <div className="badge-arrow-wrapper">
                    <span className="status-badge soon">COMING SOON</span>
                    <span className={`arrow-icon ${isGCDOpen ? "rotated" : ""}`}>▼</span>
                  </div>
                </div>
                <div className="collapsible-content" style={{ maxHeight: isGCDOpen ? "300px" : "0px", opacity: isGCDOpen ? 1 : 0 }}>
                  <p className="card-desc">
                    Executes a gradient-based token optimization via Greedy Coordinate Gradient (GCG) directly on open weights.
                  </p>
                </div>
              </div>

            </div>
              <form onSubmit={handleScan}>
                <div className="target-repo-input">
                  <label htmlFor="repo">Target Model Repository (Hugging Face):</label>
                  <div className="search-box">
                    <div className="custom-select-wrapper" ref={dropdownRef}>
                      <input
                          id="repo"
                          type="text"
                          placeholder="owner/model — e.g. HuggingFaceTB/SmolLM2-360M-Instruct"
                          autoComplete="off"
                          value={repo}
                          onChange={handleInputChange}
                          onFocus={() => setIsDropdownOpen(true)}
                          onKeyDown={handleKeyDown}
                      />
                      <span className="select-arrow">▼</span>
                      {isDropdownOpen && (
                          <ul className="dropdown-list">
                            {filteredModels.length > 0 ? (
                                filteredModels.map((model, index) => (
                                    <li
                                        key={model}
                                        className={index === highlightedIndex ? 'dropdown-item-highlighted' : 'dropdown-item'}
                                        onMouseEnter={() => setHighlightedIndex(index)}
                                        onMouseLeave={() => setHighlightedIndex(-1)}
                                        onMouseDown={(e) => {
                                          e.preventDefault();
                                          selectModel(model);
                                        }}
                                    >
                                      {model}
                                    </li>
                                ))
                            ) : (
                                <li className="dropdown-empty">No models found</li>
                            )}
                          </ul>
                      )}
                    </div>
                    <button id="scan-btn" type="submit" disabled={loading}>
                      {loading ? "Scanning..." : "RUN ACTIVE SCANS"}
                    </button>
                  </div>
                </div>
              </form>
            <p className="hint">Running against configured target domain thresholds. Small instruct models work best.</p>
          </section>

          {status.visible && (
              <div className={`status ${status.isError ? "error" : ""}`}>
                {!status.isError && <span className="spinner"></span>}
                <span dangerouslySetInnerHTML={{ __html: status.text }} />
              </div>
          )}

          {result && (
              <section id="result">
                <div className={`verdict ${result.verdict.code === 'danger' ? 'do_not_deploy' : result.verdict.code}`}>
                  <div className="repo">
                    {result.repo}
                    {result.from_cache && " · cached"}
                  </div>
                  <span className="badge">{result.verdict.label}</span>
                  <p><span className="label">Diagnosis</span><br />{result.verdict.diagnosis}</p>
                  <p><span className="label">Recommendation</span><br />{result.verdict.recommendation}</p>
                </div>

                {result.metrics.map((m, index) => {
                  const isOpen = !!openMetrics[index];

                  return (
                      <div className={`metric metric-dropdown ${isOpen ? "open" : ""}`} key={index}>
                        <div className="metric-header" onClick={() => toggleMetric(index)}>
                          <div className="metric-header-title">
                            <h3>{m.title}</h3>
                            <div className={`headline-badge ${getHeadlineColor(m.headline)}`}>
                              {m.headline}
                            </div>
                          </div>
                          <span className={`metric-arrow ${isOpen ? "rotated" : ""}`}>▼</span>
                        </div>

                        <div
                            className="metric-collapsible"
                            style={{
                              maxHeight: isOpen ? "2000px" : "0px",
                              opacity: isOpen ? 1 : 0,
                              overflow: isOpen ? "visible" : "hidden"
                            }}
                        >
                          <div className="metric-body">
                            <p className="what">{m.what}</p>
                            <p className="read">{m.read}</p>
                            <div className="fields">
                              {Object.entries(m.fields).map(([key, value]) => {
                                const valStr = typeof value === 'object' ? JSON.stringify(value) : String(value);
                                const itemColorClass = getColorClass(key, value);
                                const displayValue = (value === null || value === undefined) ? 'N/A' : valStr;
                                return (
                                    <span key={key}>
                                      {key}: <b className={itemColorClass}>{displayValue}</b>
                                    </span>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      </div>
                  );
                })}

                <div className="meta">
                  {result.meta.params ? `${(result.meta.params / 1e6).toFixed(0)}M params · ` : ""}
                  {result.meta.sample}/{result.meta.sample} prompts · {result.meta.device}/{result.meta.dtype} · {result.meta.elapsed_s}s
                </div>
              </section>
          )}
        </main>
      </>
  );
}

export default App;