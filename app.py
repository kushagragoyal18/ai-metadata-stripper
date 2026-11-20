import os
import subprocess
import uuid
from pathlib import Path
from flask import Flask, request, render_template, send_file, jsonify, after_this_request
from werkzeug.utils import secure_filename
import tempfile
import shutil

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024  # 20MB limit
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['CLEANED_FOLDER'] = '/tmp/cleaned'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CLEANED_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'tiff', 'tif', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def strip_metadata(input_path, output_path):
    """Strip all metadata including C2PA/JUMBF by re-encoding with ImageMagick and Pillow."""
    try:
        # Primary method: ImageMagick convert -strip (removes all profiles, comments, APP segments, C2PA)
        # Use high quality to minimize visual changes
        cmd = [
            'convert',
            str(input_path),
            '-strip',           # Remove all profiles and comments
            '-quality', '95',   # High quality JPEG
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0 or not os.path.exists(output_path):
            # Fallback: Pillow re-save (strips EXIF/XMP)
            from PIL import Image
            with Image.open(input_path) as img:
                # Convert to RGB if necessary for JPEG
                if img.mode in ('RGBA', 'P') and output_path.lower().endswith(('.jpg', '.jpeg')):
                    img = img.convert('RGB')
                img.save(output_path, quality=95, optimize=True)
        
        # Extra safety: if still JPEG, re-save once more with Pillow to be sure
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            from PIL import Image
            with Image.open(output_path) as img:
                img.save(output_path, quality=95, optimize=True)
        
        return True, "Metadata stripped successfully (C2PA, IPTC, EXIF, XMP removed)"
    except Exception as e:
        return False, str(e)

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
    
    # Clean up input
    try:
        os.remove(input_path)
    except:
        pass
    
    if not success or not os.path.exists(output_path):
        return jsonify({'error': f'Failed to process image: {message}'}), 500
    
    # Get file size for info
    size = os.path.getsize(output_path)
    
    return jsonify({
        'success': True,
        'download_id': file_id,
        'filename': f"cleaned_{secure_filename(file.filename)}",
        'size': size,
        'message': 'AI metadata, C2PA credentials, and all tags removed. Safe for Instagram upload.'
    })

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
