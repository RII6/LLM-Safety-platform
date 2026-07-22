import { useMemo, useState } from 'react';
import ScanModuleCard from './ScanModuleCard';
import CustomSelect from './CustomSelect';
import { modelOptions } from '../constants/modelOptions';

const ConfigSection = ({
                           repo,
                           setRepo,
                           loading,
                           onSubmit,
                           scanGeneral,
                           setScanGeneral,
                           scanInjection,
                           setScanInjection,
                           scanObfuscation,
                           setScanObfuscation,
                           scanSampling,
                           setScanSampling,
                           scanGCG,
                           setScanGCG,
                           scanMemory,
                           setScanMemory,
                           sample,
                           setSample,
                           generationEnabled,
                           setGenerationEnabled,
                           generationProvider,
                           setGenerationProvider,
                           generationModel,
                           setGenerationModel,
                           generationClass,
                           setGenerationClass,
                           generationN,
                           setGenerationN,
                           generationSeed,
                           setGenerationSeed,
                       }) => {
    const [isGeneralOpen, setIsGeneralOpen] = useState(false);
    const [isInjectionOpen, setIsInjectionOpen] = useState(false);
    const [isObfuscationOpen, setIsObfuscationOpen] = useState(false);
    const [isLeakageOpen, setIsLeakageOpen] = useState(false);
    const [isSamplingOpen, setIsSamplingOpen] = useState(false);
    const [isGCDOpen, setIsGCDOpen] = useState(false);
    const [isMemoryOpen, setIsMemoryOpen] = useState(false);

    const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

    const [isDropdownOpen, setIsDropdownOpen] = useState(false);
    const [highlightedIndex, setHighlightedIndex] = useState(-1);
    const filteredModels = useMemo(
        () => modelOptions.filter(m => m.toLowerCase().includes(repo.toLowerCase())),
        [repo]
    );

    const handleInputChange = (e) => {
        const value = e.target.value;
        setRepo(value);
        setHighlightedIndex(-1);
        setIsDropdownOpen(true);
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

    const selectModel = (model) => {
        setRepo(model);
        setIsDropdownOpen(false);
        setHighlightedIndex(-1);
    };

    const handleFormSubmit = (e) => {
        e.preventDefault();
        onSubmit(e);
    };

    return (
        <section className="config-section">
            <h2>SELECT SAFETY SCANS & ADVANCED ATTACKS</h2>

            <div className="scan-modules-list">
                <ScanModuleCard
                    id="m-general"
                    title="General Safety Test (Core Behavioral Probing)"
                    description="Evaluation over a fixed benchmark corpus of standard adversarial prompts. Tests the model's core refusal capability and comprehension against Toxicity, Doxing, Hate Speech, and Dangerous Content. Measures the Safety Margin Score via vocabulary logit distributions."
                    isActive={scanGeneral}
                    checked={scanGeneral}
                    onChange={setScanGeneral}
                    isOpen={isGeneralOpen}
                    onToggle={() => setIsGeneralOpen(!isGeneralOpen)}
                    statusBadge={{ label: 'LIVE', className: 'live' }}
                />

                <ScanModuleCard
                    id="m-injection"
                    title="Multi-Turn Behavioral Drift & Injections"
                    description="Orchestrates a three-phase dialogue to gradually shift context toward a target harmful request. Captures logit snapshots after each turn to compute KL-divergence relative to the first step. Tests both direct prompt injections and indirect injections embedded within documents."
                    isActive={scanInjection}
                    checked={scanInjection}
                    onChange={setScanInjection}
                    isOpen={isInjectionOpen}
                    onToggle={() => setIsInjectionOpen(!isInjectionOpen)}
                    statusBadge={{ label: 'LIVE', className: 'live' }}
                />

                <ScanModuleCard
                    id="m-obfuscation"
                    title="Obfuscation Attacks"
                    description="Evaluates model resilience against six obfuscation techniques: Base64 encoding, leetspeak, ROT‑13 cipher, payload splitting, low‑resource language framing (Swahili), and DAN‑style virtualization. For each harmful prompt, the module applies all obfuscators and measures the change in the safety margin (logP(refuse) − logP(comply)). The worst‑case bypass rate across all techniques reveals how easily the model can be tricked into executing harmful instructions hidden inside transformed text."
                    isActive={scanObfuscation}
                    checked={scanObfuscation}
                    onChange={setScanObfuscation}
                    isOpen={isObfuscationOpen}
                    onToggle={() => setIsObfuscationOpen(!isObfuscationOpen)}
                    statusBadge={{ label: 'LIVE', className: 'live' }}
                />

                <ScanModuleCard
                    id="m-sampling"
                    title="Sampling Instability Analysis"
                    description="Runs test scenarios across a customized temperature × top_p inference grid with N=20 runs per point. Calculates the Instability Score to detect alignment degradation."
                    checked={scanSampling}
                    onChange={setScanSampling}
                    isOpen={isSamplingOpen}
                    onToggle={() => setIsSamplingOpen(!isSamplingOpen)}
                    statusBadge={{ label: 'LIVE', className: 'live' }}
                />

                <ScanModuleCard
                    id="m-leakage"
                    title="Memorization Extraction & System Leakage"
                    description="Implements the Carlini et al. (2021) method. Generates domain-specific seed prefixes and triggers beam search using a small reference model (Pythia-70m) to compute memorization scores."
                    checked={scanMemory}
                    onChange={setScanMemory}
                    isOpen={isMemoryOpen}
                    onToggle={() => setIsLeakageOpen(!isLeakageOpen)}
                    statusBadge={{ label: 'LIVE', className: 'live' }}
                />

                <ScanModuleCard
                    id="m-gcg"
                    title="Greedy Coordinate Gradient (GCG) Attacks"
                    description="Appends known adversarial suffixes to each harmful prompt, generates a real response, and labels it with the zero-shot NLI detector (comply vs refuse). The attack success rate is the fraction of prompt × suffix attempts where the model complies, revealing how easily it can be forced into harmful compliance by adversarial suffixes."
                    isActive={scanGCG}
                    checked={scanGCG}
                    onChange={setScanGCG}
                    isOpen={isGCDOpen}
                    onToggle={() => setIsGCDOpen(!isGCDOpen)}
                    statusBadge={{ label: 'LIVE', className: 'live' }}
                />

            </div>

            <div className="advanced-settings">
                <div className="advanced-header" onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}>
                    <h3>Advanced Settings</h3>
                    <span className={`arrow-icon ${isAdvancedOpen ? 'rotated' : ''}`}>▼</span>
                </div>
                <div
                    className="advanced-content"
                    style={{
                        maxHeight: isAdvancedOpen ? '600px' : '0px',
                        opacity: isAdvancedOpen ? 1 : 0,
                        overflow: 'hidden',
                        transition: 'max-height 0.4s ease, opacity 0.3s ease',
                    }}
                >
                    <div className="sample-selector">
                        <label htmlFor="sample">Sample size:</label>
                        <input
                            id="sample"
                            type="number"
                            min="1"
                            max="200"
                            value={sample}
                            onChange={(e) => setSample(Number(e.target.value))}
                        />
                    </div>

                    <div className="generation-toggle">
                        <label>
                            <input
                                type="checkbox"
                                checked={generationEnabled}
                                onChange={(e) => setGenerationEnabled(e.target.checked)}
                            />
                            Generate additional prompts via API
                        </label>
                    </div>

                    {generationEnabled && (
                        <div className="generation-controls">
                            <label>
                                Provider
                                <select
                                    value={generationProvider}
                                    onChange={(e) => setGenerationProvider(e.target.value)}
                                >
                                    <option value="groq">Groq</option>
                                    <option value="google">Google AI Studio / Gemma</option>
                                </select>
                            </label>

                            <label>
                                Model
                                <input
                                    type="text"
                                    value={generationModel}
                                    onChange={(e) => setGenerationModel(e.target.value)}
                                    placeholder={generationProvider === 'groq' ? 'llama-3.3-70b-versatile' : 'gemma-3-27b-it'}
                                />
                            </label>

                            <label>
                                Prompts per class
                                <input
                                    type="number"
                                    min="0"
                                    max="50"
                                    value={generationN}
                                    onChange={(e) => setGenerationN(Number(e.target.value))}
                                />
                            </label>

                            <label>
                                Class
                                <select
                                    value={generationClass}
                                    onChange={(e) => setGenerationClass(e.target.value)}
                                >
                                    <option value="harmful">Harmful</option>
                                    <option value="benign">Benign</option>
                                    <option value="both">Both</option>
                                </select>
                            </label>

                            <label>
                                Seed
                                <input
                                    type="number"
                                    min="0"
                                    value={generationSeed}
                                    onChange={(e) => setGenerationSeed(Number(e.target.value))}
                                />
                            </label>
                        </div>
                    )}
                </div>
            </div>

            <form onSubmit={handleFormSubmit}>
                <div className="target-repo-input">
                    <label htmlFor="repo">Target Model Repository (Hugging Face):</label>
                    <div className="search-box">
                        <CustomSelect
                            value={repo}
                            onChange={handleInputChange}
                            onFocus={() => setIsDropdownOpen(true)}
                            onKeyDown={handleKeyDown}
                            isOpen={isDropdownOpen}
                            onToggle={setIsDropdownOpen}
                            filteredOptions={filteredModels}
                            highlightedIndex={highlightedIndex}
                            onHighlight={setHighlightedIndex}
                            onSelect={selectModel}
                            placeholder="owner/model — e.g. HuggingFaceTB/SmolLM2-360M-Instruct"
                        />
                        <button id="scan-btn" type="submit" disabled={loading}>
                            {loading ? "Scanning..." : "RUN ACTIVE SCANS"}
                        </button>
                    </div>
                </div>
            </form>
            <p className="hint">Running against configured target domain thresholds. Small instruct models work best.</p>
        </section>
    );
};

export default ConfigSection;