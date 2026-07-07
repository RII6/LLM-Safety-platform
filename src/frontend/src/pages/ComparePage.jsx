import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getColorClass, getHeadlineColor } from '../utils/colorUtils';

export default function ComparePage() {
    const { id1, id2 } = useParams();
    const [scan1, setScan1] = useState(null);
    const [scan2, setScan2] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchScans = async () => {
            try {
                const [res1, res2] = await Promise.all([
                    fetch(`/api/reports/${id1}`),
                    fetch(`/api/reports/${id2}`)
                ]);
                if (!res1.ok || !res2.ok) throw new Error('Failed to load scans');
                const data1 = await res1.json();
                const data2 = await res2.json();
                setScan1(data1);
                setScan2(data2);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchScans();
    }, [id1, id2]);

    if (loading) return <div className="loading">Loading comparison...</div>;
    if (error) return <div className="error">Error: {error}</div>;
    if (!scan1 || !scan2) return <div>Scan not found</div>;

    // Получаем список уникальных заголовков метрик (по title) из обоих сканов
    const allMetricTitles = Array.from(
        new Set([
            ...scan1.metrics.map(m => m.title),
            ...scan2.metrics.map(m => m.title)
        ])
    );

    // Функция для поиска метрики по заголовку в скане
    const findMetric = (scan, title) => scan.metrics.find(m => m.title === title);

    // Форматирование значений полей
    const formatFieldValue = (value) => {
        if (value === null || value === undefined) return '—';
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    };

    return (
        <section className="compare-page">
            <div className="compare-header">
                <h2>Compare Scans</h2>
                <Link to="/history" className="back-link">← Back to history</Link>
            </div>

            {/* Заголовки сканов */}
            <div className="compare-grid-header">
                <div className="compare-column">
                    <h3>{scan1.repo}</h3>
                    <div className={`verdict ${scan1.verdict.code === 'danger' ? 'do_not_deploy' : scan1.verdict.code}`}>
                        <span className="badge">{scan1.verdict.label}</span>
                        <p>{scan1.verdict.diagnosis}</p>
                    </div>
                    <div className="meta">{scan1.meta.created_at ? new Date(scan1.meta.created_at).toLocaleString() : ''}</div>
                </div>
                <div className="compare-column">
                    <h3>{scan2.repo}</h3>
                    <div className={`verdict ${scan2.verdict.code === 'danger' ? 'do_not_deploy' : scan2.verdict.code}`}>
                        <span className="badge">{scan2.verdict.label}</span>
                        <p>{scan2.verdict.diagnosis}</p>
                    </div>
                    <div className="meta">{scan2.meta.created_at ? new Date(scan2.meta.created_at).toLocaleString() : ''}</div>
                </div>
            </div>

            {/* Сравнение метрик */}
            <div className="compare-metrics">
                <h3>Metrics Comparison</h3>
                {allMetricTitles.map((title) => {
                    const metric1 = findMetric(scan1, title);
                    const metric2 = findMetric(scan2, title);
                    return (
                        <div className="metric-row" key={title}>
                            <div className="metric-title">
                                {title}
                                {/* Если есть headline, отображаем её с цветом */}
                                {metric1?.headline && (
                                    <span className={`headline-badge ${getHeadlineColor(metric1.headline)}`}>
                                        {metric1.headline}
                                    </span>
                                )}
                                {!metric1 && metric2?.headline && (
                                    <span className={`headline-badge ${getHeadlineColor(metric2.headline)}`}>
                                        {metric2.headline}
                                    </span>
                                )}
                            </div>
                            <div className="metric-values">
                                <div className="metric-column">
                                    {metric1 ? (
                                        <div className="metric-fields">
                                            {Object.entries(metric1.fields).map(([key, val]) => {
                                                const colorClass = getColorClass(key, val);
                                                return (
                                                    <div key={key} className="field-item">
                                                        <span className="field-key">{key}:</span>
                                                        <span className={`field-value ${colorClass}`}>
                                                            {formatFieldValue(val)}
                                                        </span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="metric-absent">—</div>
                                    )}
                                </div>
                                <div className="metric-column">
                                    {metric2 ? (
                                        <div className="metric-fields">
                                            {Object.entries(metric2.fields).map(([key, val]) => {
                                                const colorClass = getColorClass(key, val);
                                                return (
                                                    <div key={key} className="field-item">
                                                        <span className="field-key">{key}:</span>
                                                        <span className={`field-value ${colorClass}`}>
                                                            {formatFieldValue(val)}
                                                        </span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    ) : (
                                        <div className="metric-absent">—</div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>
        </section>
    );
}