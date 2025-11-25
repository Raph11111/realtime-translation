// DOM Elements
const recordButton = document.getElementById('recordButton');
const connectionStatus = document.getElementById('connectionStatus');
const originalText = document.getElementById('originalText');
const translatedText = document.getElementById('translatedText');
const targetLangSelect = document.getElementById('targetLang');
const canvas = document.getElementById('audioVisualizer');
const ctx = canvas.getContext('2d');

// State
let isRecording = false;
let audioContext;
let analyser;
let source;
let animationId;
let wsTranscripts;

// Audio Playback Queue
const audioQueue = [];
let isPlaying = false;

async function playAudioChunk(arrayBuffer) {
    // We need a separate AudioContext for playback if the visualizer one is busy or different
    // But we can reuse the global audioContext if initialized.
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
        await audioContext.resume();
    }

    try {
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        audioQueue.push(audioBuffer);
        processQueue();
    } catch (e) {
        console.error("Error decoding audio data", e);
    }
}

function processQueue() {
    if (isPlaying || audioQueue.length === 0) return;

    isPlaying = true;
    const buffer = audioQueue.shift();
    const source = audioContext.createBufferSource();
    source.buffer = buffer;
    source.connect(audioContext.destination);

    source.onended = () => {
        isPlaying = false;
        processQueue();
    };

    source.start(0);
}

// Initialize WebSocket
function connectWebSocket() {
    let wsUrl;
    if (window.location.protocol === 'file:') {
        wsUrl = 'ws://localhost:8000/ws/transcripts';
    } else {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        wsUrl = `${protocol}//${window.location.host}/ws/transcripts`;
    }

    console.log("Connecting to WebSocket:", wsUrl);
    wsTranscripts = new WebSocket(wsUrl);
    wsTranscripts.binaryType = 'arraybuffer';

    wsTranscripts.onopen = () => {
        console.log("WebSocket Connected");
        connectionStatus.classList.add('connected');
        connectionStatus.classList.remove('error');
        connectionStatus.querySelector('.text').textContent = 'Connected';
        // Send initial config
        updateConfig();
    };

    wsTranscripts.onclose = (event) => {
        console.log("WebSocket Disconnected", event);
        connectionStatus.classList.remove('connected');
        connectionStatus.querySelector('.text').textContent = 'Disconnected';
        setTimeout(connectWebSocket, 3000); // Reconnect
    };

    wsTranscripts.onerror = (error) => {
        console.error("WebSocket Error", error);
        connectionStatus.classList.remove('connected');
        connectionStatus.classList.add('error');
        connectionStatus.querySelector('.text').textContent = 'Connection Error';
    };

    wsTranscripts.onmessage = async (event) => {
        if (event.data instanceof ArrayBuffer) {
            // Handle Audio
            playAudioChunk(event.data);
        } else {
            // Handle Text
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'transcript') {
                    if (data.is_final) {
                        originalText.textContent = data.text;
                        originalText.classList.remove('placeholder');
                    }
                } else if (data.type === 'translation') {
                    translatedText.textContent = data.text;
                    translatedText.classList.remove('placeholder');
                }
            } catch (e) {
                console.error("Error parsing WebSocket message", e);
            }
        }
    };
}

// Audio Visualizer
function initVisualizer(stream) {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    analyser = audioContext.createAnalyser();
    source = audioContext.createMediaStreamSource(stream);

    source.connect(analyser);
    analyser.fftSize = 256;

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    function draw() {
        animationId = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        ctx.fillStyle = 'rgba(15, 23, 42, 0.2)'; // Fade effect
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            barHeight = dataArray[i] / 2;

            // Gradient color based on height
            const r = barHeight + 25 * (i / bufferLength);
            const g = 250 * (i / bufferLength);
            const b = 50;

            ctx.fillStyle = `rgb(${r},${g},${b})`;
            ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

            x += barWidth + 1;
        }
    }

    // Resize canvas
    function resize() {
        canvas.width = canvas.parentElement.offsetWidth;
        canvas.height = canvas.parentElement.offsetHeight;
    }
    window.addEventListener('resize', resize);
    resize();

    draw();
}

// Recording Logic
async function toggleRecording() {
    if (!isRecording) {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Start Visualizer
            initVisualizer(stream);

            isRecording = true;
            recordButton.classList.add('recording');
            document.querySelector('.badge').classList.add('active');
            recordButton.querySelector('.label').textContent = 'Stop Translation';

            // Resume AudioContext if suspended (browser policy)
            if (audioContext && audioContext.state === 'suspended') {
                await audioContext.resume();
            }

        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Microphone access required for visualizer.");
        }
    } else {
        isRecording = false;
        recordButton.classList.remove('recording');
        document.querySelector('.badge').classList.remove('active');
        recordButton.querySelector('.label').textContent = 'Start Live Translation';

        if (audioContext) {
            // Don't close audioContext as we need it for playback
            // audioContext.close(); 
            cancelAnimationFrame(animationId);
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    }
}

// Configuration
function updateConfig() {
    if (wsTranscripts && wsTranscripts.readyState === WebSocket.OPEN) {
        const targetLang = targetLangSelect.value;
        wsTranscripts.send(JSON.stringify({
            type: 'config',
            target_lang: targetLang
        }));
    }
}

// Event Listeners
recordButton.addEventListener('click', toggleRecording);
targetLangSelect.addEventListener('change', updateConfig);

// Init
connectWebSocket();
