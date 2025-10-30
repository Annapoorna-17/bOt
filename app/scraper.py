import os
import io
import base64
import hashlib
import re
import asyncio
from typing import List, Dict, Tuple, Optional, Callable
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
from PIL import Image
from openai import OpenAI
from pinecone import Pinecone

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-large")
CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX_NAME", "bot-multi") or os.getenv("PINECONE_INDEX")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")
if not PINECONE_API_KEY or not PINECONE_INDEX:
    raise RuntimeError("Pinecone API key or index name missing")

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)
oai = OpenAI(api_key=OPENAI_API_KEY)


def _pil_image_to_base64(image: Image.Image) -> str:
    """Convert PIL Image to base64 string for API transmission."""
    buffered = io.BytesIO()
    if image.mode not in ('RGB', 'L'):
        image = image.convert('RGB')
    image.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


def _describe_image(img_base64: str, img_url: str) -> str:
    """
    Use GPT-4o Vision to describe the content of an image from a website.
    Returns a text description that can be embedded alongside website text.
    """
    try:
        print(f"DEBUG: Calling GPT-4o Vision for image: {img_url}")
        response = oai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe this image in detail. Include any text, charts, diagrams, "
                                "tables, or visual information. If it contains data or specific details, "
                                "extract them precisely. This will be used for website content search."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{img_base64}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500,
            temperature=0.1
        )
        description = response.choices[0].message.content.strip()
        print(f"DEBUG: Vision API returned description ({len(description)} chars): {description[:100]}...")
        return description
    except Exception as e:
        print(f"Warning: Failed to describe image {img_url}: {e}")
        return ""


