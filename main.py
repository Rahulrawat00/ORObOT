from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import threading
import time
import re
import requests
import os
# ========= VOICE =========
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

from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from database import SessionLocal, Base, engine
from models import Chat_history


if ASSEMBLYAI_AVAILABLE:
    assemblyai.settings.api_key = "170d28750c664fa38b3dd3d0034e4f9b"
app = FastAPI()
calculator_open = False
templates = Jinja2Templates(directory="templates")

Base.metadata.create_all(bind=engine)

pending_whatsapp = None
last_contact = None


def speak(text: str):
    if not PYTTSX3_AVAILABLE:
        return
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        if voices:
            engine.setProperty('voice', voices[0].id)
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
You are a voice assistant.

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
    res = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": question,
            "stream": False
        },
        timeout=60  
    )
    return res.json()["response"]


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

    # Wait for the chat to load
    time.sleep(3)

    # Find message elements (adjust XPath as needed for WhatsApp Web structure)
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


import threading

def handle_input(text: str):
    global calculator_open
    global last_contact
    text = text.lower().strip()

    
    if "send message to" in text and "saying" in text:
        try:
            part = text.split("send message to")[1]
            name, msg = part.split("saying", 1)

            name = name.strip()
            msg = msg.strip()

            threading.Thread(
                target=send_whatsapp,
                args=(name, msg),
                daemon=True
            ).start()

            return f"Sending message to {name}"

        except:
            return "Invalid message format. Use: send message to name saying message"

   
    if "open camera" in text:
        os.system("start microsoft.windows.camera:")
        return "Opening camera"

   
    if "open calculator" in text:
        os.system("calc")
        time.sleep(2)
        calculator_open = True
        return "Calculator opened"


    
    calc_match = re.search(r"calculate\s*([0-9+\-*/(). ]+)", text)

    if calc_match:
        expression = calc_match.group(1).replace(" ", "")

        if not calculator_open:
            os.system("calc")
            time.sleep(2)
            calculator_open = True

        pyautogui.write(expression)
        pyautogui.press("enter")

        return f"Calculated {expression}"



   
    if text == "reply" and last_contact:
        msgs = get_latest_messages(last_contact, 1)
        if msgs:
            reply = ollama_answer(f"Reply to this message: {msgs[0]}")
            threading.Thread(
                target=send_whatsapp,
                args=(last_contact, reply),
                daemon=True
            ).start()
            return f"Replying to {last_contact}"

    
    return ollama_answer(text)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/send", response_class=HTMLResponse)
def send_text(request: Request, command: str = Form(...)):
    text = command.lower()
    answer = handle_input(text)

    threading.Thread(
        target=speak,
        args=(answer,),
        daemon=True
    ).start()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "speech_text": text,
            "answer": answer
        }
    )




@app.post("/listen", response_class=HTMLResponse)
def listen(request: Request):
    global pending_whatsapp
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
        args=(answer,),
        daemon=True
    ).start()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "speech_text": user_text,
            "answer": answer
        }
    )
