// static/js/theme.js
(function() {
    const THEME_KEY = 'user-theme';
    const DARK_MODE_CLASS = 'dark-mode';

    function getSavedTheme() {
        return localStorage.getItem(THEME_KEY);
    }

    function saveTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
    }

    function applyTheme(theme) {
        if (theme === 'dark') {
            document.documentElement.classList.add(DARK_MODE_CLASS);
        } else { // 'light' or null/default
            document.documentElement.classList.remove(DARK_MODE_CLASS);
        }
    }

    // Function to set a specific theme (e.g., from a dropdown or buttons)
    function setTheme(theme) {
        if (theme === 'dark' || theme === 'light') {
            applyTheme(theme);
            saveTheme(theme);
            // Dispatch an event for UI elements to update if needed (e.g., button text)
            document.dispatchEvent(new CustomEvent('themeChanged', { detail: { theme: theme } }));
        }
    }

    // Apply saved theme on initial load
    // This part should run as early as possible, ideally in a script tag in <head>
    // or at the very beginning of the body for the main script.
    const savedTheme = getSavedTheme();
    if (savedTheme) {
        applyTheme(savedTheme);
    } else {
        // Default to light theme if no preference is saved and no system preference check
        applyTheme('light'); 
    }

    // Expose functions to global scope to be called from HTML buttons/dropdown
    window.themeSwitcher = {
        setTheme: setTheme,
        getCurrentTheme: () => document.documentElement.classList.contains(DARK_MODE_CLASS) ? 'dark' : 'light'
    };

    // Optional: Listen for system preference changes if you want to support 'system' theme
    // This is more complex if you also allow user overrides.
    // window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', event => {
    //     const newColorScheme = event.matches ? "dark" : "light";
    //     // Only apply if 'system' theme is chosen or no user preference is set
    //     const currentStoredTheme = getSavedTheme();
    //     if (currentStoredTheme === 'system' || !currentStoredTheme) {
    //         applyTheme(newColorScheme); 
    //         // Note: Don't save this as user preference if it's a dynamic system change
    //     }
    // });
})();