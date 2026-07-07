import { useState } from "react";
import ConfigSection from "../components/ConfigSection";
import StatusDisplay from "../components/StatusDisplay";
import ResultSection from "../components/ResultSection";
import notificationSound from "../public/notification.mp3";

export default function HomePage() {
    const [repo, setRepo] = useState("");
    const [loading, setLoading] = useState(false);
    const [status, setStatus] = useState({ text: "", isError: false, visible: false });
    const [result, setResult] = useState(null);
    const [openMetrics, setOpenMetrics] = useState({});

    const [scanGeneral, setScanGeneral] = useState(true);
    const [scanInjection, setScanInjection] = useState(false);
    const [scanObfuscation, setScanObfuscation] = useState(false);
    const [scanSampling, setScanSampling] = useState(false);

    const [refreshKey, setRefreshKey] = useState(0);

    let audioCtx = null;

    const ensureAudioContext = async () => {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            await audioCtx.resume();
        }
        return audioCtx;
    };

    const playNotificationSound = async () => {
        try {
            const ctx = audioCtx;
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
                const ctx = audioCtx;
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
                console.error('Synthetic sound failed:', e);
            }
        }
    };

    const toggleMetric = (index) => {
        setOpenMetrics((prev) => ({
            ...prev,
            [index]: !prev[index],
        }));
    };

    const handleScan = async (e) => {
        e.preventDefault();
        const trimmedRepo = repo.trim();
        if (!trimmedRepo) return;

        await ensureAudioContext();

        setLoading(true);
        setResult(null);
        setOpenMetrics({});
        setStatus({
            text: `Scanning ${trimmedRepo} — loading the model and probing internal state… (this can take a few minutes)`,
            isError: false,
            visible: true,
        });

        const selectedModules = [];
        if (scanGeneral) selectedModules.push("general");
        if (scanInjection) selectedModules.push("prompt_injections");
        if (scanObfuscation) selectedModules.push("obfuscation");
        if (scanSampling) selectedModules.push("sampling");

        const token = localStorage.getItem('token');
        const headers = token
            ? { "Content-Type": "application/json", "Authorization": `Bearer ${token}` }
            : { "Content-Type": "application/json" };

        const fail = (msg) => {
            setStatus({ text: msg, isError: true, visible: true });
            setLoading(false);
        };

        const finish = async (scanResult) => {
            setStatus({ text: "", isError: false, visible: false });
            setResult(scanResult);
            setRefreshKey((prev) => prev + 1);
            setLoading(false);
            await playNotificationSound();
        };

        // The server runs the scan in the background; poll until the verdict is ready.
        const poll = async (jobId) => {
            try {
                const r = await fetch(`/api/scan/status/${jobId}`, { headers });
                const d = await r.json();
                if (d.status === "running") {
                    setTimeout(() => poll(jobId), 3000);
                } else if (d.status === "done") {
                    await finish(d.result);
                } else {
                    fail(d.error || "Scan failed.");
                }
            } catch (err) {
                fail("Network error: " + err.message);
            }
        };

        try {
            const res = await fetch("/api/scan", {
                method: "POST",
                headers,
                body: JSON.stringify({ repo: trimmedRepo, force: false, modules: selectedModules }),
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                fail(data.error || `Request failed (${res.status}).`);
                return;
            }
            setTimeout(() => poll(data.job_id), 2000);
        } catch (err) {
            fail("Network error: " + err.message);
        }
    };

    return (
        <>
            <ConfigSection
                repo={repo}
                setRepo={setRepo}
                loading={loading}
                onSubmit={handleScan}
                scanGeneral={scanGeneral}
                setScanGeneral={setScanGeneral}
                scanInjection={scanInjection}
                setScanInjection={setScanInjection}
                scanObfuscation={scanObfuscation}
                setScanObfuscation={setScanObfuscation}
                scanSampling={scanSampling}
                setScanSampling={setScanSampling}
            />

            <StatusDisplay
                text={status.text}
                isError={status.isError}
                visible={status.visible}
            />

            {result && (
                <ResultSection
                    result={result}
                    openMetrics={openMetrics}
                    toggleMetric={toggleMetric}
                />
            )}
        </>
    );
}