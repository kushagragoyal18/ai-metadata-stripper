import os
import subprocess
import uuid
from pathlib import Path
from flask import Flask, request, render_template, send_file, jsonify, after_this_request, Response
from werkzeug.utils import secure_filename
import tempfile
import shutil

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB limit
_tmp = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = os.path.join(_tmp, 'clearcorners-uploads')
app.config['CLEANED_FOLDER'] = os.path.join(_tmp, 'clearcorners-cleaned')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CLEANED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'tiff', 'tif', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_without_metadata(input_path, output_path):
    """Re-encode with Pillow so EXIF, XMP, and C2PA segments are not copied."""
    from PIL import Image
    with Image.open(input_path) as img:
        if output_path.lower().endswith(('.jpg', '.jpeg')) and img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        kwargs = {}
        lower = output_path.lower()
        if lower.endswith(('.jpg', '.jpeg', '.webp')):
            kwargs.update(quality=95, optimize=True)
        elif lower.endswith('.png'):
            kwargs['optimize'] = True
        img.save(output_path, **kwargs)

def strip_metadata(input_path, output_path):
    """Strip metadata with ImageMagick when it is installed, otherwise Pillow."""
    wrote = False
    try:
        result = subprocess.run(
            ['convert', str(input_path), '-strip', '-quality', '95', str(output_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        wrote = result.returncode == 0 and os.path.exists(output_path)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        wrote = False

    if not wrote:
        try:
            save_without_metadata(input_path, output_path)
        except Exception as e:
            return False, str(e)

    if not os.path.exists(output_path):
        return False, 'Could not write the cleaned image'
    return True, 'Metadata stripped successfully'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/strip', methods=['POST'])
def strip():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'File type not supported. Use JPG, PNG, WEBP, TIFF, GIF.'}), 400
    
    # Generate unique names
    file_id = str(uuid.uuid4())
    original_ext = file.filename.rsplit('.', 1)[1].lower()
    input_filename = f"{file_id}_input.{original_ext}"
    output_filename = f"{file_id}_cleaned.{original_ext}"
    
    input_path = os.path.join(app.config['UPLOAD_FOLDER'], input_filename)
    output_path = os.path.join(app.config['CLEANED_FOLDER'], output_filename)
    
    file.save(input_path)
    
    success, message = strip_metadata(input_path, output_path)
    
    if not success or not os.path.exists(output_path):
        try:
            os.remove(input_path)
        except OSError:
            pass
        return jsonify({'error': f'Failed to process image: {message}'}), 500

    download_name = f"cleaned_{secure_filename(file.filename)}"
    with open(output_path, 'rb') as cleaned:
        payload = cleaned.read()
    for path in (input_path, output_path):
        try:
            os.remove(path)
        except OSError:
            pass

    # Return the file in this response. Serverless hosts do not keep temp
    # files between this request and a later download request.
    return Response(
        payload,
        mimetype='application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{download_name}"'},
    )

@app.route('/download/<file_id>')
def download(file_id):
    # Find the cleaned file
    cleaned_dir = Path(app.config['CLEANED_FOLDER'])
    matches = list(cleaned_dir.glob(f"{file_id}_cleaned.*"))
    
    if not matches:
        return jsonify({'error': 'File not found or expired'}), 404
    
    file_path = matches[0]
    
    # Schedule cleanup after send
    @after_this_request
    def remove_file(response):
        try:
            os.remove(file_path)
        except:
            pass
        return response
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=f"cleaned_image{file_path.suffix}",
        mimetype='application/octet-stream'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
