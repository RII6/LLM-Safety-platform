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
    const [scanGCG, setScanGCG] = useState(false);

    const [refreshKey, setRefreshKey] = useState(0);

    const [sample, setSample] = useState(25);

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
            text: `Scanning <b>${trimmedRepo}</b> — loading the model and probing internal state…`,
            isError: false,
            visible: true,
        });

        try {
            const selectedModules = [];
            if (scanGeneral) selectedModules.push("general");
            if (scanInjection) selectedModules.push("prompt_injections");
            if (scanObfuscation) selectedModules.push("obfuscation");
            if (scanSampling) selectedModules.push("sampling");
            if (scanGCG) selectedModules.push("gcg");

            const token = localStorage.getItem('token');
            const res = await fetch("/api/scan", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": token ? `Bearer ${token}` : "",
                },
                body: JSON.stringify({
                    repo: trimmedRepo,
                    force: true,
                    modules: selectedModules,
                    sample: parseInt(sample, 10),  // <-- добавляем sample
                }),
            });

            const data = await res.json();

            if (!res.ok) {
                let errorMessage = data.error || `Request failed (${res.status}).`;
                if (res.status === 422 && data.detail) {
                    const sampleError = data.detail.find(d => d.loc.includes('sample'));
                    if (sampleError) {
                        errorMessage = 'Sample size must be between 1 and 200.';
                    }
                }
                setStatus({
                    text: errorMessage,
                    isError: true,
                    visible: true,
                });
            } else {
                setStatus({ text: "", isError: false, visible: false });
                setResult(data);
                setRefreshKey(prev => prev + 1);
                await playNotificationSound();
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
                scanGCG={scanGCG}
                setScanGCG={setScanGCG}
                sample={sample}
                setSample={setSample}
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