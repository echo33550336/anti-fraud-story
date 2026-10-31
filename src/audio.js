/* Background music + synthesized sound effects for the story demo.
 * BGM is an original 32 s loop generated for this project (audio/bgm.wav).
 * Autoplay rules: audio starts on the first user gesture; the toggle defaults on. */
(function () {
  'use strict';

  var BGM_SRC = 'audio/bgm.wav';
  var bgm = null;
  var ctx = null;
  var enabled = true;
  var unlocked = false;
  var started = false;

  function ensureBgm() {
    if (bgm) return bgm;
    try {
      bgm = new Audio(BGM_SRC);
      bgm.loop = true;
      bgm.preload = 'auto';
      bgm.volume = 0.30;
    } catch (error) {
      bgm = null;
    }
    return bgm;
  }

  function ensureCtx() {
    if (ctx) return ctx;
    var AudioCtor = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtor) return null;
    try {
      ctx = new AudioCtor();
    } catch (error) {
      ctx = null;
    }
    return ctx;
  }

  function resumeCtx() {
    var current = ensureCtx();
    if (current && current.state === 'suspended' && current.resume) {
      current.resume().catch(function () {});
    }
    return current;
  }

  function playBgm() {
    if (!enabled) return;
    var audio = ensureBgm();
    if (!audio) return;
    started = true;
    try {
      var promise = audio.play();
      if (promise && promise.catch) promise.catch(function () {});
    } catch (error) {
      /* ignore autoplay / unsupported errors */
    }
  }

  function pauseBgm() {
    if (bgm) {
      try { bgm.pause(); } catch (error) { /* ignore */ }
    }
  }

  function updateButton() {
    var buttons = document.querySelectorAll('.sound-toggle');
    if (!buttons.length) return;
    buttons.forEach(function (button) {
      button.textContent = enabled ? '♪ 音乐 开' : '♪ 音乐 关';
      button.setAttribute('aria-pressed', enabled ? 'true' : 'false');
      button.classList.toggle('is-off', !enabled);
    });
  }

  function unlock() {
    if (!unlocked) {
      unlocked = true;
      resumeCtx();
      playBgm();
      updateButton();
    }
  }

  function toggle() {
    if (enabled && !started) {
      unlocked = true;
      resumeCtx();
      playBgm();
      updateButton();
      return;
    }
    enabled = !enabled;
    if (enabled) {
      resumeCtx();
      playBgm();
    } else {
      pauseBgm();
    }
    updateButton();
  }

  function tone(freq, start, duration, type, volume) {
    var current = ctx;
    if (!current) return;
    var now = current.currentTime + start;
    var osc = current.createOscillator();
    var gain = current.createGain();
    osc.type = type || 'sine';
    osc.frequency.setValueAtTime(freq, now);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(volume || 0.08, now + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
    osc.connect(gain);
    gain.connect(current.destination);
    osc.start(now);
    osc.stop(now + duration + 0.03);
  }

  function sfx(name) {
    if (!enabled) return;
    if (!resumeCtx()) return;
    if (name === 'click') {
      tone(880, 0, 0.07, 'sine', 0.05);
      tone(1320, 0.02, 0.05, 'sine', 0.03);
    } else if (name === 'ring') {
      for (var i = 0; i < 3; i += 1) {
        tone(440, i * 0.34, 0.20, 'sine', 0.10);
        tone(480, i * 0.34, 0.20, 'sine', 0.07);
      }
    } else if (name === 'message') {
      tone(1046, 0, 0.10, 'sine', 0.08);
      tone(1318, 0.075, 0.16, 'sine', 0.06);
    } else if (name === 'pay') {
      tone(220, 0, 0.18, 'triangle', 0.10);
      tone(110, 0.02, 0.28, 'sine', 0.06);
    } else if (name === 'good') {
      [523.25, 659.25, 783.99].forEach(function (freq, index) {
        tone(freq, index * 0.13, 0.65, 'sine', 0.06);
      });
    } else if (name === 'bad') {
      [220.0, 174.61, 146.83].forEach(function (freq, index) {
        tone(freq, index * 0.16, 0.75, 'triangle', 0.07);
      });
    }
  }

  function firstGesture(event) {
    if (event.target && event.target.closest && event.target.closest('.sound-toggle')) return;
    document.removeEventListener('pointerdown', firstGesture);
    unlock();
  }
  document.addEventListener('pointerdown', firstGesture);

  function init() {
    var buttons = document.querySelectorAll('.sound-toggle');
    buttons.forEach(function (button) {
      button.addEventListener('click', function (event) {
        event.stopPropagation();
        toggle();
      });
    });
    updateButton();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  window.GameAudio = {
    unlock: unlock,
    toggle: toggle,
    sfx: sfx,
    isEnabled: function () { return enabled; }
  };
})();
