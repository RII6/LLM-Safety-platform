import { useRef, useState } from "react";
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
    const [scanLeakage, setScanLeakage] = useState(false);
    const [sample, setSample] = useState(25);

    const [generationEnabled, setGenerationEnabled] = useState(false);
    const [generationProvider, setGenerationProvider] = useState("groq");
    const [generationModel, setGenerationModel] = useState("");
    const [generationClass, setGenerationClass] = useState("harmful");
    const [generationN, setGenerationN] = useState(5);
    const [generationSeed, setGenerationSeed] = useState(0);

    const [, setRefreshKey] = useState(0);
    const audioCtxRef = useRef(null);

    const ensureAudioContext = async () => {
        if (!audioCtxRef.current) {
            audioCtxRef.current = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtxRef.current.state === 'suspended') {
            await audioCtxRef.current.resume();
        }
        return audioCtxRef.current;
    };

    const playNotificationSound = async () => {
        try {
            const ctx = audioCtxRef.current;
            if (!ctx) return;
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
                const ctx = audioCtxRef.current;
                if (!ctx) return;
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
        if (scanGCG) selectedModules.push("gcg");
        if (scanLeakage) selectedModules.push("memory_extraction");

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
        let logIndex = 0;
        const poll = async (jobId) => {
            try {
                const r = await fetch(`/api/scan/status/${jobId}`, { headers });
                const d = await r.json();

                if (d.logs && d.logs.length > logIndex) {
                    for (let i = logIndex; i < d.logs.length; i++) {
                        console.log(`[Backend] ${d.logs[i]}`);
                    }
                    logIndex = d.logs.length;
                }

                if (d.status === "running") {
                    setTimeout(() => poll(jobId), 1500);
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
                body: JSON.stringify({
                    repo: trimmedRepo,
                    force: true,
                    modules: selectedModules,
                    sample: parseInt(sample, 10),
                    generation: {
                        enabled: generationEnabled,
                        n: Number(generationN) || 0,
                        provider: generationProvider,
                        model: generationModel.trim() || null,
                        class: generationClass,
                        seed: Number(generationSeed) || 0,
                    },
                }),
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                let errorMessage = data.error || `Request failed (${res.status}).`;
                if (res.status === 422 && data.detail) {
                    const sampleError = data.detail.find(d => d.loc.includes('sample'));
                    if (sampleError) {
                        errorMessage = 'Sample size must be between 1 and 200.';
                    }
                }
                fail(errorMessage);
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
                scanGCG={scanGCG}
                setScanGCG={setScanGCG}
                scanLeakage={scanLeakage}
                setScanLeakage={setScanLeakage}
                sample={sample}
                setSample={setSample}
                generationEnabled={generationEnabled}
                setGenerationEnabled={setGenerationEnabled}
                generationProvider={generationProvider}
                setGenerationProvider={setGenerationProvider}
                generationModel={generationModel}
                setGenerationModel={setGenerationModel}
                generationClass={generationClass}
                setGenerationClass={setGenerationClass}
                generationN={generationN}
                setGenerationN={setGenerationN}
                generationSeed={generationSeed}
                setGenerationSeed={setGenerationSeed}
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
