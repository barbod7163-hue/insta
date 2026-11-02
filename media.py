"""Image generation, Instagram-ready JPEG conversion, and public hosting."""
import base64
import io
from pathlib import Path

from config import DATA, IMAGE_MODEL, IMAGE_QUALITY, PERSONA, ROOT, env


def generate_image(prompt, out_path, use_reference=False):
    """Generate with the OpenAI Images API and save as a 4:5 JPEG (Instagram accepts JPEG only)."""
    from openai import OpenAI
    from PIL import Image

    client = OpenAI()  # reads OPENAI_API_KEY
    full = (
        f"{prompt}\nStyle: {PERSONA['visual_style']}. Vertical composition, subject centered with "
        "margin on all sides. No text, no watermark, no logos."
    )
    ref = DATA / "reference.jpg"  # optional face/character reference for consistency
    if use_reference and ref.exists():
        with open(ref, "rb") as f:
            r = client.images.edit(model=IMAGE_MODEL, image=f, prompt=full,
                                   size="1024x1536", quality=IMAGE_QUALITY)
    else:
        r = client.images.generate(model=IMAGE_MODEL, prompt=full,
                                   size="1024x1536", quality=IMAGE_QUALITY)

    img = Image.open(io.BytesIO(base64.b64decode(r.data[0].b64_json))).convert("RGB")
    w, h = img.size
    target_h = int(w * 5 / 4)  # 4:5 is the tallest ratio feed posts allow
    if h > target_h:
        top = (h - target_h) // 2
        img = img.crop((0, top, w, top + target_h))
    img.save(out_path, "JPEG", quality=92, optimize=True)


def _github_url(path):
    """STORAGE=github: the image is already committed to this (public) repo, so serve it from
    raw.githubusercontent.com. Instagram downloads from this URL, so the repo must be public."""
    import requests

    rel = Path(path).resolve().relative_to(ROOT).as_posix()
    url = (f"https://raw.githubusercontent.com/{env('GITHUB_REPOSITORY')}/"
           f"{env('GITHUB_REF_NAME', 'main')}/{rel}")
    code = requests.head(url, timeout=20, allow_redirects=True).status_code
    if code != 200:
        raise RuntimeError(f"Image URL not publicly reachable (HTTP {code}): {url} - is the repo public?")
    return url


def upload(path, key):
    """Return a public URL for the image. STORAGE=github uses the repo itself; otherwise upload to an
    S3-compatible bucket (S3, Cloudflare R2, MinIO...). Instagram fetches this URL, so it must be public."""
    if env("STORAGE", "s3") == "github":
        return _github_url(path)
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=env("S3_ENDPOINT") or None,
        aws_access_key_id=env("S3_ACCESS_KEY"),
        aws_secret_access_key=env("S3_SECRET_KEY"),
        region_name=env("S3_REGION", "auto"),
    )
    s3.upload_file(str(path), env("S3_BUCKET"), key,
                   ExtraArgs={"ContentType": "image/jpeg", "CacheControl": "public, max-age=31536000"})
    return f"{env('PUBLIC_BASE_URL').rstrip('/')}/{key}"
