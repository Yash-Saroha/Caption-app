import io
import textwrap

import streamlit as st
from google import genai
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------- SETTINGS (you can change these) ----------------
# If you get a "model not found" error later, open Google AI Studio,
# look at the current model names, and paste a valid one here.
MODEL_NAME = "gemini-3.8-flash"

CAPTION_STYLE = "short, formal, suitable for a college presentation"
NUMBER_OF_CAPTIONS = 5

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
]
# -----------------------------------------------------------------

st.set_page_config(page_title="Caption Maker", page_icon="🖼️")
st.title("🖼️ Caption Maker")
st.caption("Upload an image, pick a caption, put it on the image, download.")


@st.cache_resource
def get_client():
    return genai.Client(api_key=st.secrets["GEMINI_API_KEY"])


def load_font(size):
    for path in FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def get_captions(image, extra_instruction=""):
    prompt = (
        f"Look at this image and write {NUMBER_OF_CAPTIONS} different captions for it. "
        f"Style: {CAPTION_STYLE}. {extra_instruction} "
        "Return only the captions, one per line, with no numbering, "
        "no bullets, no quotation marks and no extra text."
    )
    response = get_client().models.generate_content(
        model=MODEL_NAME, contents=[image, prompt]
    )
    lines = [ln.strip(" -*0123456789.\"'") for ln in response.text.splitlines()]
    return [ln for ln in lines if ln]


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = (current + " " + word).strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def add_caption(image, text, position, size_percent, color, strip):
    img = image.convert("RGBA")
    width, height = img.size
    font_size = max(14, int(width * size_percent / 100))
    font = load_font(font_size)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    margin = int(width * 0.05)
    lines = wrap_text(draw, text, font, width - 2 * margin)
    line_height = int(font_size * 1.3)
    block_height = line_height * len(lines)
    pad = int(font_size * 0.6)

    if position == "Top":
        y = margin
    elif position == "Middle":
        y = (height - block_height) // 2
    else:
        y = height - block_height - margin

    if strip:
        draw.rectangle(
            [0, y - pad, width, y + block_height + pad], fill=(0, 0, 0, 150)
        )

    for i, line in enumerate(lines):
        line_width = draw.textlength(line, font=font)
        x = (width - line_width) / 2
        draw.text(
            (x, y + i * line_height),
            line,
            font=font,
            fill=color,
            stroke_width=max(1, font_size // 18),
            stroke_fill=(0, 0, 0, 255),
        )

    return Image.alpha_composite(img, overlay).convert("RGB")


# ---------------- STEP 1: upload ----------------
uploaded = st.file_uploader("1. Upload an image", type=["jpg", "jpeg", "png", "webp"])

if uploaded:
    image = ImageOps.exif_transpose(Image.open(uploaded)).convert("RGB")
    st.image(image, use_container_width=True)

    # New image uploaded -> forget old captions
    if st.session_state.get("last_file") != uploaded.file_id:
        st.session_state["last_file"] = uploaded.file_id
        st.session_state["captions"] = []

    # ---------------- STEP 2: captions ----------------
    st.subheader("2. Get captions")
    extra = st.text_input(
        "Anything special? (optional)",
        placeholder="e.g. mention it was a tree plantation drive",
    )
    if st.button("✨ Generate captions", use_container_width=True):
        with st.spinner("Writing captions..."):
            try:
                st.session_state["captions"] = get_captions(image, extra)
            except Exception as e:
                st.error(f"Could not get captions: {e}")

    captions = st.session_state.get("captions", [])
    if captions:
        # ---------------- STEP 3: choose / edit ----------------
        st.subheader("3. Pick and edit")
        choice = st.radio("Choose a caption", captions)
        final_text = st.text_area("Edit if you want", value=choice, height=100)

        # ---------------- STEP 4: style ----------------
        st.subheader("4. Style")
        position = st.radio("Position", ["Top", "Middle", "Bottom"], index=2, horizontal=True)
        size_percent = st.slider("Text size", 2.0, 10.0, 5.0, 0.5)
        color_name = st.selectbox("Text color", ["White", "Yellow", "Black"])
        strip = st.checkbox("Dark strip behind text", value=True)
        colors = {
            "White": (255, 255, 255, 255),
            "Yellow": (255, 221, 0, 255),
            "Black": (0, 0, 0, 255),
        }

        result = add_caption(image, final_text, position, size_percent, colors[color_name], strip)

        # ---------------- STEP 5: preview + download ----------------
        st.subheader("5. Result")
        st.image(result, use_container_width=True)

        buffer = io.BytesIO()
        result.save(buffer, format="PNG")
        st.download_button(
            "⬇️ Download image",
            data=buffer.getvalue(),
            file_name="captioned.png",
            mime="image/png",
            use_container_width=True,
        )
