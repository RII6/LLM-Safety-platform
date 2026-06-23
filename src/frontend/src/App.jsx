import { useState } from "react";
import "./App.css";

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

  // Состояния для чекбоксов выбора видов безопасности
  const [scanGeneral, setScanGeneral] = useState(true);
  const [scanInjection, setScanInjection] = useState(false);

  const handleScan = async (e) => {
    e.preventDefault();
    const trimmedRepo = repo.trim();
    if (!trimmedRepo) return;

    setLoading(true);
    setResult(null);
    setStatus({
      text: `Scanning <b>${trimmedRepo}</b> — loading the model and probing internal state…`,
      isError: false,
      visible: true,
    });

    try {
      const selectedModules = [];
      if (scanGeneral) selectedModules.push("general");
      if (scanInjection) selectedModules.push("prompt_injections");

      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo: trimmedRepo,
          force: false,
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
              <div className="scan-module-card active">
                <div className="card-header" onClick={() => setIsGeneralOpen(!isGeneralOpen)} style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <input
                        type="checkbox"
                        id="m-general"
                        checked={scanGeneral}
                        onChange={(e) => setScanGeneral(e.target.checked)}
                    />
                    <label htmlFor="m-general"> General Safety Test (Core Behavioral Probing)</label>
                    <span className="status-badge live">LIVE</span>
                  </div>
                  <span style={{
                    transform: isGeneralOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.4s ease-in-out',
                    color: '#6c757d',
                    fontSize: '12px'
                  }}>▼</span>
                </div>

                <div style={{
                  maxHeight: isGeneralOpen ? '200px' : '0px',
                  opacity: isGeneralOpen ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.4s ease-in-out, opacity 0.3s ease-in-out',
                }}>
                  <p className="card-desc" style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e0e0e0' }}>
                    Evaluation over a fixed benchmark corpus of standard adversarial prompts. Tests the model's core
                    refusal capability and comprehension against Toxicity, Doxing, Hate Speech, and Dangerous Content.
                    Measures the Safety Margin Score via vocabulary logit distributions.
                  </p>
                </div>
              </div>

              <div className="scan-module-card active">
                <div className="card-header" onClick={() => setIsInjectionOpen(!isInjectionOpen)} style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%'}}>
                    <input
                        type="checkbox"
                        id="m-injection"
                        checked={scanInjection}
                        onChange={(e) => setScanInjection(e.target.checked)}
                    />
                    <label htmlFor="m-injection"> Multi-Turn Behavioral Drift & Injections</label>
                    <span className="status-badge live">LIVE</span>
                  </div>
                  <span style={{
                    transform: isInjectionOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.4s ease-in-out',
                    color: '#6c757d',
                    fontSize: '12px'
                  }}>▼</span>
                </div>

                <div style={{
                  maxHeight: isInjectionOpen ? '200px' : '0px',
                  opacity: isInjectionOpen ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.4s ease-in-out, opacity 0.3s ease-in-out',
                }}>
                  <p className="card-desc" style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e0e0e0' }}>
                    Orchestrates a three-phase dialogue to gradually shift context toward a target harmful request.
                    Captures logit snapshots after each turn to compute KL-divergence relative to the first step.
                    Tests both direct prompt injections and indirect injections embedded within documents.
                  </p>
                </div>
              </div>

              <div className="scan-module-card disabled">
                <div className="card-header" onClick={() => setIsLeakageOpen(!isLeakageOpen)} style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <input type="checkbox" id="m-leakage" disabled />
                  <label htmlFor="m-leakage">Memorization Extraction & System Leakage</label>
                  <span className="status-badge soon">COMING SOON</span>
                  <span style={{
                    transform: isLeakageOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.4s ease-in-out',
                    color: '#6c757d',
                    fontSize: '12px'
                  }}>▼</span>
                </div>
                <div style={{
                  maxHeight: isLeakageOpen ? '200px' : '0px',
                  opacity: isLeakageOpen ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.4s ease-in-out, opacity 0.3s ease-in-out',
                }}>
                  <p className="card-desc" style={{marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e0e0e0'}}>
                    Implements the Carlini et al. (2021) method. Generates domain-specific seed prefixes and triggers
                    beam search using a small reference model (Pythia-70m) to compute memorization scores.
                    Includes adversarial scenarios targeting system prompt extraction and precise data leaks.
                  </p>
                </div>
              </div>

              <div className="scan-module-card disabled">
                <div className="card-header" onClick={() => setIsSamplingOpen(!isSamplingOpen)} style={{cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <input type="checkbox" id="m-sampling" disabled />
                  <label htmlFor="m-sampling">Sampling Instability Analysis</label>
                  <span className="status-badge soon">COMING SOON</span>
                  <span style={{
                    transform: isSamplingOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.4s ease-in-out',
                    color: '#6c757d',
                    fontSize: '12px'
                  }}>▼</span>
                </div>
                <div style={{
                  maxHeight: isSamplingOpen ? '200px' : '0px',
                  opacity: isSamplingOpen ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.4s ease-in-out, opacity 0.3s ease-in-out',
                }}>
                  <p className="card-desc" style={{marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e0e0e0'}}>
                    Runs test scenarios across a customized temperature × top_p inference grid with N=20 runs per point.
                    Calculates the Instability Score (max(P_safe) - min(P_safe)) to detect alignment degradation under varying sampling parameters.
                  </p>
                </div>
              </div>

              <div className="scan-module-card disabled">
                <div className="card-header" onClick={() => setIsGCDOpen(!isGCDOpen)} style={{ cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                  <input type="checkbox" id="m-gcg" disabled />
                  <label htmlFor="m-gcg">Greedy Coordinate Gradient (GCG) Attacks</label>
                  <span className="status-badge soon">COMING SOON</span>
                  <span style={{
                    transform: isGCDOpen ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.4s ease-in-out',
                    color: '#6c757d',
                    fontSize: '12px'
                  }}>▼</span>
                </div>
                <div style={{
                  maxHeight: isGCDOpen ? '200px' : '0px',
                  opacity: isGCDOpen ? 1 : 0,
                  overflow: 'hidden',
                  transition: 'max-height 0.4s ease-in-out, opacity 0.3s ease-in-out',
                }}>
                  <p className="card-desc" style={{marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #e0e0e0'}}>
                    Executes a gradient-based token optimization via Greedy Coordinate Gradient (GCG) directly on open weights.
                    Discovers universal adversarial suffixes designed to mathematically force the model to begin its response with an affirmative token.
                  </p>
                </div>
              </div>

            </div>

            <form onSubmit={handleScan}>
              <div className="target-repo-input">
                <label htmlFor="repo">Target Model Repository (Hugging Face):</label>
                <div className="search-box">
                  <input
                      id="repo"
                      type="text"
                      placeholder="owner/model — e.g. HuggingFaceTB/SmolLM2-360M-Instruct"
                      autoComplete="off"
                      value={repo}
                      onChange={(e) => setRepo(e.target.value)}
                  />
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

                {result.metrics.map((m, index) => (
                    <div className="metric" key={index}>
                      <h3>{m.title}</h3>
                      <div className="headline">{m.headline}</div>
                      <p className="what">{m.what}</p>
                      <p className="read">{m.read}</p>
                      <div className="fields">
                        {Object.entries(m.fields).map(([key, value]) => {
                          const valStr = typeof value === 'object' ? JSON.stringify(value) : String(value);
                          const lowerVal = valStr.toLowerCase();

                          // Назначаем класс цвета в зависимости от критичности статуса
                          let highlightClass = "";
                          if (lowerVal === "high" || lowerVal === "failed" || lowerVal === "1") {
                            highlightClass = "status-danger";
                          } else if (lowerVal === "low" || lowerVal === "passed" || lowerVal === "false" || lowerVal === "blocked") {
                            highlightClass = "status-success";
                          }

                          return (
                              <span key={key}>
                              {key}: <b className={highlightClass}>{valStr}</b>
                            </span>
                          );
                        })}
                      </div>
                    </div>
                ))}

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