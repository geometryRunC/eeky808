(function () {
    "use strict";
    // relative timestamps — replaces nothing on the server, purely cosmetic
    document.querySelectorAll("[data-ts]").forEach(function (el) {
        var ts = parseFloat(el.dataset.ts);
        if (!ts) return;
        var diff = Date.now() / 1000 - ts;
        var out;
        if (diff < 60) out = Math.floor(diff) + "s ago";
        else if (diff < 3600) out = Math.floor(diff / 60) + "m ago";
        else if (diff < 86400) out = Math.floor(diff / 3600) + "h ago";
        else if (diff < 604800) out = Math.floor(diff / 86400) + "d ago";
        else out = new Date(ts * 1000).toLocaleDateString();
        el.textContent = out;
    });
})();
