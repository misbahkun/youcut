```html
{% extends "base.html" %}

{% block title %}
Pricing — Youcut
{% endblock %}


{% block content %}

<style>

    /* =====================================================
       PRICING PAGE
    ====================================================== */

    .pricing-page {

        padding:
            26px 0 80px;

    }


    .pricing-header {

        max-width:
            720px;

        margin:
            35px auto 45px;

        text-align:
            center;

    }


    .pricing-eyebrow {

        display:
            inline-flex;

        align-items:
            center;

        gap:
            7px;

        padding:
            6px 10px;

        margin-bottom:
            14px;

        background:
            var(--yc-surface-raised);

        border:
            1px solid
            var(--yc-border);

        border-radius:
            8px;

        color:
            var(--yc-primary);

        font-size:
            .7rem;

        font-weight:
            800;

        letter-spacing:
            .1em;

    }


    .pricing-header h1 {

        margin:
            0 0 14px;

        font-size:
            clamp(
                2.25rem,
                5vw,
                3.7rem
            );

        letter-spacing:
            -.055em;

    }


    .pricing-header h1 span {

        color:
            var(--yc-primary);

    }


    .pricing-header p {

        max-width:
            600px;

        margin:
            0 auto;

        color:
            var(--yc-text-2);

        font-size:
            1rem;

    }


    /* =====================================================
       STATUS
    ====================================================== */

    .pricing-status {

        max-width:
            900px;

        margin:
            0 auto 25px;

        padding:
            14px 18px;

        background:
            var(--yc-surface);

        border:
            1px solid
            var(--yc-border);

        border-radius:
            10px;

        color:
            var(--yc-text-2);

        font-size:
            .86rem;

    }


    .pricing-status strong {

        color:
            var(--yc-text);

    }


    .pricing-alert {

        max-width:
            900px;

        margin:
            0 auto 24px;

        padding:
            14px 17px;

        border-radius:
            9px;

        font-size:
            .86rem;

    }


    .pricing-alert.success {

        background:
            color-mix(
                in srgb,
                var(--yc-success) 10%,
                var(--yc-surface-raised)
            );

        border:
            1px solid
            color-mix(
                in srgb,
                var(--yc-success) 25%,
                var(--yc-border)
            );

        color:
            var(--yc-success);

    }


    .pricing-alert.warning {

        background:
            var(--yc-primary-soft);

        border:
            1px solid
            color-mix(
                in srgb,
                var(--yc-primary) 25%,
                var(--yc-border)
            );

        color:
            var(--yc-primary);

    }


    /* =====================================================
       PLAN GRID
    ====================================================== */

    .pricing-grid {

        max-width:
            1000px;

        margin:
            0 auto;

    }


    .pricing-card {

        position:
            relative;

        height:
            100%;

        padding:
            27px;

        background:
            var(--yc-surface-raised);

        border:
            1px solid
            var(--yc-border);

        border-radius:
            15px;

        box-shadow:
            var(--yc-shadow-sm);

        transition:
            transform .18s ease,
            border-color .18s ease,
            box-shadow .18s ease;

    }


    .pricing-card:hover {

        transform:
            translateY(-4px);

        border-color:
            var(--yc-border-strong);

        box-shadow:
            var(--yc-shadow-md);

    }


    .pricing-card.popular {

        border:
            1.5px solid
            var(--yc-primary);

    }


    .popular-badge {

        position:
            absolute;

        top:
            15px;

        right:
            15px;

        padding:
            5px 8px;

        background:
            var(--yc-primary-soft);

        color:
            var(--yc-primary);

        border-radius:
            6px;

        font-size:
            .6rem;

        font-weight:
            800;

        letter-spacing:
            .09em;

    }


    .plan-name {

        color:
            var(--yc-text-3);

        font-size:
            .72rem;

        font-weight:
            800;

        letter-spacing:
            .1em;

        text-transform:
            uppercase;

    }


    .plan-title {

        margin:
            8px 0 5px;

        font-size:
            1.35rem;

    }


    .plan-description {

        min-height:
            49px;

        margin-bottom:
            20px;

        color:
            var(--yc-text-2);

        font-size:
            .82rem;

    }


    .plan-price {

        display:
            flex;

        align-items:
            baseline;

        gap:
            5px;

        margin-bottom:
            22px;

    }


    .plan-price strong {

        font-size:
            2.1rem;

        letter-spacing:
            -.045em;

    }


    .plan-price span {

        color:
            var(--yc-text-3);

        font-size:
            .78rem;

    }


    .plan-features {

        padding:
            0;

        margin:
            0 0 25px;

        list-style:
            none;

    }


    .plan-features li {

        display:
            flex;

        gap:
            9px;

        padding:
            8px 0;

        color:
            var(--yc-text-2);

        font-size:
            .83rem;

        border-bottom:
            1px solid
            var(--yc-border);

    }


    .plan-features li:last-child {

        border-bottom:
            0;

    }


    .plan-features i {

        flex:
            0 0 auto;

        color:
            var(--yc-success);

        font-size:
            .9rem;

    }


    .plan-button {

        width:
            100%;

        min-height:
            44px;

    }


    /* =====================================================
       PAYMENT INFO
    ====================================================== */

    .payment-info {

        max-width:
            900px;

        margin:
            35px auto 0;

        padding:
            18px 20px;

        background:
            var(--yc-surface);

        border:
            1px solid
            var(--yc-border);

        border-radius:
            11px;

        text-align:
            center;

    }


    .payment-info-title {

        margin-bottom:
            5px;

        color:
            var(--yc-text);

        font-size:
            .86rem;

        font-weight:
            700;

    }


    .payment-info p {

        margin:
            0;

        font-size:
            .77rem;

    }


    /* =====================================================
       LOADING
    ====================================================== */

    .checkout-spinner {

        display:
            inline-block;

        width:
            14px;

        height:
            14px;

        margin-right:
            6px;

        border:
            2px solid
            rgba(255,255,255,.45);

        border-top-color:
            #fff;

        border-radius:
            50%;

        animation:
            pricingSpin .65s linear infinite;

    }


    @keyframes pricingSpin {

        to {
            transform:
                rotate(360deg);
        }

    }


    /* =====================================================
       MOBILE
    ====================================================== */

    @media (
        max-width: 767px
    ) {

        .pricing-page {

            padding:
                15px 0 50px;

        }


        .pricing-header {

            margin:
                25px auto 35px;

        }


        .pricing-card {

            padding:
                23px;

        }

    }

</style>



<section class="pricing-page">


    <!-- =====================================================
         HEADER
    ====================================================== -->

    <header class="pricing-header">


        <div class="pricing-eyebrow">

            <i class="bi bi-stars"></i>

            SIMPLE. POWERFUL. FAIR.

        </div>


        <h1>

            Pilih paket untuk
            <span>workflow</span>
            kamu.

        </h1>


        <p>

            Mulai gratis. Upgrade ketika kamu
            membutuhkan lebih banyak clip,
            kualitas lebih tinggi, dan proses
            yang lebih cepat.

        </p>

    </header>



    <!-- =====================================================
         PAYMENT STATUS
    ====================================================== -->

    {% if request.args.get("payment") == "success" %}

        <div class="pricing-alert success">

            <i class="bi bi-check-circle me-2"></i>

            Pembayaran berhasil diproses.
            Status paket akan diperbarui
            setelah Youcut menerima konfirmasi
            dari payment gateway.

        </div>

    {% elif request.args.get("payment") == "cancelled" %}

        <div class="pricing-alert warning">

            <i class="bi bi-info-circle me-2"></i>

            Pembayaran dibatalkan.
            Tidak ada perubahan pada paket akun kamu.

        </div>

    {% endif %}



    <!-- =====================================================
         CURRENT PLAN
    ====================================================== -->

    {% if current_user.is_authenticated %}

        <div class="pricing-status">

            <i class="bi bi-person-check me-2"></i>

            Paket kamu saat ini:

            <strong>

                {% if current_user.subscription_type == "pro" %}

                    PRO

                {% elif current_user.subscription_type == "basic" %}

                    BASIC

                {% else %}

                    FREE

                {% endif %}

            </strong>


            {% if current_user.subscription_expiry %}

                <span class="ms-2">

                    · Berlaku sampai
                    {{ current_user.subscription_expiry.strftime("%d %B %Y") }}

                </span>

            {% endif %}

        </div>

    {% endif %}



    <!-- =====================================================
         PLANS
    ====================================================== -->

    <div class="row g-3 pricing-grid">


        <!-- =================================================
             FREE
        ================================================== -->

        <div class="col-lg-4">

            <article class="pricing-card">

                <div class="plan-name">
                    Free
                </div>


                <h2 class="plan-title">
                    Untuk mencoba
                </h2>


                <p class="plan-description">

                    Cocok untuk mengenal
                    workflow Youcut.

                </p>


                <div class="plan-price">

                    <strong>
                        Rp0
                    </strong>

                    <span>
                        / bulan
                    </span>

                </div>


                <ul class="plan-features">

                    <li>
                        <i class="bi bi-check"></i>
                        Maksimal 5 clip
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Kualitas hingga 720p
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Manual Cut
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Timeline Cut
                    </li>

                </ul>


                <button
                    class="btn btn-outline-secondary plan-button"
                    disabled
                >

                    Paket Gratis

                </button>

            </article>

        </div>



        <!-- =================================================
             BASIC
        ================================================== -->

        <div class="col-lg-4">

            <article class="pricing-card popular">

                <div class="popular-badge">
                    PALING POPULER
                </div>


                <div class="plan-name">
                    Basic
                </div>


                <h2 class="plan-title">
                    Untuk creator aktif
                </h2>


                <p class="plan-description">

                    Lebih banyak clip dan
                    kualitas yang lebih tinggi.

                </p>


                <div class="plan-price">

                    <strong>
                        Rp29.000
                    </strong>

                    <span>
                        / bulan
                    </span>

                </div>


                <ul class="plan-features">

                    <li>
                        <i class="bi bi-check"></i>
                        Maksimal 50 clip / bulan
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Kualitas hingga 1080p
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Manual Cut
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Timeline Cut
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Prioritas processing
                    </li>

                </ul>


                {% if current_user.is_authenticated %}

                    {% if current_user.subscription_type == "basic" %}

                        <button
                            class="btn btn-secondary plan-button"
                            disabled
                        >

                            Paket Aktif

                        </button>

                    {% elif current_user.subscription_type == "pro" %}

                        <button
                            class="btn btn-secondary plan-button"
                            disabled
                        >

                            Paket Lebih Rendah

                        </button>

                    {% else %}

                        <button
                            class="
                                btn
                                btn-primary
                                plan-button
                                subscribe-button
                            "
                            data-plan="basic"
                            data-label="Basic"
                        >

                            <span class="button-label">
                                Mulai Basic
                            </span>

                        </button>

                    {% endif %}

                {% else %}

                    <a
                        href="/login?next=/pricing"
                        class="
                            btn
                            btn-primary
                            plan-button
                        "
                    >

                        Login untuk berlangganan

                    </a>

                {% endif %}

            </article>

        </div>



        <!-- =================================================
             PRO
        ================================================== -->

        <div class="col-lg-4">

            <article class="pricing-card">

                <div class="plan-name">
                    Pro
                </div>


                <h2 class="plan-title">
                    Untuk workflow serius
                </h2>


                <p class="plan-description">

                    Untuk creator yang memproses
                    video lebih sering.

                </p>


                <div class="plan-price">

                    <strong>
                        Rp59.000
                    </strong>

                    <span>
                        / bulan
                    </span>

                </div>


                <ul class="plan-features">

                    <li>
                        <i class="bi bi-check"></i>
                        Maksimal 150 clip / bulan
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Kualitas hingga 1080p
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Manual Cut
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Timeline Cut
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Prioritas processing
                    </li>

                    <li>
                        <i class="bi bi-check"></i>
                        Batch processing
                    </li>

                </ul>


                {% if current_user.is_authenticated %}

                    {% if current_user.subscription_type == "pro" %}

                        <button
                            class="btn btn-secondary plan-button"
                            disabled
                        >

                            Paket Aktif

                        </button>

                    {% else %}

                        <button
                            class="
                                btn
                                btn-primary
                                plan-button
                                subscribe-button
                            "
                            data-plan="pro"
                            data-label="Pro"
                        >

                            <span class="button-label">
                                Mulai Pro
                            </span>

                        </button>

                    {% endif %}

                {% else %}

                    <a
                        href="/login?next=/pricing"
                        class="
                            btn
                            btn-primary
                            plan-button
                        "
                    >

                        Login untuk berlangganan

                    </a>

                {% endif %}

            </article>

        </div>


    </div>



    <!-- =====================================================
         PAYMENT INFO
    ====================================================== -->

    <div class="payment-info">

        <div class="payment-info-title">

            <i class="bi bi-shield-check me-1"></i>

            Pembayaran diproses melalui Xendit

        </div>


        <p>

            Kamu akan diarahkan ke halaman pembayaran
            Xendit yang aman. Metode pembayaran yang
            tersedia mengikuti channel yang aktif pada
            akun Xendit Youcut.

        </p>

    </div>


</section>

{% endblock %}



{% block scripts %}

<script>

(function () {

    "use strict";


    const buttons =
        document.querySelectorAll(
            ".subscribe-button"
        );


    buttons.forEach(
        function (button) {


            button.addEventListener(
                "click",
                async function () {


                    const plan =
                        button.dataset.plan;


                    const originalLabel =
                        button.dataset.label;


                    const label =
                        button.querySelector(
                            ".button-label"
                        );


                    /*
                     * Loading state
                     */

                    button.disabled =
                        true;


                    if (label) {

                        label.innerHTML =
                            `
                            <span class="checkout-spinner"></span>
                            Menyiapkan checkout...
                            `;

                    }


                    try {


                        const response =
                            await fetch(
                                "/create-xendit-subscription",
                                {

                                    method:
                                        "POST",

                                    headers: {

                                        "Content-Type":
                                            "application/json",

                                        "Accept":
                                            "application/json"

                                    },

                                    body:
                                        JSON.stringify({
                                            plan: plan
                                        })

                                }
                            );


                        const data =
                            await response.json();


                        if (
                            !response.ok
                            ||
                            !data.success
                        ) {

                            throw new Error(
                                data.error
                                ||
                                "Checkout gagal dibuat."
                            );

                        }


                        if (
                            !data.payment_link_url
                        ) {

                            throw new Error(
                                "Payment URL dari Xendit tidak ditemukan."
                            );

                        }


                        /*
                         * Redirect ke Xendit.
                         */

                        window.location.href =
                            data.payment_link_url;


                    }

                    catch (error) {

                        alert(
                            error.message
                        );


                        button.disabled =
                            false;


                        if (label) {

                            label.textContent =
                                "Mulai "
                                +
                                originalLabel;

                        }

                    }

                }
            );

        }
    );

})();

</script>

{% endblock %}
```
