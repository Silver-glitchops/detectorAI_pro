import streamlit as st
import numpy as np
import cv2
import math
from PIL import Image
from io import BytesIO

# ----------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------

def get_format(img):
    try:
        return img.format
    except:
        return "UNKNOWN"


def has_exif(img):
    try:
        return img._getexif() is not None
    except:
        return False


def is_screenshot(img):
    w, h = img.size
    ratio = w / h

    common = [
        16/9,
        9/16,
        19/9,
        20/9
    ]

    for r in common:
        if abs(ratio - r) < 0.02:
            return True

    return False


# ----------------------------------------------------------
# NOISE ANALYSIS (MAD robusto)
# ----------------------------------------------------------

def noise_analysis(gray):

    edges = cv2.Canny(gray, 80, 160)
    mask = edges == 0

    smooth = gray[mask]

    if len(smooth) < 100:
        return 0.2

    median = np.median(smooth)

    mad = np.median(np.abs(smooth - median))

    noise_est = mad * 1.4826

    score = np.clip(noise_est / 25, 0, 1)

    return float(score)


# ----------------------------------------------------------
# ILUMINAÇÃO
# ----------------------------------------------------------

def illumination_consistency(gray):

    small = cv2.resize(gray, (64, 64))

    blur = cv2.GaussianBlur(small, (21,21),0)

    std = np.std(blur)

    score = np.clip(std / 40, 0, 1)

    return float(score)


# ----------------------------------------------------------
# ELA (Error Level Analysis)
# ----------------------------------------------------------

def ela_analysis(pil_img):

    buffer = BytesIO()

    pil_img.save(buffer, "JPEG", quality=90)

    buffer.seek(0)

    recompressed = Image.open(buffer)

    ela = np.abs(
        np.array(pil_img).astype(int) -
        np.array(recompressed).astype(int)
    )

    ela_gray = cv2.cvtColor(
        ela.astype(np.uint8),
        cv2.COLOR_BGR2GRAY
    )

    score = np.mean(ela_gray) / 40

    return float(np.clip(score, 0, 1))


# ----------------------------------------------------------
# ARTEFATOS DE DIFFUSION
# ----------------------------------------------------------

def diffusion_artifacts(gray):

    lap = cv2.Laplacian(gray, cv2.CV_64F)

    variance = lap.var()

    if variance < 15:
        return 0.6

    return 0.1


# ----------------------------------------------------------
# METADATA
# ----------------------------------------------------------

def metadata_score(img):

    if has_exif(img):
        return 0.1

    return 0.2


# ----------------------------------------------------------
# ANALISE PRINCIPAL
# ----------------------------------------------------------

def analyze_image(pil_img):

    img = np.array(pil_img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    fmt = get_format(pil_img)

    screenshot = is_screenshot(pil_img)

    noise = noise_analysis(gray)

    illum = illumination_consistency(gray)

    ela = ela_analysis(pil_img)

    diff = diffusion_artifacts(gray)

    meta = metadata_score(pil_img)

    # PESOS

    weights = {

        "noise": 1.1,
        "illum": 0.6,
        "ela": 1.2,
        "meta": 0.5,
        "diff": 1.3
    }

    if fmt != "JPEG":
        weights["ela"] *= 0.3

    if screenshot:
        weights["ela"] *= 0.2
        weights["noise"] *= 0.5

    total_weight = sum(weights.values())

    raw_score = (

        noise * weights["noise"] +
        illum * weights["illum"] +
        ela * weights["ela"] +
        meta * weights["meta"] +
        diff * weights["diff"]

    ) / total_weight

    prob_ai = 1 / (1 + math.exp(-6*(raw_score-0.5)))

    return {

        "prob_ai": float(prob_ai),

        "scores": {

            "noise": noise,
            "illum": illum,
            "ela": ela,
            "metadata": meta,
            "diffusion": diff

        }
    }


# ----------------------------------------------------------
# CLASSIFICAÇÃO FINAL
# ----------------------------------------------------------

def classify(prob_ai, sensitivity):

    thresholds = {

        "Alta": 0.35,
        "Normal": 0.50,
        "Baixa": 0.65

    }

    threshold = thresholds[sensitivity]

    if prob_ai >= threshold:
        return "IA"

    return "REAL"


# ----------------------------------------------------------
# STREAMLIT APP
# ----------------------------------------------------------

st.set_page_config(
    page_title="DetectorAI Pro",
    layout="centered"
)

st.title("🔎 DetectorAI Pro")

st.write(
"Detector heurístico para estimar se uma imagem pode ter sido gerada por IA."
)

sensitivity = st.selectbox(

    "Sensibilidade",

    ["Alta","Normal","Baixa"]

)

uploaded = st.file_uploader(

    "Envie uma imagem",

    type=["png","jpg","jpeg","webp"]

)

if uploaded:

    img = Image.open(uploaded)

    st.image(img, use_column_width=True)

    with st.spinner("Analisando imagem..."):

        result = analyze_image(img)

        prob = result["prob_ai"]

        label = classify(prob, sensitivity)

    st.subheader("Resultado")

    st.write(f"Probabilidade de IA: **{prob*100:.1f}%**")

    if label == "IA":

        st.error("Possível imagem gerada por IA")

    else:

        st.success("Provavelmente imagem real")

    st.subheader("Detalhes da análise")

    scores = result["scores"]

    st.write("Ruído:", round(scores["noise"],3))
    st.write("Iluminação:", round(scores["illum"],3))
    st.write("ELA:", round(scores["ela"],3))
    st.write("Metadados:", round(scores["metadata"],3))
    st.write("Artefatos diffusion:", round(scores["diffusion"],3))


st.markdown("---")

st.caption(
"Detector heurístico. Resultados podem conter erros."
)
