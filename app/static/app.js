// Global Error Handler - MUST BE FIRST
window.onerror = function (message, source, lineno, colno, error) {
    const status = document.getElementById('connectionStatus');
    if (status) {
        status.innerHTML = `<span class="text" style="color: #ef4444;">Error: ${message}</span>`;
        status.classList.add('error');
    }
    console.error("Global Error:", message, error);
};

// Debug: Set status to Initializing
const statusDebug = document.getElementById('connectionStatus');
if (statusDebug) {
    statusDebug.querySelector('.text').textContent = 'Initializing JS...';
}

// DOM Elements
const recordButton = document.getElementById('recordButton');
const connectionStatus = document.getElementById('connectionStatus');
const originalText = document.getElementById('originalText');
const translatedText = document.getElementById('translatedText');
const sourceLangSelect = document.getElementById('sourceLang');
const targetLangSelect = document.getElementById('targetLang');
const targetVoiceSelect = document.getElementById('targetVoice');
const canvas = document.getElementById('audioVisualizer');
const sourceLangBadge = document.getElementById('sourceLangBadge');
const targetLangBadge = document.getElementById('targetLangBadge');

// Check for missing elements
if (!recordButton || !connectionStatus || !sourceLangSelect || !targetLangSelect || !targetVoiceSelect || !canvas || !sourceLangBadge || !targetLangBadge) {
    throw new Error("Missing required DOM elements!");
}

const ctx = canvas.getContext('2d');

// State
let isRecording = false;
let audioContext;
let analyser;
let source;
let animationId;
let wsTranscripts;
let hasConnection = false;

// Audio Playback State
let nextStartTime = 0;

async function playAudioChunk(arrayBuffer) {
    if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (audioContext.state === 'suspended') {
        await audioContext.resume();
    }

    try {
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);

        // Scheduling logic for smooth playback
        const currentTime = audioContext.currentTime;

        // If next start time is in the past (underrun), reset it to now
        if (nextStartTime < currentTime) {
            nextStartTime = currentTime;
        }

        source.start(nextStartTime);

        // Advance next start time by duration of this chunk
        nextStartTime += audioBuffer.duration;

    } catch (e) {
        console.error("Error decoding audio data", e);
    }
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
        hasConnection = true;
        connectionStatus.classList.add('connected');
        connectionStatus.classList.remove('error');
        connectionStatus.querySelector('.text').textContent = 'Connected';
        // Send initial config
        updateConfig();
    };

    wsTranscripts.onclose = (event) => {
        console.log("WebSocket Disconnected", event);
        hasConnection = false;
        connectionStatus.classList.remove('connected');
        connectionStatus.querySelector('.text').textContent = 'Disconnected';
        setRecordingState(false);
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
                    // Remove placeholder class on first text
                    if (originalText.classList.contains('placeholder')) {
                        originalText.textContent = '';
                        originalText.classList.remove('placeholder');
                    }

                    if (data.is_final) {
                        // For final transcripts, append with a space
                        originalText.textContent += data.text + ' ';
                        originalText.classList.remove('interim');
                    } else {
                        // For interim, show in a subtle way (could add styling)
                        originalText.classList.add('interim');
                    }

                    // Auto-scroll to bottom
                    originalText.scrollTop = originalText.scrollHeight;

                } else if (data.type === 'translation') {
                    // Remove placeholder class on first text
                    if (translatedText.classList.contains('placeholder')) {
                        translatedText.textContent = '';
                        translatedText.classList.remove('placeholder');
                    }

                    // Append translation with a space
                    translatedText.textContent += data.text + ' ';

                    // Auto-scroll to bottom
                    translatedText.scrollTop = translatedText.scrollHeight;
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

        // Clear with transparency for trail effect? No, clean wipe for Lumia style
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const barWidth = (canvas.width / bufferLength) * 2.5;
        let barHeight;
        let x = 0;

        for (let i = 0; i < bufferLength; i++) {
            barHeight = dataArray[i] / 1.5; // Scale down slightly

            // Gradient color based on height/position - Lumia Cyan/Purple
            const gradient = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
            gradient.addColorStop(0, '#7000ff');
            gradient.addColorStop(1, '#00ddff');

            ctx.fillStyle = gradient;

            // Rounded bars
            ctx.beginPath();
            ctx.roundRect(x, canvas.height - barHeight, barWidth, barHeight, 5);
            ctx.fill();

            x += barWidth + 2;
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
    if (!wsTranscripts || wsTranscripts.readyState !== WebSocket.OPEN) {
        alert("Waiting for server connection before starting.");
        return;
    }

    if (!isRecording) {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Start Visualizer
            initVisualizer(stream);

            setRecordingState(true);
            sendControl('start');

            // Resume AudioContext if suspended (browser policy)
            if (audioContext && audioContext.state === 'suspended') {
                await audioContext.resume();
            }

        } catch (err) {
            console.error("Error accessing microphone:", err);
            alert("Microphone access required for visualizer.");
        }
    } else {
        setRecordingState(false);
        sendControl('stop');

        if (audioContext) {
            // Don't close audioContext as we need it for playback
            if (animationId) {
                cancelAnimationFrame(animationId);
            }
            if (ctx) {
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
        }
    }
}

function setRecordingState(active) {
    isRecording = active;
    recordButton.classList.toggle('recording', active);
    // Badge animation handled by CSS on status indicator if needed, 
    // but button pulse is enough.
    const labelSpan = recordButton.querySelector('.label');
    if (labelSpan) labelSpan.textContent = active ? 'Stop Translation' : 'Start Translation';
}

// Configuration
function updateConfig() {
    // Update Badges
    if (sourceLangBadge && sourceLangSelect) {
        sourceLangBadge.textContent = sourceLangSelect.value.toUpperCase();
    }
    if (targetLangBadge && targetLangSelect) {
        targetLangBadge.textContent = targetLangSelect.value.toUpperCase();
    }

    if (wsTranscripts && wsTranscripts.readyState === WebSocket.OPEN) {
        const sourceLang = sourceLangSelect.value;
        const targetLang = targetLangSelect.value;
        const targetVoice = targetVoiceSelect.value;

        wsTranscripts.send(JSON.stringify({
            type: 'config',
            source_lang: sourceLang,
            target_lang: targetLang,
            target_voice: targetVoice
        }));
    }
}

function sendControl(action) {
    if (wsTranscripts && wsTranscripts.readyState === WebSocket.OPEN) {
        wsTranscripts.send(JSON.stringify({
            type: 'control',
            action,
            source_lang: sourceLangSelect.value,
            target_lang: targetLangSelect.value,
            target_voice: targetVoiceSelect.value
        }));
    }
}

// Event Listeners
recordButton.addEventListener('click', toggleRecording);
sourceLangSelect.addEventListener('change', updateConfig);
targetLangSelect.addEventListener('change', updateConfig);
targetVoiceSelect.addEventListener('change', updateConfig);

// Init
// Trigger initial badge update
updateConfig();
connectWebSocket();
