(function () {
    "use strict";

    // --- card spotlight (follows the cursor) ---
    document.querySelectorAll('.card').forEach(function (card) {
        card.addEventListener('pointermove', function (e) {
            var r = card.getBoundingClientRect();
            card.style.setProperty('--mx', (e.clientX - r.left) + 'px');
            card.style.setProperty('--my', (e.clientY - r.top) + 'px');
        });
    });

    // --- background orbs drift a bit with the mouse ---
    var orbs = document.querySelectorAll('.bg-orb');
    if (orbs.length && window.matchMedia('(pointer: fine)').matches) {
        window.addEventListener('pointermove', function (e) {
            var x = (e.clientX / window.innerWidth - 0.5) * 2;
            var y = (e.clientY / window.innerHeight - 0.5) * 2;
            orbs.forEach(function (o, i) {
                var d = (i + 1) * 14;
                o.style.translate = (x * d) + 'px ' + (y * d) + 'px';
            });
        }, { passive: true });
    }

    // --- form submit ---
    var form = document.getElementById('typewriter-form');
    var input = document.getElementById('typewriter-input');
    var status = document.getElementById('typewriter-status');

    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            var text = input.value;
            if (!text.trim()) {
                status.textContent = '> type something first lol';
                return;
            }
            status.textContent = '> sending...';
            fetch('/api/typewriter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            }).then(function (res) {
                if (res.ok) {
                    status.textContent = '> sent! ' + text.length + ' chars heading to the panel';
                    input.value = '';
                } else {
                    status.textContent = '> oops server said no';
                }
            }).catch(function () {
                status.textContent = '> network error lol';
            });
        });
    }

    // --- live panel view ---
    var elChar = document.getElementById('panel-live-char');
    var elValue = document.getElementById('panel-live-value');
    var elState = document.getElementById('panel-live-state');
    var elMeta = document.getElementById('panel-live-meta');

    if (!elChar) return;

    var lastValue = null;

    function updatePanel() {
        fetch('/api/typewriter/status').then(function (res) {
            return res.json();
        }).then(function (data) {
            var hasValue = data.panel_value !== null;

            var shown = '\u2013';
            if (hasValue) {
                if (data.panel_char === ' ') shown = '\u2423';
                else if (data.panel_char) shown = data.panel_char;
            }
            elChar.textContent = shown;
            elValue.textContent = hasValue ? data.panel_value : '--------';

            if (hasValue && data.panel_value !== lastValue) {
                elChar.classList.remove('pulse');
                elValue.classList.remove('pulse');
                void elChar.offsetWidth;
                elChar.classList.add('pulse');
                elValue.classList.add('pulse');
                lastValue = data.panel_value;
            }

            if (!hasValue) {
                elState.textContent = 'waiting for panel to connect...';
                elChar.classList.add('state-inactive');
                elValue.classList.add('state-inactive');
            } else if (data.text) {
                elState.textContent = 'live \u00b7 typing now';
                elChar.classList.remove('state-inactive');
                elValue.classList.remove('state-inactive');
            } else if (data.panel_active) {
                elState.textContent = 'live \u00b7 idle \u00b7 panel holding last char';
                elChar.classList.remove('state-inactive');
                elValue.classList.remove('state-inactive');
            } else {
                elState.textContent = 'panel idle \u00b7 last seen ' + data.since_last_served + 's ago';
                elChar.classList.add('state-inactive');
                elValue.classList.add('state-inactive');
            }

            if (data.text) {
                var preview = data.text.slice(0, 24) + (data.text.length > 24 ? '\u2026' : '');
                elMeta.textContent = 'pos ' + data.pos + ' / ' + data.buffer_length + ' \u00b7 "' + preview + '"';
            } else if (hasValue) {
                var held = data.panel_char === ' ' ? '\u2423' : data.panel_char;
                elMeta.textContent = 'idle \u00b7 holding "' + held + '"';
            } else {
                elMeta.textContent = '';
            }
        }).catch(function () {
            elState.textContent = '> lost connection';
        });
    }

    updatePanel();
    setInterval(updatePanel, 150);
})();
