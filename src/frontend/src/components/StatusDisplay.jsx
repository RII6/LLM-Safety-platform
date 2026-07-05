import React from 'react';

const StatusDisplay = ({ text, isError, visible }) => {
    if (!visible) return null;
    return (
        <div className={`status ${isError ? "error" : ""}`}>
            {!isError && <span className="spinner"></span>}
            <span>{text}</span>
        </div>
    );
};

export default StatusDisplay;
