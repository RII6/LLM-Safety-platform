import { useState } from 'react';
import MetricDropdown from './MetricDropdown';
import CompareSelectModal from './CompareSelectModal';

const ResultSection = ({ result, openMetrics, toggleMetric }) => {
    const [showCompareModal, setShowCompareModal] = useState(false);

    const verdictClass = result.verdict.code === 'danger' ? 'do_not_deploy' : result.verdict.code;
    const generated = result.meta.generated || {};
    const generatedCount = (generated.harmful || 0) + (generated.benign || 0);

    const downloadJSON = () => {
        const data = {
            repo: result.repo,
            verdict: result.verdict,
            metrics: result.metrics,
            meta: result.meta,
            downloaded_at: new Date().toISOString()
        };
        const json = JSON.stringify(data, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `scan_${result.repo.replace('/', '_')}_${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const openCompareModal = () => setShowCompareModal(true);
    const closeCompareModal = () => setShowCompareModal(false);

    return (
        <section id="result">
            <div className={`verdict ${verdictClass}`}>
                <div className="verdict-header">
                    <div className="repo">
                        {result.repo}
                        {result.from_cache && " · cached"}
                    </div>
                    <div className="verdict-actions">
                        <button onClick={openCompareModal} className="compare-btn-small" title="Compare with another scan">
                            ⇄ Compare with...
                        </button>
                        <button onClick={downloadJSON} className="download-btn-small" title="Download JSON">
                            ⬇ JSON
                        </button>
                    </div>
                </div>
                <span className="badge">{result.verdict.label}</span>
                <p><span className="label">Diagnosis</span><br />{result.verdict.diagnosis}</p>
                <p><span className="label">Recommendation</span><br />{result.verdict.recommendation}</p>
            </div>

            {result.metrics.map((metric, index) => (
                <MetricDropdown
                    key={index}
                    metric={metric}
                    index={index}
                    isOpen={!!openMetrics[index]}
                    onToggle={toggleMetric}
                />
            ))}

            <div className="meta">
                {result.meta.params ? `${(result.meta.params / 1e6).toFixed(0)}M params · ` : ""}
                {result.meta.sample}/{result.meta.sample} prompts · {result.meta.device}/{result.meta.dtype} · {result.meta.elapsed_s}s
                {generatedCount > 0 && ` · ${generatedCount} generated prompts`}
            </div>

            {showCompareModal && (
                <CompareSelectModal
                    currentScanId={result.id}
                    currentRepo={result.repo}
                    onClose={closeCompareModal}
                />
            )}
        </section>
    );
};

export default ResultSection;
