"""
DetectorAI v5
Sistema híbrido: heurística + ML opcional

Principais melhorias:
- FFT radial spectrum
- análise de bordas
- artefatos de difusão
- detecção de upscaling
- textura estatística
- regra anti-falso-positivo (câmera)
- suporte a modelo ML (XGBoost / sklearn)
"""

import streamlit as st
import numpy as np
import cv2
from PIL import Image, ExifTags
import io
import math
import joblib
from dataclasses import dataclass
from typing import Dict, Any

# ============================
# CONFIG
# ============================

MODEL_PATH = "detector_model.joblib"   # opcional

st.set_page_config(
    page_title="DetectorAI v5",
    page_icon="🧠",
    layout="wide"
)

# ============================
# UTILIDADES
# ============================

def pil_to_cv(img):
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def extract_exif(img):

    result = {
        "has_exif": False,
        "camera": False
    }

    try:
        exif = img.getexif()

        if exif:

            result["has_exif"] = True

            for tag_id, val in exif.items():

                tag = ExifTags.TAGS.get(tag_id, tag_id)

                if tag in ["Make","Model"]:
                    result["camera"] = True

    except:
        pass

    return result


# ============================
# RUÍDO
# ============================

def analyze_noise(gray):

    blur = cv2.GaussianBlur(gray,(3,3),0)

    noise = gray.astype(float) - blur.astype(float)

    std = np.std(noise)

    score = np.clip(std/25,0,1)

    return std, score


# ============================
# FFT
# ============================

def analyze_fft(gray):

    f = np.fft.fft2(gray)

    fshift = np.fft.fftshift(f)

    magnitude = np.log(np.abs(fshift)+1)

    center = magnitude[
        magnitude.shape[0]//4:3*magnitude.shape[0]//4,
        magnitude.shape[1]//4:3*magnitude.shape[1]//4
    ]

    diff = magnitude.mean() - center.mean()

    score = np.clip(abs(diff)/5,0,1)

    return diff, score


# ============================
# TEXTURA
# ============================

def analyze_texture(gray):

    hist = cv2.calcHist([gray],[0],None,[256],[0,256])

    hist = hist / hist.sum()

    entropy = -np.sum(hist*np.log2(hist+1e-9))

    score = np.clip(entropy/8,0,1)

    return entropy, score


# ============================
# UPSCALING
# ============================

def detect_upscaling(gray):

    lap = cv2.Laplacian(gray,cv2.CV_64F)

    var = lap.var()

    score = 1 - np.clip(var/500,0,1)

    return var, score


# ============================
# DIFUSÃO
# ============================

def diffusion_artifacts(gray):

    blur = cv2.GaussianBlur(gray,(9,9),0)

    diff = gray.astype(float) - blur.astype(float)

    energy = np.mean(diff**2)

    score = np.clip(energy*5,0,1)

    return energy, score


# ============================
# ELA
# ============================

def ela(img):

    buffer = io.BytesIO()

    img.save(buffer,format="JPEG",quality=90)

    buffer.seek(0)

    recompressed = Image.open(buffer)

    diff = np.abs(
        np.array(img,dtype=int) -
        np.array(recompressed,dtype=int)
    )

    ela_val = diff.mean()

    score = np.clip(ela_val/20,0,1)

    return ela_val, score


# ============================
# BORDAS
# ============================

def edge_density(gray):

    edges = cv2.Canny(gray,80,200)

    density = edges.mean()

    score = np.clip(density/50,0,1)

    return density, score


# ============================
# LOGISTIC
# ============================

def logistic(x):

    return 1/(1+math.exp(-8*(x-0.5)))


# ============================
# RESULT
# ============================

@dataclass
class Result:

    label:str
    prob_ai:float
    features:Dict[str,Any]


# ============================
# CARREGAR MODELO
# ============================

def load_model():

    try:
        model = joblib.load(MODEL_PATH)
        return model
    except:
        return None


# ============================
# DETECTOR
# ============================

def analyze(img):

    exif = extract_exif(img)

    bgr = pil_to_cv(img)

    gray = cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)

    noise_std, noise_score = analyze_noise(gray)

    fft_diff, fft_score = analyze_fft(gray)

    entropy, texture_score = analyze_texture(gray)

    sharp, upscale_score = detect_upscaling(gray)

    energy, diff_score = diffusion_artifacts(gray)

    ela_val, ela_score = ela(img)

    edge_val, edge_score = edge_density(gray)

    features = np.array([
        noise_score,
        fft_score,
        texture_score,
        upscale_score,
        diff_score,
        ela_score,
        edge_score
    ])

    # ======================
    # ML MODEL
    # ======================

    model = load_model()

    if model:

        prob_ai = model.predict_proba([features])[0][1]

    else:

        weights = np.array([
            1.3,  # noise
            2.0,  # fft
            1.2,  # texture
            1.5,  # upscale
            2.2,  # diffusion
            1.0,  # ela
            1.0   # edges
        ])

        score = (features*weights).sum()/weights.sum()

        prob_ai = logistic(score)

    # ======================
    # REDUZ FALSO POSITIVO
    # ======================

    if exif["camera"] and noise_score < 0.4:

        prob_ai *= 0.45

    label = "IA" if prob_ai > 0.5 else "REAL"

    return Result(
        label=label,
        prob_ai=float(prob_ai),
        features={
            "noise":noise_std,
            "fft":fft_diff,
            "texture_entropy":entropy,
            "sharpness":sharp,
            "diffusion_energy":energy,
            "ela":ela_val,
            "edges":edge_val,
            "exif":exif
        }
    )


# ============================
# UI
# ============================

st.title("🧠 DetectorAI v5")

uploaded = st.file_uploader(
    "Envie uma imagem",
    type=["jpg","jpeg","png","webp"]
)

if uploaded:

    img = Image.open(uploaded)

    st.image(img,use_container_width=True)

    if st.button("Analisar"):

        result = analyze(img)

        if result.label == "IA":

            st.error(
                f"🤖 Provável IA ({result.prob_ai*100:.1f}%)"
            )

        else:

            st.success(
                f"📷 Provável real ({(1-result.prob_ai)*100:.1f}%)"
            )

        st.subheader("Features")

        st.json(result.features)
