document.addEventListener('DOMContentLoaded', function() {
    // ========== Halaman Form Timeline Awal ==========
    const timelineForm = document.getElementById('timelineForm');
    if (timelineForm) {
        timelineForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            const youtubeUrl = document.getElementById('youtubeUrl').value;
            const quality = document.getElementById('quality').value;
            const orientation = document.getElementById('orientation').value;

            try {
                const resp = await fetch('/api/timeline/create_job', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({youtube_url: youtubeUrl, quality, orientation})
                });
                const data = await resp.json();
                if (data.redirect) {
                    window.location.href = data.redirect;
                } else {
                    alert('Error: ' + (data.error || 'Gagal membuat job'));
                }
            } catch (err) {
                alert('Gagal terhubung ke server.');
            }
        });
    }

    // ========== Halaman Edit Timeline ==========
    if (window.timelineConfig) {
        const config = window.timelineConfig;
        const jobId = config.jobId;
        const duration = parseFloat(config.duration);
        const quality = config.quality;
        const orientation = config.orientation;

        const cutsContainer = document.getElementById('cutsContainer');
        const addCutBtn = document.getElementById('addCutBtn');
        const processBtn = document.getElementById('processCutsBtn');
        const statusArea = document.getElementById('statusArea');
        const progressBar = document.getElementById('progressBar');
        const resultContainer = document.getElementById('resultContainer');
        const downloadAllBtn = document.getElementById('downloadAllBtn');
        const video = document.getElementById('mainVideo');

        let cutCount = 0;

        function createCutRow() {
            cutCount++;
            const rowDiv = document.createElement('div');
            rowDiv.className = 'cut-row mb-3 p-2 border rounded';
            rowDiv.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h6 class="mb-0">Potongan ${cutCount}</h6>
                    <button class="btn btn-sm btn-danger remove-cut">Hapus</button>
                </div>
                <div class="row">
                    <div class="col-md-5 mb-2">
                        <label>Mulai: <span class="start-val">0.0</span> detik</label>
                        <div class="start-slider"></div>
                    </div>
                    <div class="col-md-5 mb-2">
                        <label>Selesai: <span class="end-val">${duration.toFixed(1)}</span> detik</label>
                        <div class="end-slider"></div>
                    </div>
                    <div class="col-md-2">
                        <video class="preview-video w-100" controls style="max-height:80px;"></video>
                    </div>
                </div>
            `;
            cutsContainer.appendChild(rowDiv);

            // Inisialisasi noUiSlider
            const startSlider = rowDiv.querySelector('.start-slider');
            const endSlider = rowDiv.querySelector('.end-slider');

            noUiSlider.create(startSlider, {
                start: [0],
                connect: [true, false],
                range: { min: 0, max: duration },
                step: 0.1,
                tooltips: false
            });
            noUiSlider.create(endSlider, {
                start: [duration],
                connect: [false, true],
                range: { min: 0, max: duration },
                step: 0.1,
                tooltips: false
            });

            const startValSpan = rowDiv.querySelector('.start-val');
            const endValSpan = rowDiv.querySelector('.end-val');

            startSlider.noUiSlider.on('update', function(values) {
                const val = parseFloat(values[0]).toFixed(1);
                startValSpan.textContent = val;
            });
            endSlider.noUiSlider.on('update', function(values) {
                const val = parseFloat(values[0]).toFixed(1);
                endValSpan.textContent = val;
            });

            // Hapus potongan
            rowDiv.querySelector('.remove-cut').addEventListener('click', function() {
                if (cutsContainer.children.length > 1) {
                    rowDiv.remove();
                    cutCount--;
                } else {
                    alert('Minimal satu potongan diperlukan.');
                }
            });
        }

        // Buat potongan pertama
        createCutRow();

        addCutBtn.addEventListener('click', function() {
            if (cutsContainer.children.length >= 15) {
                alert('Maksimal 15 potongan.');
                return;
            }
            createCutRow();
        });

        processBtn.addEventListener('click', async function() {
            const cuts = [];
            document.querySelectorAll('.cut-row').forEach(row => {
                const start = parseFloat(row.querySelector('.start-val').textContent);
                const end = parseFloat(row.querySelector('.end-val').textContent);
                if (end > start) {
                    cuts.push({start, end});
                }
            });

            if (cuts.length === 0) {
                alert('Tidak ada potongan valid.');
                return;
            }

            statusArea.style.display = 'block';
            progressBar.style.width = '0%';
            progressBar.textContent = '0%';
            resultContainer.innerHTML = '';
            downloadAllBtn.style.display = 'none';

            try {
                const resp = await fetch('/api/timeline/cut', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        job_id: jobId,
                        cuts: cuts,
                        quality: quality,
                        orientation: orientation
                    })
                });
                const data = await resp.json();
                if (data.status === 'completed') {
                    progressBar.style.width = '100%';
                    progressBar.textContent = '100%';
                    displayResults(data.outputs, data.zip_path);
                } else {
                    alert('Error: ' + (data.error || 'Gagal memotong video'));
                }
            } catch (err) {
                alert('Gagal memproses permintaan.');
            }
        });

        function displayResults(outputs, zipPath) {
            resultContainer.innerHTML = '';
            outputs.forEach((name, index) => {
                const col = document.createElement('div');
                col.className = 'col-md-4 mb-3';
                col.innerHTML = `
                    <div class="card h-100">
                        <video class="card-img-top" controls style="max-height:200px;">
                            <source src="/api/download_clip/${jobId}/${index}" type="video/mp4">
                        </video>
                        <div class="card-body text-center">
                            <h6>${name}</h6>
                            <a href="/api/download_clip/${jobId}/${index}" class="btn btn-sm btn-primary">Download</a>
                        </div>
                    </div>
                `;
                resultContainer.appendChild(col);
            });

            if (zipPath) {
                downloadAllBtn.style.display = 'block';
                downloadAllBtn.onclick = () => {
                    window.location.href = `/api/manual/download_zip/${jobId}`;
                };
            }
        }
    }
});