import threading
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import threading
import time
import re
import requests
import os
import json
import hashlib
import zipfile
import smtplib
import socket
import subprocess
import base64
import traceback
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from urllib.parse import quote_plus
from email.message import EmailMessage
from rag_service import PersonalRAG

try:
    from google.auth.transport.requests import Request as GoogleAuthRequest
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CONTACTS_LIBS_AVAILABLE = True
except Exception:
    GOOGLE_CONTACTS_LIBS_AVAILABLE = False
# ========= VOICE / DESKTOP LIBS =========
try:
    import sounddevice
    from scipy.io.wavfile import write
    SOUNDDEVICE_AVAILABLE = True
    SOUNDDEVICE_IMPORT_ERROR = ""
except Exception as ex:
    sounddevice = None
    write = None
    SOUNDDEVICE_AVAILABLE = False
    SOUNDDEVICE_IMPORT_ERROR = str(ex)
try:
    import assemblyai
    ASSEMBLYAI_AVAILABLE = True
except Exception:
    assemblyai = None
    ASSEMBLYAI_AVAILABLE = False
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    pyttsx3 = None
    PYTTSX3_AVAILABLE = False
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False
try:
    import cv2
    CV2_AVAILABLE = True
except Exception:
    cv2 = None
    CV2_AVAILABLE = False
try:
    import pytesseract
    PYTESSERACT_AVAILABLE = True
except Exception:
    pytesseract = None
    PYTESSERACT_AVAILABLE = False
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except Exception:
    YOLO = None
    YOLO_AVAILABLE = False

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from database import SessionLocal, Base, engine
from models import Chat_history


ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "").strip()

if ASSEMBLYAI_AVAILABLE and ASSEMBLYAI_API_KEY:
    assemblyai.settings.api_key = ASSEMBLYAI_API_KEY
app = FastAPI()
calculator_open = False
templates = Jinja2Templates(directory="templates")

Base.metadata.create_all(bind=engine)
rag = PersonalRAG(knowledge_dir="knowledge", index_file="rag_index.json")

pending_whatsapp = None
pending_flipkart_cod = False
pending_amazon_cod = False
pending_marketplace_choice = None
pending_linkedin_post = None
last_contact = None
CONTACTS_FILE = "contacts.json"
GOOGLE_TOKEN_FILE = "google_token.json"
GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_CONTACTS_SCOPES = ["https://www.googleapis.com/auth/contacts"]
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
SMTP_CONFIG_FILE = "smtp_config.json"
WHATSAPP_ADD_CONTACT_XPATHS = [
    "//button[@aria-label='Add to contacts']",
    "//span[normalize-space()='Add to contacts']/ancestor::button[1]",
    "//*[contains(text(),'Add to contacts')]",
    "//*[contains(text(),'Create new contact')]",
]
WHATSAPP_FIRST_NAME_XPATHS = [
    "//input[@aria-label='First name']",
    "//input[contains(@aria-label,'First')]",
    "//input[@name='first_name']",
]
WHATSAPP_LAST_NAME_XPATHS = [
    "//input[@aria-label='Last name']",
    "//input[contains(@aria-label,'Last')]",
    "//input[@name='last_name']",
]
WHATSAPP_PHONE_XPATHS = [
    "//input[@aria-label='Phone']",
    "//input[contains(@aria-label,'phone')]",
    "//input[@type='tel']",
]
WHATSAPP_SAVE_CONTACT_XPATHS = [
    "//button[@aria-label='Save']",
    "//span[normalize-space()='Save']/ancestor::button[1]",
    "//*[contains(text(),'Save')]/ancestor::button[1]",
]
WHATSAPP_CALL_XPATHS = [
    "//header//button[@aria-label='Call']",
    "//header//button[@title='Call']",
    "//header//span[@data-icon='call']/ancestor::button[1]",
    "//header//span[contains(@data-icon,'call')]/ancestor::button[1]",
    "//button[@aria-label='Call']",
    "//button[@title='Call']",
    "//span[@data-icon='call']/ancestor::button[1]",
]
WHATSAPP_VIDEO_CALL_XPATHS = [
    "//header//button[@aria-label='Video call']",
    "//header//button[@title='Video call']",
    "//header//span[@data-icon='video-call']/ancestor::button[1]",
    "//header//span[contains(@data-icon,'video')]/ancestor::button[1]",
    "//button[@aria-label='Video call']",
    "//button[@title='Video call']",
    "//span[@data-icon='video-call']/ancestor::button[1]",
]
WHATSAPP_ATTACH_XPATHS = [
    "//button[@title='Attach']",
    "//button[@aria-label='Attach']",
    "//div[@title='Attach']",
    "//span[@data-icon='clip']/ancestor::button[1]",
]
LINKEDIN_START_POST_XPATHS = [
    "//button[contains(@aria-label, 'Start a post')]",
    "//button[contains(., 'Start a post')]",
    "//a[contains(@href, '/post/new/')]",
]
LINKEDIN_EDITOR_XPATHS = [
    "//div[@role='textbox' and @contenteditable='true']",
    "//div[contains(@class,'ql-editor') and @contenteditable='true']",
]
LINKEDIN_POST_BUTTON_XPATHS = [
    "//button[@aria-label='Post']",
    "//button[normalize-space()='Post']",
    "//button[contains(@class,'share-actions__primary-action')]",
]
LANGUAGE_MAP={
    'en':'English',
    'hi':'Hindi',
    'sp':'Spanish',
    'fr':'French',
}
LAST_USER_MESSAGE =""
LAST_AI_ANSWER =""
LANGUAGE_ALIASES = {
    "english": "en", "en":"en",
    "hindi" :"hi", "hi":"hi",
    "spanish": "sp", "sp":"sp",
    "french": "fr", "fr":"fr"
}
QUESTION_STARTERS = ("what", "who", "why", "when", "where", "how", "which", "is", "are", "do", "does", "did", "can", "could", "should", "would")

_OLLAMA_SESSION = requests.Session()
_OLLAMA_OPTIONS = {

    "keep_alive": "5m",

    "num_predict": 64,

    "num_ctx": 1024,

    "temperature": 0.2,
    "top_p": 0.9,
}
VISION_MODEL_CANDIDATES = [
    "llava:latest",
    "llava",
    "bakllava:latest",
    "moondream:latest",
]
VISION_CAPTURE_DIR = "vision_captures"
_VISION_MODELS_CACHE = None
YOLO_MODEL_NAME = "yolov8n.pt"
_YOLO_MODEL_CACHE = None
HANDHELD_PRIORITY_LABELS = {
    "cell phone", "remote", "book", "bottle", "cup", "wine glass",
    "fork", "knife", "spoon", "toothbrush", "scissors", "banana",
    "apple", "orange", "sandwich", "pizza", "mouse", "keyboard",
}

def _safe_language(code: str):
    code = (code or "").strip().lower()
    return code if code in LANGUAGE_MAP else "en"

def text_translator(text:str):
    t= (text or "").strip().lower()
    patterns = [
        r'translate(?: this|last|previous)?\s*command to ([a-z]+)',
        f'translate it to ([a-z]+)',
        f'convert this command to ([a-z]+)'
    ]
    for p in patterns:
        m = re.search(p,t)
        if m:
            target_lang_text = m.group(1).strip()
            language_code = LANGUAGE_ALIASES.get(target_lang_text, target_lang_text)
            return _safe_language(language_code)
        return None

# def text_translator(text:str):
#     t = (text of " ").strip().lower()
#     m = re.search(r"translate(?: this/last/previous)?\s*command to ([a-z]+)",t)
#     if m:
#         land






def _translate_text(text: str, language_code: str):
    lang = _safe_language(language_code)
    if not text or lang == "en":
        return text

    target_lang = LANGUAGE_MAP.get(lang, "English")
    prompt = (
        f"Translate this text to {target_lang}. "
        "Return only translated text and keep the meaning exact:\n"
        f"{text}"
    )

    try:
        res = _OLLAMA_SESSION.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False,
                "options": _OLLAMA_OPTIONS,
            },
            timeout=(5, 45),
        )
        translated = (res.json().get("response") or "").strip()
        return translated or text
    except Exception:
        return text


def speak(text: str, language_code: str = "en"):
    if not PYTTSX3_AVAILABLE:
        return

    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices")
        lang = _safe_language(language_code)

        if voices:
            selected_voice = voices[0].id
            if lang == "hi":
                for voice in voices:
                    name = (voice.name or "").lower()
                    langs = " ".join([str(v).lower() for v in (getattr(voice, "languages", []) or [])])
                    if "hindi" in name or "hi" in langs:
                        selected_voice = voice.id
                        break
            engine.setProperty("voice", selected_voice)

        engine.setProperty("rate", 200)
        engine.setProperty("volume", 1.0)
        engine.say(text)
        engine.runAndWait()
    except Exception as ex:
        print(f"Text-to-speech unavailable: {ex}")


def listen_voice():
    if not SOUNDDEVICE_AVAILABLE:
        raise RuntimeError(f"Voice input is unavailable: {SOUNDDEVICE_IMPORT_ERROR}")
    if not ASSEMBLYAI_AVAILABLE:
        raise RuntimeError("Voice transcription is unavailable: assemblyai is not installed")

    fs = 16000
    seconds = 5

    audio = sounddevice.rec(int(seconds * fs), samplerate=fs, channels=1)
    sounddevice.wait()
    write("voice.wav", fs, audio)

    transcriber = assemblyai.Transcriber()
    transcript = transcriber.transcribe("voice.wav")

    return transcript.text.lower() if transcript.text else ""



def ollama_answer(question: str):
    prompt = f"""
You are a orobot assistant and behaves like a agentic ai and take decision.

RULES:
- Answer in ONE or TWO short sentences.
- Do NOT repeat document text.
- Do NOT explain unless asked.
- If the answer is a definition, give a SIMPLE definition.
- If the answer is a fact, give ONLY the fact.
- If the documents contain the answer, use them.
- If not, answer from your own knowledge.



Question:
{question}

Short answer:
"""
    res = _OLLAMA_SESSION.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False,
            "options": _OLLAMA_OPTIONS
        },
        timeout=(5, 60)
    )
    return res.json()["response"]


def _ensure_vision_dir():
    os.makedirs(VISION_CAPTURE_DIR, exist_ok=True)


def _image_to_base64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _capture_screen_image():
    try:
        _ensure_vision_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(VISION_CAPTURE_DIR, f"screen_{stamp}.png")
        image = pyautogui.screenshot()
        image.save(path)
        return True, path
    except Exception as ex:
        return False, f"Could not capture screen: {ex}"


def _capture_camera_image():
    if not CV2_AVAILABLE:
        return False, "OpenCV is not installed. Install with: pip install opencv-python"
    try:
        _ensure_vision_dir()
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        path = os.path.join(VISION_CAPTURE_DIR, f"camera_{stamp}.png")
        cam = cv2.VideoCapture(0)
        if not cam.isOpened():
            return False, "Could not open camera device."
        frame = None
        try:
            for _ in range(6):
                ok, frame = cam.read()
                if ok:
                    time.sleep(0.08)
            if frame is None:
                return False, "Camera opened but could not read frame."
            cv2.imwrite(path, frame)
        finally:
            cam.release()
        return True, path
    except Exception as ex:
        return False, f"Could not capture camera image: {ex}"


def _query_is_object_name_request(query: str) -> bool:
    q = (query or "").strip().lower()
    triggers = [
        "what is in my hand",
        "in my hand",
        "what i have in my hand",
        "what am i holding",
        "identify object",
        "name the object",
        "which object",
    ]
    return any(t in q for t in triggers)


def _get_yolo_model():
    global _YOLO_MODEL_CACHE
    if _YOLO_MODEL_CACHE is not None:
        return _YOLO_MODEL_CACHE, None
    if not YOLO_AVAILABLE:
        return None, "Ultralytics is not installed. Install with: pip install ultralytics"
    try:
        _YOLO_MODEL_CACHE = YOLO(YOLO_MODEL_NAME)
        return _YOLO_MODEL_CACHE, None
    except Exception as ex:
        return None, f"Could not load YOLO model ({YOLO_MODEL_NAME}): {ex}"


def _detect_objects_with_yolo(image_path: str):
    model, err = _get_yolo_model()
    if not model:
        return False, err, None
    try:
        results = model(image_path, verbose=False)
    except Exception as ex:
        return False, f"YOLO inference failed: {ex}", None
    if not results:
        return False, "YOLO returned no results.", None

    result = results[0]
    boxes = getattr(result, "boxes", None)
    if boxes is None or boxes.cls is None or len(boxes) == 0:
        return False, "No objects detected in frame.", None

    names = getattr(result, "names", {}) or {}
    cls_vals = boxes.cls.tolist()
    conf_vals = boxes.conf.tolist() if boxes.conf is not None else [0.0] * len(cls_vals)
    detections = []
    for cls_id, conf in zip(cls_vals, conf_vals):
        cid = int(cls_id)
        if isinstance(names, dict):
            label = str(names.get(cid, cid))
        else:
            label = str(names[cid]) if cid < len(names) else str(cid)
        detections.append({"label": label.replace("_", " "), "conf": float(conf)})

    if not detections:
        return False, "No confident object labels found.", None

    detections.sort(key=lambda d: d["conf"], reverse=True)
    priority = [d for d in detections if d["label"].lower() in HANDHELD_PRIORITY_LABELS]
    best = (priority[0] if priority else detections[0])
    top = detections[:3]
    top_str = ", ".join([f"{d['label']} ({d['conf']:.2f})" for d in top])
    return True, f"Detected object: {best['label']} ({best['conf']:.2f}). Top detections: {top_str}", best["label"]


def _extract_vision_query(text_raw: str, default_query: str):
    text = (text_raw or "").strip()
    if not text:
        return default_query
    patterns = [
        r"^(?:analy[sz]e|describe|read|explain)\s+(?:my\s+)?(?:screen|camera)\s*(?:for|about)?\s*",
        r"^(?:what(?:'s| is)\s+on\s+my\s+screen)\s*(?:for|about)?\s*",
        r"^(?:look\s+through\s+camera)\s*(?:and)?\s*",
        r"^(?:see\s+my\s+screen)\s*(?:and)?\s*",
    ]
    query = text
    for p in patterns:
        query = re.sub(p, "", query, flags=re.IGNORECASE).strip()
    return query or default_query


def _ask_vision_model(image_path: str, query: str):
    image_b64 = _image_to_base64(image_path)
    base_prompt = (
        "You are a desktop assistant with vision. "
        "Answer directly and clearly based only on the image and user request.\n"
        f"User request: {query}"
    )
    strict_prompt = (
        "You are a precise vision assistant. "
        "Return plain English only. No symbols-only output, no markdown, no code. "
        "If content is unreadable or unclear, explicitly say that and mention what is visible.\n"
        f"User request: {query}"
    )
    object_prompt = (
        "You are an object recognition assistant. "
        "Identify the main handheld object if visible. "
        "If no hand-held object is clear, say: No clear handheld object visible. "
        "Answer in one short sentence only.\n"
        f"User request: {query}"
    )

    def _low_quality_vision_text(text: str) -> bool:
        t = (text or "").strip()
        if len(t) < 3:
            return True
        alpha_count = sum(ch.isalpha() for ch in t)
        if alpha_count < 2:
            return True
        token_count = len(re.findall(r"[A-Za-z]{2,}", t))
        if token_count < 1:
            return True
        symbol_ratio = sum(not ch.isalnum() and not ch.isspace() for ch in t) / max(len(t), 1)
        if symbol_ratio > 0.60:
            return True
        return False

    def _unusable_best_effort_vision_text(text: str) -> bool:
        t = (text or "").strip()
        if len(t) < 8:
            return True
        if len(re.findall(r"[A-Za-z]{2,}", t)) < 2:
            return True
        if sum(ch.isalnum() for ch in t) / max(len(t), 1) < 0.35:
            return True
        bad_symbol_ratio = sum(ch in "[]{}()<>|`~" for ch in t) / max(len(t), 1)
        if bad_symbol_ratio > 0.30:
            return True
        return False

    def _get_installed_ollama_models():
        global _VISION_MODELS_CACHE
        if _VISION_MODELS_CACHE is not None:
            return _VISION_MODELS_CACHE
        try:
            res = _OLLAMA_SESSION.get("http://localhost:11434/api/tags", timeout=(3, 10))
            if res.status_code != 200:
                _VISION_MODELS_CACHE = set()
                return _VISION_MODELS_CACHE
            models = res.json().get("models", []) or []
            names = set()
            for m in models:
                n = (m or {}).get("name")
                if n:
                    names.add(n.strip())
            _VISION_MODELS_CACHE = names
            return _VISION_MODELS_CACHE
        except Exception:
            _VISION_MODELS_CACHE = set()
            return _VISION_MODELS_CACHE

    installed_models = _get_installed_ollama_models()
    available_candidates = [m for m in VISION_MODEL_CANDIDATES if m in installed_models]
    if not available_candidates and installed_models:
        # Also accept bare-prefix matches (e.g., llava variants).
        for m in sorted(installed_models):
            if any(m.startswith(prefix.split(":")[0]) for prefix in VISION_MODEL_CANDIDATES):
                available_candidates.append(m)
    if not available_candidates:
        return False, "No installed vision model found. Run: ollama pull llava", None

    last_error = "Vision model did not return a usable answer."
    errors = []
    best_effort_text = ""
    best_effort_model = None
    prompt_variants = (
        (base_prompt, 0.2),
        (strict_prompt, 0.0),
        (object_prompt, 0.0),
    )

    for model in available_candidates:
        for prompt, temp in prompt_variants:
            try:
                res = _OLLAMA_SESSION.post(
                    "http://localhost:11434/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "images": [image_b64],
                        "stream": False,
                        "options": {
                            **_OLLAMA_OPTIONS,
                            "num_predict": 220,
                            "temperature": temp,
                        },
                    },
                    timeout=(8, 120),
                )
                if res.status_code != 200:
                    last_error = f"{model} returned HTTP {res.status_code}"
                    errors.append(last_error)
                    continue
                text = (res.json().get("response") or "").strip()
                if text and (not _unusable_best_effort_vision_text(text)) and len(text) > len(best_effort_text):
                    best_effort_text = text
                    best_effort_model = model
                if text and not _low_quality_vision_text(text):
                    return True, text, model
                last_error = f"{model} returned low-quality output"
                errors.append(last_error)
            except Exception as ex:
                last_error = f"{model} failed: {ex}"
                errors.append(last_error)
                continue
    if best_effort_text:
        return True, f"{best_effort_text}\n\n(best-effort vision output)", best_effort_model
    if errors:
        return False, "; ".join(errors[:3]), None
    return False, last_error, None


def _extract_text_from_image_ocr(image_path: str):
    if not PYTESSERACT_AVAILABLE:
        return False, "OCR fallback unavailable because pytesseract is not installed."
    try:
        tesseract_cmd = getattr(pytesseract.pytesseract, "tesseract_cmd", "") if pytesseract else ""
        if not tesseract_cmd or not os.path.exists(tesseract_cmd):
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for p in common_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    break
        if CV2_AVAILABLE:
            img = cv2.imread(image_path)
            if img is None:
                return False, "Could not read captured image for OCR."
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            ocr_text = pytesseract.image_to_string(binary)
        else:
            ocr_text = pytesseract.image_to_string(image_path)
        cleaned = re.sub(r"\s+", " ", (ocr_text or "")).strip()
        if not cleaned:
            return False, "OCR read no text from the screenshot."
        return True, cleaned
    except Exception as ex:
        return False, (
            f"OCR failed: {ex}. "
            "Install Tesseract OCR and ensure tesseract.exe is in PATH, "
            "or install it at C:\\Program Files\\Tesseract-OCR\\tesseract.exe."
        )