def _extract_text_from_html(html: str, base_url: str) -> Tuple[str, str]:
    """
    Extract text content and title from HTML.
    Returns (title, text_content)
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Extract title
    title = ""
    if soup.title:
        title = soup.title.string.strip() if soup.title.string else ""

    # Remove script and style elements
    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()

    # Get text
    text = soup.get_text(separator='\n', strip=True)

    # Clean up text
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    text = '\n'.join(lines)

    return title, text


def _extract_images_from_html(html: str, base_url: str) -> List[str]:
    """
    Extract image URLs from HTML with minimal filtering.
    Returns list of absolute image URLs.
    """
    soup = BeautifulSoup(html, 'html.parser')
    image_urls = []

    # Very minimal skip patterns - only truly decorative items
    skip_patterns = ['favicon', 'icon-', 'logo-', 'sprite', '1x1', 'pixel', 'blank.']

    # Find all img tags
    for img in soup.find_all('img'):
        # Try multiple attributes (Wikipedia uses srcset, src, data-src, etc.)
        src = None

        # Try srcset first (Wikipedia uses this)
        srcset = img.get('srcset')
        if srcset:
            # srcset can have multiple URLs, take the first one
            src = srcset.split(',')[0].split()[0]

        # Fallback to src attributes
        if not src:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')

        if not src:
            continue

        # Convert relative URLs to absolute
        absolute_url = urljoin(base_url, src)

        # Skip data URLs
        if absolute_url.startswith('data:'):
            continue

        # Very minimal filtering - only skip obvious UI elements
        url_lower = absolute_url.lower()
        if any(pattern in url_lower for pattern in skip_patterns):
            continue

        # Skip very small images by dimensions (if specified)
        width = img.get('width')
        height = img.get('height')
        if width and height:
            try:
                w = int(width.replace('px', ''))
                h = int(height.replace('px', ''))
                if w < 30 or h < 30:  # Very small threshold
                    continue
            except (ValueError, TypeError):
                pass

        image_urls.append(absolute_url)

    print(f"DEBUG: _extract_images_from_html found {len(image_urls)} images")
    if image_urls:
        print(f"DEBUG: Sample images: {image_urls[:3]}")

    return image_urls


async def _download_and_analyze_image(
    img_url: str,
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    progress_callback: Optional[Callable] = None
) -> str:
    """
    Download an image from URL and analyze it with GPT-4o Vision (async).
    Uses semaphore to limit concurrent downloads.
    Returns description text.
    """
    async with semaphore:  # Limit concurrent image processing
        try:
            if progress_callback:
                await progress_callback(f"Downloading image: {img_url[:60]}...")

            print(f"DEBUG: Downloading image: {img_url}")

            # Skip SVG files as they can't be processed by PIL
            if img_url.lower().endswith('.svg'):
                print(f"DEBUG: Skipping SVG file (not supported by Vision API)")
                return ""

            # Reduced timeout from 10s to 7s per image for faster processing
            response = await client.get(img_url, timeout=7.0, follow_redirects=True)
            response.raise_for_status()

            # Load image with size limit check
            image_bytes = response.content

            # Check file size before loading (skip if > 5MB for faster processing)
            if len(image_bytes) > 5 * 1024 * 1024:
                print(f"DEBUG: Skipping large image (>{len(image_bytes)/1024/1024:.1f}MB)")
                return ""

            # Try to open image with PIL
            try:
                pil_image = Image.open(io.BytesIO(image_bytes))
                print(f"DEBUG: Image loaded: {pil_image.width}x{pil_image.height}px, mode={pil_image.mode}")
            except Exception as img_error:
                print(f"DEBUG: Failed to open image with PIL: {img_error}")
                return ""

            # Skip very small images (likely decorative/icons)
            if pil_image.width < 50 or pil_image.height < 50:
                print(f"DEBUG: Skipping small image ({pil_image.width}x{pil_image.height}px)")
                return ""

            # Resize if too large to save API costs and memory
            max_size = 2048
            if max(pil_image.width, pil_image.height) > max_size:
                ratio = max_size / max(pil_image.width, pil_image.height)
                new_size = (int(pil_image.width * ratio), int(pil_image.height * ratio))
                pil_image = pil_image.resize(new_size, Image.Resampling.LANCZOS)
                print(f"DEBUG: Resized image to {new_size[0]}x{new_size[1]}px")

            if progress_callback:
                await progress_callback(f"Analyzing image with Vision API...")

            img_base64 = _pil_image_to_base64(pil_image)

            # Clean up image from memory immediately
            pil_image.close()
            del pil_image
            del image_bytes

            return _describe_image(img_base64, img_url)

        except httpx.TimeoutException:
            print(f"Warning: Timeout downloading image {img_url}")
            return ""
        except Exception as e:
            print(f"Warning: Could not download/analyze image {img_url}: {e}")
            return ""


def _chunk_text(text: str, max_chars: int = 3000, overlap: int = 400):
    """
    Simple, fast chunker that respects sentence boundaries when possible.
    Fixed infinite loop issue.
    """
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) <= max_chars:
        return [text] if text else []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + max_chars, len(text))
        window = text[start:end]

        # Find sentence boundary
        cut = max(window.rfind('. '), window.rfind('? '), window.rfind('! '))

        # If no sentence boundary or at end, use full window
        if cut == -1 or end == len(text):
            cut = len(window)
        else:
            cut += 1  # Include the punctuation

        chunk = window[:cut].strip()
        if chunk:
            chunks.append(chunk)

        # Move forward (FIXED: ensure we always move forward)
        next_start = start + cut - overlap

        # Ensure we make progress (prevent infinite loop)
        if next_start <= start:
            next_start = start + max(1, cut // 2)  # Jump at least halfway

        start = next_start

        # Safety check: if we've reached the end, break
        if end >= len(text):
            break

    # dedupe / clean
    out = []
    last = ""
    for c in chunks:
        if c and c != last:
            out.append(c)
            last = c

    print(f"DEBUG: Chunking complete, created {len(out)} chunks from {len(text)} chars")
    return out


def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """Generate embeddings for text chunks."""
    resp = oai.embeddings.create(model=EMBED_MODEL, input=chunks)
    return [d.embedding for d in resp.data]


def upsert_website_chunks(tenant_code: str, user_code: str, url: str, chunks: List[str]) -> int:
    """
    Upsert website chunks to Pinecone with metadata.
    """
    embs = embed_chunks(chunks)
    vectors = []

    # Create a unique identifier for this URL
    url_hash = hashlib.md5(url.encode()).hexdigest()[:12]

    for i, (chunk, vec) in enumerate(zip(chunks, embs)):
        vid = hashlib.sha256(f"{tenant_code}:website:{url_hash}:{i}".encode()).hexdigest()
        vectors.append({
            "id": vid,
            "values": vec,
            "metadata": {
                "tenant_code": tenant_code,
                "user_code": user_code,
                "source_type": "website",  # Distinguish from documents
                "url": url,
                "chunk_index": i,
                "text": chunk
            }
        })

    index.upsert(vectors=vectors, namespace=tenant_code)
    return len(vectors)


async def scrape_and_index_website(
    url: str,
    tenant_code: str,
    user_code: str,
    max_images: int = 10,
    max_concurrent_images: int = 5,
    progress_callback: Optional[Callable] = None
) -> Tuple[str, int]:
    """
    Scrape a website, extract text and images, analyze with Vision API, and index to Pinecone.
    Now uses async/await for concurrent image processing.

    Args:
        url: Website URL to scrape
        tenant_code: Tenant identifier
        user_code: User identifier
        max_images: Maximum number of images to analyze (to control costs)
        max_concurrent_images: Max number of images to process concurrently (default: 5, increased from 3)
        progress_callback: Optional async callback for progress updates

    Returns:
        Tuple of (page_title, num_chunks_indexed)
    """
    print(f"DEBUG: Starting website scraping for {url}")

    # Create async HTTP client with connection pooling and limits
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    timeout = httpx.Timeout(12.0, connect=4.0)  # Reduced from 15s to 12s for faster processing

    async with httpx.AsyncClient(limits=limits, timeout=timeout, follow_redirects=True) as client:
        # Fetch HTML
        try:
            if progress_callback:
                await progress_callback(f"Fetching website: {url}")

            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            print(f"DEBUG: Fetched {len(html)} bytes of HTML")
        except Exception as e:
            raise RuntimeError(f"Failed to fetch website: {e}")

        # Extract text and title
        if progress_callback:
            await progress_callback("Extracting text content...")

        title, text_content = _extract_text_from_html(html, url)
        print(f"DEBUG: Extracted title: {title}")
        print(f"DEBUG: Extracted {len(text_content)} chars of text")

        # Extract images
        if progress_callback:
            await progress_callback("Finding images...")

        image_urls = _extract_images_from_html(html, url)
        print(f"DEBUG: Found {len(image_urls)} images")

        # Limit images to process
        images_to_process = image_urls[:max_images]

        # Analyze images CONCURRENTLY with semaphore control
        image_descriptions = []
        if images_to_process:
            print(f"DEBUG: Processing {len(images_to_process)} images...")
            if progress_callback:
                await progress_callback(f"Processing {len(images_to_process)} images in parallel...")

            # Semaphore limits concurrent image processing
            semaphore = asyncio.Semaphore(max_concurrent_images)

            # Process all images concurrently (but limited by semaphore)
            tasks = [
                _download_and_analyze_image(img_url, client, semaphore, progress_callback)
                for img_url in images_to_process
            ]

            print(f"DEBUG: Waiting for {len(tasks)} image processing tasks...")
            # Wait for all image processing to complete
            descriptions = await asyncio.gather(*tasks, return_exceptions=True)
            print(f"DEBUG: Image processing complete, got {len(descriptions)} results")

            # Collect successful descriptions
            for i, desc in enumerate(descriptions):
                if isinstance(desc, str) and desc:
                    image_descriptions.append(f"\n[IMAGE {i+1}]: {desc}\n")
                    print(f"DEBUG: Added description for image {i+1}")
                elif isinstance(desc, Exception):
                    print(f"DEBUG: Image {i+1} failed with exception: {desc}")
        else:
            print(f"DEBUG: No images to process, skipping image analysis")

    # Combine text and image descriptions
    print(f"DEBUG: Combining content...")
    if progress_callback:
        await progress_callback("Combining content and creating embeddings...")

    all_content = f"Website: {url}\nTitle: {title}\n\n{text_content}"

    if image_descriptions:
        all_content += "\n\n=== VISUAL CONTENT FROM WEBSITE ===\n"
        all_content += "\n".join(image_descriptions)

    print(f"DEBUG: Final content length: {len(all_content)} chars")

    # Chunk and index
    if not all_content.strip():
        print(f"DEBUG: No content to index, returning early")
        return title, 0

    print(f"DEBUG: Chunking text...")
    chunks = _chunk_text(all_content)
    print(f"DEBUG: Created {len(chunks)} chunks")

    if progress_callback:
        await progress_callback(f"Indexing {len(chunks)} chunks to vector database...")

    # Run the blocking upsert operation in a thread pool to avoid blocking the event loop
    num_chunks = await asyncio.to_thread(
        upsert_website_chunks, tenant_code, user_code, url, chunks
    )

    if progress_callback:
        await progress_callback(f"Completed! Indexed {num_chunks} chunks.")

    print(f"DEBUG: Indexed {num_chunks} chunks for website {url}")
    return title, num_chunks
