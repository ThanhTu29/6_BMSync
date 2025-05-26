document.addEventListener('DOMContentLoaded', () => {
    const themeSelect = document.getElementById('themeSelection');
    const htmlElement = document.documentElement; // Target <html> element for theme classes

    // Function to apply the theme
    function applyTheme(theme) {
        htmlElement.classList.remove('dark-mode', 'contrast-mode', 'light-mode'); // Remove existing theme classes
        if (theme === 'dark') {
            htmlElement.classList.add('dark-mode');
        } else if (theme === 'contrast') {
            htmlElement.classList.add('contrast-mode');
        } else {
            htmlElement.classList.add('light-mode'); // Default to light or explicitly light
        }
        localStorage.setItem('selectedTheme', theme);
    }

    // Apply saved theme on page load
    const savedTheme = localStorage.getItem('selectedTheme');
    if (savedTheme) {
        applyTheme(savedTheme);
        if (themeSelect) {
            themeSelect.value = savedTheme;
        }
    } else {
        // If no saved theme, apply the default selected in HTML (or light)
        const initialTheme = themeSelect ? themeSelect.value : 'light';
        applyTheme(initialTheme);
    }

    // Event listener for theme selection change
    if (themeSelect) {
        themeSelect.addEventListener('change', function() {
            applyTheme(this.value);
        });
    }

    // Ensure the admin_base.html correctly loads this script
    // And that CSS files (style.css and admin_style.css) have definitions for:
    // html.light-mode body { ... }
    // html.dark-mode body { ... }
    // html.contrast-mode body { ... }
    // And other elements as needed.
});