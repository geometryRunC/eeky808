(function () {
    "use strict";

    var SID_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
    var SID_LEN = 4;

    function isValidSid(s) {
        if (!s || s.length !== SID_LEN) return false;
        for (var i = 0; i < s.length; i++) {
            if (SID_CHARS.indexOf(s.charAt(i)) === -1) return false;
        }
        return true;
    }

    function generateSid() {
        var s = "";
        for (var i = 0; i < SID_LEN; i++) {
            s += SID_CHARS.charAt(Math.floor(Math.random() * SID_CHARS.length));
        }
        return s;
    }

    // --- SID resolution ---
    var params = new URLSearchParams(window.location.search);
    var SID = params.get("sid");
    if (!isValidSid(SID)) {
        SID = generateSid();
        params.set("sid", SID);
        history.replaceState(null, "", "/typewriter?" + params.toString());
    }

    var sidEl = document.getElementById("session-sid");
    var sidInline = document.getElementById("sid-inline");
    var copyStatus = document.getElementById("copy-status");

    sidEl.textContent = SID;
    sidInline.textContent = SID;

    function headers() {
        return { "sid": SID };
    }
    function jsonHeaders() {
        return { "Content-Type": "application/json", "sid": SID };
    }

    // --- copy ---
    document.getElementById("copy-sid").addEventListener("click", function () {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(SID).then(function () {
                copyStatus.textContent = "> copied " + SID;
                setTimeout(function () { copyStatus.textContent = ""; }, 2000);
            }).catch(function () {
                copyStatus.textContent = "> could not copy, select manually";
            });
        } else {
            copyStatus.textContent = "> " + SID;
        }
    });

    // --- new ---
    document.getElementById("new-sid").addEventListener("click", function () {
        window.location.href = "/typewriter?sid=" + encodeURIComponent(generateSid());
    });

    // --- join ---
    var joinInput = document.getElementById("join-input");
    var joinBtn = document.getElementById("join-btn");

    function attemptJoin() {
        var raw = (joinInput.value || "").trim();
        if (!isValidSid(raw)) {
            copyStatus.textContent = "> sid must be 4 letters or numbers";
            return;
        }
        window.location.href = "/typewriter?sid=" + encodeURIComponent(raw);
    }

    joinBtn.addEventListener("click", attemptJoin);
    joinInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            attemptJoin();
        }
    });
    joinInput.addEventListener("input", function () {
        copyStatus.textContent = "";
    });

    // --- form submit ---
    var form = document.getElementById("typewriter-form");
    var input = document.getElementById("typewriter-input");
    var status = document.getElementById("typewriter-status");

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        var text = input.value;
        if (!text.trim()) {
            status.textContent = "> type something first lol";
            return;
        }
        status.textContent = "> sending...";
        fetch("/api/typewriter", {
            method: "POST",
            headers: jsonHeaders(),
            body: JSON.stringify({ text: text })
        }).then(function (res) {
            if (res.ok) {
                status.textContent = "> sent! " + text.length + " chars for session " + SID;
                input.value = "";
            } else {
                status.textContent = "> oops server said no";
            }
        }).catch(function () {
            status.textContent = "> network error lol";
        });
    });

    // --- clear ---
    document.getElementById("clear-btn").addEventListener("click", function () {
        fetch("/api/typewriter/clear", { method: "POST", headers: headers() })
            .then(function () { status.textContent = "> cleared"; })
            .catch(function () { status.textContent = "> network error"; });
    });

    // --- live panel view ---
    var elChar = document.getElementById("panel-live-char");
    var elValue = document.getElementById("panel-live-value");
    var elState = document.getElementById("panel-live-state");
    var elMeta = document.getElementById("panel-live-meta");

    var lastValue = null;

    function updatePanel() {
        fetch("/api/typewriter/status", { headers: headers() })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var hasValue = data.panel_value !== null;

                var shown = "\u2013";
                if (hasValue) {
                    if (data.panel_char === " ") shown = "\u2423";
                    else if (data.panel_char) shown = data.panel_char;
                }
                elChar.textContent = shown;
                elValue.textContent = hasValue ? data.panel_value : "--------";

                if (hasValue && data.panel_value !== lastValue) {
                    elChar.classList.remove("pulse");
                    elValue.classList.remove("pulse");
                    void elChar.offsetWidth;
                    elChar.classList.add("pulse");
                    elValue.classList.add("pulse");
                    lastValue = data.panel_value;
                }

                if (!hasValue) {
                    elState.textContent = "waiting for panel to connect...";
                    elChar.classList.add("state-inactive");
                    elValue.classList.add("state-inactive");
                } else if (data.text) {
                    elState.textContent = "live \u00b7 typing now";
                    elChar.classList.remove("state-inactive");
                    elValue.classList.remove("state-inactive");
                } else if (data.panel_active) {
                    elState.textContent = "live \u00b7 idle \u00b7 panel holding last char";
                    elChar.classList.remove("state-inactive");
                    elValue.classList.remove("state-inactive");
                } else {
                    elState.textContent = "panel idle \u00b7 last seen " + data.since_last_served + "s ago";
                    elChar.classList.add("state-inactive");
                    elValue.classList.add("state-inactive");
                }

                if (data.text) {
                    var preview = data.text.slice(0, 24) + (data.text.length > 24 ? "\u2026" : "");
                    elMeta.textContent = "pos " + data.pos + " / " + data.buffer_length + " \u00b7 \"" + preview + "\"";
                } else if (hasValue) {
                    var held = data.panel_char === " " ? "\u2423" : data.panel_char;
                    elMeta.textContent = "idle \u00b7 holding \"" + held + "\"";
                } else {
                    elMeta.textContent = "";
                }
            }).catch(function () {
                elState.textContent = "> lost connection";
            });
    }

    updatePanel();
    setInterval(updatePanel, 150);
})();
