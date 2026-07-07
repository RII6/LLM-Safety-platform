import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '../utils/api';


const CompareSelectModal = ({ currentScanId, currentRepo, onClose }) => {
    const [scans, setScans] = useState([]);
    const [filteredScans, setFilteredScans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');
    const navigate = useNavigate();

    useEffect(() => {
        const fetchScans = async () => {
            try {
                const res = await apiFetch('/api/reports');
                if (!res.ok) throw new Error('Failed to fetch scans');
                const data = await res.json();
                const otherScans = data.filter(scan => scan.id !== currentScanId);
                setScans(otherScans);
                setFilteredScans(otherScans);
            } catch (err) {
                console.error('Error loading scans:', err);
            } finally {
                setLoading(false);
            }
        };
        if (currentScanId) {
            fetchScans();
        } else {
            setLoading(false);
        }
    }, [currentScanId]);

    useEffect(() => {
        const lowerFilter = filter.toLowerCase();
        const filtered = scans.filter(scan =>
            scan.repo.toLowerCase().includes(lowerFilter)
        );
        setFilteredScans(filtered);
    }, [filter, scans]);

    const handleSelect = (scanId) => {
        if (currentScanId && scanId) {
            navigate(`/compare/${currentScanId}/${scanId}`);
            onClose();
        } else {
            console.error('Invalid scan IDs for comparison');
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content compare-select-modal" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h2 className="modal-title">Select scan to compare</h2>
                    <button className="modal-close" onClick={onClose}>×</button>
                </div>
                <div className="modal-body">
                    <div className="filter-input">
                        <input
                            type="text"
                            placeholder="Filter by repository name..."
                            value={filter}
                            onChange={(e) => setFilter(e.target.value)}
                            autoFocus
                        />
                    </div>
                    {loading ? (
                        <div className="loading">Loading scans...</div>
                    ) : filteredScans.length === 0 ? (
                        <div className="no-scans">
                            {scans.length === 0
                                ? 'No other scans available'
                                : 'No scans match your filter'}
                        </div>
                    ) : (
                        <ul className="scan-list-select">
                            {filteredScans.map(scan => (
                                <li
                                    key={scan.id}
                                    className="scan-item-select"
                                    onClick={() => handleSelect(scan.id)}
                                >
                                    <span className="scan-repo">{scan.repo}</span>
                                    {scan.created_at && (
                                        <span className="scan-date">
                                            {new Date(scan.created_at).toLocaleString()}
                                        </span>
                                    )}
                                    <span className={`scan-verdict ${scan.verdict}`}>
                                        {scan.verdict}
                                    </span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>
        </div>
    );
};

export default CompareSelectModal;