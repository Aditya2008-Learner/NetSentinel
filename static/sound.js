/**
 * Net Sentinel — Sound Feedback System (Web Audio API)
 *
 * Professional, local procedural audio synthesis for Security Operations Center feedback.
 * Zero external audio files or network dependencies.
 * Complies with strict CSP (no inline scripts/eval) and browser autoplay policies.
 */

(function (window) {
    'use strict';

    const STORAGE_KEY_ENABLED = 'net_sentinel_sound_enabled';
    const STORAGE_KEY_VOLUME = 'net_sentinel_sound_volume';

    // State variables
    let audioCtx = null;
    let masterGain = null;
    let isUnlocked = false;
    let enabled = true;
    let volume = 0.5; // Default volume: 50%
    const lastPlayedTimes = {
        success: 0,
        error: 0,
        alert: 0,
        click: 0
    };
    const THROTTLE_MS = 250; // Throttle to prevent duplicate/overlapping sounds

    // Load persisted preferences
    try {
        const storedEnabled = localStorage.getItem(STORAGE_KEY_ENABLED);
        if (storedEnabled !== null) {
            enabled = storedEnabled === 'true';
        }
        const storedVolume = localStorage.getItem(STORAGE_KEY_VOLUME);
        if (storedVolume !== null) {
            const parsed = parseFloat(storedVolume);
            if (!isNaN(parsed) && parsed >= 0 && parsed <= 1) {
                volume = parsed;
            }
        }
    } catch (e) {
        // localStorage may be disabled or restricted; keep defaults
    }

    /**
     * Initializes the Web Audio API context if not already created.
     */
    function getAudioContext() {
        if (!audioCtx) {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (AudioContextClass) {
                audioCtx = new AudioContextClass();
                masterGain = audioCtx.createGain();
                masterGain.gain.setValueAtTime(volume, audioCtx.currentTime);
                masterGain.connect(audioCtx.destination);
            }
        }
        return audioCtx;
    }

    /**
     * Unlocks audio after user interaction.
     */
    function unlockAudio() {
        if (isUnlocked) return;
        const ctx = getAudioContext();
        if (ctx) {
            if (ctx.state === 'suspended') {
                ctx.resume().then(function () {
                    isUnlocked = true;
                }).catch(function () {});
            } else {
                isUnlocked = true;
            }
        }
    }

    // Attach unlock listeners to user gesture events
    const unlockEvents = ['click', 'keydown', 'touchstart', 'pointerdown'];
    function onFirstInteraction() {
        unlockAudio();
        unlockEvents.forEach(function (evt) {
            window.removeEventListener(evt, onFirstInteraction, true);
        });
    }
    unlockEvents.forEach(function (evt) {
        window.addEventListener(evt, onFirstInteraction, { capture: true, once: false, passive: true });
    });

    /**
     * Creates an envelope-controlled tone.
     */
    function playTone(freq, type, startTime, duration, attack, decay, peakGain) {
        if (!audioCtx || !masterGain) return null;

        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc.type = type || 'sine';
        osc.frequency.setValueAtTime(freq, startTime);

        gain.gain.setValueAtTime(0.0001, startTime);
        gain.gain.exponentialRampToValueAtTime(Math.max(peakGain, 0.0002), startTime + attack);
        gain.gain.exponentialRampToValueAtTime(0.0001, startTime + attack + decay);

        osc.connect(gain);
        gain.connect(masterGain);

        osc.start(startTime);
        osc.stop(startTime + duration);

        return { osc: osc, gain: gain };
    }

    /**
     * 1. SUCCESS SOUND:
     * A soft, elegant two-note electronic chime ("ting") for completed operations.
     * Notes: E5 (659.25 Hz) followed by B5 (987.77 Hz), soft sine with gentle harmonics.
     */
    function playSuccess() {
        const ctx = getAudioContext();
        if (!ctx || ctx.state !== 'running') return;

        const now = ctx.currentTime;
        const note1Freq = 659.25; // E5
        const note2Freq = 987.77; // B5

        // Note 1 (grace note)
        playTone(note1Freq, 'sine', now, 0.12, 0.015, 0.09, 0.16);

        // Note 2 (resolving chime)
        playTone(note2Freq, 'sine', now + 0.07, 0.35, 0.02, 0.30, 0.22);

        // Subtle overtone for sparkle
        playTone(note2Freq * 1.5, 'sine', now + 0.07, 0.20, 0.02, 0.16, 0.04);
    }

    /**
     * 2. ERROR / CANCEL SOUND:
     * A short, muted descending electronic tone for failed, rejected, or cancelled operations.
     * Pitch slides from ~320 Hz to ~160 Hz with soft decay.
     */
    function playError() {
        const ctx = getAudioContext();
        if (!ctx || ctx.state !== 'running') return;

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        const filter = ctx.createBiquadFilter();

        // Muted lowpass filter to prevent harshness
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(800, now);
        filter.frequency.exponentialRampToValueAtTime(200, now + 0.22);

        osc.type = 'triangle';
        osc.frequency.setValueAtTime(320, now);
        osc.frequency.exponentialRampToValueAtTime(160, now + 0.22);

        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(0.20, now + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);

        osc.connect(filter);
        filter.connect(gain);
        gain.connect(masterGain);

        osc.start(now);
        osc.stop(now + 0.24);
    }

    /**
     * 3. SECURITY ALERT SOUND:
     * A subtle double-pulse notification for high-priority security events.
     * Two short pulses at ~830 Hz spaced by 70ms.
     */
    function playAlert() {
        const ctx = getAudioContext();
        if (!ctx || ctx.state !== 'running') return;

        const now = ctx.currentTime;
        const freq = 830.61; // G#5

        // Pulse 1
        playTone(freq, 'sine', now, 0.07, 0.01, 0.05, 0.18);
        playTone(freq * 2, 'sine', now, 0.05, 0.01, 0.03, 0.03); // harmonic

        // Pulse 2 (slightly higher in pitch: 880 Hz A5)
        playTone(880, 'sine', now + 0.10, 0.14, 0.01, 0.11, 0.22);
        playTone(880 * 2, 'sine', now + 0.10, 0.08, 0.01, 0.05, 0.04);
    }

    /**
     * 4. INTERACTION SOUND:
     * An optional quiet click for selected important interactions.
     * Ultra-short bandpassed tactile click (15ms).
     */
    function playClick() {
        const ctx = getAudioContext();
        if (!ctx || ctx.state !== 'running') return;

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(1200, now);
        osc.frequency.exponentialRampToValueAtTime(400, now + 0.015);

        gain.gain.setValueAtTime(0.0001, now);
        gain.gain.exponentialRampToValueAtTime(0.08, now + 0.003);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.015);

        osc.connect(gain);
        gain.connect(masterGain);

        osc.start(now);
        osc.stop(now + 0.02);
    }

    /**
     * Public sound trigger interface.
     * @param {'success'|'error'|'alert'|'click'} type
     */
    function play(type) {
        if (!enabled) return;
        if (!isUnlocked) {
            // Attempt auto-unlock if user has interacted
            unlockAudio();
            if (!isUnlocked) return;
        }

        const now = Date.now();
        if (now - (lastPlayedTimes[type] || 0) < THROTTLE_MS) {
            return; // Throttle repeated events
        }
        lastPlayedTimes[type] = now;

        try {
            switch (type) {
                case 'success':
                    playSuccess();
                    break;
                case 'error':
                    playError();
                    break;
                case 'alert':
                    playAlert();
                    break;
                case 'click':
                    playClick();
                    break;
            }
        } catch (err) {
            // Audio failure should never block UI or throw
            console.warn('[NetSentinelSound] Playback error:', err);
        }
    }

    /**
     * Updates master volume (0.0 to 1.0).
     */
    function setVolume(newVolume) {
        const clamped = Math.max(0, Math.min(1, parseFloat(newVolume) || 0));
        volume = clamped;
        if (masterGain && audioCtx) {
            masterGain.gain.setValueAtTime(volume, audioCtx.currentTime);
        }
        try {
            localStorage.setItem(STORAGE_KEY_VOLUME, volume.toFixed(2));
        } catch (e) {}
    }

    /**
     * Enables or disables sound effects globally.
     */
    function setEnabled(isEnabled) {
        enabled = Boolean(isEnabled);
        try {
            localStorage.setItem(STORAGE_KEY_ENABLED, enabled ? 'true' : 'false');
        } catch (e) {}
    }

    // Expose sound manager API on window
    window.NetSentinelSound = {
        play: play,
        setVolume: setVolume,
        getVolume: function () { return volume; },
        setEnabled: setEnabled,
        isEnabled: function () { return enabled; },
        unlock: unlockAudio,
        isUnlocked: function () { return isUnlocked; }
    };

})(window);
