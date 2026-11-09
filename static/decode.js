(function () {
    "use strict";

    var form = document.getElementById('decode-form');
    if (!form) return;

    var typeEl = document.getElementById('decode-type');
    var valueEl = document.getElementById('decode-value');
    var status = document.getElementById('decode-status');
    var output = document.getElementById('decode-output');

    function renderOutput(fields) {
        output.hidden = false;
        output.innerHTML = '';
        Object.keys(fields).forEach(function (key) {
            var row = document.createElement('div');
            row.className = 'decode-row';

            var k = document.createElement('span');
            k.className = 'decode-row-key';
            k.textContent = key;

            var v = document.createElement('span');
            v.className = 'decode-row-val';
            v.textContent = String(fields[key]);

            row.appendChild(k);
            row.appendChild(v);
            output.appendChild(row);
        });
    }

    form.addEventListener('submit', function (e) {
        e.preventDefault();

        var blockType = typeEl.value;
        var value = valueEl.value.trim();

        if (!value) {
            status.textContent = '> paste a value first lol';
            output.hidden = true;
            return;
        }

        status.textContent = '> decoding...';
        output.hidden = true;

        fetch('/api/decode', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ type: blockType, value: value })
        }).then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, data: data };
            });
        }).then(function (r) {
            if (r.ok) {
                renderOutput(r.data);
                status.textContent = '> decoded ' + Object.keys(r.data).length + ' fields';
            } else {
                status.textContent = '> ' + (r.data.detail || 'decode failed');
                output.hidden = true;
            }
        }).catch(function () {
            status.textContent = '> network error';
            output.hidden = true;
        });
    });

    // auto-decode on type change if value exists
    typeEl.addEventListener('change', function () {
        if (valueEl.value.trim()) {
            form.dispatchEvent(new Event('submit'));
        }
    });
})();
