(function () {
    "use strict";

    var textarea = document.getElementById("rt-input");
    var preview = document.getElementById("rt-preview");
    var status = document.getElementById("rt-status");
    if (!textarea) return;

    // --- Roblox font face → closest CSS font for preview ---
    var FONT_MAP = {
        Arial: "Arial, Helvetica, sans-serif",
        ArialBold: "Arial, Helvetica, sans-serif",
        SourceSans: "system-ui, -apple-system, sans-serif",
        SourceSansBold: "system-ui, -apple-system, sans-serif",
        Bodoni: "'Bodoni MT', Didot, Georgia, serif",
        Garamond: "Garamond, 'Times New Roman', serif",
        Antique: "Georgia, 'Times New Roman', serif",
        Merriweather: "Georgia, serif",
        Cartoon: "'Comic Sans MS', 'Chalkboard SE', cursive",
        Highway: "Impact, 'Arial Black', sans-serif",
        SciFi: "'Arial Narrow', sans-serif",
        Arcade: "'Courier New', monospace",
        Fantasy: "Papyrus, fantasy",
        Bangers: "Impact, 'Arial Black', cursive",
        FredokaOne: "'Comic Sans MS', cursive",
        LuckiestGuy: "Impact, sans-serif",
        PermanentMarker: "'Comic Sans MS', cursive",
        Creepster: "Impact, cursive",
        GrenzeGotisch: "Georgia, serif",
        Gotham: "Montserrat, 'Helvetica Neue', sans-serif",
        GothamMedium: "Montserrat, 'Helvetica Neue', sans-serif",
        GothamBold: "Montserrat, 'Helvetica Neue', sans-serif",
        GothamBlack: "Montserrat, 'Helvetica Neue', sans-serif",
        Code: "'Courier New', monospace",
        RobotoMono: "'Courier New', monospace",
        SpecialElite: "'Courier New', monospace",
        AmaticSC: "cursive",
        IndieFlower: "cursive",
        Kalam: "cursive",
        PatrickHand: "cursive",
        Roboto: "Roboto, Arial, sans-serif",
        RobotoCondensed: "'Arial Narrow', sans-serif",
        Oswald: "Impact, 'Arial Narrow', sans-serif",
        Nunito: "Arial, sans-serif",
        JosefinSans: "Arial, sans-serif",
        Jura: "Arial, sans-serif",
        Michroma: "Arial, sans-serif",
        TitilliumWeb: "Arial, sans-serif",
        Ubuntu: "Ubuntu, Arial, sans-serif",
        Sarpanch: "Arial, sans-serif",
        DenkOne: "Arial, sans-serif",
        Fondamento: "Georgia, serif"
    };

    // --- wrap selection with open/close tags ---
    function wrapSelection(openTag, closeTag) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        var selected = value.substring(start, end);
        textarea.value = value.substring(0, start) + openTag + selected + closeTag + value.substring(end);
        var newStart = start + openTag.length;
        textarea.selectionStart = newStart;
        textarea.selectionEnd = newStart + selected.length;
        textarea.focus();
        update();
    }

    function insertAtCursor(text) {
        var start = textarea.selectionStart;
        var end = textarea.selectionEnd;
        var value = textarea.value;
        textarea.value = value.substring(0, start) + text + value.substring(end);
        textarea.selectionStart = textarea.selectionEnd = start + text.length;
        textarea.focus();
        update();
    }

    // --- color helpers ---
    function toRgba(color, alpha) {
        if (!color) return "rgba(0,0,0," + alpha + ")";
        if (color.indexOf("rgb") === 0) {
            var m = color.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
            if (m) return "rgba(" + m[1] + "," + m[2] + "," + m[3] + "," + alpha + ")";
        }
        if (color.charAt(0) === "#") {
            var hex = color.slice(1);
            if (hex.length === 3) hex = hex[0]+hex[0]+hex[1]+hex[1]+hex[2]+hex[2];
            if (hex.length === 6) {
                var r = parseInt(hex.slice(0,2), 16);
                var g = parseInt(hex.slice(2,4), 16);
                var b = parseInt(hex.slice(4,6), 16);
                return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
            }
        }
        return color;
    }

    // --- roblox rich text → html for preview ---
    function robloxToHtml(text) {
        var html = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");

        html = html
            .replace(/&amp;lt;/g, "&lt;")
            .replace(/&amp;gt;/g, "&gt;")
            .replace(/&amp;quot;/g, "&quot;")
            .replace(/&amp;apos;/g, "&#39;")
            .replace(/&amp;amp;/g, "&amp;");

        html = html.replace(/&lt;!--[\s\S]*?--&gt;/g, "");

        // <font ...>
        html = html.replace(/&lt;font\s+([^&]*?)&gt;/g, function (m, attrs) {
            var styles = [];
            var color = attrs.match(/color="([^"]+)"/);
            var size = attrs.match(/size="(\d+)"/);
            var face = attrs.match(/face="([^"]+)"/);
            var weight = attrs.match(/weight="([^"]+)"/);
            var trans = attrs.match(/transparency="([\d.]+)"/);
            if (color) styles.push("color:" + color[1]);
            if (size) styles.push("font-size:" + size[1] + "px");
            if (face) {
                var mapped = FONT_MAP[face[1]] || face[1];
                styles.push("font-family:" + mapped);
            }
            if (weight) styles.push("font-weight:" + weight[1]);
            if (trans) styles.push("opacity:" + (1 - parseFloat(trans[1])));
            return '<span style="' + styles.join(";") + '">';
        });
        html = html.replace(/&lt;\/font&gt;/g, "</span>");

        // <stroke ...>
        html = html.replace(/&lt;stroke\s+([^&]*?)&gt;/g, function (m, attrs) {
            var color = attrs.match(/color="([^"]+)"/);
            var th = attrs.match(/(?:thickness|th)="([\d.]+)"/);
            var tr = attrs.match(/(?:transparency|tr)="([\d.]+)"/);
            var c = color ? color[1] : "#000";
            var t = th ? th[1] : "1";
            var strokeColor = tr ? toRgba(c, 1 - parseFloat(tr[1])) : c;
            return '<span style="-webkit-text-stroke:' + t + 'px ' + strokeColor + '">';
        });
        html = html.replace(/&lt;\/stroke&gt;/g, "</span>");

        // <mark ...> or <mark>
        html = html.replace(/&lt;mark\s+([^&]*?)&gt;/g, function (m, attrs) {
            var color = attrs.match(/color="([^"]+)"/);
            var tr = attrs.match(/transparency="([\d.]+)"/);
            var bg = color ? color[1] : "#ffff00";
            if (tr) bg = toRgba(bg, 1 - parseFloat(tr[1]));
            return '<span style="background-color:' + bg + '">';
        });
        html = html.replace(/&lt;mark&gt;/g, '<span style="background-color:#ffff00">');
        html = html.replace(/&lt;\/mark&gt;/g, "</span>");

        // simple tags
        html = html
            .replace(/&lt;b&gt;/gi, "<b>").replace(/&lt;\/b&gt;/gi, "</b>")
            .replace(/&lt;i&gt;/gi, "<i>").replace(/&lt;\/i&gt;/gi, "</i>")
            .replace(/&lt;u&gt;/gi, "<u>").replace(/&lt;\/u&gt;/gi, "</u>")
            .replace(/&lt;s&gt;/gi, "<s>").replace(/&lt;\/s&gt;/gi, "</s>")
            .replace(/&lt;br\s*\/?&gt;/gi, "<br>");

        // uppercase / smallcaps
        html = html
            .replace(/&lt;(?:uppercase|uc)&gt;/gi, '<span style="text-transform:uppercase">')
            .replace(/&lt;\/(?:uppercase|uc)&gt;/gi, "</span>")
            .replace(/&lt;(?:smallcaps|sc)&gt;/gi, '<span style="font-variant:small-caps">')
            .replace(/&lt;\/(?:smallcaps|sc)&gt;/gi, "</span>");

        return html;
    }

    // --- live preview ---
    function update() {
        var html = robloxToHtml(textarea.value);
        if (!html || !html.replace(/<[^>]*>/g, "").trim()) {
            preview.innerHTML = '<span class="rt-preview-empty">your title preview will appear here</span>';
        } else {
            preview.innerHTML = html;
        }
    }

    // --- tag buttons ---
    document.querySelectorAll("[data-tag]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            var tag = btn.dataset.tag;
            wrapSelection("<" + tag + ">", "</" + tag + ">");
        });
    });

    // --- color ---
    document.getElementById("rt-color").addEventListener("change", function (e) {
        wrapSelection('<font color="' + e.target.value + '">', "</font>");
    });

    // --- size ---
    document.getElementById("rt-size-apply").addEventListener("click", function () {
        var size = document.getElementById("rt-size").value || "16";
        wrapSelection('<font size="' + size + '">', "</font>");
    });

    // --- font face ---
    document.getElementById("rt-font-apply").addEventListener("click", function () {
        var face = document.getElementById("rt-font").value;
        if (!face) {
            status.textContent = "> pick a font first";
            return;
        }
        wrapSelection('<font face="' + face + '">', "</font>");
    });

    // --- stroke ---
    var strokePanel = document.getElementById("rt-stroke-panel");
    document.getElementById("rt-stroke-open").addEventListener("click", function () {
        strokePanel.hidden = !strokePanel.hidden;
    });

    document.getElementById("rt-stroke-apply").addEventListener("click", function () {
        var c = document.getElementById("rt-stroke-color").value;
        var th = document.getElementById("rt-stroke-thickness").value || "1";
        var tr = document.getElementById("rt-stroke-trans").value || "0";
        wrapSelection(
            '<stroke color="' + c + '" thickness="' + th + '" transparency="' + tr + '">',
            "</stroke>"
        );
    });

    // --- escape chars ---
    document.querySelectorAll("[data-insert]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            insertAtCursor(btn.dataset.insert);
        });
    });

    // --- clear ---
    document.getElementById("rt-clear").addEventListener("click", function () {
        textarea.value = "";
        update();
        status.textContent = "> cleared";
    });

    // --- copy ---
    document.getElementById("rt-copy").addEventListener("click", function () {
        if (!textarea.value) {
            status.textContent = "> nothing to copy";
            return;
        }
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(textarea.value).then(function () {
                status.textContent = "> copied markup to clipboard";
                setTimeout(function () { status.textContent = ""; }, 2000);
            }).catch(function () {
                status.textContent = "> could not copy";
            });
        } else {
            textarea.select();
            document.execCommand("copy");
            status.textContent = "> copied";
        }
    });

    textarea.addEventListener("input", update);
    update();
})();
