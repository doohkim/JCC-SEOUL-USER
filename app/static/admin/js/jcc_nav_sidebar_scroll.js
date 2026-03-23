'use strict';
(function () {
    const STORAGE_KEY = 'jcc.admin.navSidebarScrollTop';

    function sidebar() {
        return document.getElementById('nav-sidebar');
    }

    function save() {
        const el = sidebar();
        if (!el) {
            return;
        }
        sessionStorage.setItem(STORAGE_KEY, String(el.scrollTop));
    }

    function restore() {
        const el = sidebar();
        if (!el) {
            return;
        }
        const raw = sessionStorage.getItem(STORAGE_KEY);
        if (raw === null) {
            return;
        }
        const y = parseInt(raw, 10);
        if (!Number.isFinite(y) || y < 0) {
            return;
        }
        el.scrollTop = y;
    }

    function bind() {
        const el = sidebar();
        if (!el) {
            return;
        }
        el.addEventListener('scroll', save, {passive: true});
        el.addEventListener(
            'click',
            function (ev) {
                if (ev.target.closest('a')) {
                    save();
                }
            },
            true
        );
        restore();
        requestAnimationFrame(restore);
    }

    window.addEventListener('load', function () {
        requestAnimationFrame(bind);
    });
    window.addEventListener('pageshow', function (ev) {
        if (ev.persisted) {
            requestAnimationFrame(restore);
        }
    });
    window.addEventListener('pagehide', save);
})();
