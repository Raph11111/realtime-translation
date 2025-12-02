// Global Error Handler - MUST BE FIRST
window.onerror = function (message, source, lineno, colno, error) {
    const status = document.getElementById('connectionStatus');
    if (status) {
        status.innerHTML = `<span class="text" style="color: #ef4444;">Error: ${message}</span>`;
        status.classList.add('error');
    }
    console.error("Global Error:", message, error);
};
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
const audioInputSelect = document.getElementById('audioInput');
const canvas = document.getElementById('audioVisualizer');

// Check for missing elements
if (!recordButton || !connectionStatus || !sourceLangSelect || !targetLangSelect || !targetVoiceSelect || !canvas) {
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

// Audio Device Management
async function fetchAudioDevices() {
    try {
        const response = await fetch('/api/devices');
        const devices = await response.json();

        audioInputSelect.innerHTML = ''; // Clear loading option

        if (devices.length === 0) {
            const option = document.createElement('option');
            option.text = "No devices found";
            audioInputSelect.add(option);
            return;
        }

        devices.forEach(device => {
            const option = document.createElement('option');
            option.value = device.index;
            option.text = device.name;
            if (device.is_default) {
                option.selected = true;
            }
            audioInputSelect.add(option);
        });
    } catch (error) {
        console.error("Error fetching audio devices:", error);
        audioInputSelect.innerHTML = '<option>Error loading devices</option>';
    }
}

async function changeAudioDevice() {
    const deviceIndex = parseInt(audioInputSelect.value);
    console.log("Switching to device index:", deviceIndex);

    try {
        const response = await fetch('/api/devices', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ device_index: deviceIndex })
        });

        const result = await response.json();
        if (result.status === 'success') {
            console.log("Device switched successfully");
        } else {
            console.error("Failed to switch device:", result.message);
            alert("Failed to switch device: " + result.message);
        }
    } catch (error) {
        console.error("Error switching device:", error);
    }
}

// Event Listeners
recordButton.addEventListener('click', toggleRecording);
sourceLangSelect.addEventListener('change', updateConfig);
targetLangSelect.addEventListener('change', updateConfig);
targetVoiceSelect.addEventListener('change', updateConfig);
audioInputSelect.addEventListener('change', changeAudioDevice);

// Init
fetchAudioDevices();
connectWebSocket();