def _summarize_ocr_text_for_query(query: str, ocr_text: str):
    prompt = (
        "You are a desktop assistant. "
        "Use only the OCR text below to answer the user's request in 2-4 short lines.\n"
        f"User request: {query}\n"
        f"OCR text: {ocr_text[:4000]}"
    )
    try:
        res = _OLLAMA_SESSION.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False,
                "options": {
                    **_OLLAMA_OPTIONS,
                    "num_predict": 180,
                    "temperature": 0.1,
                },
            },
            timeout=(6, 90),
        )
        if res.status_code != 200:
            return None
        text = (res.json().get("response") or "").strip()
        return text or None
    except Exception:
        return None


def _query_prefers_ocr(query: str) -> bool:
    q = (query or "").strip().lower()
    keywords = [
        "summarize visible text",
        "visible text",
        "read text",
        "extract text",
        "text on screen",
        "ocr",
    ]
    return any(k in q for k in keywords)


def _looks_unusable_vision_answer(answer: str) -> bool:
    t = (answer or "").strip()
    if not t:
        return True
    if len(t) < 8:
        return True
    t_lower = t.lower()
    if t_lower == "(best-effort vision output)":
        return True
    if "<unk>" in t_lower:
        return True
    if "<s>" in t_lower or "</s>" in t_lower:
        return True
    if sum(ch in "<>" for ch in t) >= 4:
        return True
    cleaned = re.sub(r"<unk>|<s>|</s>", " ", t_lower)
    if len(re.findall(r"[a-z]{2,}", cleaned)) < 2:
        return True
    if sum(ch.isalnum() for ch in t) / max(len(t), 1) < 0.35:
        return True
    return False


def analyze_screen_with_vision(text_raw: str):
    query = _extract_vision_query(text_raw, "Describe what is on my screen.")
    ok, image_or_note = _capture_screen_image()
    if not ok:
        return False, image_or_note
    image_path = image_or_note

    # OCR is more reliable for "read/summarize visible text" than VLM output.
    prefer_ocr = _query_prefers_ocr(query)
    ocr_ok, ocr_text_or_note = _extract_text_from_image_ocr(image_path) if prefer_ocr else (False, "")
    if ocr_ok:
        summarized = _summarize_ocr_text_for_query(query, ocr_text_or_note)
        if summarized:
            return True, (
                f"{summarized}\n\n(source: screen, mode: OCR fallback)"
            )
        return True, (
            f"I read text from screen but could not summarize reliably. "
            f"Detected text: {ocr_text_or_note[:600]}\n\n(source: screen, mode: OCR fallback)"
        )

    ok, answer_or_error, model = _ask_vision_model(image_path, query)
    if ok and not _looks_unusable_vision_answer(answer_or_error):
        return True, f"{answer_or_error}\n\n(source: screen, model: {model})"

    if not prefer_ocr:
        ocr_ok, ocr_text_or_note = _extract_text_from_image_ocr(image_path)
        if ocr_ok:
            summarized = _summarize_ocr_text_for_query(query, ocr_text_or_note)
            if summarized:
                return True, (
                    f"{summarized}\n\n(source: screen, mode: OCR fallback)"
                )
            return True, (
                f"I read text from screen but could not summarize reliably. "
                f"Detected text: {ocr_text_or_note[:600]}\n\n(source: screen, mode: OCR fallback)"
            )

    if ok and _looks_unusable_vision_answer(answer_or_error):
        return False, (
            "Screen captured but model returned unusable tokens. "
            "OCR fallback is unavailable or could not read text. "
            f"Model output sample: {answer_or_error[:120]}"
        )
    if ok:
        return True, (
            f"{answer_or_error}\n\n(source: screen, model: {model}, note: OCR fallback unavailable)"
        )
    return False, (
        "Screen captured but vision analysis failed. "
        f"Reason: {answer_or_error}. "
        f"OCR fallback status: {ocr_text_or_note}. "
        "Install or run a vision-capable Ollama model, e.g. `ollama pull llava`."
    )


def analyze_camera_with_vision(text_raw: str):
    query = _extract_vision_query(text_raw, "Describe what the camera sees.")
    object_name_query = _query_is_object_name_request(query)
    reasons = []
    last_model = None
    for _ in range(3):
        ok, image_or_note = _capture_camera_image()
        if not ok:
            reasons.append(image_or_note)
            continue
        image_path = image_or_note
        if object_name_query:
            yolo_ok, yolo_note, _ = _detect_objects_with_yolo(image_path)
            if yolo_ok:
                return True, f"{yolo_note}\n\n(source: camera, model: {YOLO_MODEL_NAME})"
            reasons.append(yolo_note)
            if "Ultralytics is not installed" in (yolo_note or ""):
                return False, yolo_note
        ok, answer_or_error, model = _ask_vision_model(image_path, query)
        last_model = model or last_model
        if ok and not _looks_unusable_vision_answer(answer_or_error):
            return True, f"{answer_or_error}\n\n(source: camera, model: {model})"
        reasons.append(answer_or_error if answer_or_error else "unusable vision output")
        time.sleep(0.25)

    unique_reasons = []
    seen = set()
    for r in reasons:
        rr = (r or "").strip()
        if not rr:
            continue
        key = rr.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_reasons.append(rr)
    brief_reason = "; ".join(unique_reasons[:3]) or "vision model returned low-quality output."
    return False, (
        "Camera frame captured but vision analysis failed after 3 attempts. "
        f"Reason: {brief_reason}. "
        f"Last model: {last_model or 'unknown'}. "
        "Try better lighting, keep the object close and centered, and hold still for 2 seconds. "
        "For object names, install YOLO support: pip install ultralytics."
    )


def _is_screen_vision_request(text_norm: str) -> bool:
    t = (text_norm or "").strip().lower()
    patterns = [
        r"\banaly[sz]e (my )?screen\b",
        r"\bdescribe (my )?screen\b",
        r"\bread (my )?screen\b",
        r"\bwhat('?s| is) on my screen\b",
        r"\bsee my screen\b",
        r"\bscreen vision\b",
    ]
    return any(re.search(p, t) for p in patterns)


def _is_camera_vision_request(text_norm: str) -> bool:
    t = (text_norm or "").strip().lower()
    patterns = [
        r"\banaly[sz]e (my )?camera\b",
        r"\bdescribe (my )?camera\b",
        r"\blook through camera\b",
        r"\bsee through camera\b",
        r"\bcamera vision\b",
    ]
    return any(re.search(p, t) for p in patterns)


def send_whatsapp(contact: str, message: str):
    global last_contact
    last_contact = contact

    options = Options()
    options.add_argument("--start-maximized")


    profile_path = os.path.join(os.getcwd(), "whatsapp_profile")
    os.makedirs(profile_path, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_path}")

    driver = webdriver.Edge(options=options)
    driver.get("https://web.whatsapp.com")


    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "pane-side"))
    )


    phone = _normalize_phone(contact)
    if phone:
        encoded_msg = quote_plus(message)
        driver.get(f"https://web.whatsapp.com/send?phone={phone}&text={encoded_msg}")
        box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, "//footer//div[@contenteditable='true']")
            )
        )
        box.send_keys(Keys.ENTER)
    else:
        search = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@contenteditable='true'][@role='textbox']")
            )
        )

        search.send_keys(contact)
        time.sleep(2)
        search.send_keys(Keys.ENTER)

        box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, "//footer//div[@contenteditable='true']")
            )
        )

        box.send_keys(message)
        box.send_keys(Keys.ENTER)


def _build_whatsapp_driver():
    options = Options()
    options.add_argument("--start-maximized")
    profile_path = os.path.join(os.getcwd(), "whatsapp_profile")
    os.makedirs(profile_path, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_path}")
    return webdriver.Edge(options=options)


def _click_first_xpath(driver, xpaths, timeout=6):
    for xp in xpaths:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            try:
                element.click()
            except Exception:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            continue
    return False


def _type_first_xpath(driver, xpaths, value, timeout=6):
    for xp in xpaths:
        try:
            element = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.XPATH, xp))
            )
            element.clear()
            element.send_keys(value)
            return True
        except Exception:
            continue
    return False


def save_contact_and_send_hi_whatsapp(name: str, phone: str, message: str = "Hi"):
    clean_phone = _normalize_phone(phone)
    if not clean_phone:
        return False, "Invalid phone number."

    first_name = (name or "").strip().split()[0] if (name or "").strip() else "Contact"
    last_name = " ".join((name or "").strip().split()[1:])
    driver = _build_whatsapp_driver()
    save_success = False
    save_note = "Could not find WhatsApp add-contact UI elements."

    try:
        driver.get("https://web.whatsapp.com")
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "pane-side"))
        )

        driver.get(f"https://web.whatsapp.com/send?phone={clean_phone}")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='main']"))
        )

        add_clicked = _click_first_xpath(driver, WHATSAPP_ADD_CONTACT_XPATHS, timeout=8)
        if add_clicked:
            first_ok = _type_first_xpath(driver, WHATSAPP_FIRST_NAME_XPATHS, first_name, timeout=8)
            if first_ok:
                if last_name:
                    _type_first_xpath(driver, WHATSAPP_LAST_NAME_XPATHS, last_name, timeout=3)
                _type_first_xpath(driver, WHATSAPP_PHONE_XPATHS, f"+{clean_phone}", timeout=3)
                save_success = _click_first_xpath(driver, WHATSAPP_SAVE_CONTACT_XPATHS, timeout=8)
                save_note = "Saved in WhatsApp contact UI." if save_success else "Opened contact form but save button was not found."

        encoded_msg = quote_plus(message or "Hi")
        driver.get(f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}")
        box = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, "//footer//div[@contenteditable='true']")
            )
        )
        box.send_keys(Keys.ENTER)
    except Exception as ex:
        try:
            send_whatsapp(clean_phone, message or "Hi")
        except Exception:
            pass
        return False, f"WhatsApp save flow failed: {ex}"
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return save_success, save_note


def get_latest_messages(contact: str, num_messages: int = 5):
    options = Options()
    options.add_argument("--start-maximized")

    profile_path = os.path.join(os.getcwd(), "whatsapp_profile")
    os.makedirs(profile_path, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_path}")

    driver = webdriver.Edge(options=options)
    driver.get("https://web.whatsapp.com")

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "pane-side"))
    )

    # Search for the contact
    search = WebDriverWait(driver, 30).until(
        EC.presence_of_element_located(
            (By.XPATH, "//div[@contenteditable='true'][@role='textbox']")
        )
    )

    search.send_keys(contact)
    time.sleep(2)
    search.send_keys(Keys.ENTER)

    time.sleep(3)

    messages = driver.find_elements(By.XPATH, "//div[@data-pre-plain-text]")

    latest_messages = []
    for msg in messages[-num_messages:]:
        try:
            text = msg.text
            if text:
                latest_messages.append(text)
        except:
            continue

    driver.quit()
    return latest_messages



def call_whatsapp(contact: str, is_video: bool = False):
    global last_contact
    last_contact = contact

    driver = _build_whatsapp_driver()
    driver.get("https://web.whatsapp.com")

    WebDriverWait(driver, 60).until(
        EC.presence_of_element_located((By.ID, "pane-side"))
    )

    phone = _normalize_phone(contact)
    if phone:
        driver.get(f"https://web.whatsapp.com/send?phone={phone}")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='main']//header"))
        )
    else:
        search = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@id='side']//div[@contenteditable='true'][@role='textbox']")
            )
        )
        search.click()
        search.send_keys(Keys.CONTROL, "a")
        search.send_keys(Keys.DELETE)
        search.send_keys(contact)
        time.sleep(2)
        try:
            first_chat = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "(//div[@id='pane-side']//div[@role='listitem'])[1]")
                )
            )
            first_chat.click()
        except Exception:
            search.send_keys(Keys.ENTER)

    WebDriverWait(driver, 30).until(
        EC.presence_of_element_located((By.XPATH, "//div[@id='main']//header"))
    )

    target_xpaths = WHATSAPP_VIDEO_CALL_XPATHS if is_video else WHATSAPP_CALL_XPATHS
    clicked = _click_first_xpath(driver, target_xpaths, timeout=10)
    if not clicked:
        raise RuntimeError(
            "Could not find WhatsApp call button. "
            "Your account/browser may not support web calling for this chat."
        )


def _strip_quotes(s: str):
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == '"') or (s[0] == s[-1] == "'")):
        return s[1:-1].strip()
    return s


def _looks_like_question(text: str) -> bool:
    t = text.strip().lower()
    return t.endswith("?") or t.startswith(QUESTION_STARTERS)


def _normalize_phone(value: str):
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) >= 8 else None


def _extract_phone_candidate(text: str) -> Optional[str]:
    m = re.search(r"(\+?\d[\d\s()-]{7,}\d)", text or "")
    if not m:
        return None
    return _normalize_phone(m.group(1))


def _find_contact_in_saved_contacts(text_norm: str) -> Optional[str]:
    contacts = _load_contacts()
    for _, entry in contacts.items():
        saved_name = (entry or {}).get("name", "").strip()
        if not saved_name:
            continue
        if re.search(rf"\b{re.escape(saved_name.lower())}\b", text_norm):
            return saved_name
    return None


def _extract_contact_candidate(text: str) -> Optional[str]:
    text = (text or "").strip()
    text_norm = text.lower()

    quoted = re.search(r'["\']([^"\']{2,})["\']', text)
    if quoted:
        return _strip_quotes(quoted.group(1))

    saved = _find_contact_in_saved_contacts(text_norm)
    if saved:
        return saved

    patterns = [
        r"(?:call|dial|ring|phone|video\s*call|voice\s*call)\s+(?:to\s+|with\s+)?([a-zA-Z][a-zA-Z\s.'-]{1,50})",
        r"(?:to|with)\s+([a-zA-Z][a-zA-Z\s.'-]{1,50})",
        r"([a-zA-Z][a-zA-Z\s.'-]{1,50})\s+ko\b",
    ]
    stop_words = {
        "on whatsapp", "whatsapp", "now", "please", "abhi", "audio", "video",
        "voice", "call", "karo", "lagao", "milao", "karo na", "please now"
    }

    for pattern in patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = _strip_quotes(m.group(1)).strip()
        candidate_norm = candidate.lower()
        for sw in stop_words:
            candidate_norm = re.sub(rf"\b{re.escape(sw)}\b", "", candidate_norm).strip()
        candidate_norm = re.sub(r"\s{2,}", " ", candidate_norm).strip(" .,:;!?")
        if len(candidate_norm) >= 2:
            return candidate_norm.title()
    return None


def _parse_call_intent_fuzzy(text_raw: str) -> Optional["Intent"]:
    text = (text_raw or "").strip()
    text_norm = text.lower()
    if not text:
        return None

    call_keywords = [
        "call", "voice call", "audio call", "video call", "dial", "ring",
        "phone", "call karo", "phone karo", "call lagao", "lagao", "milao",
        "video karo", "whatsapp call"
    ]
    has_call_signal = any(k in text_norm for k in call_keywords)
    if not has_call_signal:
        return None

    is_video = any(k in text_norm for k in ["video call", "video", "vc"])
    phone = _extract_phone_candidate(text)
    if phone:
        return Intent("video_call_contact" if is_video else "call_contact", contact=phone, phone=phone)

    contact = _extract_contact_candidate(text)
    if contact:
        return Intent("video_call_contact" if is_video else "call_contact", contact=contact)

    return None


def _extract_linkedin_topic(text_raw: str) -> Optional[str]:
    text = (text_raw or "").strip()
    if not text:
        return None

    patterns = [
        r"^(?:write|create|generate|make)\s+(?:a\s+)?linkedin\s+(?:post|content)\s+(?:about|on)\s+(.+)$",
        r"^(?:post|publish)\s+(?:on\s+)?linkedin\s+(?:about|on)\s+(.+)$",
        r"^linkedin\s+(?:post|content)\s+(?:about|on)\s+(.+)$",
    ]
    for pattern in patterns:
        m = re.match(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        topic = _strip_quotes(m.group(1)).strip(" .")
        if topic:
            return topic
    return None


def _build_linkedin_driver():
    options = Options()
    options.add_argument("--start-maximized")
    profile_path = os.path.join(os.getcwd(), "linkedin_profile")
    os.makedirs(profile_path, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_path}")
    return webdriver.Edge(options=options)


def _generate_linkedin_post(topic: str, avoid_text: str = ""):
    clean_topic = (topic or "").strip()
    if not clean_topic:
        return "Sharing a quick update today. Learning never stops. #learning #growth"

    variation_note = (
        f"\nDo not repeat this previous draft:\n{avoid_text.strip()}\n"
        if (avoid_text or "").strip()
        else ""
    )
    prompt = f"""
You are writing a LinkedIn post.
Topic: {clean_topic}

Rules:
- Write only one post body in plain text.
- Keep it under 120 words.
- Professional but human tone.
- Include 3 to 5 relevant hashtags.
- No markdown, no labels, no explanations.
{variation_note}
"""

    try:
        res = _OLLAMA_SESSION.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False,
                "options": {
                    **_OLLAMA_OPTIONS,
                    "num_predict": 220,
                    "temperature": 0.7,
                },
            },
            timeout=(5, 60),
        )
        draft = (res.json().get("response") or "").strip()
        if draft:
            return draft
    except Exception:
        pass

    return (
        f"Quick thought on {clean_topic}: consistency beats intensity. Small daily progress builds real momentum over time. "
        "What has helped you stay consistent?\n\n#linkedin #productivity #growthmindset"
    )


