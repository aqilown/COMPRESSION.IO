import os
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from io import BytesIO
from threading import Thread

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)

PRESETS = {'/screen', '/ebook', '/printer', '/prepress'}
GS = shutil.which('gswin64c') or shutil.which('gs')  # Windows / Linux+Mac binary name

# shortcut: in-memory task dict, single process only; use Redis/Celery if you deploy with >1 worker
COMPRESS_TASKS = {}


def compress_one(src, dst, quality):
    subprocess.run([
        GS, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={quality}",
        "-dNumRenderingThreads=8", "-dBufferSpace=1000000000",
        "-dColorImageDownsampleThreshold=1.0",
        "-dGrayImageDownsampleThreshold=1.0",
        "-dMonoImageDownsampleThreshold=1.0",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={dst}", src,
    ], check=True, capture_output=True, text=True)


def process_compression(task_id, file_paths, quality, temp_dir):
    try:
        if len(file_paths) == 1:
            name, src = file_paths[0]
            result = src + "_compressed.pdf"
            compress_one(src, result, quality)
            download_name, mimetype = f"{os.path.splitext(name)[0]}_compressed.pdf", 'application/pdf'
        else:
            result = os.path.join(temp_dir, "Hasil_Compress_Bulk.zip")
            with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, src in file_paths:
                    out = src + "_compressed.pdf"
                    compress_one(src, out, quality)
                    zf.write(out, arcname=f"compressed_{name}")
            download_name, mimetype = "Hasil_Compress_Bulk.zip", 'application/zip'
        COMPRESS_TASKS[task_id] = {'status': 'done', 'result_path': result,
                                   'download_name': download_name,
                                   'mimetype': mimetype, 'temp_dir': temp_dir}
    except Exception as e:
        err = getattr(e, 'stderr', None) or str(e)
        COMPRESS_TASKS[task_id] = {'status': 'error', 'error': err}
        shutil.rmtree(temp_dir, ignore_errors=True)  # nobody downloads a failed task


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/compress-pdf', methods=['POST'])
def api_compress_pdf():
    files = [f for f in request.files.getlist('files') if f.filename]
    if not files:
        return jsonify({'error': 'Upload PDF-nya dulu!'}), 400
    if not GS:
        return jsonify({'error': 'Ghostscript tidak ditemukan di PATH'}), 500

    quality = request.form.get('quality', '/ebook')
    if quality not in PRESETS:  # value goes straight into the gs command line
        return jsonify({'error': 'Preset tidak valid'}), 400

    temp_dir = tempfile.mkdtemp()
    try:
        file_paths = []
        for i, f in enumerate(files):
            name = secure_filename(f.filename)  # blocks path traversal like ..\..\x
            if not name.lower().endswith('.pdf'):
                raise ValueError(f'Bukan file PDF: {f.filename}')
            path = os.path.join(temp_dir, f"{i}_{name}")  # index avoids duplicate-name overwrite
            f.save(path)
            file_paths.append((name, path))
    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify({'error': str(e)}), 400

    task_id = str(uuid.uuid4())
    COMPRESS_TASKS[task_id] = {'status': 'processing'}
    Thread(target=process_compression, args=(task_id, file_paths, quality, temp_dir), daemon=True).start()
    return jsonify({'task_id': task_id})


@app.route('/api/compress-status/<task_id>')
def api_compress_status(task_id):
    task = COMPRESS_TASKS.get(task_id)
    if not task:
        return jsonify({'error': 'Task tidak ditemukan'}), 404
    return jsonify({'status': task['status'], 'error': task.get('error')})


@app.route('/api/compress-download/<task_id>')
def api_compress_download(task_id):
    task = COMPRESS_TASKS.get(task_id)  
    if not task or task['status'] != 'done':
        return "Invalid task atau belum selesai", 400
    del COMPRESS_TASKS[task_id]

    with open(task['result_path'], 'rb') as f:  # read into memory so temp dir can be deleted now
        data = f.read()
    shutil.rmtree(task['temp_dir'], ignore_errors=True)
    return send_file(BytesIO(data), as_attachment=True,
                     download_name=task['download_name'], mimetype=task['mimetype'])


if __name__ == '__main__':
    print("Menjalankan Compressor Engine...")
    app.run(debug=True)