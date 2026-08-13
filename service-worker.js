const CACHE_NAME = "youcut-v1";

const STATIC_ASSETS = [
    "/",
    "/statics/manifest.json"
];


self.addEventListener(
    "install",
    event => {

        event.waitUntil(

            caches
                .open(CACHE_NAME)
                .then(cache => {

                    return cache.addAll(
                        STATIC_ASSETS
                    );

                })

        );

        self.skipWaiting();

    }
);


self.addEventListener(
    "activate",
    event => {

        event.waitUntil(

            caches
                .keys()
                .then(keys => {

                    return Promise.all(

                        keys
                            .filter(
                                key =>
                                    key !== CACHE_NAME
                            )
                            .map(
                                key =>
                                    caches.delete(key)
                            )

                    );

                })

        );

        self.clients.claim();

    }
);


self.addEventListener(
    "fetch",
    event => {

        const request =
            event.request;


        const url =
            new URL(
                request.url
            );


        /*
         * Jangan cache:
         *
         * - API
         * - video
         * - download
         * - POST request
         */

        if (
            request.method !== "GET"
            ||
            url.pathname.startsWith(
                "/api/"
            )
            ||
            url.pathname.startsWith(
                "/webhooks/"
            )
            ||
            request.destination === "video"
            ||
            url.pathname.includes(
                "/download"
            )
        ) {

            return;

        }


        /*
         * Untuk halaman dan aset:
         *
         * Network first.
         * Kalau offline, gunakan cache.
         */

        event.respondWith(

            fetch(request)

                .then(response => {

                    if (
                        response
                        &&
                        response.status === 200
                    ) {

                        const cloned =
                            response.clone();


                        caches
                            .open(CACHE_NAME)
                            .then(
                                cache => {

                                    cache.put(
                                        request,
                                        cloned
                                    );

                                }
                            );

                    }


                    return response;

                })

                .catch(() => {

                    return caches
                        .match(request)
                        .then(
                            cached => {

                                return (
                                    cached
                                    ||
                                    caches.match("/")
                                );

                            }
                        );

                })

        );

    }
);