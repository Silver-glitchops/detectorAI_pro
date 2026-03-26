"""
DetectorAI v4
Detector heurístico avançado de imagens IA vs reais

Novas análises:
- frequência FFT
- textura estatística
- artefatos de difusão
- detecção de upscaling
- scoring logístico
"""

import streamlit as st
import numpy as np
import cv2
from PIL import Image, ExifTags
import io
import math
from dataclasses import dataclass
from typing import Dict, Any


st.set_page_config(
    page_title="DetectorAI v4",
    page_icon="🔬",
    layout="wide"
)

# =============================
# UTILIDADES
# =============================

def pil_to_cv(img):
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

def extract_exif(img):

    result = {"has_exif": False, "camera": False}

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


# =============================
# ANÁLISE DE RUÍDO
# =============================

def analyze_noise(gray):

    blur = cv2.GaussianBlur(gray,(3,3),0)

    noise = gray.astype(float) - blur.astype(float)

    std = np.std(noise)

    score = np.clip(std/25,0,1)

    return {
        "noise_std":float(std),
        "score":float(score)
    }


# =============================
# ELA
# =============================

def error_level_analysis(img):

    buffer = io.BytesIO()

    img.save(buffer,format="JPEG",quality=90)

    buffer.seek(0)

    recompressed = Image.open(buffer)

    diff = np.abs(np.array(img,dtype=int) - np.array(recompressed,dtype=int))

    ela = diff.mean()

    score = np.clip(ela/20,0,1)

    return {
        "ela_value":float(ela),
        "score":float(score)
    }


# =============================
# FFT FREQUENCY
# =============================

def analyze_frequency(gray):

    f = np.fft.fft2(gray)

    fshift = np.fft.fftshift(f)

    magnitude = np.log(np.abs(fshift)+1)

    center = magnitude[
        magnitude.shape[0]//4:3*magnitude.shape[0]//4,
        magnitude.shape[1]//4:3*magnitude.shape[1]//4
    ]

    diff = magnitude.mean() - center.mean()

    score = np.clip(abs(diff)/5,0,1)

    return {
        "freq_diff":float(diff),
        "score":float(score)
    }


# =============================
# TEXTURA
# =============================

def analyze_texture(gray):

    hist = cv2.calcHist([gray],[0],None,[256],[0,256])

    hist = hist / hist.sum()

    entropy = -np.sum(hist*np.log2(hist+1e-9))

    score = np.clip(entropy/8,0,1)

    return {
        "entropy":float(entropy),
        "score":float(score)
    }


# =============================
# UPSCALING
# =============================

def detect_upscaling(gray):

    lap = cv2.Laplacian(gray,cv2.CV_64F)

    var = lap.var()

    score = 1 - np.clip(var/500,0,1)

    return {
        "sharpness":float(var),
        "score":float(score)
    }


# =============================
# DIFUSÃO
# =============================

def diffusion_artifacts(gray):

    blur = cv2.GaussianBlur(gray,(9,9),0)

    diff = gray.astype(float) - blur.astype(float)

    energy = np.mean(diff**2)

    score = np.clip(energy*5,0,1)

    return {
        "energy":float(energy),
        "score":float(score)
    }


# =============================
# FUNÇÃO LOGÍSTICA
# =============================

def logistic(x):

    return 1/(1+math.exp(-8*(x-0.5)))


# =============================
# DETECTOR PRINCIPAL
# =============================

@dataclass
class Result:

    label:str
    prob_ai:float
    metrics:Dict[str,Any]


def analyze(img):

    exif = extract_exif(img)

    bgr = pil_to_cv(img)

    gray = cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)

    noise = analyze_noise(gray)

    ela = error_level_analysis(img)

    freq = analyze_frequency(gray)

    texture = analyze_texture(gray)

    upscale = detect_upscaling(gray)

    diffusion = diffusion_artifacts(gray)

    weights = {

        "noise":1.2,
        "ela":1.0,
        "freq":2.0,
        "texture":1.2,
        "upscale":1.5,
        "diffusion":2.2

    }

    score = (
        noise["score"]*weights["noise"] +
        ela["score"]*weights["ela"] +
        freq["score"]*weights["freq"] +
        texture["score"]*weights["texture"] +
        upscale["score"]*weights["upscale"] +
        diffusion["score"]*weights["diffusion"]
    )

    total_w = sum(weights.values())

    final_score = score/total_w

    prob_ai = logistic(final_score)

    # redução falso positivo

    if exif["camera"] and noise["score"] < 0.4:

        prob_ai *= 0.5

    label = "IA" if prob_ai>0.5 else "REAL"

    return Result(
        label=label,
        prob_ai=float(prob_ai),
        metrics={
            "noise":noise,
            "ela":ela,
            "frequency":freq,
            "texture":texture,
            "upscale":upscale,
            "diffusion":diffusion,
            "exif":exif
        }
    )


# =============================
# INTERFACE
# =============================

st.title("🔬 DetectorAI v4")

uploaded = st.file_uploader(
    "Envie uma imagem",
    type=["jpg","jpeg","png","webp"]
)

if uploaded:

    img = Image.open(uploaded)

    st.image(img,use_container_width=True)

    if st.button("Analisar"):

        res = analyze(img)

        if res.label=="IA":

            st.error(f"🤖 Provável IA ({res.prob_ai*100:.1f}%)")

        else:

            st.success(f"📷 Provável real ({(1-res.prob_ai)*100:.1f}%)")

        st.subheader("Métricas")

        st.json(res.metrics)
