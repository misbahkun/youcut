document.addEventListener('DOMContentLoaded', function() {
    const cutsContainer = document.getElementById('cutsContainer');
    const addCutBtn = document.getElementById('addCut');
    const form = document.getElementById('manualForm');
    const statusArea = document.getElementById('statusArea');
    const progressBar = document.getElementById('progressBar');
    const statusMessage = document.getElementById('statusMessage');
    const resultContainer = document.getElementById('resultContainer');
    const downloadAllBtn = document.getElementById('downloadAllBtn');
    let jobId = null;

    // Template satu baris potongan dengan input HH:MM:SS
    function createCutRow() {
        const row = document.createElement('div');
        row.className = 'cut-row row g-2 mb-2 align-items-end';
        row.innerHTML = `
            <div class="col-md-3">
                <label class="form-label">Mulai (HH:MM:SS)</label>
                <div class="input-group">
                    <input type="number" class="form-control start-hh" min="0" max="99" placeholder="00" required>
                    <span class="input-group-text">:</span>
                    <input type="number" class="form-control start-mm" min="0" max="59" placeholder="00" required>
                    <span class="input-group-text">:</span>
                    <input type="number" class="form-control start-ss" min="0" max="59" placeholder="00" required>
                </div>
            </div>
            <div class="col-md-3">
                <label class="form-label">Selesai (HH:MM:SS)</label>
                <div class="input-group">
                    <input type="number" class="form-control end-hh" min="0" max="99" placeholder="00" required>
                    <span class="input-group-text">:</span>
                    <input type="number" class="form-control end-mm" min="0" max="59" placeholder="00" required>
                    <span class="input-group-text">:</span>
                    <input type="number" class="form-control end-ss" min="0" max="59" placeholder="00" required>
                </div>
            </div>
            <div class="col-md-2">
                <button type="button" class="btn btn-danger btn-sm remove-cut">Hapus</button>
            </div>
        `;
        // Event hapus
        row.querySelector('.remove-cut').addEventListener('click', function() {
            if (cutsContainer.children.length > 1) {
                row.remove();
                updateRemoveButtons();
            } else {
                alert('Minimal satu potongan diperlukan.');
            }
        });
        return row;
    }

    // Update visibilitas tombol hapus (jika hanya satu baris, sembunyikan)
    function updateRemoveButtons() {
        const rows = cutsContainer.querySelectorAll('.cut-row');
        rows.forEach(row => {
            const btn = row.querySelector('.remove-cut');
            btn.style.display = rows.length > 1 ? '' : 'none';
        });
    }

    // Tambah potongan pertama
    cutsContainer.appendChild(createCutRow());
    updateRemoveButtons();

    // Tombol tambah potongan
    addCutBtn.addEventListener('click', function() {
        if (cutsContainer.children.length >= 15) {
            alert('Maksimal 15 potongan.');
            return;
        }
        cutsContainer.appendChild(createCutRow());
        updateRemoveButtons();
    });

    // Helper: konversi HH:MM:SS ke detik
    function hhmmssToSeconds(hh, mm, ss) {
        return (parseInt(hh) || 0) * 3600 + (parseInt(mm) || 0) * 60 + (parseInt(ss) || 0);
    }

    // Submit form
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const youtubeUrl = document.getElementById('youtubeUrl').value.trim();
        const quality = document.getElementById('quality').value;
        const orientation = document.getElementById('orientation').value;

        // Validasi link YouTube sederhana
        if (!youtubeUrl.includes('youtube.com/watch') && !youtubeUrl.includes('youtu.be/')) {
            alert('Masukkan URL YouTube yang valid.');
            return;
        }

        // Kumpulkan potongan
        const cuts = [];
        const rows = cutsContainer.querySelectorAll('.cut-row');
        rows.forEach(row => {
            const startH = row.querySelector('.start-hh').value;
            const startM = row.querySelector('.start-mm').value;
            const startS = row.querySelector('.start-ss').value;
            const endH = row.querySelector('.end-hh').value;
            const endM = row.querySelector('.end-mm').value;
            const endS = row.querySelector('.end-ss').value;
            if (startH !== '' && startM !== '' && startS !== '' && endH !== '' && endM !== '' && endS !== '') {
                const startSec = hhmmssToSeconds(startH, startM, startS);
                const endSec = hhmmssToSeconds(endH, endM, endS);
                if (endSec > startSec) {
                    cuts.push({ start: startSec, end: endSec });
                } else {
                    alert('Waktu selesai harus lebih besar dari waktu mulai.');
                    throw new Error('Validasi gagal');
                }
            }
        });

        if (cuts.length === 0) {
            alert('Isi minimal satu potongan.');
            return;
        }

        // Tampilkan status area
        statusArea.style.display = 'block';
        resultContainer.innerHTML = '';
        downloadAllBtn.style.display = 'none';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        statusMessage.textContent = 'Mengunduh video...';

        try {
            const response = await fetch('/api/manual/create_job', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    youtube_url: youtubeUrl,
                    cuts: cuts,
                    quality: quality,
                    orientation: orientation
                })
            });
            const data = await response.json();
            if (data.error) {
                statusMessage.textContent = 'Error: ' + data.error;
                return;
            }
            jobId = data.job_id;
            pollStatus();
        } catch (err) {
            statusMessage.textContent = 'Gagal menghubungi server.';
        }
    });

    function pollStatus() {
        const interval = setInterval(async () => {
            try {
                const resp = await fetch(`/api/manual/job_status/${jobId}`);
                const status = await resp.json();
                progressBar.style.width = status.progress + '%';
                progressBar.textContent = status.progress + '%';

                if (status.status === 'completed') {
                    clearInterval(interval);
                    statusMessage.textContent = 'Selesai!';
                    displayResults(status.outputs, status.zip_path);
                } else if (status.status === 'error') {
                    clearInterval(interval);
                    statusMessage.textContent = 'Error: ' + status.error;
                } else {
                    statusMessage.textContent = 'Status: ' + status.status;
                }
            } catch (err) {
                clearInterval(interval);
                statusMessage.textContent = 'Gagal memeriksa status.';
            }
        }, 1000);
    }

    function displayResults(outputs, zipPath) {
        resultContainer.innerHTML = '';
        outputs.forEach((name, index) => {
            const col = document.createElement('div');
            col.className = 'col-md-4 mb-3';
            col.innerHTML = `
                <div class="card">
                    <video class="card-img-top video-preview" controls>
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
});