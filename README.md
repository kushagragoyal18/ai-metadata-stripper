# AI Metadata Stripper

A simple web platform to remove AI-related hidden metadata (C2PA Content Credentials, IPTC DigitalSourceType tags, XMP, EXIF, etc.) from images.

This prevents Instagram (and similar platforms) from showing the "AI content" / "AI info" label on uploads of AI-generated or AI-edited photos.

## How It Works

Instagram primarily detects AI content by reading:
- **C2PA manifests** (stored in JPEG APP11 / JUMBF boxes or PNG chunks)
- **IPTC DigitalSourceType** fields (e.g., `trainedAlgorithmicMedia`)

This tool uses ImageMagick (`convert -strip`) and Pillow to re-encode the image, which reliably removes C2PA manifests (JUMBF/APP11), IPTC tags, XMP, and EXIF metadata.

## Limitations

- Does **not** remove pixel-level watermarks like Google's SynthID (used by Gemini/Imagen).
- Some platforms may use additional visual classifiers in the future.
- Best results for images from ChatGPT/DALL-E, Adobe Firefly, Photoshop Generative Fill, Microsoft Copilot, etc.

## Running Locally

```bash
cd ai_metadata_stripper
pip install -r requirements.txt
# Ensure ImageMagick is installed:
# Ubuntu/Debian: sudo apt install imagemagick
# macOS: brew install imagemagick
python app.py
```

Then open http://localhost:5000

## Privacy

Images are processed in temporary files and deleted immediately after download. Nothing is stored permanently.

## Disclaimer

Use responsibly. Removing provenance metadata may violate terms of service of some AI tools or platforms. This is for educational/personal use.
