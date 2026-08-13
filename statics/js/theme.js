```javascript
(function () {

    "use strict";

    const STORAGE_KEY = "youcut-theme";


    function getSystemTheme() {

        return window.matchMedia(
            "(prefers-color-scheme: dark)"
        ).matches
            ? "dark"
            : "light";

    }


    function getSavedTheme() {

        const saved =
            localStorage.getItem(STORAGE_KEY);

        if (
            saved === "dark" ||
            saved === "light"
        ) {
            return saved;
        }

        /*
         * Kompatibilitas dengan versi
         * lama project.
         */

        const oldSaved =
            localStorage.getItem("theme");

        if (
            oldSaved === "dark" ||
            oldSaved === "light"
        ) {
            return oldSaved;
        }

        return null;
    }


    function getTheme() {

        return (
            getSavedTheme() ||
            getSystemTheme()
        );

    }


    function applyTheme(theme) {

        const html =
            document.documentElement;


        /*
         * Ini yang dipakai CSS baru.
         */

        html.setAttribute(
            "data-theme",
            theme
        );


        /*
         * Hapus class theme lama
         * supaya tidak konflik.
         */

        html.classList.remove(
            "light-theme",
            "dark-theme"
        );


        /*
         * Tambahkan class untuk
         * kompatibilitas lama.
         */

        html.classList.add(
            theme + "-theme"
        );


        const toggle =
            document.getElementById(
                "themeToggle"
            );


        const icon =
            document.getElementById(
                "themeIcon"
            );


        const label =
            document.getElementById(
                "themeLabel"
            );


        if (toggle) {

            toggle.setAttribute(
                "aria-pressed",
                theme === "dark"
                    ? "true"
                    : "false"
            );

        }


        if (icon) {

            icon.className =
                theme === "dark"
                    ? "bi bi-moon-stars-fill"
                    : "bi bi-sun-fill";

        }


        if (label) {

            label.textContent =
                theme === "dark"
                    ? "Dark"
                    : "Light";

        }


        const meta =
            document.querySelector(
                'meta[name="theme-color"]'
            );


        if (meta) {

            meta.setAttribute(
                "content",
                theme === "dark"
                    ? "#111211"
                    : "#f0f0ed"
            );

        }

    }


    function saveTheme(theme) {

        /*
         * Simpan di dua key agar
         * kompatibel dengan versi lama.
         */

        localStorage.setItem(
            STORAGE_KEY,
            theme
        );

        localStorage.setItem(
            "theme",
            theme
        );

    }


    function toggleTheme() {

        const currentTheme =
            document.documentElement
                .getAttribute(
                    "data-theme"
                );


        const nextTheme =
            currentTheme === "dark"
                ? "light"
                : "dark";


        saveTheme(nextTheme);

        applyTheme(nextTheme);

    }


    /*
     * Terapkan tema SEBELUM
     * DOM selesai dimuat.
     */

    applyTheme(
        getTheme()
    );


    document.addEventListener(
        "DOMContentLoaded",
        function () {

            /*
             * Sinkronkan ulang.
             */

            applyTheme(
                getTheme()
            );


            const toggle =
                document.getElementById(
                    "themeToggle"
                );


            if (!toggle) {

                console.warn(
                    "Youcut: #themeToggle tidak ditemukan."
                );

                return;
            }


            /*
             * Hindari event listener
             * terpasang dua kali.
             */

            if (
                toggle.dataset.themeReady === "true"
            ) {

                return;
            }


            toggle.dataset.themeReady = "true";


            toggle.addEventListener(
                "click",
                function (event) {

                    event.preventDefault();

                    toggleTheme();

                }
            );

        }
    );


    /*
     * Kalau user belum memilih tema
     * secara manual, ikuti perubahan
     * tema Windows/browser.
     */

    const media =
        window.matchMedia(
            "(prefers-color-scheme: dark)"
        );


    function systemThemeChanged() {

        if (!getSavedTheme()) {

            applyTheme(
                getSystemTheme()
            );

        }

    }


    if (
        typeof media.addEventListener === "function"
    ) {

        media.addEventListener(
            "change",
            systemThemeChanged
        );

    } else if (
        typeof media.addListener === "function"
    ) {

        media.addListener(
            systemThemeChanged
        );

    }

})();
```
