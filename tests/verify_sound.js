/**
 * Verification test suite for NetSentinel Sound Feedback system.
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const basePath = path.resolve(__dirname, '..');
const soundJsPath = path.join(basePath, 'static', 'sound.js');
const indexHtmlPath = path.join(basePath, 'templates', 'index.html');

console.log('--- Starting Sound Feedback Verification ---');

// 1. Check sound.js exists
assert(fs.existsSync(soundJsPath), 'static/sound.js must exist');
const soundContent = fs.readFileSync(soundJsPath, 'utf8');

// 2. Mock browser environment to test NetSentinelSound API and localStorage logic
const mockLocalStorage = {
    store: {},
    getItem(key) {
        return this.store.hasOwnProperty(key) ? this.store[key] : null;
    },
    setItem(key, val) {
        this.store[key] = String(val);
    },
    clear() {
        this.store = {};
    }
};

const mockWindow = {
    addEventListener: () => {},
    removeEventListener: () => {},
    localStorage: mockLocalStorage,
    AudioContext: function() {
        this.currentTime = 0;
        this.state = 'suspended';
        this.destination = {};
        this.createGain = () => ({
            gain: {
                setValueAtTime: () => {},
                exponentialRampToValueAtTime: () => {}
            },
            connect: () => {}
        });
        this.createOscillator = () => ({
            type: 'sine',
            frequency: {
                setValueAtTime: () => {},
                exponentialRampToValueAtTime: () => {}
            },
            connect: () => {},
            start: () => {},
            stop: () => {}
        });
        this.createBiquadFilter = () => ({
            type: 'lowpass',
            frequency: {
                setValueAtTime: () => {},
                exponentialRampToValueAtTime: () => {}
            },
            connect: () => {}
        });
        this.resume = () => {
            this.state = 'running';
            return Promise.resolve();
        };
    }
};

// Execute sound.js in mock environment
const vm = require('vm');
const context = vm.createContext({
    window: mockWindow,
    localStorage: mockLocalStorage,
    console: console,
    Date: Date,
    parseFloat: parseFloat,
    isNaN: isNaN,
    Math: Math,
    Boolean: Boolean
});

vm.runInContext(soundContent, context);

const NetSentinelSound = mockWindow.NetSentinelSound;
assert(NetSentinelSound, 'window.NetSentinelSound must be defined');

// Check all required methods
const requiredMethods = ['play', 'setVolume', 'getVolume', 'setEnabled', 'isEnabled', 'unlock', 'isUnlocked'];
for (const method of requiredMethods) {
    assert.strictEqual(typeof NetSentinelSound[method], 'function', `NetSentinelSound.${method} must be a function`);
}
console.log('✓ NetSentinelSound exists with all required methods:', requiredMethods.join(', '));

// Test localStorage persistence logic for volume and enabled
NetSentinelSound.setVolume(0.85);
assert.strictEqual(mockLocalStorage.getItem('net_sentinel_sound_volume'), '0.85');
assert.strictEqual(NetSentinelSound.getVolume(), 0.85);

NetSentinelSound.setVolume(1.5); // Should clamp to 1.0
assert.strictEqual(NetSentinelSound.getVolume(), 1.0);
NetSentinelSound.setVolume(-0.2); // Should clamp to 0.0
assert.strictEqual(NetSentinelSound.getVolume(), 0.0);

NetSentinelSound.setEnabled(false);
assert.strictEqual(mockLocalStorage.getItem('net_sentinel_sound_enabled'), 'false');
assert.strictEqual(NetSentinelSound.isEnabled(), false);

NetSentinelSound.setEnabled(true);
assert.strictEqual(mockLocalStorage.getItem('net_sentinel_sound_enabled'), 'true');
assert.strictEqual(NetSentinelSound.isEnabled(), true);
console.log('✓ localStorage persistence logic for enabled and volume verified');

// Test unlock exists and doesn't throw
assert.doesNotThrow(() => {
    NetSentinelSound.unlock();
}, 'unlock() should not throw');
console.log('✓ Unlock method exists and is callable');

testSoundTypes();

// Verify all four sound types: 'success', 'error', 'alert', 'click'
function testSoundTypes() {
    const soundTypes = ['success', 'error', 'alert', 'click'];
    for (const type of soundTypes) {
        assert.doesNotThrow(() => {
            NetSentinelSound.play(type);
        }, `play('${type}') should not throw`);
    }
    console.log('✓ Handled all 4 sound types cleanly:', soundTypes.join(', '));
    testCspCompliance();
}

function testCspCompliance() {

    // 3. Verify CSP and templates/index.html compliance
    assert(fs.existsSync(indexHtmlPath), 'templates/index.html must exist');
    const htmlContent = fs.readFileSync(indexHtmlPath, 'utf8');

    // Check script tags
    assert(htmlContent.includes('<script src="/static/sound.js?v=1.0"></script>'), 'index.html must include /static/sound.js');
    assert(htmlContent.includes('<script src="/static/app.js?v=2.1"></script>'), 'index.html must include /static/app.js');

    // Check for inline script blocks (<script>...</script> without src)
    const inlineScriptMatches = htmlContent.match(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi);
    assert(!inlineScriptMatches || inlineScriptMatches.length === 0, 'index.html must not contain inline scripts');

    // Check for inline event handlers like onclick, onload, etc.
    const inlineHandlers = htmlContent.match(/\s+on[a-z]+\s*=\s*["'][^"']*["']/gi);
    assert(!inlineHandlers || inlineHandlers.length === 0, `index.html must not contain inline event handlers (found: ${inlineHandlers})`);

    console.log('✓ CSP compliance verified: No inline scripts or inline event handlers in templates/index.html');
    console.log('--- All verifications passed successfully ---');
}