def post_on_linkedin(content: str):
    draft = (content or "").strip()
    if not draft:
        return False, "LinkedIn content is empty."

    driver = _build_linkedin_driver()
    try:
        driver.get("https://www.linkedin.com/feed/")
        WebDriverWait(driver, 45).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        started = _click_first_xpath(driver, LINKEDIN_START_POST_XPATHS, timeout=8)
        if not started:
            driver.get("https://www.linkedin.com/post/new/")

        editor_ready = _type_first_xpath(driver, LINKEDIN_EDITOR_XPATHS, draft, timeout=20)
        if not editor_ready:
            return False, "Could not find LinkedIn post editor. Please login once in the opened browser."

        posted = _click_first_xpath(driver, LINKEDIN_POST_BUTTON_XPATHS, timeout=12)
        if not posted:
            return False, "Draft was filled but Post button was not found."

        time.sleep(2)
        return True, "LinkedIn post published."
    except Exception as ex:
        return False, f"LinkedIn posting failed: {ex}"
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _load_contacts():
    if not os.path.exists(CONTACTS_FILE):
        return {}
    try:
        with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_contacts(data: dict):
    with open(CONTACTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _save_contact(name: str, phone: str):
    contacts = _load_contacts()
    key = name.strip().lower()
    existing = contacts.get(key, {})
    contacts[key] = {
        "name": name.strip(),
        "phone": phone,
        "email": existing.get("email", ""),
    }
    _save_contacts(contacts)


def _get_phone(name: str):
    return _load_contacts().get(name.strip().lower(), {}).get("phone")


def _is_valid_email(value: str) -> bool:
    return bool(EMAIL_REGEX.match((value or "").strip()))


def _get_contact_entry(name: str) -> Optional[dict]:
    key = (name or "").strip().lower()
    if not key:
        return None
    contacts = _load_contacts()
    if key in contacts:
        return contacts.get(key)
    for _, entry in contacts.items():
        saved_name = (entry or {}).get("name", "").strip().lower()
        if saved_name == key:
            return entry
    return None


def _save_contact_email(name: str, email: str):
    contacts = _load_contacts()
    key = name.strip().lower()
    existing = contacts.get(key, {})
    contacts[key] = {
        "name": name.strip(),
        "phone": existing.get("phone", ""),
        "email": email.strip().lower(),
    }
    _save_contacts(contacts)


def _resolve_email_recipient(target: str) -> Optional[str]:
    candidate = _strip_quotes(target or "").strip()
    if _is_valid_email(candidate):
        return candidate.lower()
    entry = _get_contact_entry(candidate)
    if not entry:
        return None
    email_value = (entry.get("email") or "").strip().lower()
    return email_value if _is_valid_email(email_value) else None


def _extract_label_value(text: str, labels: str, stops: str) -> Optional[str]:
    m = re.search(
        rf"\b(?:{labels})\b\s*[:\-]?\s*(.+?)(?=(?:\s+\b(?:{stops})\b\s*[:\-]?)|$)",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    return _strip_quotes(m.group(1)).strip()


def _parse_save_email_command(text_raw: str):
    text = (text_raw or "").strip()
    patterns = [
        r"^(?:save|add|store)\s+(?:email|mail)\s+(?:for\s+)?(.+?)\s+([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$",
        r"^(?:save|add|store)\s+(.+?)\s+(?:email|mail)\s+(?:as|is)?\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})$",
    ]
    for pattern in patterns:
        m = re.match(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        name = _strip_quotes(m.group(1)).strip()
        email = _strip_quotes(m.group(2)).strip().lower()
        if name and _is_valid_email(email):
            return name, email
    return None


def _looks_like_email_request(text_raw: str) -> bool:
    t = (text_raw or "").lower().strip()
    if not t:
        return False
    return (
        ("email" in t or "mail" in t)
        and any(k in t for k in ("send", "compose", "write", "subject", "message", "body", "text"))
    )


def _parse_email_command(text_raw: str):
    text = (text_raw or "").strip()
    if not _looks_like_email_request(text):
        return None

    subject_labels = r"subject|sub|title|topic"
    message_labels = r"message|msg|body|text|content|saying"
    recipient_labels = r"to|for"
    all_stops = r"to|for|subject|sub|title|topic|message|msg|body|text|content|saying"

    recipient = _extract_label_value(text, recipient_labels, r"subject|sub|title|topic|message|msg|body|text|content|saying")
    subject = _extract_label_value(text, subject_labels, r"to|for|message|msg|body|text|content|saying")
    message = _extract_label_value(text, message_labels, r"$^")

    if not recipient:
        m = re.search(
            r"\b(?:send\s+)?(?:an?\s+)?(?:email|mail)\s+(?:to\s+)?(.+?)(?=\s+\b(?:subject|sub|title|topic|message|msg|body|text|content|saying)\b|$)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            recipient = _strip_quotes(m.group(1)).strip()

    if not subject:
        m = re.search(
            r"\babout\s+(.+?)(?=\s+\b(?:message|msg|body|text|content|saying)\b|$)",
            text,
            flags=re.IGNORECASE,
        )
        if m:
            subject = _strip_quotes(m.group(1)).strip()

    if not message:
        m = re.search(
            rf"\b(?:{all_stops})\b\s*[:\-]?\s*(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if m and ("message" in text.lower() or "body" in text.lower() or "text" in text.lower() or "saying" in text.lower()):
            message = _strip_quotes(m.group(1)).strip()

    if not recipient or not subject or not message:
        return None

    recipient = re.sub(r"^(?:please\s+)?(?:send\s+)?(?:an?\s+)?(?:email|mail)\s+", "", recipient, flags=re.IGNORECASE).strip()
    recipient = re.sub(r"\s{2,}", " ", recipient)
    subject = re.sub(r"\s{2,}", " ", subject).strip()
    message = message.strip()
    if not recipient or not subject or not message:
        return None
    return {"recipient": recipient, "subject": subject, "message": message}


def _send_email_smtp(to_email: str, subject: str, message: str):
    cfg = _get_smtp_config()
    host = cfg["host"]
    port = cfg["port"]
    username = cfg["username"]
    password = cfg["password"]
    from_email = cfg["from_email"]

    # Gmail app passwords are often copied with spaces in 4-char groups.
    if "gmail.com" in host.lower():
        password = password.replace(" ", "")

    if not username or not password:
        return (
            False,
            "SMTP credentials are missing. Set SMTP_USERNAME and SMTP_PASSWORD environment variables.",
        )
    if not _is_valid_email(from_email):
        return False, "SMTP_FROM or SMTP_USERNAME is not a valid sender email."
    if not _is_valid_email(to_email):
        return False, "Recipient email is not valid."

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(message)

    try:
        with smtplib.SMTP(host, port, timeout=25) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(msg)
        return True, None
    except Exception as ex:
        return False, str(ex)


def _load_dotenv_file(path: str = ".env") -> dict:
    data = {}
    if not os.path.exists(path):
        return data
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    data[key] = value
    except Exception:
        return {}
    return data


def _load_smtp_json_config() -> dict:
    if not os.path.exists(SMTP_CONFIG_FILE):
        return {}
    try:
        with open(SMTP_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_smtp_json_config(updates: dict) -> bool:
    current = _load_smtp_json_config()
    if not isinstance(current, dict):
        current = {}
    for k, v in (updates or {}).items():
        if v is None:
            continue
        current[k] = v
    try:
        with open(SMTP_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _mask_secret(value: str, left: int = 2, right: int = 2):
    raw = (value or "").strip()
    if not raw:
        return "missing"
    if len(raw) <= left + right:
        return "*" * len(raw)
    return raw[:left] + ("*" * (len(raw) - left - right)) + raw[-right:]


def _parse_set_smtp_command(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    text_norm = text.lower()
    if not (
        text_norm.startswith("set smtp")
        or text_norm.startswith("configure smtp")
        or text_norm.startswith("update smtp")
    ):
        return None

    token_pattern = re.compile(
        r"\b(smtp\s+host|host|port|username|user|email|from|password|pass|app\s+password)\b\s*[:=]?\s*",
        flags=re.IGNORECASE,
    )
    matches = list(token_pattern.finditer(text))
    if not matches:
        return {}

    parsed = {}

    def _norm_label(raw_label: str):
        label = re.sub(r"\s+", " ", (raw_label or "").strip().lower())
        if label in {"smtp host", "host"}:
            return "host"
        if label in {"port"}:
            return "port"
        if label in {"username", "user", "email"}:
            return "username"
        if label in {"from"}:
            return "from_email"
        if label in {"password", "pass", "app password"}:
            return "password"
        return label

    for i, m in enumerate(matches):
        key = _norm_label(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if (i + 1) < len(matches) else len(text)
        value = text[start:end].strip().strip(",;")
        value = _strip_quotes(value).strip()
        if not value:
            continue
        if key == "port":
            if value.isdigit():
                parsed[key] = int(value)
            continue
        parsed[key] = value

    return parsed


def _handle_set_smtp_command(text_raw: str) -> Optional[str]:
    fields = _parse_set_smtp_command(text_raw)
    if fields is None:
        return None
    if not fields:
        return (
            "Could not parse SMTP fields. Example: "
            "set smtp host smtp.gmail.com port 587 username your@gmail.com password \"app_password\" from your@gmail.com"
        )

    clean = {}
    if "host" in fields:
        clean["host"] = str(fields["host"]).strip()
    if "port" in fields:
        try:
            clean["port"] = int(fields["port"])
        except Exception:
            pass
    if "username" in fields:
        clean["username"] = str(fields["username"]).strip()
    if "password" in fields:
        clean["password"] = str(fields["password"]).strip()
    if "from_email" in fields:
        clean["from_email"] = str(fields["from_email"]).strip()

    if "username" in clean and not _is_valid_email(clean["username"]):
        return "SMTP username/email is invalid."
    if "from_email" in clean and not _is_valid_email(clean["from_email"]):
        return "SMTP from email is invalid."
    if "port" in clean and (clean["port"] <= 0 or clean["port"] > 65535):
        return "SMTP port must be between 1 and 65535."

    ok = _save_smtp_json_config(clean)
    if not ok:
        return "Could not save SMTP config file."

    cfg = _get_smtp_config()
    return (
        "SMTP config saved. "
        f"host={cfg['host']} port={cfg['port']} "
        f"username={_mask_secret(cfg['username'], 3, 0)} "
        f"password={_mask_secret(cfg['password'], 0, 0)} "
        f"from={cfg['from_email'] or 'missing'}"
    )


def _first_non_empty(*values):
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _get_smtp_config() -> dict:
    dot = _load_dotenv_file(".env")
    js = _load_smtp_json_config()

    host = _first_non_empty(
        os.getenv("SMTP_HOST"),
        dot.get("SMTP_HOST"),
        js.get("host"),
        "smtp.gmail.com",
    )
    port_raw = _first_non_empty(
        os.getenv("SMTP_PORT"),
        dot.get("SMTP_PORT"),
        js.get("port"),
        "587",
    )
    try:
        port = int(port_raw)
    except Exception:
        port = 587

    username = _first_non_empty(
        os.getenv("SMTP_USERNAME"),
        os.getenv("EMAIL_USERNAME"),
        dot.get("SMTP_USERNAME"),
        dot.get("EMAIL_USERNAME"),
        js.get("username"),
        js.get("email"),
    )
    password = _first_non_empty(
        os.getenv("SMTP_PASSWORD"),
        os.getenv("EMAIL_PASSWORD"),
        dot.get("SMTP_PASSWORD"),
        dot.get("EMAIL_PASSWORD"),
        js.get("password"),
        js.get("app_password"),
    )
    from_email = _first_non_empty(
        os.getenv("SMTP_FROM"),
        dot.get("SMTP_FROM"),
        js.get("from_email"),
        username,
    )
    return {
        "host": host,
        "port": port,
        "username": username.strip(),
        "password": password.strip(),
        "from_email": from_email.strip(),
    }

def _get_google_credentials():
    if not GOOGLE_CONTACTS_LIBS_AVAILABLE:
        return None, "Google Contacts packages are not installed."

    creds = None
    if os.path.exists(GOOGLE_TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(
                GOOGLE_TOKEN_FILE, GOOGLE_CONTACTS_SCOPES
            )
        except Exception:
            creds = None

    if creds and creds.valid:
        return creds, None

    try:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleAuthRequest())
        else:
            if not os.path.exists(GOOGLE_CREDENTIALS_FILE):
                return None, f"{GOOGLE_CREDENTIALS_FILE} not found."
            flow = InstalledAppFlow.from_client_secrets_file(
                GOOGLE_CREDENTIALS_FILE, GOOGLE_CONTACTS_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(GOOGLE_TOKEN_FILE, "w", encoding="utf-8") as token_file:

                       token_file.write(creds.to_json())
        return creds, None
    except Exception as ex:
        return None, f"Google auth failed: {ex}"


def _save_google_contact(name: str, phone: str):
    creds, auth_error = _get_google_credentials()
    if auth_error:
        return False, auth_error

    first_name = (name or "").strip().split()[0] if (name or "").strip() else "Contact"
    last_name = " ".join((name or "").strip().split()[1:])
    formatted_phone = f"+{phone}" if phone and not str(phone).startswith("+") else phone
    body = {
        "names": [{"givenName": first_name, "familyName": last_name}],
        "phoneNumbers": [{"value": formatted_phone}],
    }
    try:
        service = build("people", "v1", credentials=creds, cache_discovery=False)
        service.people().createContact(body=body).execute()
        return True, None
    except HttpError as ex:
        return False, f"Google Contacts API error: {ex}"
    except Exception as ex:
        return False, f"Google contact save failed: {ex}"


@dataclass
class Intent:
    name: str
    contact: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None


def _parse_intent(text_raw: str) -> Intent:
    text = (text_raw or "").strip()
    if not text:
        return Intent("empty")

    patterns = [
        (r"^(?:video\s+call)\s+(.+?)(?:\s+on\s+whatsapp)?$", "video_call_contact"),
        (r"^(?:call|voice\s+call)\s+(.+?)(?:\s+on\s+whatsapp)?$", "call_contact"),
        (r"^(?:save|add)\s+(.+?)\s+(\+?\d[\d\s()-]{7,})\s+(?:on\s+)?whatsapp$", "save_whatsapp_and_hi"),
        (r"^(?:save|add)\s+contact\s+(.+?)\s+(\+?\d[\d\s()-]{7,})$", "save_contact"),
        (r"^([a-zA-Z][a-zA-Z\s.'-]{1,})\s+(\+?\d[\d\s()-]{7,})$", "save_and_send_hi"),
        (r"^(?:send\s+)?hi\s+to\s+(.+?)\s+(\+?\d[\d\s()-]{7,})$", "send_hi_with_phone"),
        (r"^(?:send\s+)?hi\s+to\s+(.+)$", "send_hi"),
        (r'^send\s+"(.+)"\s+to\s+(.+)$', "send_message_quoted"),
    ]

    for pattern, kind in patterns:
        m = re.match(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue

        if kind == "save_contact":
            contact = _strip_quotes(m.group(1))
            phone = _normalize_phone(m.group(2))
            if contact and phone:
                return Intent("save_contact", contact=contact, phone=phone)
            return Intent("invalid_contact")

        if kind == "save_whatsapp_and_hi":
            contact = _strip_quotes(m.group(1))
            phone = _normalize_phone(m.group(2))
            if contact and phone:
                return Intent("save_whatsapp_and_hi", contact=contact, phone=phone, message="Hi")
            return Intent("invalid_contact")

        if kind == "send_hi_with_phone":
            contact = _strip_quotes(m.group(1))
            phone = _normalize_phone(m.group(2))
            if contact and phone:
                return Intent("send_hi", contact=contact, phone=phone, message="Hi")
            return Intent("invalid_contact")

        if kind == "save_and_send_hi":
            contact = _strip_quotes(m.group(1))
            phone = _normalize_phone(m.group(2))
            if contact and phone:
                return Intent("save_and_send_hi", contact=contact, phone=phone, message="Hi")
            return Intent("invalid_contact")

        if kind == "send_hi":
            contact = _strip_quotes(m.group(1))
            if contact:
                return Intent("send_hi", contact=contact, message="Hi")
            return Intent("invalid_contact")

        if kind == "send_message_quoted":
            message = _strip_quotes(m.group(1))
            contact = _strip_quotes(m.group(2))
            if contact and message:
                return Intent("send_message", contact=contact, message=message)
            return Intent("invalid_command")

        if kind == "call_contact":
            contact = _strip_quotes(m.group(1))
            if contact:
                return Intent("call_contact", contact=contact)
            return Intent("invalid_command")

        if kind == "video_call_contact":
            contact = _strip_quotes(m.group(1))
            if contact:
                return Intent("video_call_contact", contact=contact)
            return Intent("invalid_command")

    fuzzy_call_intent = _parse_call_intent_fuzzy(text_raw)
    if fuzzy_call_intent:
        return fuzzy_call_intent

    return Intent("unknown")


def _parse_whatsapp(text_raw: str):
    text = text_raw.strip()
    if not text:
        return None, None
    text_norm = text.lower()

    # Prevent accidental triggering from generic phrases like "go to cart ...".
    has_message_intent = any(
        k in text_norm for k in ("send", "message", "msg", "whatsapp", "text", "bhej", "bhejo")
    )
    if not has_message_intent:
        return None, None

    m = re.search(r"\bto\b\s+(.+)", text, flags=re.IGNORECASE)
    if m:
        tail = m.group(1).strip()
        if tail:
            parts = tail.split(None, 1)
            if len(parts) >= 2:
                name = _strip_quotes(parts[0])
                msg = _strip_quotes(parts[1])
                if name and msg and not _looks_like_question(text):
                    return name, msg


    m = re.search(r"^(?P<name>.+?)\s+ko\s+(?:message|msg|whatsapp|text)?\s*(?:bhej|bhejo|send)?\s*(?:do)?\s*(?:ki|:)?\s*(?P<msg>.+)$", text, flags=re.IGNORECASE)
    if m:
        name = _strip_quotes(m.group("name"))
        msg = _strip_quotes(m.group("msg"))
        if name and msg and not _looks_like_question(text):
            return name, msg

    return None, None


def _parse_calc_expression(text: str):
    calc_match = re.search(r"([0-9+\-*/(). ]+)", text)
    if not calc_match:
        return None
    expression = calc_match.group(1).replace(" ", "")
    if any(op in expression for op in ['+', '-', '*', '/']):
        return expression
    return None


def _sanitize_windows_filename(raw_name: str):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", (raw_name or ""))
    cleaned = cleaned.strip().rstrip(".")
    return cleaned[:120]


def _sanitize_windows_folder_name(raw_name: str):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1F]', "", (raw_name or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
    if not cleaned:
        return ""
    reserved_names = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    if cleaned.upper() in reserved_names:
        return ""
    return cleaned[:120]


def _extract_desktop_folder_name(text_raw: str) -> Optional[str]:
    text = (text_raw or "").strip()
    if not text:
        return None

    patterns = [
        r"^(?:create|make)\s+(?:a\s+)?(?:new\s+)?folder\s+(?:named|called)?\s*(.+?)\s+(?:on|in)\s+(?:the\s+)?desktop$",
        r"^(?:create|make)\s+(?:a\s+)?(?:new\s+)?folder\s+(?:on|in)\s+(?:the\s+)?desktop\s+(?:named|called)?\s*(.+)$",
        r"^(?:create|make)\s+(?:a\s+)?(?:new\s+)?folder\s+(?:named|called)?\s*(.+)$",
    ]
    for pattern in patterns:
        m = re.match(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        name = _strip_quotes(m.group(1))
        name = _sanitize_windows_folder_name(name)
        return name if name else ""
    return None


def _resolve_desktop_path() -> str:
    candidates = [
        os.path.join(os.path.expanduser("~"), "Desktop"),
        os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
        os.path.join(os.environ.get("OneDrive", ""), "Desktop"),
    ]
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return candidates[0]


def _create_folder_on_desktop(folder_name: str):
    safe_name = _sanitize_windows_folder_name(folder_name)
    if not safe_name:
        return False, "Folder name is invalid. Please use a valid folder name."

    desktop_dir = _resolve_desktop_path()
    if not desktop_dir:
        return False, "Could not locate Desktop path."

    target = os.path.join(desktop_dir, safe_name)
    try:
        os.makedirs(target, exist_ok=True)
        return True, f"Folder is ready on Desktop: {target}"
    except Exception as ex:
        return False, f"Could not create Desktop folder: {ex}"


def _xml_escape(text: str):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _word_target_path(filename: str) -> Optional[str]:
    safe_name = _sanitize_windows_filename(filename)
    if not safe_name:
        return None
    documents_dir = os.path.join(os.path.expanduser("~"), "Documents")
    os.makedirs(documents_dir, exist_ok=True)
    return os.path.join(documents_dir, f"{safe_name}.docx")


def _extract_word_whatsapp_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    t = text.lower()
    if not text:
        return None
    if "whatsapp" not in t:
        return None
    if not any(k in t for k in ("word", "docx", "document", "file")):
        return None
    if not any(k in t for k in ("send", "share")):
        return None
    if not any(k in t for k in ("write", "content", "text", "message", "body")):
        return None

    contact = None
    contact_patterns = [
        r"\b(?:to|for)\s+([a-zA-Z][a-zA-Z0-9\s.'-]{1,80}?)(?=\s+\b(?:on|via)\s+whatsapp\b|\s+\bwhatsapp\b|$)",
        r"\bwhatsapp\s+(?:to|for)\s+([a-zA-Z][a-zA-Z0-9\s.'-]{1,80})$",
    ]
    for pattern in contact_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            candidate = _strip_quotes(m.group(1)).strip(" .,:;!?")
            if candidate:
                contact = candidate
                break
    if not contact:
        return None

    content = None
    content_patterns = [
        r"\b(?:content|text|message|body)\s*(?:is|:)?\s*\"([^\"]+)\"",
        r"\b(?:content|text|message|body)\s*(?:is|:)?\s*'([^']+)'",
        r"\b(?:content|text|message|body)\s*(?:is|:)?\s*\[([^\]]+)\]",
        r"\b(?:content|text|message|body)\s*(?:is|:)?\s*(.+?)(?=\s+\b(?:and\s+)?(?:send|share)\b|\s+\bto\b|\s+\bon\s+whatsapp\b|\s+\bvia\s+whatsapp\b|$)",
        r"\bwrite\s+\"([^\"]+)\"",
        r"\bwrite\s+'([^']+)'",
        r"\bwrite\s+\[([^\]]+)\]",
        r"\bwrite\s+(.+?)(?=\s+\b(?:and\s+)?(?:send|share)\b|\s+\bto\b|\s+\bon\s+whatsapp\b|\s+\bvia\s+whatsapp\b|$)",
    ]
    for pattern in content_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            candidate = _strip_quotes(m.group(1)).strip()
            if candidate:
                content = candidate

                break
    if not content:
        return None

    filename = None
    filename_patterns = [
        r"\b(?:named|called|titled|filename|file\s+name|name\s+is)\s+(.+?)(?=\s+\b(?:with|content|text|message|body|write|and|send|share|to|on|via)\b|$)",
        r"\b(?:create|make|new|generate)\s+(?:a\s+)?(?:word\s+)?(?:file|document|doc)\s+(.+?)(?=\s+\b(?:with|content|text|message|body|write|and|send|share|to|on|via)\b|$)",
    ]
    for pattern in filename_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            candidate = _clean_filename_candidate(m.group(1))
            if candidate:
                filename = candidate
                break
    if not filename:
        filename = f"whatsapp-note-{int(time.time())}"

    return {"contact": contact, "content": content, "filename": filename}


def _looks_like_flipkart(text: str) -> bool:
    t = (text or "").lower()
    return bool(re.search(r"\b(flipkart|flip\s*cart|flip card)\b", t))


def _looks_like_amazon(text: str) -> bool:
    t = (text or "").lower()
    return bool(re.search(r"\b(amazon|amazaon|amzon|amajon)\b", t))


def _has_shopping_action_signal(text: str) -> bool:
    t = (text or "").lower()
    signals = [
        "buy", "purchase", "order", "shop", "search", "find", "look for", "need to buy",
        "i want to buy", "want to buy", "get me",
        "kharid", "kharidna", "kharid do", "khareed", "khareedna",
        "lena hai", "leni hai", "le do", "mangwa do", "mangwa do", "order kar", "order kr",
        "dhoondo", "dhundo", "dikhao", "dekhna", "chahiye"
    ]
    return any(s in t for s in signals)


def _clean_product_candidate(value: Optional[str]) -> Optional[str]:
    candidate = _strip_quotes(value or "").strip()
    if not candidate:
        return None
    candidate = re.sub(r"\s+", " ", candidate).strip(" .,:;!?")
    candidate = re.sub(
        r"^(?:flipkart|flip\s*cart|flip\s*card|amazon|amazaon|amzon|amajon)\s+(?:pe|par|mein|me)\s+",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()
    candidate = re.sub(r"\b(chahiye|chaiye|please|plz)\b$", "", candidate, flags=re.IGNORECASE).strip(" .,:;!?")
    if not candidate:
        return None
    if re.match(r"^(?:size|colou?r|cod|cash\s+on\s+delivery|pay\s+on\s+delivery)\b", candidate, flags=re.IGNORECASE):
        return None
    return candidate


def _extract_flipkart_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    t = text.lower()
    if not text:
        return None
    if not _looks_like_flipkart(t):
        return None
    has_action = _has_shopping_action_signal(t) or ("open" in t)
    wants_cod = ("cash on delivery" in t) or re.search(r"\bcod\b", t) is not None
    if not has_action and not wants_cod:
        return None

    size = None
    color = None

    size_match = re.search(
        r"\bsize\s*(?:is|=|:)?\s*([a-z0-9][a-z0-9.\- ]{0,20}?)(?=\s+\b(?:colou?r|cash\s+on\s+delivery|cod)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if size_match:
        size = _strip_quotes(size_match.group(1)).strip(" .,:;!?")

    color_match = re.search(
        r"\bcolou?r\s*(?:is|=|:)?\s*([a-z][a-z ]{1,20}?)(?=\s+\b(?:size|cash\s+on\s+delivery|cod)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if color_match:
        color = _strip_quotes(color_match.group(1)).strip(" .,:;!?")

    product = None
    quoted = re.search(r'["\']([^"\']{2,120})["\']', text)
    if quoted:
        product = _strip_quotes(quoted.group(1)).strip()
    else:
        action_patterns = [
            r"\b(?:search|find|look for|buy)\s+(.+?)(?=\s+\b(?:on\s+flipkart|in\s+flipkart|at\s+flipkart|size|colou?r)\b|$)",
            r"\b(?:kharid(?:na)?|khareed(?:na)?|lena|leni|le)\s+(.+?)(?=\s+\b(?:flipkart|flip\s*cart|size|colou?r)\b|$)",
            r"\b(?:dhoondo|dhundo|dikhao)\s+(.+?)(?=\s+\b(?:flipkart|flip\s*cart|size|colou?r)\b|$)",
            r"\b(.+?)\s+(?:dhoondo|dhundo|dikhao)(?=\s+\b(?:size|colou?r)\b|$)",
            r"\b(?:flipkart|flip\s*cart)\s+(?:pe|par|mein|me)\s+(.+?)(?=\s+\b(?:size|colou?r|cod|cash\s+on\s+delivery)\b|$)",
            r"\bflipkart\s+(?:for|me)\s+(.+?)(?=\s+\b(?:size|colou?r)\b|$)",
            r"\bopen\s+flipkart(?:\s+and)?\s+(?:search|find|look\s+for)\s+(.+?)(?=\s+\b(?:size|colou?r)\b|$)",
        ]
        for pat in action_patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                candidate = _clean_product_candidate(m.group(1))
                if candidate:
                    product = candidate
                    break

    if not product and ("all items" in t or "all products" in t):
        product = "all items"
    if not product and has_action:
        return None
    if not product:
        product = "all items"

    product = _clean_product_candidate(product)
    if not product:
        return None

    return {"product": product, "size": size, "color": color, "cod": bool(wants_cod)}


def _extract_amazon_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    t = text.lower()
    if not text:
        return None
    if not _looks_like_amazon(t):
        return None
    has_action = _has_shopping_action_signal(t) or ("open" in t)
    wants_cod = ("cash on delivery" in t) or re.search(r"\bcod\b", t) is not None or ("pay on delivery" in t)
    if not has_action and not wants_cod:
        return None

    size = None
    color = None
    size_match = re.search(
        r"\bsize\s*(?:is|=|:)?\s*([a-z0-9][a-z0-9.\- ]{0,20}?)(?=\s+\b(?:colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if size_match:
        size = _strip_quotes(size_match.group(1)).strip(" .,:;!?")

    color_match = re.search(
        r"\bcolou?r\s*(?:is|=|:)?\s*([a-z][a-z ]{1,20}?)(?=\s+\b(?:size|cash\s+on\s+delivery|pay\s+on\s+delivery|cod)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if color_match:
        color = _strip_quotes(color_match.group(1)).strip(" .,:;!?")

    product = None
    quoted = re.search(r'["\']([^"\']{2,120})["\']', text)
    if quoted:
        product = _strip_quotes(quoted.group(1)).strip()
    else:
        action_patterns = [
            r"\b(?:search|find|look for|buy)\s+(.+?)(?=\s+\b(?:on\s+amazon|in\s+amazon|at\s+amazon|size|colou?r)\b|$)",
            r"\b(?:kharid(?:na)?|khareed(?:na)?|lena|leni|le)\s+(.+?)(?=\s+\b(?:amazon|amazaon|amzon|amajon|size|colou?r)\b|$)",
            r"\b(?:dhoondo|dhundo|dikhao)\s+(.+?)(?=\s+\b(?:amazon|amazaon|amzon|amajon|size|colou?r)\b|$)",
            r"\b(.+?)\s+(?:dhoondo|dhundo|dikhao)(?=\s+\b(?:size|colou?r)\b|$)",
            r"\b(?:amazon|amazaon|amzon|amajon)\s+(?:pe|par|mein|me)\s+(.+?)(?=\s+\b(?:size|colou?r|cod|cash\s+on\s+delivery|pay\s+on\s+delivery)\b|$)",
            r"\bamazon\s+(?:for|me)\s+(.+?)(?=\s+\b(?:size|colou?r)\b|$)",
            r"\bopen\s+amazon(?:\s+and)?\s+(?:search|find|look\s+for)\s+(.+?)(?=\s+\b(?:size|colou?r)\b|$)",
        ]
        for pat in action_patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                candidate = _clean_product_candidate(m.group(1))
                if candidate:
                    product = candidate
                    break

    if not product and ("all items" in t or "all products" in t):
        product = "all items"
    if not product and has_action:
        return None
    if not product:
        product = "all items"

    product = _clean_product_candidate(product)
    if not product:
        return None
    return {"product": product, "size": size, "color": color, "cod": bool(wants_cod)}


def _extract_marketplace_choice_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    t = text.lower()
    if not text:
        return None
    if _looks_like_flipkart(t) or _looks_like_amazon(t):
        return None

    has_buy_signal = _has_shopping_action_signal(t)
    has_checkout_signal = any(
        k in t for k in (
            "go to cart", "cart", "checkout", "place order", "place all order",
            "place all the order", "order now", "buy now",
            "cart me", "cart mein", "checkout kar", "order place", "payment kar"
        )
    )
    if not has_buy_signal and not has_checkout_signal:
        return None

    size = None
    color = None
    wants_cod = ("cash on delivery" in t) or ("cod" in t) or ("pay on delivery" in t)

    size_match = re.search(
        r"\bsize\s*(?:is|=|:)?\s*([a-z0-9][a-z0-9.\- ]{0,20}?)(?=\s+\b(?:colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if size_match:
        size = _strip_quotes(size_match.group(1)).strip(" .,:;!?")

    color_match = re.search(
        r"\bcolou?r\s*(?:is|=|:)?\s*([a-z][a-z ]{1,20}?)(?=\s+\b(?:size|cash\s+on\s+delivery|pay\s+on\s+delivery|cod)\b|$)",
        text,
        flags=re.IGNORECASE,
    )
    if color_match:
        color = _strip_quotes(color_match.group(1)).strip(" .,:;!?")

    product = None
    quoted = re.search(r'["\']([^"\']{2,120})["\']', text)
    if quoted:
        product = _strip_quotes(quoted.group(1)).strip()
    else:
        product_patterns = [
            r"\b(?:buy|purchase|get|search|find|look for)\s+(.+?)(?=\s+\b(?:size|colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod|from|on)\b|$)",
            r"\bi\s+want\s+to\s+buy\s+(.+?)(?=\s+\b(?:size|colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod|from|on)\b|$)",
            r"\bwant\s+to\s+buy\s+(.+?)(?=\s+\b(?:size|colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod|from|on)\b|$)",
            r"\bmujhe\s+(.+?)\s+(?:chahiye|lena\s+hai|leni\s+hai)\b",
            r"\b(?:kharid(?:na)?|khareed(?:na)?|lena|leni|le)\s+(.+?)(?=\s+\b(?:size|colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod|from|on)\b|$)",
            r"\b(?:dhoondo|dhundo|dikhao)\s+(.+?)(?=\s+\b(?:size|colou?r|cash\s+on\s+delivery|pay\s+on\s+delivery|cod|from|on)\b|$)",
        ]
        for pattern in product_patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                candidate = _clean_product_candidate(m.group(1))
                if candidate:
                    product = candidate
                    break

    if product:
        product = _clean_product_candidate(product)
    if not product and has_buy_signal and not has_checkout_signal:
        return None

    action = "checkout" if has_checkout_signal and not product else "search"
    if action == "checkout" and not product:
        product = "all items"
    return {"action": action, "product": product, "size": size, "color": color, "cod": bool(wants_cod)}


def _extract_flipkart_checkout_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    t = text.lower()
    if not text:
        return None

    has_flipkart_signal = "flipkart" in t or "cart" in t
    has_checkout_signal = any(
        k in t for k in (
            "place order", "place all order", "place all the order",
            "checkout", "order now", "buy now", "go to cart", "cart"
        )
    )
    wants_cod = ("cash on delivery" in t) or ("cod" in t)
    has_other_tool_signal = any(
        k in t for k in ("whatsapp", "message", "msg", "email", "mail", "video call", "call")
    )
    if has_flipkart_signal and has_checkout_signal and not has_other_tool_signal:
        return {"cod": bool(wants_cod)}
    return None


def _extract_amazon_checkout_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    t = text.lower()
    if not text:
        return None

    has_amazon_signal = "amazon" in t or "cart" in t
    has_checkout_signal = any(
        k in t for k in (
            "place order", "place all order", "place all the order",
            "checkout", "order now", "buy now", "go to cart", "cart"
        )
    )
    wants_cod = ("cash on delivery" in t) or ("pay on delivery" in t) or ("cod" in t)
    has_other_tool_signal = any(
        k in t for k in ("whatsapp", "message", "msg", "email", "mail", "video call", "call")
    )
    if has_amazon_signal and has_checkout_signal and not has_other_tool_signal:
        return {"cod": bool(wants_cod)}
    return None


def _dismiss_flipkart_login_popup(driver):
    close_xpaths = [
        "//button[contains(@class,'_2KpZ6l') and normalize-space()='âœ•']",
        "//button[@aria-label='Close']",
        "//button[contains(@class,'_2doB4z')]",
    ]
    for xp in close_xpaths:
        try:
            btn = WebDriverWait(driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, xp))
            )
            try:
                btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn)
            time.sleep(0.8)
            return True
        except Exception:
            continue
    return False


def _apply_flipkart_cod_filter(driver) -> bool:
    _dismiss_flipkart_login_popup(driver)
    cod_xpaths = [
        "//div[normalize-space()='Cash on Delivery']",
        "//span[normalize-space()='Cash on Delivery']",
        "//label[contains(., 'Cash on Delivery')]",
        "//*[self::div or self::span or self::a][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cash on delivery')]",
        "//input[@type='checkbox']/ancestor::*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cash on delivery')][1]",
    ]

    for _ in range(2):
        for xp in cod_xpaths:
            try:
                elems = driver.find_elements(By.XPATH, xp)
                for elem in elems:
                    if not elem.is_displayed():
                        continue
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                    except Exception:
                        pass
                    try:
                        elem.click()
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", elem)
                        except Exception:
                            continue
                    time.sleep(1.5)
                    return True
            except Exception:
                continue
        _dismiss_flipkart_login_popup(driver)
        time.sleep(1.0)
    return False


def _click_first_visible_xpath(driver, xpaths, timeout=8) -> bool:
    for xp in xpaths:
        try:
            elems = WebDriverWait(driver, timeout).until(
                lambda d: d.find_elements(By.XPATH, xp)
            )
            for elem in elems:
                if not elem.is_displayed():
                    continue
                if not elem.is_enabled():
                    continue
                disabled_attr = (elem.get_attribute("disabled") or "").strip().lower()
                aria_disabled = (elem.get_attribute("aria-disabled") or "").strip().lower()
                class_name = (elem.get_attribute("class") or "").strip().lower()
                if disabled_attr in {"true", "disabled"}:
                    continue
                if aria_disabled == "true":
                    continue
                if "disabled" in class_name:
                    continue
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
                except Exception:
                    pass
                try:
                    elem.click()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", elem)
                    except Exception:
                        try:
                            elem.send_keys(Keys.ENTER)
                        except Exception:
                            continue
                time.sleep(1.0)
                return True
        except Exception:
            continue
    return False


def _click_with_retries(driver, xpaths, timeout=10, retries=3, delay=1.5) -> bool:
    for _ in range(max(1, retries)):
        if _click_first_visible_xpath(driver, xpaths, timeout=timeout):
            return True
        time.sleep(max(0.2, delay))
    return False


def _find_place_order_button(driver):
    final_place_xpaths = [
        "//button[normalize-space()='Place Order']",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'place order and pay')]",
        "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'place order')]",
        "//span[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'place order')]/ancestor::button[1]",
    ]
    for xp in final_place_xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xp)
            for elem in elems:
                if elem.is_displayed() and elem.is_enabled():
                    return elem
        except Exception:
            continue
    return None


def place_flipkart_cart_orders_cod():
    driver = _build_whatsapp_driver()
    try:
        driver.get("https://www.flipkart.com/viewcart")
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        _dismiss_flipkart_login_popup(driver)

        page_text = (driver.page_source or "").lower()
        if "your cart is empty" in page_text:
            return False, "Flipkart cart is empty."

        place_order_xpaths = [
            "//button[normalize-space()='Place Order']",
            "//span[normalize-space()='Place Order']/ancestor::button[1]",
            "//button[contains(., 'Place Order')]",
        ]
        _click_with_retries(driver, place_order_xpaths, timeout=8, retries=2)

        deliver_here_xpaths = [
            "//button[normalize-space()='Deliver Here']",
            "//span[normalize-space()='Deliver Here']/ancestor::button[1]",
        ]
        _click_with_retries(driver, deliver_here_xpaths, timeout=6, retries=2)

        continue_xpaths = [
            "//button[normalize-space()='Continue']",
            "//span[normalize-space()='Continue']/ancestor::button[1]",
            "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
            "//span[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]/ancestor::button[1]",
        ]
        _click_with_retries(driver, continue_xpaths, timeout=6, retries=2)

        cod_ok = _apply_flipkart_cod_filter(driver)
        if not cod_ok:
            cod_fallback_xpaths = [
                "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cash on delivery')]",
                "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cod')]",
            ]
            cod_ok = _click_first_visible_xpath(driver, cod_fallback_xpaths, timeout=8)
        if not cod_ok:
            return False, "Reached checkout but could not select Cash on Delivery."

        final_place_xpaths = [
            "//button[normalize-space()='Place Order']",
            "//span[normalize-space()='Place Order']/ancestor::button[1]",
            "//button[contains(., 'Place Order')]",
            "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'place order and pay')]",
        ]
        final_ok = _click_with_retries(driver, final_place_xpaths, timeout=10, retries=4, delay=2.0)
        if not final_ok:
            maybe_btn = _find_place_order_button(driver)
            if maybe_btn:
                disabled_state = (
                    f"enabled={maybe_btn.is_enabled()} "
                    f"aria-disabled={maybe_btn.get_attribute('aria-disabled')} "
                    f"disabled={maybe_btn.get_attribute('disabled')}"
                )
                return False, f"COD selected but final Place Order appears blocked ({disabled_state})."
        if not final_ok:
            return False, "COD selected. Please click final Place Order manually."

        return True, "Attempted to place Flipkart cart order using Cash on Delivery."
    except Exception as ex:
        return False, f"Flipkart COD checkout failed: {ex}"


def _apply_amazon_cod_filter(driver) -> bool:
    cod_xpaths = [
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cash on delivery')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pay on delivery')]",
        "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cod')]",
    ]
    return _click_first_visible_xpath(driver, cod_xpaths, timeout=10)


def place_amazon_cart_orders_cod():
    driver = _build_whatsapp_driver()
    try:
        driver.get("https://www.amazon.in/gp/cart/view.html")
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        page_text = (driver.page_source or "").lower()
        if "your amazon cart is empty" in page_text or "cart is empty" in page_text:
            return False, "Amazon cart is empty."

        proceed_xpaths = [
            "//input[contains(@name,'proceedToRetailCheckout')]",
            "//span[contains(., 'Proceed to Buy')]/ancestor::a[1]",
            "//input[contains(@aria-labelledby, 'sc-buy-box-ptc-button')]",
            "//a[contains(., 'Proceed to Buy')]",
        ]
        proceed_ok = _click_with_retries(driver, proceed_xpaths, timeout=10, retries=3, delay=1.5)
        if not proceed_ok:
            return False, "Could not click Amazon 'Proceed to Buy' from cart."
        time.sleep(2)

        cod_ok = _apply_amazon_cod_filter(driver)
        if not cod_ok:
            return False, "Reached Amazon checkout but could not select COD."

        place_xpaths = [
            "//input[contains(@name, 'placeYourOrder')]",
            "//input[contains(@id, 'submitOrderButtonId')]",
            "//input[contains(@value, 'Place your order')]",
            "//span[contains(., 'Place your order')]/ancestor::button[1]",
            "//button[contains(., 'Place your order')]",
        ]
        final_ok = _click_with_retries(driver, place_xpaths, timeout=10, retries=4, delay=2.0)
        if not final_ok:
            return False, "COD selected. Please click final Amazon Place your order manually."
        return True, "Attempted to place Amazon cart order using COD."
    except Exception as ex:
        return False, f"Amazon COD checkout failed: {ex}"


def open_flipkart_search(product: str, size: Optional[str] = None, color: Optional[str] = None, cod: bool = False):
    query_parts = [product.strip()]
    if size:
        query_parts.append(f"size {size.strip()}")
    if color:
        query_parts.append(color.strip())
    query = " ".join([q for q in query_parts if q]).strip()
    if not query:
        return False, "Please provide a product name for Flipkart search."

    driver = _build_whatsapp_driver()
    try:
        encoded = quote_plus(query)
        driver.get(f"https://www.flipkart.com/search?q={encoded}")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        _dismiss_flipkart_login_popup(driver)
        if cod:
            cod_ok = _apply_flipkart_cod_filter(driver)
            if cod_ok:
                return True, f"Opened Flipkart search for: {query} with Cash on Delivery filter."
            return True, f"Opened Flipkart search for: {query}. Could not confirm COD filter click."
        return True, f"Opened Flipkart search for: {query}"
    except Exception as ex:
        try:
            driver.quit()
        except Exception:
            pass
        return False, f"Could not open Flipkart search: {ex}"


def open_amazon_search(product: str, size: Optional[str] = None, color: Optional[str] = None, cod: bool = False):
    query_parts = [product.strip()]
    if size:
        query_parts.append(f"size {size.strip()}")
    if color:
        query_parts.append(color.strip())
    if cod:
        query_parts.append("cash on delivery")
    query = " ".join([q for q in query_parts if q]).strip()
    if not query:
        return False, "Please provide a product name for Amazon search."

    driver = _build_whatsapp_driver()
    try:
        encoded = quote_plus(query)
        driver.get(f"https://www.amazon.in/s?k={encoded}")
        return True, f"Opened Amazon search for: {query}"
    except Exception as ex:
        try:
            driver.quit()
        except Exception:
            pass
        return False, f"Could not open Amazon search: {ex}"


def _clean_filename_candidate(value: str) -> Optional[str]:
    candidate = _strip_quotes(value or "").strip()
    candidate = re.sub(r"\s+", " ", candidate)
    candidate = re.sub(r"\.docx?$", "", candidate, flags=re.IGNORECASE).strip()
    candidate = re.sub(
        r"\b(?:in|on)\s+(?:ms\s+word|microsoft\s+word|word)\b.*$",
        "",
        candidate,
        flags=re.IGNORECASE,
    ).strip()
    candidate = re.sub(r"\b(?:please|plz|now|right now)\b", "", candidate, flags=re.IGNORECASE).strip()
    candidate = _sanitize_windows_filename(candidate)
    if not candidate:
        return None
    blocked = {"file", "document", "doc", "word", "microsoft word", "new file", "new document"}
    if candidate.lower() in blocked:
        return None
    return candidate


def _is_word_create_request(text_raw: str) -> bool:
    t = (text_raw or "").lower().strip()
    if not t:
        return False
    has_word_target = (
        ("microsoft" in t and "word" in t)
        or "ms word" in t
        or re.search(r"\bopen\s+word\b", t) is not None
    )
    has_create_signal = any(k in t for k in ("create", "make", "new", "generate"))
    has_file_signal = any(k in t for k in ("file", "document", "doc", "notes", "report", "resume", "letter"))
    return has_word_target and has_create_signal and has_file_signal


def _extract_word_filename(text_raw: str) -> Optional[str]:
    text = (text_raw or "").strip()

    # Most reliable: explicit filename markers.
    marker_patterns = [
        r"\b(?:named|called|titled|filename|file\s+name|name\s+is|name)\s+(.+)$",
        r"\b(?:create|make|new)\s+(?:a\s+)?(?:file|document|doc)\s+as\s+(.+)$",
    ]
    for pattern in marker_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = _clean_filename_candidate(m.group(1))
        if candidate:
            return candidate

    # Next: quoted text anywhere in the command.
    quoted = re.search(r'["\']([^"\']{1,120})["\']', text)
    if quoted:
        candidate = _clean_filename_candidate(quoted.group(1))
        if candidate:
            return candidate

    # Fallback: extract tail after object phrase.
    fallback_patterns = [
        r"\b(?:create|make|new|generate)\s+(?:a\s+)?(?:microsoft\s+word\s+)?(?:file|document|doc)\s+(.+)$",
        r"\b(?:open\s+)?(?:microsoft\s+)?word(?:\s+and)?\s+(?:create|make|new|generate)\s+(?:a\s+)?(?:file|document|doc)\s+(.+)$",
    ]
    for pattern in fallback_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        tail = m.group(1).strip()
        tail = re.sub(
            r"^(?:with\s+name|with\s+title|named|called|as)\s+",
            "",
            tail,
            flags=re.IGNORECASE,
        )
        candidate = _clean_filename_candidate(tail)
        if candidate:
            return candidate

    return None


def _create_word_document(filename: str, content: str = "", open_in_word: bool = True):
    target = _word_target_path(filename)
    if not target:
        return False, "I need a valid file name, for example: create Word file named meeting-notes."
    safe_content = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = safe_content.split("\n") if safe_content else [""]
    paragraphs = []
    for line in lines:
        escaped = _xml_escape(line)
        if line.startswith(" ") or line.endswith(" "):
            paragraphs.append(f'<w:p><w:r><w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>')
        else:
            paragraphs.append(f"<w:p><w:r><w:t>{escaped}</w:t></w:r></w:p>")
    body_xml = "\n    ".join(paragraphs)

    should_write = (not os.path.exists(target)) or bool(content)
    if should_write:
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "[Content_Types].xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""",
            )
            zf.writestr(
                "_rels/.rels",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>""",
            )
            zf.writestr(
                "word/document.xml",
                """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    """
                + body_xml
                + """
  </w:body>
</w:document>""",
            )

    if open_in_word:
        try:
            os.system(f'start "" winword "{target}"')
            return True, f"Opened Microsoft Word and created file: {target}"
        except Exception as ex:
            return False, f"Could not open Word and create file: {ex}"
    return True, f"Created Word file: {target}"


def _is_website_create_request(text_raw: str) -> bool:
    t = (text_raw or "").lower().strip()
    if not t:
        return False
    has_website_signal = any(k in t for k in ("website", "web site", "webpage", "web page", "site"))
    has_create_signal = any(k in t for k in ("create", "make", "build", "generate"))
    return has_website_signal and has_create_signal


def _extract_website_name(text_raw: str) -> Optional[str]:
    text = (text_raw or "").strip()
    if not text:
        return None

    project_name_patterns = [
        r"\bproject\s*name\s*[:\-]\s*[\"']([^\"']{1,80})[\"']",
        r"\bproject\s*name\s*[:\-]\s*([a-zA-Z0-9][a-zA-Z0-9 &'\-]{1,80})",
    ]
    for pattern in project_name_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = _strip_quotes(m.group(1)).strip(" .,:;!?")
        if candidate:
            return candidate

    marker_patterns = [
        r"\b(?:create|make|build|generate)\s+(?:a\s+)?(?:new\s+)?(?:website|web\s*site|web\s*page|site)\s+(?:for|named|called)\s+(.+?)(?=\s+\bwith\b|\s+\bincluding\b|\s+\bthat\b|\s*[:\-]\s*|$)",
        r"\b(?:website|web\s*site|web\s*page|site)\s+for\s+(.+?)(?=\s+\bwith\b|\s+\bincluding\b|\s+\bthat\b|\s*[:\-]\s*|$)",
        r"\b(?:name|named|called|title|titled)\s+(.+?)(?=\s+\bwith\b|\s+\bincluding\b|\s+\bthat\b|\s*[:\-]\s*|$)",
    ]
    for pattern in marker_patterns:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        tail = _strip_quotes(m.group(1)).strip()
        tail = re.sub(
            r"\b(?:please|plz|now|website\s+goal|target\s+audience|pages?|core\s+features?|success\s+metrics)\b.*$",
            "",
            tail,
            flags=re.IGNORECASE,
        ).strip(" .,:;!?")
        if tail:
            return tail

    quoted = re.search(r'["\']([^"\']{1,100})["\']', text)
    if quoted:
        candidate = _strip_quotes(quoted.group(1)).strip(" .,:;!?")
        if candidate:
            return candidate
    return None


def _extract_website_prompt_payload(text_raw: str) -> Optional[dict]:
    text = (text_raw or "").strip()
    if not text:
        return None
    if not _is_website_create_request(text):
        return None

    base_text = text
    brief = ""

    splitters = [
        r"\bwith\s+(?:prompt|details|requirements|design|features?)\s*[:\-]?\s*(.+)$",
        r"\bthat\s+includes?\s+(.+)$",
        r"\bincluding\s+(.+)$",
        r"\bwith\s+(.+)$",
        r"[:\-]\s*(.+)$",
    ]
    for pattern in splitters:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if not m:
            continue
        candidate = _strip_quotes(m.group(1)).strip()
        if candidate and len(candidate) >= 8:
            brief = candidate
            base_text = text[:m.start()].strip()
            break

    site_name = _extract_website_name(base_text) or _extract_website_name(brief) or "My Website"
    if brief and site_name:
        brief = re.sub(rf"^\s*{re.escape(site_name)}\s*", "", brief, flags=re.IGNORECASE).strip(" ,.-")
    if not brief and site_name:
        style_name_match = re.search(r"^(.+?)\s+in\s+(.+?)\s+style$", site_name, flags=re.IGNORECASE)
        if style_name_match:
            site_name = style_name_match.group(1).strip(" .,:;-")
            style_hint = style_name_match.group(2).strip(" .,:;-")
            if style_hint:
                brief = f"style: {style_hint}"
    return {"name": site_name, "brief": brief}


def _find_free_local_port(start: int = 8000, end: int = 8100) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return 8000


def _parse_generated_website_blocks(raw_text: str):
    text = (raw_text or "").strip()
    if not text:
        return None
    m = re.search(
        r"---HTML---\s*(.*?)\s*---CSS---\s*(.*?)\s*---JS---\s*(.*)",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return None
    html = m.group(1).strip()
    css = m.group(2).strip()
    js = m.group(3).strip()
    html = re.sub(r"^```(?:html)?\s*|\s*```$", "", html, flags=re.IGNORECASE | re.DOTALL).strip()
    css = re.sub(r"^```(?:css)?\s*|\s*```$", "", css, flags=re.IGNORECASE | re.DOTALL).strip()
    js = re.sub(r"^```(?:javascript|js)?\s*|\s*```$", "", js, flags=re.IGNORECASE | re.DOTALL).strip()
    if not html or "<html" not in html.lower():
        return None
    return {"html": html, "css": css, "js": js}


def _looks_like_real_website_output(parts: dict) -> bool:
    html = (parts.get("html") or "").lower()
    css = (parts.get("css") or "").lower()
    js = (parts.get("js") or "").lower()
    if len(html) < 1400 or len(css) < 900:
        return False
    if "project name:" in html or "website goal:" in html or "target audience:" in html:
        return False
    required_html = ["<nav", "<section", "<footer"]
    if sum(1 for token in required_html if token in html) < 3:
        return False
    if "@" not in css and "media" not in css:
        return False
    if len(js) < 80:
        return False
    return True


def _choose_layout_mode(site_name: str, brief: str, archetype: str, design_spec: Optional[dict] = None) -> str:
    text = f"{site_name or ''} {brief or ''}".lower()
    spec = design_spec or {}
    requested_layout = (spec.get("layout") or "").lower()
    requested_style = (spec.get("style") or "").lower()

    if "editorial" in requested_layout or "editorial" in requested_style:
        return "editorial"
    if "bento" in requested_layout or "bento" in requested_style:
        return "bento"
    if "corporate" in requested_layout or "corporate" in requested_style:
        return "corporate"
    if any(k in text for k in ("minimal luxury", "luxury", "minimal", "editorial", "magazine")):
        return "editorial"
    if any(k in text for k in ("bento", "grid", "blocks", "cards")):
        return "bento"
    if any(k in text for k in ("corporate", "clean", "classic", "professional")):
        return "corporate"
    seed = abs(hash(f"{site_name}|{brief}|{archetype}")) % 3
    return ["editorial", "bento", "corporate"][seed]


def _extract_list_block(text: str, label_pattern: str) -> list:
    m = re.search(
        rf"{label_pattern}\s*[:\-]\s*(.+?)(?=\b(?:project\s+name|website\s+goal|target\s+audience|pages?|core\s+features?|success\s+metrics)\b|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return []
    block = m.group(1).strip()
    raw_parts = re.split(r"(?:\u2022|•|\n|;|\||\d+\.\s+|- )", block)
    items = []
    for p in raw_parts:
        cleaned = re.sub(r"\s+", " ", (p or "")).strip(" .,:;!-")
        if len(cleaned) >= 3:
            items.append(cleaned)
    return items[:8]


def _extract_single_field(text: str, label_pattern: str) -> str:
    m = re.search(
        rf"{label_pattern}\s*[:\-]\s*(.+?)(?=\b(?:project\s+name|website\s+goal|target\s+audience|pages?|core\s+features?|success\s+metrics)\b|$)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ""
    value = re.sub(r"\s+", " ", m.group(1)).strip(" .")
    return value[:260]


def _build_spec_from_brief(site_name: str, brief: str) -> dict:
    text = (brief or "").strip()
    name = _extract_website_name(text) or site_name or "My Website"
    goal = _extract_single_field(text, r"website\s+goal")
    if not goal:
        goal = "A modern website designed to present services and convert visitors."
    audience = _extract_list_block(text, r"target\s+audience")
    pages = _extract_list_block(text, r"pages?(?:\s*\([^)]*\))?")
    features = _extract_list_block(text, r"core\s+features?")

    if not pages:
        pages = ["Home", "Services", "About", "Contact"]
    cleaned_pages = []
    for p in pages:
        page = re.sub(r"^\d+\s*[.)-]?\s*", "", p).strip()
        page = page.split("-", 1)[0].split(":", 1)[0].strip()
        if page:
            cleaned_pages.append(page.title())
    pages = cleaned_pages[:7] if cleaned_pages else ["Home", "Services", "About", "Contact"]

    if not features:
        features = [
            "Responsive design across mobile and desktop",
            "Clear service presentation with call-to-action",
            "Fast and smooth user interactions",
        ]
    if not audience:
        audience = ["Local customers", "Online visitors", "Returning clients"]

    return {
        "name": name,
        "goal": goal,
        "audience": audience[:5],
        "pages": pages,
        "features": features[:6],
    }


def _page_filename_from_label(label: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")
    if not token:
        token = "page"
    home_aliases = {"home", "landing", "main", "homepage", "home-page"}
    if token in home_aliases:
        return "index.html"
    return f"{token}.html"


def _page_summary_from_label(label: str, goal: str, feature: str) -> str:
    keyword = (label or "").strip().lower()
    feature_text = (feature or "").strip()
    goal_text = (goal or "").strip()
    if "menu" in keyword:
        return "Explore our curated menu with categories, highlights, and clear pricing."
    if "about" in keyword:
        return "Learn our story, values, and the people behind the experience."
    if "reserv" in keyword or "book" in keyword:
        return "Choose your preferred date and share booking details in one quick form."
    if "contact" in keyword:
        return "Reach us through the form, location details, and business hours."
    if "gallery" in keyword:
        return "Browse visual highlights that capture the brand atmosphere."
    if feature_text:
        return feature_text
    if goal_text:
        return goal_text
    return f"Key information for {label}."


def _detect_website_archetype(site_name: str, brief: str) -> str:
    text = f"{site_name or ''} {brief or ''}".lower()
    rules = [
        ("restaurant", ("restaurant", "cafe", "food", "menu", "dining", "bakery")),
        ("portfolio", ("portfolio", "freelancer", "resume", "cv", "artist", "photographer", "developer", "designer")),
        ("saas", ("saas", "software", "app", "product", "platform", "dashboard", "startup")),
        ("ecommerce", ("shop", "store", "ecommerce", "e-commerce", "catalog", "cart")),
        ("agency", ("agency", "marketing", "studio", "consulting", "branding")),
        ("education", ("school", "college", "academy", "course", "institute", "training")),
        ("healthcare", ("clinic", "doctor", "hospital", "medical", "health", "wellness", "dental")),
    ]
    for archetype, keywords in rules:
        if any(k in text for k in keywords):
            return archetype
    return "business"


def _archetype_profile(archetype: str) -> dict:
    profiles = {
        "restaurant": {
            "nav": ["Home", "Menu", "About", "Reservations", "Contact"],
            "sections": ["Signature Dishes", "Chef Highlights", "Dining Experience", "Reservation Form"],
            "voice": "warm, sensory, hospitality-first",
            "cta": "Reserve a Table",
        },
        "portfolio": {
            "nav": ["Home", "Projects", "Services", "About", "Contact"],
            "sections": ["Featured Work", "Case Studies", "Process", "Testimonials"],
            "voice": "confident, creator-focused",
            "cta": "View Projects",
        },
        "saas": {
            "nav": ["Home", "Features", "Pricing", "Integrations", "Contact"],
            "sections": ["Product Value", "Feature Grid", "Customer Logos", "Plans"],
            "voice": "clear, technical, conversion-focused",
            "cta": "Start Free Trial",
        },
        "ecommerce": {
            "nav": ["Home", "Shop", "Collections", "Reviews", "Contact"],
            "sections": ["Best Sellers", "Collections", "Benefits", "FAQ"],
            "voice": "retail-focused and trust-building",
            "cta": "Shop Now",
        },
        "agency": {
            "nav": ["Home", "Services", "Work", "Team", "Contact"],
            "sections": ["What We Do", "Selected Work", "Approach", "Client Stories"],
            "voice": "bold, strategic, premium",
            "cta": "Book Strategy Call",
        },
        "education": {
            "nav": ["Home", "Programs", "Faculty", "Admissions", "Contact"],
            "sections": ["Programs", "Outcomes", "Campus Life", "Enrollment"],
            "voice": "trustworthy, structured, aspirational",
            "cta": "Apply Now",
        },
        "healthcare": {
            "nav": ["Home", "Services", "Doctors", "Appointments", "Contact"],
            "sections": ["Care Services", "Specialists", "Patient Reviews", "Appointment Form"],
            "voice": "calm, credible, patient-first",
            "cta": "Book Appointment",
        },
        "business": {
            "nav": ["Home", "Services", "About", "Testimonials", "Contact"],
            "sections": ["Core Services", "Why Choose Us", "Client Results", "Contact Form"],
            "voice": "professional, concise, outcome-focused",
            "cta": "Get Started",
        },
    }
    return profiles.get(archetype, profiles["business"])


def _hsl_to_hex(h: int, s: int, l: int) -> str:
    c = (1 - abs(2 * (l / 100.0) - 1)) * (s / 100.0)
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = (l / 100.0) - c / 2
    if 0 <= h < 60:
        r1, g1, b1 = c, x, 0
    elif 60 <= h < 120:
        r1, g1, b1 = x, c, 0
    elif 120 <= h < 180:
        r1, g1, b1 = 0, c, x
    elif 180 <= h < 240:
        r1, g1, b1 = 0, x, c
    elif 240 <= h < 300:
        r1, g1, b1 = x, 0, c
    else:
        r1, g1, b1 = c, 0, x
    r = int((r1 + m) * 255)
    g = int((g1 + m) * 255)
    b = int((b1 + m) * 255)
    return f"#{r:02x}{g:02x}{b:02x}"


def _archetype_visual_theme(
    archetype: str,
    site_name: str = "",
    brief: str = "",
    design_spec: Optional[dict] = None
) -> dict:
    spec = design_spec or {}
    seed_input = f"{site_name}|{brief}|{archetype}|{time.time_ns()}"
    seed_hex = hashlib.sha256(seed_input.encode("utf-8")).hexdigest()
    seed = int(seed_hex[:8], 16)

    base_hues = {
        "restaurant": 28,
        "portfolio": 214,
        "saas": 198,
        "ecommerce": 328,
        "agency": 150,
        "education": 220,
        "healthcare": 174,
        "business": 205,
    }
    base_hue = base_hues.get(archetype, 205)
    hue = (base_hue + (seed % 81) - 40) % 360
    hue2 = (hue + 26 + (seed % 29)) % 360
    sat = 62 + (seed % 16)
    sat2 = max(48, min(84, sat - 8 + (seed % 11)))
    bg_sat = 34 + (seed % 12)
    bg_light = 8 + (seed % 5)

    style = (spec.get("style") or "").lower()
    if "minimal" in style:
        sat = max(42, sat - 18)
        sat2 = max(36, sat2 - 16)
    if "luxury" in style:
        hue = (hue + 12) % 360
        sat = max(45, sat - 10)

    font_pairs = [
        ("Georgia, 'Times New Roman', serif", "'Trebuchet MS', 'Segoe UI', sans-serif"),
        ("'Avenir Next', 'Segoe UI', sans-serif", "'Segoe UI', 'Helvetica Neue', sans-serif"),
        ("'Franklin Gothic Medium', 'Arial Narrow', sans-serif", "'Segoe UI', Tahoma, sans-serif"),
        ("'Cambria', Georgia, serif", "'Calibri', 'Segoe UI', sans-serif"),
        ("'Gill Sans', 'Trebuchet MS', sans-serif", "'Verdana', 'Segoe UI', sans-serif"),
        ("'Palatino Linotype', 'Book Antiqua', serif", "'Segoe UI', Tahoma, sans-serif"),
    ]
    pair = font_pairs[seed % len(font_pairs)]
    if "minimal" in style:
        pair = ("'Avenir Next', 'Segoe UI', sans-serif", "'Segoe UI', 'Helvetica Neue', sans-serif")
    if "luxury" in style:
        pair = ("'Palatino Linotype', 'Book Antiqua', serif", "'Segoe UI', Tahoma, sans-serif")

    return {
        "bg": _hsl_to_hex(int(hue), int(bg_sat), int(bg_light)),
        "accent": _hsl_to_hex(int(hue), int(sat), 57),
        "accent_2": _hsl_to_hex(int(hue2), int(sat2), 52),
        "font_heading": pair[0],
        "font_body": pair[1],
    }


def _extract_prompt_design_spec(site_name: str, brief: str) -> dict:
    raw = (brief or "").strip()
    text = raw.lower()

    def _extract_field(patterns: list) -> str:
        for pattern in patterns:
            m = re.search(pattern, raw, flags=re.IGNORECASE)
            if m:
                value = (m.group(1) or "").strip(" .,:;")
                if value:
                    return value
        return ""

    layout = _extract_field([
        r"\blayout\s*[:\-]\s*([a-zA-Z0-9 ,/_-]+)",
        r"\buse\s+([a-zA-Z0-9 -]+)\s+layout",
    ])
    style = _extract_field([
        r"\bstyle\s*[:\-]\s*([a-zA-Z0-9 ,/_-]+)",
        r"\bin\s+([a-zA-Z0-9 ,/_-]+)\s+style",
    ])
    tone = _extract_field([
        r"\btone\s*[:\-]\s*([a-zA-Z0-9 ,/_-]+)",
        r"\bvoice\s*[:\-]\s*([a-zA-Z0-9 ,/_-]+)",
    ])
    cta = _extract_field([
        r"\b(?:cta|call\s*to\s*action|button\s*text)\s*[:\-]\s*([^\n.;]+)",
        r"\bbutton\s+text\s+([^\n.;]+)",
    ])
    sections_text = _extract_field([
        r"\bsections?\s*[:\-]\s*([^\n]+)",
        r"\binclude\s+sections?\s*[:\-]?\s*([^\n]+)",
    ])
    colors_text = _extract_field([
        r"\b(?:palette|colors?|colour|theme)\s*[:\-]\s*([^\n]+)",
        r"\b(?:palette|colors?|colour|theme)\s+([^\n]+)",
    ])
    fonts_text = _extract_field([
        r"\b(?:fonts?|font\s*style|typography)\s*[:\-]\s*([^\n]+)",
        r"\buse\s+fonts?\s+([^\n]+)",
    ])
    must_have_text = _extract_field([
        r"\b(?:must\s*have|required|include)\s*[:\-]\s*([^\n]+)",
    ])
    must_avoid_text = _extract_field([
        r"\b(?:must\s*avoid|avoid|do\s+not\s+use|no)\s*[:\-]\s*([^\n]+)",
    ])

    sections = []
    if sections_text:
        for item in re.split(r"[,|;/]", sections_text):
            cleaned = re.sub(r"\s+", " ", item).strip(" .:-")
            if cleaned:
                sections.append(cleaned)

    hex_colors = re.findall(r"#[0-9a-fA-F]{3,6}", raw)
    return {
        "raw_prompt": raw,
        "industry": site_name or "",
        "layout": layout.lower().strip(),
        "style": style.lower().strip(),
        "tone": tone.strip(),
        "cta": cta.strip(),
        "sections": sections[:8],
        "colors": colors_text.strip(),
        "fonts": fonts_text.strip(),
        "must_have": must_have_text.strip(),
        "must_avoid": must_avoid_text.strip(),
        "hex_colors": hex_colors[:4],
        "is_minimal": ("minimal" in text),
        "is_luxury": ("luxury" in text),
        "is_monochrome": ("monochrome" in text or "black and white" in text),
    }


def _apply_design_spec_to_theme(theme: dict, design_spec: dict) -> dict:
    merged = dict(theme or {})
    spec = design_spec or {}
    colors_text = (spec.get("colors") or "").lower()
    hex_colors = spec.get("hex_colors") or []

    if spec.get("is_monochrome"):
        merged["bg"] = "#0f0f10"
        merged["accent"] = "#f3f4f6"
        merged["accent_2"] = "#9ca3af"
    elif "black and gold" in colors_text or "gold and black" in colors_text:
        merged["bg"] = "#0b0b0b"
        merged["accent"] = "#d4af37"
        merged["accent_2"] = "#f5d66b"
    elif len(hex_colors) >= 2:
        merged["accent"] = hex_colors[0]
        merged["accent_2"] = hex_colors[1]
        if len(hex_colors) >= 3:
            merged["bg"] = hex_colors[2]
    elif len(hex_colors) == 1:
        merged["accent"] = hex_colors[0]

    fonts_text = spec.get("fonts") or ""
    if fonts_text:
        merged["font_heading"] = fonts_text
        merged["font_body"] = fonts_text
    return merged


def _build_prompt_driven_website(spec: dict, design_spec: Optional[dict] = None) -> dict:
    name_raw = spec.get("name") or "My Website"
    goal_raw = spec.get("goal") or ""
    pages = spec.get("pages") or ["Home", "Services", "About", "Contact"]
    features = spec.get("features") or []
    audience = spec.get("audience") or []

    page_defs = []
    seen_files = set()
    for i, label in enumerate(pages[:8]):
        filename = _page_filename_from_label(label)
        if filename in seen_files:
            filename = f"{filename.replace('.html', '')}-{i+1}.html"
        seen_files.add(filename)
        page_defs.append(
            {
                "label": label,
                "filename": filename,
                "summary": _page_summary_from_label(
                    label,
                    goal_raw,
                    features[i] if i < len(features) else "",
                ),
            }
        )

    has_index = any(p["filename"] == "index.html" for p in page_defs)
    if not has_index:
        page_defs.insert(
            0,
            {
                "label": "Home",
                "filename": "index.html",
                "summary": goal_raw or "Welcome to our business website.",
            },
        )

    spec_overrides = design_spec or {}
    archetype = _detect_website_archetype(name_raw, f"{goal_raw} {' '.join(features)}")
    theme = _apply_design_spec_to_theme(
        _archetype_visual_theme(archetype, name_raw, goal_raw, spec_overrides),
        spec_overrides
    )
    custom_tone = (spec_overrides.get("tone") or "").strip()
    custom_cta = (spec_overrides.get("cta") or "").strip()
    custom_sections = spec_overrides.get("sections") or []

    brand_name = _xml_escape(name_raw)
    goal = _xml_escape(goal_raw)
    audience_html = "".join([f"<li>{_xml_escape(a)}</li>" for a in audience[:5]])
    feature_cards = "\n          ".join(
        [
            f'<article class="card"><h3>{_xml_escape(f"Feature {i+1}")}</h3><p>{_xml_escape(item)}</p></article>'
            for i, item in enumerate(features[:6])
        ]
    ) or '<article class="card"><h3>Feature</h3><p>Responsive and conversion-focused website experience.</p></article>'

    pages_html = {}
    for page in page_defs:
        current_file = page["filename"]
        nav_html = "\n          ".join(
            [
                f'<a class="{"active" if p["filename"] == current_file else ""}" href="{p["filename"]}">{_xml_escape(p["label"])}</a>'
                for p in page_defs
            ]
        )
        page_title = f'{_xml_escape(page["label"])} | {brand_name}'
        summary = _xml_escape(page["summary"])
        is_home = current_file == "index.html"
        is_contact_like = any(
            token in (page["label"] or "").lower()
            for token in ("contact", "reservation", "booking", "book")
        )

        home_blocks = ""
        if is_home:
            home_cta = _xml_escape(custom_cta or "Get Started")
            home_blocks = f"""
    <section class="hero container">
      <div>
        <p class="eyebrow">{_xml_escape(custom_tone or "Business Website")}</p>
        <h1>{brand_name}</h1>
        <p>{goal}</p>
        <div class="hero-actions">
          <a class="btn primary" href="contact.html">{home_cta}</a>
          <a class="btn ghost" href="{page_defs[min(1, len(page_defs)-1)]['filename']}">Explore</a>
        </div>
      </div>
      <aside class="hero-box">
        <h3>Target Audience</h3>
        <ul>{audience_html or "<li>Modern digital customers</li>"}</ul>
      </aside>
    </section>

    <section class="container section">
      <h2>{_xml_escape(custom_sections[0] if len(custom_sections) > 0 else "Core Features")}</h2>
      <div class="grid cards">
          {feature_cards}
      </div>
    </section>
"""

        contact_block = ""
        if is_contact_like or is_home:
            contact_block = """
    <section class="container section">
      <h2>Contact / Reservation</h2>
      <form id="leadForm" class="lead-form">
        <input type="text" name="name" placeholder="Your Name" required>
        <input type="email" name="email" placeholder="Email Address" required>
        <textarea name="message" rows="4" placeholder="Tell us what you need"></textarea>
        <button type="submit" class="btn primary">Submit</button>
      </form>
      <p id="leadMessage"></p>
    </section>
"""

        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{page_title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <div class="container nav-wrap">
      <a class="brand" href="index.html">{brand_name}</a>
      <nav>
          {nav_html}
      </nav>
    </div>
  </header>

  <main>
    {home_blocks}
    <section class="container section">
      <h2>{_xml_escape(page["label"])}</h2>
      <p>{summary}</p>
    </section>
{contact_block}
  </main>

  <footer class="site-footer">
    <div class="container">
      <p>{brand_name} | Built from your prompt.</p>
    </div>
  </footer>
  <script src="script.js"></script>
</body>
</html>
"""
        pages_html[current_file] = html

    css = """:root{
  --bg:#081323;
  --surface:#0f1c33;
  --surface-2:#0c172b;
  --text:#e6edf7;
  --muted:#a2b9d8;
  --line:rgba(162,185,216,.28);
  --brand:#22d3ee;
  --brand-2:#0ea5e9;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  font-family:"Segoe UI",Tahoma,sans-serif;
  color:var(--text);
  background:
    radial-gradient(circle at 0% 0%, rgba(20,184,166,.35), transparent 40%),
    radial-gradient(circle at 100% 0%, rgba(14,165,233,.3), transparent 40%),
    var(--bg);
}
.container{width:min(1120px,92vw);margin:0 auto}
.site-header{
  position:sticky;top:0;z-index:20;
  border-bottom:1px solid var(--line);
  backdrop-filter:blur(10px);
  background:rgba(8,19,35,.78);
}
.nav-wrap{display:flex;justify-content:space-between;align-items:center;min-height:70px}
.brand{color:#fff;text-decoration:none;font-weight:800}
nav{display:flex;gap:16px;flex-wrap:wrap}
nav a{color:var(--muted);text-decoration:none;font-weight:600}
nav a:hover{color:#fff}
nav a.active{color:#fff;border-bottom:2px solid var(--brand)}
.hero,.section{
  margin-top:22px;padding:28px;border-radius:18px;
  border:1px solid var(--line);
  background:linear-gradient(145deg,var(--surface),var(--surface-2));
  box-shadow:0 16px 45px rgba(2,6,23,.35);
}
.hero{display:grid;grid-template-columns:1.15fr .85fr;gap:16px}
.eyebrow{text-transform:uppercase;letter-spacing:.08em;color:var(--brand);font-size:12px;font-weight:700}
h1{margin:.25rem 0 1rem;font-size:clamp(2rem,3.8vw,3.2rem);line-height:1.05}
h2{margin:0 0 .9rem}
.hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.btn{
  border:1px solid transparent;border-radius:12px;padding:10px 16px;
  color:#fff;text-decoration:none;font-weight:700;background:transparent;cursor:pointer
}
.btn.primary{background:linear-gradient(135deg,var(--brand),var(--brand-2))}
.btn.ghost{border-color:var(--line)}
.hero-box ul{margin:.5rem 0 0 1.1rem;padding:0}
.grid{display:grid;gap:14px}
.cards{grid-template-columns:repeat(3,minmax(0,1fr))}
.card{
  border:1px solid var(--line);border-radius:14px;padding:16px;
  background:rgba(6,15,29,.65)
}
.lead-form{display:grid;gap:10px}
input,textarea{
  width:100%;border:1px solid var(--line);border-radius:10px;padding:12px;
  background:rgba(2,8,19,.6);color:#fff
}
#leadMessage{min-height:22px;color:#7dd3fc}
.site-footer{margin:28px 0 18px;color:var(--muted)}
@media (max-width:980px){.hero{grid-template-columns:1fr}.cards{grid-template-columns:1fr 1fr}}
@media (max-width:640px){.cards{grid-template-columns:1fr}}
"""
    archetype = _detect_website_archetype(
        name_raw,
        f"{goal_raw} {' '.join(features)} {' '.join(pages)}"
    )
    theme = _apply_design_spec_to_theme(theme, spec_overrides)
    css = css.replace("--bg:#081323;", f"--bg:{theme['bg']};")
    css = css.replace("--brand:#22d3ee;", f"--brand:{theme['accent']};")
    css = css.replace("--brand-2:#0ea5e9;", f"--brand-2:{theme['accent_2']};")
    css = css.replace(
        'font-family:"Segoe UI",Tahoma,sans-serif;',
        f'font-family:{theme["font_body"]};'
    )
    css = css.replace(
        "h1{margin:.25rem 0 1rem;font-size:clamp(2rem,3.8vw,3.2rem);line-height:1.05}",
        f"h1{{margin:.25rem 0 1rem;font-size:clamp(2rem,3.8vw,3.2rem);line-height:1.05;font-family:{theme['font_heading']};}}"
    )
    css = css.replace(
        "h2{margin:0 0 .9rem}",
        f"h2{{margin:0 0 .9rem;font-family:{theme['font_heading']};}}"
    )
    css = css.replace("rgba(20,184,166,.35)", "var(--brand-2)")
    css = css.replace("rgba(14,165,233,.3)", "var(--brand)")
    js = """const form = document.getElementById('leadForm');
const msg = document.getElementById('leadMessage');
if (form && msg) {
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const name = (data.get('name') || 'Guest').toString().trim();
    msg.textContent = `Thanks ${name}. We will contact you shortly.`;
    form.reset();
  });
}
document.querySelectorAll('a[href^=\"#\"]').forEach((link) => {
  link.addEventListener('click', (e) => {
    const href = link.getAttribute('href');
    if (!href || href.endsWith('.html')) return;
    const target = document.querySelector(href);
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});
"""
    return {"pages": pages_html, "css": css, "js": js}


def _real_website_fallback(site_name: str, brief: str) -> dict:
    title = _xml_escape(site_name)
    summary = _xml_escape(brief or "A premium handcrafted digital experience.")
    design_spec = _extract_prompt_design_spec(site_name, brief)
    archetype = _detect_website_archetype(site_name, brief)
    profile = _archetype_profile(archetype)
    nav = profile["nav"]
    sections = profile["sections"]
    if design_spec.get("sections"):
        sections = design_spec["sections"][:4] + sections
    cta = _xml_escape(design_spec.get("cta") or profile["cta"])
    eyebrow = _xml_escape((design_spec.get("tone") or profile["voice"]).title())
    nav1 = _xml_escape(nav[0] if len(nav) > 0 else "Home")
    nav2 = _xml_escape(nav[1] if len(nav) > 1 else "Services")
    nav3 = _xml_escape(nav[2] if len(nav) > 2 else "About")
    nav4 = _xml_escape(nav[3] if len(nav) > 3 else "Testimonials")
    nav5 = _xml_escape(nav[4] if len(nav) > 4 else "Contact")
    s1 = _xml_escape(sections[0] if len(sections) > 0 else "Core Services")
    s2 = _xml_escape(sections[1] if len(sections) > 1 else "Why Choose Us")
    s3 = _xml_escape(sections[2] if len(sections) > 2 else "Client Results")
    s4 = _xml_escape(sections[3] if len(sections) > 3 else "Contact Form")
    layout_mode = _choose_layout_mode(site_name, brief, archetype, design_spec)
    theme = _apply_design_spec_to_theme(
        _archetype_visual_theme(archetype, site_name, brief, design_spec),
        design_spec
    )

    if layout_mode == "editorial":
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{summary}">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="#home">{title}</a>
    <nav><a href="#story">{nav2}</a><a href="#work">{nav3}</a><a href="#notes">{nav4}</a><a href="#contact">{nav5}</a></nav>
  </header>
  <main id="home">
    <section class="hero">
      <p class="eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p class="lead">{summary}</p>
      <a class="btn" href="#contact">{cta}</a>
    </section>
    <section id="story" class="strip"><h2>{s1}</h2><p>Built with a minimalist, premium-first direction focused on clarity and trust.</p></section>
    <section id="work" class="columns">
      <article><h3>{s2}</h3><p>Intentional visual hierarchy, controlled spacing, and high-contrast readability.</p></article>
      <article><h3>{s3}</h3><p>Concise content blocks designed for scanning and conversion.</p></article>
      <article><h3>{s4}</h3><p>Simple and clean lead capture flow with fewer distractions.</p></article>
    </section>
    <section id="contact" class="contact">
      <form id="bookingForm">
        <input type="text" name="name" placeholder="Your Name" required>
        <input type="email" name="email" placeholder="Email Address" required>
        <textarea name="notes" rows="4" placeholder="Tell us what you need"></textarea>
        <button type="submit">{cta}</button>
      </form>
      <p id="formMessage"></p>
    </section>
  </main>
  <script src="script.js"></script>
</body>
</html>
"""
        css = f""":root{{--bg:{theme["bg"]};--paper:#f6f2ea;--ink:#151515;--accent:{theme["accent"]};--line:#d7cfbf}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:{theme["font_body"]}}}
.topbar{{display:flex;justify-content:space-between;align-items:center;padding:24px 6vw;border-bottom:1px solid var(--line);position:sticky;top:0;background:rgba(246,242,234,.95)}}
.brand{{font-family:{theme["font_heading"]};font-weight:700;text-decoration:none;color:var(--ink)}}
nav{{display:flex;gap:18px}}nav a{{text-decoration:none;color:#333}}
.hero{{padding:12vw 6vw 8vw;max-width:980px}}.eyebrow{{letter-spacing:.08em;text-transform:uppercase;color:#555}}
h1{{font-family:{theme["font_heading"]};font-size:clamp(2rem,8vw,5rem);line-height:1.02;margin:.2em 0}}
.lead{{font-size:1.2rem;max-width:62ch}}.btn{{display:inline-block;margin-top:18px;padding:12px 18px;border:1px solid #1f1f1f;text-decoration:none;color:#111}}
.strip{{padding:32px 6vw;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.columns{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:42px 6vw}}.columns article{{padding:20px;border:1px solid var(--line);background:#fff}}
.contact{{padding:20px 6vw 56px}}form{{display:grid;gap:10px;max-width:700px}}input,textarea,button{{padding:12px;border:1px solid #bbb;background:#fff}}
@media(max-width:860px){{.columns{{grid-template-columns:1fr}}}}
"""
        js = """const f=document.getElementById('bookingForm');const m=document.getElementById('formMessage');if(f&&m){f.addEventListener('submit',e=>{e.preventDefault();const d=new FormData(f);m.textContent=`Thanks ${(d.get('name')||'Guest').toString().trim()}. We received your request.`;f.reset();});}"""
        return {"html": html, "css": css, "js": js}

    if layout_mode == "bento":
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{summary}">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header"><a class="brand" href="#home">{title}</a><nav><a href="#grid">{nav2}</a><a href="#proof">{nav3}</a><a href="#contact">{nav5}</a></nav></header>
  <main id="home" class="container">
    <section id="grid" class="bento">
      <article class="tile large"><p>{eyebrow}</p><h1>{title}</h1><p>{summary}</p><a href="#contact">{cta}</a></article>
      <article class="tile"><h3>{s1}</h3><p>Focused offer positioning with clear user journey.</p></article>
      <article class="tile"><h3>{s2}</h3><p>Segmented blocks for faster scanning and trust.</p></article>
      <article class="tile"><h3>{s3}</h3><p>High-intent CTAs placed at decision points.</p></article>
      <article class="tile"><h3>{s4}</h3><p>Lean contact capture without clutter.</p></article>
    </section>
    <section id="proof" class="proof"><h2>Proof</h2><ul><li>Conversion-ready layout</li><li>Mobile optimized blocks</li><li>Distinct visual rhythm</li></ul></section>
    <section id="contact" class="contact"><form id="bookingForm"><input name="name" placeholder="Name" required><input type="email" name="email" placeholder="Email" required><button type="submit">{cta}</button></form><p id="formMessage"></p></section>
  </main>
  <script src="script.js"></script>
</body>
</html>
"""
        css = f""":root{{--bg:{theme["bg"]};--surface:#0f172a;--line:rgba(148,163,184,.25);--text:#e5e7eb;--a:{theme["accent"]};--b:{theme["accent_2"]}}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 10% 10%,var(--b),transparent 35%),radial-gradient(circle at 90% 0%,var(--a),transparent 30%),var(--bg);color:var(--text);font-family:{theme["font_body"]}}}
.site-header{{display:flex;justify-content:space-between;align-items:center;padding:18px 4vw;border-bottom:1px solid var(--line)}}.brand{{font-family:{theme["font_heading"]};font-weight:700;color:#fff;text-decoration:none}}nav{{display:flex;gap:14px}}nav a{{color:#cbd5e1;text-decoration:none}}
.container{{width:min(1120px,94vw);margin:28px auto}}.bento{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}}
.tile{{background:rgba(2,6,23,.58);border:1px solid var(--line);border-radius:16px;padding:18px}}.tile.large{{grid-column:span 2;grid-row:span 2}}h1{{font-family:{theme["font_heading"]};font-size:clamp(2rem,4vw,3.2rem);margin:.2em 0}}
a{{color:#fff}}.proof,.contact{{margin-top:16px;padding:18px;border:1px solid var(--line);border-radius:16px;background:rgba(2,6,23,.45)}}
form{{display:flex;gap:10px;flex-wrap:wrap}}input,button{{padding:11px;border-radius:10px;border:1px solid var(--line);background:#0b1220;color:#fff}}
@media(max-width:920px){{.bento{{grid-template-columns:1fr 1fr}}.tile.large{{grid-column:span 2;grid-row:auto}}}}@media(max-width:640px){{.bento{{grid-template-columns:1fr}}.tile.large{{grid-column:auto}}}}
"""
        js = """const f=document.getElementById('bookingForm');const m=document.getElementById('formMessage');if(f&&m){f.addEventListener('submit',e=>{e.preventDefault();m.textContent='Request submitted. We will contact you shortly.';f.reset();});}"""
        return {"html": html, "css": css, "js": js}

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{summary}">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <div class="container nav-wrap">
      <a class="brand" href="#home">{title}</a>
      <nav>
        <a href="#home">{nav1}</a>
        <a href="#services">{nav2}</a>
        <a href="#gallery">{nav3}</a>
        <a href="#testimonials">{nav4}</a>
        <a href="#contact">{nav5}</a>
      </nav>
    </div>
  </header>

  <main id="home">
    <section class="hero container">
      <div class="hero-copy">
        <p class="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p>{summary}</p>
        <div class="hero-actions">
          <a class="btn primary" href="#contact">{cta}</a>
          <a class="btn ghost" href="#services">Explore {nav2}</a>
        </div>
      </div>
      <div class="hero-card">
        <h3>Why Customers Choose Us</h3>
        <ul>
          <li>Fast and responsive experience</li>
          <li>Clean and conversion-focused layout</li>
          <li>Mobile-first design</li>
        </ul>
      </div>
    </section>

    <section id="services" class="container section">
      <h2>{s1}</h2>
      <div class="grid cards">
        <article class="card"><h3>Signature Experience</h3><p>High-quality service with a polished customer journey.</p></article>
        <article class="card"><h3>Custom Packages</h3><p>Flexible options to match different customer needs.</p></article>
        <article class="card"><h3>Priority Support</h3><p>Quick help and follow-up for every inquiry.</p></article>
      </div>
    </section>

    <section id="gallery" class="container section">
      <h2>{s2}</h2>
      <div class="grid gallery">
        <div class="tile">Atmosphere</div>
        <div class="tile">Best Seller</div>
        <div class="tile">Customer Moments</div>
        <div class="tile">Team In Action</div>
      </div>
    </section>

    <section id="testimonials" class="container section">
      <h2>{s3}</h2>
      <div class="grid cards">
        <blockquote class="card quote">"Excellent quality and smooth booking process."<span>- Alex</span></blockquote>
        <blockquote class="card quote">"Looks premium and works great on mobile."<span>- Priya</span></blockquote>
        <blockquote class="card quote">"We saw better engagement after launch."<span>- Jordan</span></blockquote>
      </div>
    </section>

    <section id="contact" class="container section">
      <h2>{s4}</h2>
      <form id="bookingForm" class="contact-form">
        <input type="text" name="name" placeholder="Your Name" required>
        <input type="email" name="email" placeholder="Email Address" required>
        <input type="date" name="date" required>
        <textarea name="notes" rows="4" placeholder="Any special request?"></textarea>
        <button type="submit" class="btn primary">Request Reservation</button>
      </form>
      <p id="formMessage" class="form-message"></p>
    </section>
  </main>

  <footer class="site-footer">
    <div class="container footer-wrap">
      <p>{title} | Designed for real-world impact as a {archetype} website.</p>
    </div>
  </footer>

  <script src="script.js"></script>
</body>
</html>
"""
    css = f""":root {{
  --bg: {theme["bg"]};
  --surface: #10192d;
  --surface-2: #0c1528;
  --text: #e2e8f0;
  --muted: #93c5fd;
  --accent: {theme["accent"]};
  --accent-2: {theme["accent_2"]};
  --line: rgba(148, 163, 184, 0.22);
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: {theme["font_body"]};
  color: var(--text);
  background:
    radial-gradient(circle at 0% 0%, var(--accent-2) 0%, transparent 45%),
    radial-gradient(circle at 100% 0%, var(--accent) 0%, transparent 40%),
    var(--bg);
  line-height: 1.6;
}}
.container {{ width: min(1120px, 92vw); margin: 0 auto; }}
.site-header {{
  position: sticky;
  top: 0;
  z-index: 40;
  backdrop-filter: blur(8px);
  background: rgba(11, 18, 32, 0.75);
  border-bottom: 1px solid var(--line);
}}
.nav-wrap {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  min-height: 72px;
}}
.brand {{
  color: #fff;
  font-weight: 800;
  text-decoration: none;
  letter-spacing: 0.2px;
}}
nav {{ display: flex; gap: 18px; flex-wrap: wrap; }}
nav a {{ color: var(--muted); text-decoration: none; font-weight: 600; }}
nav a:hover {{ color: #fff; }}
.hero {{
  margin-top: 40px;
  display: grid;
  gap: 20px;
  grid-template-columns: 1.2fr 0.8fr;
}}
.hero-copy, .hero-card, .section {{
  border: 1px solid var(--line);
  border-radius: 18px;
  background: linear-gradient(145deg, rgba(16, 25, 45, 0.95), rgba(12, 21, 40, 0.95));
  box-shadow: 0 20px 50px rgba(2, 6, 23, 0.35);
  padding: 28px;
}}
.eyebrow {{
  color: var(--accent);
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
}}
h1 {{ margin: 0 0 12px; font-size: clamp(2rem, 4vw, 3.25rem); line-height: 1.1; }}
h2 {{ margin: 0 0 14px; font-size: clamp(1.5rem, 2.2vw, 2rem); }}
h1, h2, .brand {{ font-family: {theme["font_heading"]}; }}
.hero-actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }}
.btn {{
  border: 1px solid transparent;
  border-radius: 12px;
  padding: 10px 16px;
  text-decoration: none;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}}
.btn.primary {{ background: linear-gradient(135deg, var(--accent), var(--accent-2)); }}
.btn.ghost {{ border-color: var(--line); background: transparent; }}
.section {{ margin-top: 22px; }}
.grid {{ display: grid; gap: 14px; }}
.cards {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
.card {{
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.75);
}}
.quote span {{ display: block; margin-top: 10px; color: var(--muted); }}
.gallery {{ grid-template-columns: repeat(4, minmax(0, 1fr)); }}
.tile {{
  min-height: 120px;
  border-radius: 14px;
  border: 1px dashed var(--line);
  display: grid;
  place-items: center;
  color: #bae6fd;
  background: rgba(2, 132, 199, 0.08);
}}
.contact-form {{
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}}
.contact-form textarea,
.contact-form button {{ grid-column: 1 / -1; }}
input, textarea {{
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 12px;
  color: #fff;
  background: rgba(15, 23, 42, 0.9);
}}
.form-message {{ min-height: 20px; color: #7dd3fc; }}
.site-footer {{ margin: 30px 0 20px; color: #93c5fd; }}
@media (max-width: 980px) {{
  .hero {{ grid-template-columns: 1fr; }}
  .cards {{ grid-template-columns: 1fr 1fr; }}
  .gallery {{ grid-template-columns: 1fr 1fr; }}
}}
@media (max-width: 640px) {{
  nav {{ gap: 10px; font-size: 14px; }}
  .cards, .gallery, .contact-form {{ grid-template-columns: 1fr; }}
}}
"""
    js = """const form = document.getElementById('bookingForm');
const message = document.getElementById('formMessage');
if (form && message) {
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const name = (data.get('name') || 'Guest').toString().trim();
    message.textContent = `Thanks ${name}. Reservation request received.`;
    form.reset();
  });
}
document.querySelectorAll('a[href^=\"#\"]').forEach((link) => {
  link.addEventListener('click', (e) => {
    const id = link.getAttribute('href');
    const target = id ? document.querySelector(id) : null;
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});
"""
    return {"html": html, "css": css, "js": js}


def _generate_website_code_with_ollama(site_name: str, brief: str):
    clean_name = (site_name or "My Website").strip()
    clean_brief = (brief or "").strip()
    spec = _build_spec_from_brief(clean_name, clean_brief)
    design_spec = _extract_prompt_design_spec(clean_name, clean_brief)
    spec_fallback = _build_prompt_driven_website(spec, design_spec=design_spec)
    archetype = _detect_website_archetype(clean_name, clean_brief)
    profile = _archetype_profile(archetype)
    theme = _apply_design_spec_to_theme(_archetype_visual_theme(archetype), design_spec)
    layout_mode = _choose_layout_mode(clean_name, clean_brief, archetype, design_spec)
    explicit_multi_page = ("pages" in clean_brief.lower()) and len(spec.get("pages") or []) > 1
    if explicit_multi_page:
        return spec_fallback
    spec_json = json.dumps(design_spec, ensure_ascii=True)
    prompt = f"""
You are a senior front-end engineer.
Generate a complete production-style static marketing website based on this request.

Website name: {clean_name}
User requirements: {clean_brief if clean_brief else "Create a clean modern homepage with hero, about, and contact sections."}
User prompt (verbatim): {clean_brief if clean_brief else "(no extra prompt provided)"}
Detected site type: {archetype}
Preferred navigation: {", ".join(profile["nav"])}
Content emphasis: {", ".join(profile["sections"])}
Tone: {profile["voice"]}
Primary CTA text: {profile["cta"]}
Preferred palette: background {theme["bg"]}, primary {theme["accent"]}, secondary {theme["accent_2"]}
Preferred typography: headings {theme["font_heading"]}, body {theme["font_body"]}
Layout direction: {layout_mode}
Parsed prompt spec JSON: {spec_json}

Hard rules:
- Return exactly three blocks in this order:
---HTML---
...full index.html...
---CSS---
...full styles.css...
---JS---
...full script.js...
- HTML must include: <!doctype html>, responsive meta tag, and links to styles.css and script.js.
- User prompt overrides defaults. If prompt conflicts with defaults, follow user prompt.
- Structure and copy must match the detected site type. Avoid irrelevant sections.
- Do not reuse the same generic layout every time; create a distinct visual direction per request.
- Use the preferred palette and typography so the site style fits the business type.
- Follow the layout direction exactly and avoid generic hero+3cards if layout direction is editorial or bento.
- CSS must be modern and polished with strong layout, spacing system, gradients/surfaces, hover states, and media queries.
- JS must add real interactivity (form handling, nav behavior, or filters/tabs).
- Do not use markdown code fences.
- Keep text concise and readable, not giant paragraphs.
"""
    try:
        res = _OLLAMA_SESSION.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False,
                "options": {
                    **_OLLAMA_OPTIONS,
                    "num_predict": 1800,
                    "temperature": 0.75,
                },
            },
            timeout=(5, 120),
        )
        generated = (res.json().get("response") or "").strip()
        parsed = _parse_generated_website_blocks(generated)
        if parsed and _looks_like_real_website_output(parsed):
            return parsed
    except Exception:
        pass

    if clean_brief:
        return _real_website_fallback(clean_name, clean_brief)
    return _real_website_fallback(clean_name, clean_brief)


def _create_website_project(site_name: str, brief: str = ""):
    display_name = (site_name or "").strip()
    folder_name = _sanitize_windows_folder_name(display_name)
    if not folder_name:
        return False, "Website name is invalid. Example: create website for Rahul Portfolio."

    desktop_dir = _resolve_desktop_path()
    if not desktop_dir:
        return False, "Could not locate Desktop path."

    websites_root = os.path.join(desktop_dir, "websites")
    target_dir = os.path.join(websites_root, folder_name)
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as ex:
        return False, f"Could not create website folder: {ex}"

    generated = _generate_website_code_with_ollama(display_name, brief)
    css_content = generated["css"]
    js_content = generated["js"]
    created_pages_count = 1
    try:
        if "pages" in generated:
            created_pages_count = len(generated["pages"])
            for filename, html_content in generated["pages"].items():
                with open(os.path.join(target_dir, filename), "w", encoding="utf-8") as f:
                    f.write(html_content)
        else:
            with open(os.path.join(target_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(generated["html"])
        with open(os.path.join(target_dir, "styles.css"), "w", encoding="utf-8") as f:
            f.write(css_content)
        with open(os.path.join(target_dir, "script.js"), "w", encoding="utf-8") as f:
            f.write(js_content)
    except Exception as ex:
        return False, f"Could not write website files: {ex}"

    port = _find_free_local_port()
    try:
        subprocess.Popen(
            ["python", "-m", "http.server", str(port)],
            cwd=target_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(1.0)
        os.system(f'start "" "http://127.0.0.1:{port}"')
    except Exception as ex:
        return False, f"Website created, but local server could not start: {ex}"

    return True, f"Website created with {created_pages_count} page(s) in {target_dir} and opened at http://127.0.0.1:{port}"


def send_whatsapp_document(contact: str, file_path: str, caption: str = ""):
    if not file_path or not os.path.exists(file_path):
        return False, "Document path is invalid."

    driver = _build_whatsapp_driver()
    try:
        driver.get("https://web.whatsapp.com")
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "pane-side"))
        )

        phone = _normalize_phone(contact)
        if phone:
            driver.get(f"https://web.whatsapp.com/send?phone={phone}")
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[@id='main']"))
            )
        else:
            search = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[@id='side']//div[@contenteditable='true'][@role='textbox']")
                )
            )
            search.click()
            search.send_keys(Keys.CONTROL, "a")
            search.send_keys(Keys.DELETE)
            search.send_keys(contact)
            time.sleep(2)
            try:
                first_chat = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable(
                        (By.XPATH, "(//div[@id='pane-side']//div[@role='listitem'])[1]")
                    )
                )
                first_chat.click()
            except Exception:
                search.send_keys(Keys.ENTER)

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//div[@id='main']//footer"))
        )

        _click_first_xpath(driver, WHATSAPP_ATTACH_XPATHS, timeout=8)
        file_inputs = WebDriverWait(driver, 15).until(
            lambda d: d.find_elements(By.CSS_SELECTOR, "input[type='file']")
        )
        if not file_inputs:
            return False, "Could not find WhatsApp file input."

        target_input = None
        for elem in file_inputs:
            accept = (elem.get_attribute("accept") or "").strip()
            if accept == "*" or not accept:
                target_input = elem
                break
        if target_input is None:
            target_input = file_inputs[0]

        target_input.send_keys(os.path.abspath(file_path))
        time.sleep(3)

        if caption:
            try:
                caption_box = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@contenteditable='true'][@data-tab='10']")
                    )
                )
                caption_box.send_keys(caption)
            except Exception:
                pass

        sent = False
        send_selectors = [
            "//span[@data-icon='send']/ancestor::button[1]",
            "//button[@aria-label='Send']",
            "//button[@title='Send']",
        ]
        for selector in send_selectors:
            try:
                buttons = driver.find_elements(By.XPATH, selector)
                for btn in reversed(buttons):
                    if btn.is_displayed() and btn.is_enabled():
                        try:
                            btn.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", btn)
                        sent = True
                        break
                if sent:
                    break
            except Exception:
                continue

        if not sent:
            try:
                # In the documen
                # t preview composer, Enter often sends the attachment.
                preview_box = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located(
                        (By.XPATH, "//div[@contenteditable='true'][@role='textbox']")
                    )
                )
                preview_box.send_keys(Keys.ENTER)
                sent = True
            except Exception:
                pass

        if not sent:
            return False, "Document attached but could not trigger Send button."

        time.sleep(1.5)
        return True, "Document sent on WhatsApp."
    except Exception as ex:
        return False, f"Failed to send WhatsApp document: {ex}"
    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _format_rag_sources(sources):
    if not sources:
        return ""
    lines = []
    for src in sources[:5]:
        label = src.get("label", "Unknown source")
        date = src.get("date", "unknown")
        score = src.get("score", "0.000")
        lines.append(f"- {label} | date={date} | score={score}")
    return "\nSources:\n" + "\n".join(lines)


def _answer_from_rag(query: str):
    result = rag.answer(query, top_k=5, min_score=0.12, allow_system_fallback=True)
    if not result.used_rag:
        return None
    return result.answer + _format_rag_sources(result.sources)


def _open_calculator_app() -> bool:
    try:
        os.startfile("calc.exe")
        return True
    except Exception:
        pass

    launchers = [
        ["calc.exe"],
        ["cmd", "/c", "start", "", "calc.exe"],
        ["explorer.exe", "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"],
    ]
    for cmd in launchers:
        try:
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            continue
    return False


def handle_input(text: str):
    global LAST_USER_MESSAGE
    global calculator_open
    global last_contact
    global pending_flipkart_cod
    global pending_amazon_cod
    global pending_marketplace_choice
    global pending_linkedin_post
    text_raw = (text or "").strip()
    text_norm = text_raw.lower().strip()

    target_lang  = text_translator(text_raw)
    if target_lang  is not None:
        if not LAST_USER_MESSAGE:
            return "No previous command found to translate"
        return _translate_text(LAST_USER_MESSAGE, target_lang)
    if text_raw:
        LAST_USER_MESSAGE = text_raw



    if not text_norm:
        return "I didn't catch that."

    if pending_linkedin_post is not None:
        if re.search(r"\b(yes|haan|ha|approve|approved|confirm|continue|go ahead)\b", text_norm):
            payload = pending_linkedin_post
            pending_linkedin_post = None
            ok, note = post_on_linkedin(payload.get("draft") or "")
            return note

        if re.search(r"\b(no|reject|change|another|retry)\b", text_norm):
            topic = (pending_linkedin_post or {}).get("topic", "")
            previous_draft = (pending_linkedin_post or {}).get("draft", "")
            new_draft = _generate_linkedin_post(topic, avoid_text=previous_draft)
            pending_linkedin_post = {"topic": topic, "draft": new_draft}
            return (
                f"Here is another LinkedIn draft for '{topic}':\n\n{new_draft}\n\n"
                "Approve this? Reply yes to post or no for another draft."
            )

        if re.search(r"\b(cancel|stop)\b", text_norm):
            pending_linkedin_post = None
            return "LinkedIn post flow cancelled."

        current_topic = (pending_linkedin_post or {}).get("topic", "your topic")
        current_draft = (pending_linkedin_post or {}).get("draft", "")
        return (
            f"Pending LinkedIn draft for '{current_topic}':\n\n{current_draft}\n\n"
            "Reply yes to post, no for another draft, or cancel."
        )

    linkedin_topic = _extract_linkedin_topic(text_raw)
    if linkedin_topic:
        draft = _generate_linkedin_post(linkedin_topic)
        pending_linkedin_post = {"topic": linkedin_topic, "draft": draft}
        return (
            f"LinkedIn draft for '{linkedin_topic}':\n\n{draft}\n\n"
            "Approve this? Reply yes to post or no for another draft."
        )

    if pending_marketplace_choice is not None:
        if re.search(r"\b(no|cancel|stop|nahi|nahin)\b", text_norm):
            pending_marketplace_choice = None
            return "Shopping action cancelled."
        has_flipkart = _looks_like_flipkart(text_norm)
        has_amazon = _looks_like_amazon(text_norm)
        if has_flipkart == has_amazon:
            return "Choose exactly one site: flipkart or amazon."

        payload = pending_marketplace_choice
        pending_marketplace_choice = None
        action = payload.get("action", "search")
        cod = bool(payload.get("cod", False))
        if has_flipkart:
            if action == "checkout":
                pending_flipkart_cod = True
                return "Flipkart cart checkout is ready. Say yes to continue or no to cancel."
            ok, note = open_flipkart_search(
                payload.get("product") or "all items",
                payload.get("size"),
                payload.get("color"),
                cod,
            )
            return note

        if action == "checkout":
            pending_amazon_cod = True
            return "Amazon cart checkout is ready. Say yes to continue or no to cancel."
        ok, note = open_amazon_search(
            payload.get("product") or "all items",
            payload.get("size"),
            payload.get("color"),
            cod,
        )
        return note

    if pending_flipkart_cod:
        if re.search(r"\b(yes|haan|ha|confirm|continue|go ahead)\b", text_norm):
            pending_flipkart_cod = False
            ok, note = place_flipkart_cart_orders_cod()
            return note
        if re.search(r"\b(no|cancel|stop|nahi|nahin)\b", text_norm):
            pending_flipkart_cod = False
            return "Flipkart COD checkout cancelled."
        return "Please say yes to place order with COD, or no to cancel."

    if pending_amazon_cod:
        if re.search(r"\b(yes|haan|ha|confirm|continue|go ahead)\b", text_norm):
            pending_amazon_cod = False
            ok, note = place_amazon_cart_orders_cod()
            return note
        if re.search(r"\b(no|cancel|stop|nahi|nahin)\b", text_norm):
            pending_amazon_cod = False
            return "Amazon COD checkout cancelled."
        return "Please say yes to place Amazon order with COD, or no to cancel."

    desktop_folder_name = _extract_desktop_folder_name(text_raw)
    if desktop_folder_name is not None:
        if not desktop_folder_name:
            return "Please provide a valid folder name, for example: create folder Projects on desktop."
        ok, note = _create_folder_on_desktop(desktop_folder_name)
        return note

    if _is_website_create_request(text_raw):
        payload = _extract_website_prompt_payload(text_raw) or {}
        website_name = (payload.get("name") or "").strip()
        website_brief = (payload.get("brief") or "").strip()
        if not website_name:
            return "Please provide website name, for example: create a website for Rahul Portfolio."
        ok, note = _create_website_project(website_name, website_brief)
        return note

    if text_norm in {
        "index docs", "index documents", "index knowledge",
        "build index", "reindex docs", "reindex knowledge"
    }:
        stats = rag.build_index()
        return (
            f"Knowledge indexed. Files scanned: {stats['files']}. "
            f"Chunks stored: {stats['chunks']}."
        )

    if text_norm in {"rag status", "knowledge status", "index status"}:
        chunks = len(rag.index.get("chunks", []))
        updated = rag.index.get("updated_at") or "never"
        roots = ", ".join([p.as_posix() for p in rag.system_roots]) or "none"
        return f"Knowledge chunks: {chunks}. Last indexed: {updated}. System scan roots: {roots}"

    if text_norm.startswith("ask docs:") or text_norm.startswith("ask knowledge:"):
        query = text_raw.split(":", 1)[1].strip() if ":" in text_raw else ""
        if not query:
            return "Please provide a query after 'ask docs:'."
        rag_answer = _answer_from_rag(query)
        if rag_answer:
            return rag_answer
        return "I could not find enough evidence in your indexed knowledge."

    smtp_set_response = _handle_set_smtp_command(text_raw)
    if smtp_set_response is not None:
        return smtp_set_response

    if text_norm in {"smtp status", "email status", "mail status"}:
        cfg = _get_smtp_config()
        masked_user = cfg["username"][:3] + "***" if cfg["username"] else "missing"
        password_state = "set" if cfg["password"] else "missing"
        return (
            f"SMTP host={cfg['host']} port={cfg['port']} "
            f"username={masked_user} password={password_state} from={cfg['from_email'] or 'missing'}"
        )

    save_email_data = _parse_save_email_command(text_raw)
    if save_email_data:
        name, email = save_email_data
        _save_contact_email(name, email)
        return f"Saved email for {name}: {email}"

    email_cmd = _parse_email_command(text_raw)
    if email_cmd:
        recipient_token = email_cmd["recipient"]
        to_email = _resolve_email_recipient(recipient_token)
        if not to_email:
            return (
                f"I don't have a saved email for {recipient_token}. "
                f"Use: save email for {recipient_token} name@example.com"
            )
        ok, note = _send_email_smtp(
            to_email,
            email_cmd["subject"],
            email_cmd["message"],
        )
        if ok:
            return f"Email sent to {recipient_token} ({to_email})"
        return f"Could not send email: {note}"

    if _looks_like_email_request(text_raw):
        return (
            "Please include recipient, subject, and message. "
            "Example: send email to Rahul subject Project Update message Meeting at 6 PM."
        )

    word_whatsapp_payload = _extract_word_whatsapp_payload(text_raw)
    if word_whatsapp_payload:
        filename = word_whatsapp_payload["filename"]
        content = word_whatsapp_payload["content"]
        contact = word_whatsapp_payload["contact"]
        ok, note = _create_word_document(filename, content, open_in_word=False)
        if not ok:
            return note
        file_path = _word_target_path(filename)
        if not file_path:
            return "File name is invalid for Word document creation."
        send_ok, send_note = send_whatsapp_document(contact, file_path, "")
        if send_ok:
            return f"Created and sent Word file to {contact} on WhatsApp: {file_path}"
        return f"Created Word file, but send failed for {contact}: {send_note}"

    flipkart_payload = _extract_flipkart_payload(text_raw)
    if flipkart_payload:
        ok, note = open_flipkart_search(
            flipkart_payload["product"],
            flipkart_payload.get("size"),
            flipkart_payload.get("color"),
            flipkart_payload.get("cod", False),
        )
        return note

    amazon_payload = _extract_amazon_payload(text_raw)
    if amazon_payload:
        ok, note = open_amazon_search(
            amazon_payload["product"],
            amazon_payload.get("size"),
            amazon_payload.get("color"),
            amazon_payload.get("cod", False),
        )
        return note

    flipkart_checkout_payload = _extract_flipkart_checkout_payload(text_raw)
    if flipkart_checkout_payload:
        pending_flipkart_cod = True
        return (
            "I can go to Flipkart cart and place the order in Cash on Delivery mode where available. "
            "Say yes to continue or no to cancel."
        )

    amazon_checkout_payload = _extract_amazon_checkout_payload(text_raw)
    if amazon_checkout_payload:
        pending_amazon_cod = True
        return (
            "I can go to Amazon cart and place the order in COD mode where available. "
            "Say yes to continue or no to cancel."
        )

    marketplace_choice_payload = _extract_marketplace_choice_payload(text_raw)
    if marketplace_choice_payload:
        pending_marketplace_choice = marketplace_choice_payload
        return "Which site do you want: flipkart or amazon? Choose only one."

    try:
        intent = _parse_intent(text_raw)

        if intent.name == "save_contact":
            _save_contact(intent.contact, intent.phone)
            google_ok, google_note = _save_google_contact(intent.contact, intent.phone)
            if google_ok:
                return f"Saved {intent.contact} locally and in Google Contacts."
            return f"Saved {intent.contact} locally. Google sync skipped: {google_note}"

        if intent.name == "send_hi":
            target_phone = intent.phone or _get_phone(intent.contact or "")
            if target_phone:
                _save_contact(intent.contact, target_phone)
                threading.Thread(
                    target=send_whatsapp,
                    args=(target_phone, intent.message or "Hi"),
                    daemon=True
                ).start()
                return f"Sending Hi to {intent.contact}"
            return f"I don't have a saved number for {intent.contact}. Use: save contact {intent.contact} +911234567890"

        if intent.name == "save_and_send_hi":
            _save_contact(intent.contact or "", intent.phone or "")
            google_ok, google_note = _save_google_contact(
                intent.contact or "", intent.phone or ""
            )
            save_ok, save_note = save_contact_and_send_hi_whatsapp(
                intent.contact or "",
                intent.phone or "",
                intent.message or "Hi"
            )
            status = "Saved contact in WhatsApp." if save_ok else "Could not confirm WhatsApp contact save."
            google_status = (
                "Name saved to Google Contacts for WhatsApp sync."
                if google_ok else
                f"Google sync failed: {google_note}"
            )
            return f"{status} {google_status} Message sent to {intent.contact}. Details: {save_note}"

        if intent.name == "save_whatsapp_and_hi":
            _save_contact(intent.contact or "", intent.phone or "")
            google_ok, google_note = _save_google_contact(
                intent.contact or "", intent.phone or ""
            )
            save_ok, save_note = save_contact_and_send_hi_whatsapp(
                intent.contact or "",
                intent.phone or "",
                intent.message or "Hi"
            )
            status = "Saved contact in WhatsApp." if save_ok else "Could not confirm WhatsApp contact save."
            google_status = (
                "Name saved to Google Contacts for WhatsApp sync."
                if google_ok else
                f"Google sync failed: {google_note}"
            )
            return f"{status} {google_status} Message sent to {intent.contact}. Details: {save_note}"

        if intent.name == "send_message":
            target = _get_phone(intent.contact or "") or intent.contact
            threading.Thread(
                target=send_whatsapp,
                args=(target, intent.message or ""),
                daemon=True
            ).start()
            return f"Sending message to {intent.contact}"

        if intent.name == "call_contact":
            target = _get_phone(intent.contact or "") or intent.contact
            try:
                call_whatsapp(target, False)
                return f"Calling {intent.contact} on WhatsApp"
            except Exception as ex:
                return f"Could not start call for {intent.contact}: {ex}"

        if intent.name == "video_call_contact":
            target = _get_phone(intent.contact or "") or intent.contact
            try:
                call_whatsapp(target, True)
                return f"Starting video call with {intent.contact} on WhatsApp"
            except Exception as ex:
                return f"Could not start video call for {intent.contact}: {ex}"

        if intent.name in ("invalid_contact", "invalid_command"):
            if re.search(r"\b(whatsapp|contact|message|send|save|dial|call|video)\b", text_norm):
                return "Command format looks invalid. Try: save contact Rahul +911234567890"
    except Exception:
        pass


    name, msg = _parse_whatsapp(text_raw)
    if name and msg:
        target = _get_phone(name) or name
        threading.Thread(
            target=send_whatsapp,
            args=(target, msg),
            daemon=True
        ).start()
        return f"Sending message to {name}"


    if _is_screen_vision_request(text_norm):
        ok, note = analyze_screen_with_vision(text_raw)
        return note

    if _is_camera_vision_request(text_norm):
        ok, note = analyze_camera_with_vision(text_raw)
        return note

    if "open camera" in text_norm or text_norm in {"camera", "start camera", "launch camera"}:
        os.system("start microsoft.windows.camera:")
        return "Opening camera"


    if (
        re.search(r"\b(open|start|launch)\s+(the\s+)?calculator\b", text_norm)
        or text_norm in {"calculator", "calc", "open calc"}
    ):
        if _open_calculator_app():
            time.sleep(1)
            calculator_open = True
            return "Calculator opened"
        return "Could not open Calculator on this system."

    if text_norm in {"open microsoft word", "open ms word", "open word"}:
        os.system("start winword")
        return "Opening Microsoft Word"

    if _is_word_create_request(text_raw):
        filename = _extract_word_filename(text_raw)
        if not filename:
            return "Please tell me the file name, for example: open Microsoft Word and create file named notes."
        ok, message = _create_word_document(filename)
        return message



    expression = _parse_calc_expression(text_norm)
    if expression:
        if not calculator_open:
            if not _open_calculator_app():
                return "Could not open Calculator to run the expression."
            time.sleep(1)
            calculator_open = True

        pyautogui.write(expression)
        pyautogui.press("enter")

        return f"Calculated {expression}"




    if text_norm == "reply" and last_contact:
        msgs = get_latest_messages(last_contact, 1)
        if msgs:
            reply = ollama_answer(f"Reply to this message: {msgs[0]}")
            threading.Thread(
                target=send_whatsapp,
                args=(last_contact, reply),
                daemon=True
            ).start()
            return f"Replying to {last_contact}"

    rag_trigger = (
        "ask" in text_norm
        or "client" in text_norm
        or "document" in text_norm
        or "email" in text_norm
        or text_norm.endswith("?")
    )
    if rag_trigger and rag.has_index():
        rag_answer = _answer_from_rag(text_raw)
        if rag_answer:
            return rag_answer

    return ollama_answer(text_norm)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    history = recentChats(30)
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "language": "en", "history": history}
    )


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "orobot",
        "assemblyai_configured": bool(ASSEMBLYAI_API_KEY),
        "voice_input_enabled": bool(
            SOUNDDEVICE_AVAILABLE and ASSEMBLYAI_AVAILABLE and ASSEMBLYAI_API_KEY
        ),
    }


@app.post("/send", response_class=HTMLResponse)
def send_text(request: Request, command: str = Form(...), language: str = Form("en")):
    history = recentChats(30)

    language = _safe_language(language)
    text = command.strip()
    raw_answer = handle_input(text)
    answer = _translate_text(raw_answer, language)
    db =SessionLocal()
    db.add(Chat_history(question=text, answer = answer, source = 'general'))
    db.commit()
    db.close()

    threading.Thread(
        target=speak,
        args=(answer, language),
        daemon=True
    ).start()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "speech_text": text,
            "answer": answer,
            "language": language,
            "history":history
        }
    )


@app.post("/listen", response_class=HTMLResponse)
def listen(request: Request, language: str = Form("en")):
    history = recentChats(30)
    global pending_whatsapp
    language = _safe_language(language)

    if not SOUNDDEVICE_AVAILABLE or not ASSEMBLYAI_AVAILABLE:
        answer = (
            "Voice input is not available on this deployed server. "
            "Please type your command instead."
        )
        if SOUNDDEVICE_IMPORT_ERROR:
            print(f"Voice input disabled: {SOUNDDEVICE_IMPORT_ERROR}")
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "speech_text": "",
                "answer": answer,
                "language": language,
                "history": history,
            }
        )

    fs = 16000
    s = 5

    audio = sounddevice.rec(int(s * fs), samplerate=fs, channels=1)
    sounddevice.wait()
    write("voice.wav", fs, audio)

    transcriber = assemblyai.Transcriber()
    transcript = transcriber.transcribe("voice.wav")
    user_text = transcript.text.lower() if transcript.text else ""

    print("VOICE:", user_text)

    user_text = user_text.replace("sand message", "send message")
    user_text = user_text.replace("send massage", "send message")

    if pending_whatsapp:
        if "yes" in user_text:
            contact = pending_whatsapp['contact']
            message = pending_whatsapp['message']
            threading.Thread(
                target=send_whatsapp,
                args=(contact, message),
                daemon=True
            ).start()
            answer = f"Sending message to {contact}"
            pending_whatsapp = None
        elif "no" in user_text:
            answer = "Message sending cancelled"
            pending_whatsapp = None
        else:
            answer = "Please say yes or no to confirm sending the message"
    else:
        answer = handle_input(user_text)

    answer = _translate_text(answer, language)

    db = SessionLocal()
    db.add(Chat_history(
        question=user_text,
        answer=answer,
        source="general"
    ))
    db.commit()
    db.close()

    threading.Thread(
        target=speak,
        args=(answer, language),
        daemon=True
    ).start()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "speech_text": user_text,
            "answer": answer,
            "language": language,
            "history":history
        }
    )

def recentChats(limit: int =20):
    db = SessionLocal()
    try:
        rows = (
            db.query(Chat_history)
            .order_by(Chat_history.id.desc())
            .limit(limit)
            .all()

        )
        rows.reverse()
        return rows
    except Exception:
        traceback.print_exc()
        return []
    finally:
        db.close()
