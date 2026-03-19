// theme.js
(function () {
    function getStoredTheme() {
        return localStorage.getItem('prism_theme') || 'system';
    }

    function applyTheme(theme) {
        if (theme === 'system') {
            const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
        } else {
            document.documentElement.setAttribute('data-theme', theme);
        }
    }

    // Apply exact theme right away to avoid flash of incorrect styles
    const initialTheme = getStoredTheme();
    applyTheme(initialTheme);

    // Watch for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (localStorage.getItem('prism_theme') === 'system' || !localStorage.getItem('prism_theme')) {
            applyTheme('system');
        }
    });

    // Expose to attach to UI toggles
    window.setPrismTheme = function (theme) {
        localStorage.setItem('prism_theme', theme);
        applyTheme(theme);
    };

    window.getPrismTheme = getStoredTheme;
})();
