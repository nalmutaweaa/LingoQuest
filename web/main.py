# LingoQuest: the web version (pygbag). The camera and microphone run in the browser
# and the AI calls go through the Render server.
import pygame
import asyncio  # pygbag needs this
import csv
import io
import os
import json
import unicodedata
import time
import math
import random

# a sound that cannot load must not stop the game
class NoSound:
    def play(self, *a, **k): return None
    def stop(self): pass
    def set_volume(self, *a): pass
    def get_length(self): return 0

real_exists = os.path.exists
def web_exists(path):
    return real_exists(path) or (path.endswith((".wav", ".mp3")) and real_exists(path[:-4] + ".ogg"))
os.path.exists = web_exists

def make_sound(path):
    if path.endswith((".wav", ".mp3")) and real_exists(path[:-4] + ".ogg"):
        path = path[:-4] + ".ogg"
    try:
        return pygame.mixer.Sound(path)
    except Exception as e:
        print("sound failed:", path, e)
        return NoSound()


import platform

SERVER = "https://servertest-6j5q.onrender.com"  # your Render link, no slash at the end
PAGE_COLOR = "#a8d8f0"
PAGE_TOP = "LingoQuest - Learn it, Find it, Collect it!"  # the text above the game
PAGE_BOTTOM = "© 2026 LingoQuest. All rights reserved."  # the text under the game

class NoMic:
    def stop(self): pass
    def wait(self): pass
    def rec(self, *a, **k): pass
sd = NoMic()

JS = """
window.lq = {state: "idle", text: ""};
window.lq_wake = function(server) { fetch(server + "/", {mode: "no-cors"}).catch(function() {}); };

function lq_box() {
  var box = document.createElement("div");
  box.style.cssText = "position:fixed;left:0;top:0;width:100%;height:100%;background:rgba(0,0,0,0.85);z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:16px;font-family:Arial;";
  return box;
}
function lq_button(text, color) {
  var b = document.createElement("button");
  b.textContent = text;
  b.style.cssText = "font-size:24px;font-weight:bold;padding:14px 32px;border:3px solid #5a1450;border-radius:12px;color:white;background:" + color + ";";
  return b;
}

window.lq_cam = null;

async function lq_send(url, form) {
  var last;
  for (var i = 0; i < 8; i++) {
    var r = null;
    try { r = await fetch(url, {method: "POST", body: form}); } catch (e) { last = e; }
    if (r) {
      if (r.ok) return await r.json();
      if (r.status < 502 || r.status > 504) throw new Error("server " + r.status);
      last = new Error("server " + r.status);
    }
    lq.text = "waking";
    await new Promise(function(ok) { setTimeout(ok, 6000); });
  }
  throw last;
}
function lq_place() {
  if (!lq_cam) return;
  var r = (document.getElementById("canvas") || document.querySelector("canvas")).getBoundingClientRect();
  var sx = r.width / 800, sy = r.height / 640;
  var v = lq_cam.video.style;
  v.left = (r.left + 289 * sx) + "px"; v.top = (r.top + 273 * sy) + "px";
  v.width = (222 * sx) + "px"; v.height = (208 * sy) + "px";
}
window.addEventListener("resize", lq_place);

window.lq_open = async function() {
  lq.state = "busy"; lq.text = "";
  var stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}});
  } catch (e) {
    lq.text = "camera not allowed"; lq.state = "error"; return;
  }
  var video = document.createElement("video");
  video.autoplay = true; video.playsInline = true; video.muted = true;
  video.srcObject = stream;
  video.style.cssText = "position:fixed;object-fit:cover;border-radius:6px;z-index:99999;";
  document.body.appendChild(video);
  lq_cam = {stream: stream, video: video};
  lq_place();
  lq.state = "live";
};

window.lq_close = function() {
  if (!lq_cam) return;
  lq_cam.stream.getTracks().forEach(function(t) { t.stop(); });
  lq_cam.video.remove();
  lq_cam = null;
};

window.lq_snap = function(word, server, path) {
  lq.state = "busy"; lq.text = "";
  if (!lq_cam || !lq_cam.video.videoWidth) { lq.text = "no camera"; lq.state = "error"; return; }
  var video = lq_cam.video;
  var scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
  var c = document.createElement("canvas");
  c.width = Math.round(video.videoWidth * scale); c.height = Math.round(video.videoHeight * scale);
  c.getContext("2d").drawImage(video, 0, 0, c.width, c.height);
  c.toBlob(async function(blob) {
    try {
      var f = new FormData();
      f.append("word", word);
      f.append("photo", blob, "photo.jpg");
      var d = await lq_send(server + (path || "/hunt"), f);
      lq.text = d.correct ? "yes" : "no"; lq.state = "done";
    } catch (e) { lq.text = String(e); lq.state = "error"; }
  }, "image/jpeg", 0.8);
};

window.lq_speak = async function(lang, server, seconds) {
  lq.state = "recording"; lq.text = "";
  var stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true});
  } catch (e) {
    lq.text = "microphone not allowed"; lq.state = "error"; return;
  }
  var rec = new MediaRecorder(stream);
  var chunks = [];
  rec.ondataavailable = function(e) { chunks.push(e.data); };
  rec.onstop = async function() {
    stream.getTracks().forEach(function(t) { t.stop(); });
    lq.state = "busy";
    var blob = new Blob(chunks, {type: rec.mimeType});
    var type = blob.type || "audio/webm";
    var ext = type.indexOf("mp4") >= 0 ? "mp4" : type.indexOf("ogg") >= 0 ? "ogg" : "webm";
    try {
      var f = new FormData();
      f.append("language", lang);
      f.append("recording", blob, "speech." + ext);
      var d = await lq_send(server + "/speak", f);
      lq.text = d.heard || ""; lq.state = "done";
    } catch (e) { lq.text = String(e); lq.state = "error"; }
  };
  rec.start();
  setTimeout(function() { rec.stop(); }, seconds * 1000);
};
"""
PAGE_JS = """
function lq_line(text) {
  var d = document.createElement("div");
  d.textContent = text;
  d.style.cssText = "position:fixed;left:0;width:100%;text-align:center;font:bold 15px Arial;color:#1b3a57;pointer-events:none;z-index:1;";
  document.body.appendChild(d);
  return d;
}
var lq_top = lq_line("PAGE_TOP"), lq_bottom = lq_line("PAGE_BOTTOM");
function lq_texts() {
  var c = document.getElementById("canvas") || document.querySelector("canvas");
  var r = c.getBoundingClientRect();
  lq_top.style.display = r.top > 30 ? "block" : "none";
  lq_top.style.top = (r.top / 2 - 10) + "px";
  var room = window.innerHeight - r.bottom;
  lq_bottom.style.display = room > 30 ? "block" : "none";
  lq_bottom.style.top = (r.bottom + room / 2 - 10) + "px";
}
setInterval(lq_texts, 500);
window.addEventListener("resize", lq_texts);
"""
try:
    platform.window.eval(JS)
    platform.window.lq_wake(SERVER)
    platform.window.eval("var c = document.getElementById('canvas') || document.querySelector('canvas'); for (var e = c.parentElement; e; e = e.parentElement) e.style.setProperty('background', '" + PAGE_COLOR + "', 'important');")
    platform.window.eval("setInterval(function() { lq_wake('" + SERVER + "'); }, 600000)")
    platform.window.eval(PAGE_JS.replace("PAGE_TOP", PAGE_TOP).replace("PAGE_BOTTOM", PAGE_BOTTOM))
except Exception as error:
    print("browser bridge failed:", error)

lq_kind = ""
cam_on = False  # is the camera open inside the frame
typed = ""

def lq_read():
    "what the browser says now: (state, text)"
    try:
        return str(platform.window.eval("lq.state")), str(platform.window.eval("lq.text"))
    except Exception as error:
        print("bridge read failed:", error)
        return "error", "bridge"

# ------LOADING MODELS,DF..---------------
KEY = os.getenv("OPENROUTER_KEY") 

MODEL= "nvidia/nemotron-3.5-super-vl:free"
codes = {"japanese": "ja", "french": "fr", "spanish": "es"}

# read csv
with open("vocab_final.csv", encoding="utf-8", newline="") as f:  # no utf-8-sig in the browser
    text = f.read().lstrip("\ufeff")  # remove the invisible mark at the start
df = list(csv.DictReader(io.StringIO(text)))
for r in df:
    r["model_class"] = r["english"].lower().replace(" ", "_")

show_column = {"japanese": "ja_show", "french": "french", "spanish": "spanish"}
audio_column =  {"japanese": "audio_ja", "french": "audio_fr", "spanish": "audio_es"}  # map with cols


pygame.init()
screen = pygame.display.set_mode((800,640))
# load images function
def load(path,size):
    picture= pygame.image.load(path).convert_alpha()  # for transpaent images
    return pygame.transform.scale(picture,size)

tier_color= {"gold":(255,200,40),"silver":(140,150,172),"bronze":(200,130,70)}
BLUE=(169, 217, 239)
TEXT_DARK = (40, 30, 50)    
OUTLINE_PINK = (150, 50, 100)

# ---- LOAD BACKGROUNDS -------
bg_home= load("images/backgrounds/home.png",(800, 640))
bg_map=load("images/backgrounds/bg_map.jpg",(800, 640))
bg_welcome = load("images/backgrounds/welcome.png", (800, 640))

japan_home = load("images/backgrounds/japan_home.png", (800, 640))
japan_school = load("images/backgrounds/japan_school.png", (800, 640))
japan_outdoor = load("images/backgrounds/japan_outdoor.png", (800, 640))

france_home = load("images/backgrounds/france_home.png", (800, 640))
france_school = load("images/backgrounds/france_school.png", (800, 640))
france_outdoor = load("images/backgrounds/france_outdoor.png", (800, 640))

spain_home = load("images/backgrounds/spain_home.png", (800, 640))
spain_school = load("images/backgrounds/spain_school.png", (800, 640))
spain_outdoor = load("images/backgrounds/spain_outdoor.png", (800, 640))

girl_img= load("images/guide/guide_idle.png",(270, 360))
boy_img= load("images/guide/guide_boy_idle.png",(270, 360))
# waving guides (bigger, for when the mouse is on them)
wave_frames = {
    "girl": [load("images/guide/guide_wave_1.png", (324, 432)), load("images/guide/guide_wave_2.png", (324, 432))],
    "boy": [load("images/guide/guide_boy_wave_1.png", (324, 432)), load("images/guide/guide_boy_wave_2.png", (324, 432))],
}

# map with countries
bg_map = pygame.Surface((800, 640))
bg_map.fill(BLUE)

countries = ("japan", "france", "spain")
country_width = {"japan": 300, "france": 220, "spain": 270}
country_pos = {"japan": (590, 235), "france": (165, 255), "spain": (435, 480)}
flag_height = {"japan": 30, "france": 30, "spain": -5}  # smaller = flag higher
grow_amount = 0.15

country_size = {}
country_big = {}
flag_frames = {}
for c in countries:
    raw = pygame.image.load("images/country/" + c + ".png").convert_alpha()
    w, h = raw.get_size()
    country_size[c] = (country_width[c], int(h * country_width[c] / w))
    big_w = int(country_width[c] * (1 + grow_amount))
    country_big[c] = pygame.transform.smoothscale(raw, (big_w, int(h * big_w / w)))
    flag_frames[c] = []
    for n in range(1, 5):
        flag_frames[c].append(pygame.image.load("images/country/flag_" + c + "_" + str(n) + ".png").convert_alpha())

# plane (put images/country/plane.png facing right to use your own)
if os.path.exists("images/country/plane.png"):
    raw = pygame.image.load("images/country/plane.png").convert_alpha()
    plane_img = pygame.transform.smoothscale(raw, (90, int(raw.get_height() * 90 / raw.get_width())))
else:
    plane_img = pygame.Surface((90, 50), pygame.SRCALPHA)
    pygame.draw.polygon(plane_img, (240, 100, 160), [(35, 22), (58, 22), (40, 2)])
    pygame.draw.polygon(plane_img, (240, 100, 160), [(35, 28), (58, 28), (40, 48)])
    pygame.draw.polygon(plane_img, (240, 100, 160), [(12, 22), (24, 22), (8, 8)])
    pygame.draw.ellipse(plane_img, (255, 255, 255), (8, 15, 76, 20))
    pygame.draw.ellipse(plane_img, (90, 20, 80), (8, 15, 76, 20), 3)

# icons
icon_back = load("images/ui/ui_back.png", (60, 60))
icon_menu = load("images/ui/ui_menu.png", (60, 60))
icon_passport = load("images/ui/ui_passport.png", (60, 60))
if os.path.exists("images/ui/ui_dictionary.png"):
    icon_dictionary = load("images/ui/ui_dictionary.png", (60, 60))  # your own dictionary icon
else:  # no picture yet: a blue square with Aa
    icon_dictionary = pygame.Surface((60, 60), pygame.SRCALPHA)
    pygame.draw.rect(icon_dictionary, (120, 170, 230), (4, 4, 52, 52), border_radius=12)
    pygame.draw.rect(icon_dictionary, (66, 40, 76), (4, 4, 52, 52), 3, border_radius=12)
    aa = pygame.font.SysFont("arial", 26, bold=True).render("Aa", True, (255, 255, 255))
    icon_dictionary.blit(aa, aa.get_rect(center=(30, 30)))
adventure_icon = {
    "Home Adventure": load("images/ui/adventure_home.png", (150, 150)),
    "School Adventure": load("images/ui/adventure_school.png", (150, 150)),
    "Outdoor Adventure": load("images/ui/adventure_park.png", (150, 150)),
}
mode_icon = {m: load("images/ui/mode_" + m + ".png", (64, 64)) for m in ("learn", "cards", "hunt", "speak")}
box_text = {
    "Home Adventure": ["I'm at", "home"],
    "School Adventure": ["I'm at", "school"],
    "Outdoor Adventure": ["I'm", "outside"],
}

backgrounds = {
    ("japan", "home"): japan_home,
    ("japan", "school"): japan_school,
    ("japan", "outdoor"): japan_outdoor,
    ("france", "home"): france_home,
    ("france", "school"): france_school,
    ("france", "outdoor"): france_outdoor,
    ("spain", "home"): spain_home,
    ("spain", "school"): spain_school,
    ("spain", "outdoor"): spain_outdoor,
}

play_normal = load("images/backgrounds/button_play.png", (280, 96))
play_hover = load("images/backgrounds/button_play_hover.png", (280, 96))

menus= {
    "japan": load("images/backgrounds/japan_menu.png", (800, 640)),
    "france": load("images/backgrounds/france_menu.png", (800, 640)),
    "spain": load("images/backgrounds/spain_menu.png", (800, 640))
}
# passport
passport_frames= [
    load("images/passport/passport_mini_1_closed.png", (500, 360)),
    load ("images/passport/passport_mini_2_half_open.png",(500,360)),
    load("images/passport/passport_mini_3_open.png",(500,360))
]

# background of the guide talks (japan_intro.png ...)
intros = {}
for c in ("japan", "france", "spain"):
    intro_file = "images/backgrounds/" + c + "_intro.png"
    if os.path.exists(intro_file):
        intros[c] = load(intro_file, (800, 640))

city_maps = {}
for c in ("japan", "france", "spain"):
    map_file = "images/backgrounds/" + c + "_map.png"
    if os.path.exists(map_file):
        city_maps[c] = load(map_file, (800, 640))

book_file = "images/passport/passport_collection.png"  # open book for the stamps page
passport_book = load(book_file, (760, 507)) if os.path.exists(book_file) else None

pygame.display.set_caption("LingoQuest")
font_file = "fonts/game_font.ttf"  # put the font you like here
system_font = "arialrounded"
jp_file = "fonts/jp_font.ttf"
def game_font(size):
    if os.path.exists(font_file):
        return pygame.font.Font(font_file, size)
    if os.path.exists(jp_file):
        return pygame.font.Font(jp_file, size)
    return pygame.font.SysFont(system_font, size)
font = game_font(34)
soft_file = "fonts/soft_font.ttf"
def soft_font(size):
    if os.path.exists(soft_file):
        return pygame.font.Font(soft_file, size)
    return game_font(size)


# JP FONT = not supported (specific one meiryo)
def jp_font_of(size):
    if os.path.exists(jp_file):
        return pygame.font.Font(jp_file, size)
    return pygame.font.SysFont("msgothic", size)
word_font = jp_font_of(56)


# -------game memory --------------
state = "name"  # screen we are at now
name=""  # player name
language= ""  # jp,fr,es
adventure=""  # school, home,outdoor
mode= ""  # learn,card,hunt,speak
checking=False
result=None
words = None
result_time=0
sfx_done = set()  # result sounds already played
closed_shift = 100
stamp_wait = 0
index = 0
score = 0
message = ""
menu_message =""
state="start"
passport={}  # dic of won stamps(lang,adv,type)
if os.path.exists("passport_city.json"):
    with open("passport_city.json") as f:
        passport = json.load(f)
stamped= False  # has he won
reward_tier =None  # gold,silver,bronze
guide = ""
voice_profile="default"  # my voice
voice_status=""  # msg
voice_done = False
voice_sec=15

guide_lines = {
    "stage_1_learn": "Stage one! Let's learn the words!",
    "stage_2_speak": "Stage two! Let's speak!",
    "stage_3_hunt":  "Stage three! Let's find it!",
    "stage_4_cards": "Stage four! Show your card!",
    "stage_1_speak": "Stage one! Let's speak!",
    "stage_2_hunt":  "Stage two! Let's find it!",
    "stage_3_cards": "Stage three! Show your card!",
    "go_learn":  "Let's learn the words!",
    "go_hunt":   "Hunt time! Let's find it!",
    "go_speak":  "Speak time! Say it out loud!",
    "go_cards":  "Card time! Show me your card!",
    "round_1":   "Round one! Let's start!",
    "round_2":   "Round two! A little harder!",
    "round_3":   "Round three! The last one!",
    "passed":    "You did it! Great job!",
    "failed":    "Oh, we will do it again. We need to get more to pass this round.",
    "stamp_bronze": "You got the bronze stamp!",
    "stamp_silver": "You got the silver stamp!",
    "stamp_gold":   "Wow! You got the gold stamp!",
}

voice_lines = {
    "welcome":   "Welcome to LingoQuest! What is your name?",
    "language":  "Pick a language!",
    "adventure": "Pick your adventure!",
    "stamps":    "Look at all my stamps!",
    "kid_yes_1":  "Nice! I got it!",
    "kid_yes_2":  "Good job, me!",
    "kid_yes_3":  "Amazing! That was cool!",
    "kid_yes_4":  "Cool! I did it!",
    "kid_oops_1": "Oops! Let's try again.",
    "kid_oops_2": "Don't give up!",
    "kid_oops_3": "Almost there! Try again.",
    "kid_oops_4": "That's okay. One more time!",
    # the three places: click and hover
    "kid_home_1":    "I'm at home! Let's start!",
    "kid_school_1":  "I'm at school! Let's start!",
    "kid_outdoor_1": "I'm outside! Let's start!",
    "hover_home":    "Let's start at home!",
    "hover_school":  "Let's go to school!",
    "hover_outdoor": "Let's go outside!",
    # the countries on the map
    "hover_japan":  "Let's see Japan!",
    "hover_france": "Let's see France!",
    "hover_spain":  "Let's see Spain!",
    # trips
    "travel_japan":  "Let's travel to Japan!",
    "travel_france": "Let's travel to France!",
    "travel_spain":  "Let's travel to Spain!",
    "bus_go":        "Let's take the bus!",
}


talks = {
    "welcome": [
        ["Hi {name}! I'm your guide.", "Welcome to LingoQuest!"],
        ["Travel the world and learn", "new words in other languages!"],
        ["Pick a country, then an adventure.", "You will learn the words by", "hunting for real objects!"],
        ["Are you ready?", "Let's pick a country!"],
    ],
    "country_japanese": [
        ["Konnichiwa! Welcome to Japan!", "That means hello."],
        ["Japan is in Asia. The capital", "is Tokyo. The money is the yen."],
        ["You will learn words, then play", "Hunt and Speak to win stars.", "Every round gets harder!"],
        ["We start our tour in Tokyo!", "Where are you right now?"],
    ],
    "country_french": [
        ["Bonjour! Welcome to France!", "That means hello."],
        ["France is in Europe. The capital", "is Paris. The money is the euro."],
        ["You will learn words, then play", "Hunt and Speak to win stars.", "Every round gets harder!"],
        ["We start our tour in Paris!", "Where are you right now?"],
    ],
    "country_spanish": [
        ["Hola! Welcome to Spain!", "That means hello."],
        ["Spain is in Europe. The capital", "is Madrid. The money is the euro."],
        ["You will learn words, then play", "Hunt and Speak to win stars.", "Every round gets harder!"],
        ["We start our tour in Madrid!", "Where are you right now?"],
    ],
    "round_1": [
        ["Welcome! Round 1 is easy.", "You play 4 games:", "Learn, Speak, Hunt and Cards."],
        ["Learn the words, say them out", "loud and find them. Get 5 out", "of 10 to pass. Cards: order online!"],
    ],
    "round_2": [
        ["Round 2! A bit harder.", "Same 4 games, fewer hints."],
        ["Get 7 out of 10 to pass.", "Listen and look well!"],
    ],
    "round_3": [
        ["Round 3! The last one!", "Same 4 games, even fewer hints."],
        ["Get 7 out of 10 to pass.", "You can do it!"],
    ],
    "howto_learn": [
        ["Let's learn the words!", "Press Listen to hear it,", "then press Next."],
    ],
    "howto_cards": [
        ["Show me your card!", "Hold it up to the camera", "and press the button."],
        ["You need the LingoQuest cards", "to play. You can order them", "from our website!"],
    ],
    "howto_hunt": [
        ["Now find it! I say a word.", "Show it to the camera", "and press the button."],
    ],
    "howto_hunt_2": [
        ["Harder! Only the word now.", "Listen, find it, and", "press the button."],
    ],
    "howto_hunt_3": [
        ["Last one! Only listen.", "Find it and press", "the button."],
    ],
    "howto_speak": [
        ["Now say it out loud!", "Press the mic and", "say the word."],
    ],
    "howto_speak_2": [
        ["Harder! The word and a", "small picture. Press the mic", "and say it."],
    ],
    "howto_speak_3": [
        ["Last one! Only the picture.", "Press the mic and", "say it out loud."],
    ],
}


hovered = ""
grow = {"japan": 0.0, "france": 0.0, "spain": 0.0}
last_tick = 0
last_state = ""
travel_start = 0
travel_time = 2600
travel_country = ""
talk_pages = []  # pages of the talk now
talk_key = ""
talk_page = 0
talk_start = 0
talk_after = ""  # screen after the talk
stamp_saved = True
ask_start = 0
star_done = set()
hold_until = 0
kid_talking_until = 0
word_play_at = 0
seen_rounds = set()  # rounds the guide already explained
seen_howto = set()  # modes the guide already explained
box_pos = (250, 330)  # dialogue box
box_width = 540  # height follows your picture
text_pos = (65, 70)  # first line inside the box
line_gap = 32
write_guide = True
tag_pos = (135, 31)
city = 0  # same as stop (the old screens use it)
stop = 0
rnd = 0
stop_adv = ["Home Adventure", "School Adventure", "Outdoor Adventure"]
stop_label = ["Home", "School", "Outdoor"]
levels = [
    {"timer": 0,  "hunt":  {"clue": ["picture", "word", "romaji", "english"], "listens": None},
                  "speak": {"clue": ["picture", "word", "romaji", "english"], "listens": None}},
    {"timer": 0,  "hunt":  {"clue": ["word", "romaji"], "listens": None},
                  "speak": {"clue": ["picture", "word"], "listens": None}},
    {"timer": 0,  "hunt":  {"clue": ["audio"], "listens": None},
                  "speak": {"clue": ["picture"], "listens": 0}},
]
pass_marks = [0.5, 0.7, 0.7]  # answers to pass each round
listens_left = None
round_steps = []
seq_pos = 0  # which one we are in
in_round = False
ask_kind = ""
ask_texts = {"revise": (["Do you want to", "revise the words?"], ["Revise", "Skip"]),
             "cards": (["Do you have your", "LingoQuest cards?"], ["Yes", "Skip"]),
             "harder": (["You got a star!", "What now?"], ["Next round", "Map"]),
             "last": (["All 3 rounds done!", "What now?"], ["Again", "Map"])}
game_passed = True
banner_start = 0  # when the "Round 1" picture showed up
bus_at = -1
bus_from = 0
bus_to = 0
bus_start = 0  # when the bus left (0 = not moving)
bus_time = 3000  # how long the drive takes (ms)
instructions = {"learn": "Look, listen and say it!", "hunt": "Find this and show it to the camera!",
                "cards": "Hold up the card for this word!", "speak": "Press the mic and say the word!"}
test_mode = False
captured = None
flash_until = 0
city_note = ""  # message on the map
city_note_time = 0
time_left = 0  # ms left for this word
timer_index = -1  # the word the timer is counting for
stamps_from = ""
viewing = -1
passport_page = 0  # which two pages of the book we see
menu_states = ("language", "city", "adventure", "choose", "mode", "result", "stamps", "ask", "banner")
plain_menu = True
scaled_cache = {}
icon_cache = {}
stamp_cache = {}

recording= False  # true when mic records
record_start=0  # sec
record_seconds = 3  # how long the mic listens in Speak
hunt_strict = False
record_buffer=None  # recorded sound
heard_text = ""  # what whisper model heards/returns
praised = False  # ture if correct+gj
# ----------- helper functions ----------------
def write(text,y, f=font):
    surface = f.render(text,True,TEXT_DARK)
    screen.blit(surface, surface.get_rect(center=(400,y)))

button_pics = {}
for pic_name in ("button", "button_hover"):
    if os.path.exists("images/ui/" + pic_name + ".png"):
        button_pics[pic_name] = pygame.image.load("images/ui/" + pic_name + ".png").convert_alpha()

def button (rect,label):
    hover = rect.collidepoint(pygame.mouse.get_pos())     
    if hover:
        hover_sound(rect)
    key = "button_hover" if hover else "button"
    if key in button_pics:  # the picture button
        screen.blit(pygame.transform.scale(button_pics[key], rect.size), rect)
        text = (button_font if rect.height < 60 else font).render(label, True, (150, 50, 100))  # dark pink text on the white button
        screen.blit(text, text.get_rect(center=(rect.centerx, rect.centery - 3)))
        return
    color = (255, 140, 190) if hover else (240, 100, 160)  # lighter pink hover
    pygame.draw.rect(screen, (170, 50, 110), rect.move(0, 6), border_radius=20)  # shadow under the button
    pygame.draw.rect(screen, color, rect, border_radius=20)  # the button
    pygame.draw.rect(screen, (90, 20, 80), rect, 4, border_radius=20)  # dark outline
    text = font.render(label, True, (255, 255, 255))
    screen.blit(text, text.get_rect(center=rect.center))

box_pic = pygame.image.load("images/ui/box.png").convert_alpha() if os.path.exists("images/ui/box.png") else None
def draw_panel(rect):
    "white pixel box (images/ui/box.png), the 4 corners stay as they are and the middle stretches"
    if box_pic is None:
        pygame.draw.rect(screen, (251, 246, 236), rect, border_radius=24)
        pygame.draw.rect(screen, OUTLINE_PINK, rect, 4, border_radius=24)
        return
    c = 16  # corner size
    size = box_pic.get_width()
    xs = [(rect.x, c, 0, c), (rect.x + c, rect.w - 2 * c, c, size - 2 * c), (rect.right - c, c, size - c, c)]
    ys = [(rect.y, c, 0, c), (rect.y + c, rect.h - 2 * c, c, size - 2 * c), (rect.bottom - c, c, size - c, c)]
    for dx, dw, sx, sw in xs:
        for dy, dh, sy, sh in ys:
            piece = box_pic.subsurface((sx, sy, sw, sh))
            screen.blit(pygame.transform.scale(piece, (dw, dh)), (dx, dy))

sfx_cache = {}
def find_effect(sound):
    "finds the file even if it is called 'Sfx hover.wav' (looks for the sound name at the end)"
    want = sound.replace("_", "")
    if os.path.isdir("audio/effect"):
        for file_name in os.listdir("audio/effect"):
            stem, ext = os.path.splitext(file_name)
            plain = "".join(c for c in stem.lower() if c.isalpha())
            if ext.lower() in (".wav", ".mp3", ".ogg") and plain.endswith(want):
                return "audio/effect/" + file_name
    return None

def get_effect(sound):
    "loads a sound from audio/effect once"
    if sound not in sfx_cache:
        path = find_effect(sound)
        if path is None:
            print("sound not found in audio/effect:", sound)
        sfx_cache[sound] = make_sound(path) if path is not None else None
        if sfx_cache[sound] is not None and sound == "hover":
            sfx_cache[sound].set_volume(0.4)  # hover is quiet
    return sfx_cache[sound]

def sfx(sound):
    "plays a short sound effect"
    effect = get_effect(sound)
    if effect is not None:
        effect.play()

last_frame = None  # the last picture before the passport
stamps_bg = None  # ... blurred
stamps_veil = pygame.Surface((800, 640), pygame.SRCALPHA)
stamps_veil.fill((255, 255, 255, 70))
hover_now = set()  # rects the mouse is on in this frame
hover_before = set()  # ... and in the frame before
def hover_sound(rect):
    "hover sound once when the mouse arrives on a rect"
    hover_now.add(tuple(rect))
    if tuple(rect) not in hover_before:
        sfx("hover")

def clicked(rect,event):
    return event.type == pygame.MOUSEBUTTONDOWN and rect.collidepoint(event.pos)

def image_button(rect,normal,hover):
    if rect.collidepoint(pygame.mouse.get_pos()):  # mouse on
        hover_sound(rect)
        screen.blit(hover,rect) 
    else:
        screen.blit(normal,rect)  # normal
        
def play_music(path):
    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(0.3)
        pygame.mixer.music.play(-1)  # play on loop
    except Exception as e:
        print("music failed:", path, e)


def play_correct():
    "This function plays sfx sound when ansewer is correct"
    if os.path.exists("audio/effect/correct.wav"):
        make_sound("audio/effect/correct.wav").play()
        
def play_wrong():
    "This function plays sfx sound when ansewer is wrong"
    if os.path.exists("audio/effect/wrong.wav"):
        make_sound("audio/effect/wrong.wav").play()    

def word_picture(english):
    "This function return the image of the word"
    path= "images/vocab/"+english+ ".png"
    if os.path.exists(path):
        return load(path,(240,240))
    return None  # no pic fine
    
def check_object(frame,word):
    "function process img and send it to model through api key from openrouter for object detection using prompt to check weather the vocab mateche the uploaded image, answers with yes or no"
    # convert img -> format for api to take
    small=cv2.resize(frame,(320,240))  # smaller will run faster
    ok,jpg = cv2.imencode(".jpg",small)
    picture= base64.b64encode(jpg.tobytes()).decode()
    prompt= "Is there a " + word + " in this photo? Answer only by yes or no."
    if hunt_strict:
        prompt = "Is there exactly a " + word + " in this photo? Similar objects do not count (a glass is not a cup, a tissue is not a towel). Answer only by yes or no."

    start = time.time()
    try:
        reply = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": "Bearer " + KEY},
            json={
                "model": MODEL,
                "reasoning": {"enabled": False},
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + picture}},
                ]}],
            },
            timeout=30,  # wait 30s for answer
        )
        print(reply.status_code, reply.text[:200])
        text = reply.json()["choices"][0]["message"]["content"]
        with open("hunt_log.csv", "a", encoding="utf-8") as f:
            f.write(",".join([word, text.strip().replace(",", " ")[:20], str(reply.status_code), str(round(time.time() - start, 2))]) + "\n")
        return text.strip().lower().startswith("yes")
    except Exception as error:
        print(" problem:", error)
        return False

def run_card_check(frame, wanted):
    "cards use the same checking flow as hunt"
    global checking, result
    time.sleep(0.8)
    result = detect_card(frame, wanted)
    checking = False

def run_check(frame,word):
    global checking, result
    result=check_object(frame,word)
    checking=False
    
def update_score(score,correct):
    if correct:
        return score + 1
    return score

def play_word(row):
    path=row[audio_column[language]]
    if path.endswith(".mp3") and os.path.exists(path[:-4] + ".ogg"):  # the browser plays ogg, not mp3
        path = path[:-4] + ".ogg"
    if os.path.exists(path):
        sound= make_sound(path)
        sound.set_volume(1.0)  # loudest
        sound.play()
# pretrained model for card prediction
def detect_card (frame, wanted):
    results= model.predict(frame, conf=0.3)
    for box in results[0].boxes:
        if model.names[int(box.cls[0])]==wanted:
            return True
    return False


city_names = {"japanese": ["Tokyo", "Osaka", "Sapporo"],
              "french": ["Paris", "Lyon", "Marseille"],
              "spanish": ["Madrid", "Barcelona", "Seville"]}
city_tier = ["bronze", "silver", "gold"]  # the round gives the stamp color

def get_tier(score,total):
    if score / total >= pass_marks[rnd]:
        return city_tier[rnd]  # enough right = stamp of this round
    return None  # under 0.5 no stamp

def round_done(st, r):
    "true if the stamp of round r is in the passport"
    return city_tier[r] in passport.get(name + "|" + language + "|" + stop_adv[st] + "|round", [])

def stars_of(st):
    "one star for each round passed in a row"
    n = 0
    while n < 3 and round_done(st, n):
        n += 1
    return n

def city_open(c):
    return True  # all stops are open

# --passport--
# stamp function
def save_stamp(tier):
    slot = name + "|" + language + "|" + adventure + "|" + mode
    if slot not in passport:
        passport[slot]= []  # new list for this slot
    if tier not in passport[slot]:
        passport[slot].append(tier)  # add tire  when we dont have it(new)
        with open ("passport_city.json","w") as f:  # write pass to file
            json.dump(passport,f)
# load stamps path
country= {"japanese": "japan", "french": "france", "spanish": "spain"}
stamp_images={}
for c in ("japan","france","spain"):
    for m in ("learn","hunt","speak","cards"):
        for folder in ("images/stamp/", "images/stamps/"):  # your folder is called stamp
            path = folder + "stamp_" + c + "_" + m + ".png"
            if os.path.exists(path):
                stamp_images[(c,m)]= load(path,(320,320))

for c in ("japan","france","spain"):
    if (c, "hunt") in stamp_images:
        stamp_images[(c, "round")] = stamp_images[(c, "hunt")]
for lang in country:
    for i in range(3):
        for folder in ("images/stamp/", "images/stamps/"):
            path = folder + "stamp_" + country[lang] + "_" + city_names[lang][i].lower() + ".png"
            if os.path.exists(path):
                stamp_images[(country[lang], "city", i)] = load(path,(320,320))
# color stamp
def tinted(pic,color):
    copy = pic.copy()
    copy.fill(color, special_flags= pygame.BLEND_RGB_MULT)
    return copy

def lerp(a,b,t):
    return a + (b - a) * t

def phase(elapsed,start,length):
    return max(0, min((elapsed - start) / length, 1))

def book_spot(x, y):
    "the book scene is a bit smaller (0.8) and lower, this moves a point to its new place"
    return (400 + (x - 400) * 0.9, 318 + (y - 290) * 0.9)

def draw_tool(x,y):
    pygame.draw.rect(screen, (120, 70, 40), (x - 25, y - 90, 50, 70), border_radius=10)  # handle
    pygame.draw.rect(screen, (90, 50, 30), (x - 45, y - 25, 90, 25), border_radius=6)  # base

# helpers
guide_big = {"girl": pygame.transform.smoothscale(girl_img, (380, 507)),
             "boy": pygame.transform.smoothscale(boy_img, (380, 507))}
box_file = ""
for folder in ("images/guide/", "images/ui/"):
    for file_name in ("dialog_box.png", "dialogue_box.png"):
        if os.path.exists(folder + file_name):
            box_file = folder + file_name
if box_file != "":
    box_img = pygame.image.load(box_file).convert_alpha()
    box_size = (box_width, int(box_width * box_img.get_height() / box_img.get_width()))
    dialogue_panel = pygame.transform.smoothscale(box_img, box_size)
else:
    box_size = (box_width, 270)
    dialogue_panel = pygame.Surface(box_size, pygame.SRCALPHA)
    pygame.draw.rect(dialogue_panel, (251, 246, 236, 240), dialogue_panel.get_rect(), border_radius=28)
    pygame.draw.rect(dialogue_panel, OUTLINE_PINK, dialogue_panel.get_rect(), 3, border_radius=28)
small_font = soft_font(24)
tag_font = game_font(27)
talk_btn_font = game_font(18)
mid_font = game_font(28)
button_font = game_font(24)
tiny_font = jp_font_of(16)

def scaled_country(c, w, h):
    key = (c, w, h)
    if key not in scaled_cache:
        scaled_cache[key] = pygame.transform.smoothscale(country_big[c], (w, h))
    return scaled_cache[key]

def tag(text, center, f=tag_font, color=(240, 100, 160)):
    surface = f.render(text, True, (255, 255, 255))
    box = surface.get_rect(center=center).inflate(26, 10)
    pygame.draw.rect(screen, color, box, border_radius=14)
    pygame.draw.rect(screen, OUTLINE_PINK, box, 3, border_radius=14)
    screen.blit(surface, surface.get_rect(center=center))

flag_spot = {"japan": (78, 45), "france": (92, -10), "spain": (68, 0)}

flag_rect = {}
flag_drag = ""

def draw_flag(c, place, width, wave, on_map=False, k=1):
    flag = flag_frames[c][(pygame.time.get_ticks() // 150) % 4 if wave else 0]
    height = int(flag.get_height() * width / flag.get_width())
    flag = pygame.transform.scale(flag, (width, height))
    if on_map:
        flag_rect[c] = flag.get_rect(midbottom=(place.centerx + flag_spot[c][0] * k, place.centery + flag_spot[c][1] * k))
        screen.blit(flag, flag_rect[c])
    else:
        screen.blit(flag, flag.get_rect(midbottom=(place.centerx, place.top + flag_height[c])))

label_name = {"japan": "日本語", "france": "Français", "spain": "Español"}
label_english = {"japan": "Japanese", "france": "French", "spain": "Spanish"}
label_font = {"japan": jp_font_of(40), "france": game_font(38), "spain": game_font(38)}
label_small_font = soft_font(20)
map_label_font = game_font(30)

outlined_cache = {}

def draw_outlined(text, f, color, center):
    "text with a white edge, so it shows on any background (made once, then kept)"
    key = (text, id(f), color)
    if key not in outlined_cache:
        white = f.render(text, True, (255, 255, 255))
        main = f.render(text, True, color)
        picture = pygame.Surface((white.get_width() + 8, white.get_height() + 8), pygame.SRCALPHA)
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)):  # the white copies make the round edge
            picture.blit(white, (4 + dx, 4 + dy))
        picture.blit(main, (4, 4))  # the real text on top
        outlined_cache[key] = picture
    picture = outlined_cache[key]
    screen.blit(picture, picture.get_rect(center=center))

def draw_title_box(text, y=40, x=400):
    "the white rounded box with the title of the screen"
    title = font.render(text, True, TEXT_DARK)
    box = title.get_rect(center=(x, y)).inflate(44, 22)
    pygame.draw.rect(screen, (255, 255, 255), box, border_radius=24)
    pygame.draw.rect(screen, (230, 220, 235), box, 3, border_radius=24)
    screen.blit(title, title.get_rect(center=(x, y)))

def draw_countries():
    global last_tick
    now = pygame.time.get_ticks()
    dt = now - last_tick
    last_tick = now
    over = ""
    for c in countries:
        hover = click_area[c].collidepoint(pygame.mouse.get_pos())
        if hover:
            over = c
            grow[c] = min(1, grow[c] + dt / 200)
        else:
            grow[c] = max(0, grow[c] - dt / 200)
        w = int(country_size[c][0] * (1 + grow_amount * grow[c]))
        h = int(country_size[c][1] * (1 + grow_amount * grow[c]))
        pic = scaled_country(c, w, h)
        place = pic.get_rect(center=country_pos[c])
        screen.blit(pic, place)
        draw_flag(c, place, int(64 + 32 * grow[c]), hover, True)
        color = (196, 70, 122) if hover else (66, 40, 76)  # pink on hover, plum normally
        draw_outlined(label_name[c], label_font[c], color, (place.centerx, place.bottom - 20))
        draw_outlined(label_english[c], label_small_font, color, (place.centerx, place.bottom + 14))
    return over

def plane_pos(s):
    x = lerp(-40, 400, s)
    y = lerp(580, 330, s) - math.sin(math.pi * s) * 80
    return x, y

talk_channel = None
talk_has_voice = False
def play_talk(key, page):
    global talk_has_voice
    pygame.mixer.stop()
    path = "audio/voice/talk/" + key + "_" + str(page + 1) + ".wav"
    talk_has_voice = os.path.exists(path)
    hello = ""
    if page == 0 and key.startswith("country_"):
        for ext in (".wav", ".mp3", ".ogg"):
            if os.path.exists("audio/voice/talk/hello_" + key[8:] + ext):
                hello = "audio/voice/talk/hello_" + key[8:] + ext
    if hello != "":
        channel = make_sound(hello).play()
        if talk_has_voice and channel is not None:
            channel.queue(make_sound(path))
    elif talk_has_voice:
        make_sound(path).play()

def start_talk(key, after):
    global state, talk_pages, talk_key, talk_page, talk_start, talk_after
    talk_pages = [[line.replace("{name}", name) for line in page] for page in talks[key]]
    talk_key = key
    talk_page = 0
    talk_start = pygame.time.get_ticks()
    talk_after = after
    state = "talk"
    play_talk(key, 0)

def finish_talk():
    global state
    pygame.mixer.stop()
    state = talk_after
    if talk_after == "language":
        play_voice("language")
    elif talk_after == "adventure":
        play_voice("adventure")
    elif talk_after == "play":
        start_play()
    elif talk_after == "round":
        start_round()
    elif talk_after == "back":
        state = "play"

later_line = ("", 0)
def guide_say_later(name, wait=700):
    "the guide line comes after the round sound"
    global later_line
    later_line = (name, pygame.time.get_ticks() + wait)

def begin_game():
    sfx("round_begin")  # the sound of a new step
    if in_round:
        start_play()
        return
    key = "howto_" + mode + "_" + str(rnd + 1)
    if key not in talks:
        key = "howto_" + mode
    if key in seen_howto:
        if seq_pos > 0:
            guide_say_later("go_" + mode)
        start_play()
    else:
        seen_howto.add(key)
        start_talk(key, "play")  # the guide explains it the first time

def go_stop(i):
    "the bus is at stop i: start the next round of it"
    global stop, city, adventure, rnd
    stop = i
    city = i
    adventure = stop_adv[i]
    rnd = min(stars_of(i), 2)
    round_intro()

def start_round():
    global in_round, seq_pos, round_steps
    in_round = True
    seq_pos = 0
    round_steps = (["learn"] if rnd == 0 else []) + ["speak", "hunt", "cards", "round"]
    start_door(door_titles[round_steps[0]], go_step, "Stage 1", "stage_1_" + round_steps[0])  # the door opens on the first game too

def go_step():
    "next game of the round (revise and cards ask first)"
    global mode, state, ask_kind, banner_start, stamped, reward_tier
    step = round_steps[seq_pos]
    if step == "revise":
        ask_kind = step
        state = "ask"
    elif step == "cards" and len([r for r in df if r["category"] == adventure and r["model_class"] != ""]) == 0:
        next_step()  # no card words in this place
    elif step == "banner":  # the Round 1 picture
        state = "banner"
        banner_start = pygame.time.get_ticks()
    elif step == "round":  # the stamp at the end of the round
        mode = "round"
        stamped = False
        reward_tier = None
        state = "result"
    else:
        mode = step
        state = "play"
        begin_game()

door_start = 0
door_text = ""
door_pending = None  # what happens when the door is closed
door_close_ms, door_hold_ms, door_open_ms = 500, 1200, 500
door_pictures = {}

door_titles = {"learn": "Let's learn!", "speak": "Let's speak!", "hunt": "Let's find it!", "cards": "Show your card!"}
door_plate_color = {"japan": (255, 240, 220), "france": (66, 40, 76), "spain": (50, 90, 170)}  # the text colour on each plate
door_country = "japan"
door_stage = ""
door_open_played = False
door_hold_now = 1200

def voice_length(name):
    "how long the kid's line is (seconds), 0 if there is no file"
    for folder in (voice_profile, "default"):
        path = "audio/voice/" + folder + "/" + name + ".wav"
        if os.path.exists(path):
            return make_sound(path).get_length()
    return 0

def start_door(text, action, stage="", voice=""):
    "the door closes, the plate shows the stage, the next screen is made, the door opens"
    global door_start, door_text, door_pending, door_country, door_stage, door_open_played, door_hold_now
    if door_start != 0:  # a door is already closed: just go on
        action()
        return
    door_start = pygame.time.get_ticks()
    door_text = text
    door_stage = stage
    door_country = country[language]
    door_open_played = False
    door_pending = action
    sfx("door_close")
    door_hold_now = door_hold_ms
    if voice != "" and voice_length(voice) > 0:
        door_hold_now = int(voice_length(voice) * 1000) + 300
        guide_say_later(voice, door_close_ms)

found_pictures = {}
def find_picture(file_name):
    "looks for a picture in images/ and all its folders (once)"
    if not found_pictures:
        for folder, _, files in os.walk("images"):
            for f in files:
                found_pictures.setdefault(f, os.path.join(folder, f).replace("\\", "/"))
    return found_pictures.get(file_name)

def door_panel(side):
    "one half of the door: images/ui/door_<country>_<side>.png (or door_<side>.png), or a paper door we draw"
    key = (door_country, side)
    if key not in door_pictures:
        file_path = find_picture("door_" + door_country + "_" + side + ".png")
        picture = ui_img(file_path, (400, 640)) if file_path else None
        if picture is None:
            print("door picture not found: images/ui/door_" + door_country + "_" + side + ".png (using the plain door)")
            picture = pygame.Surface((400, 640))
            picture.fill((150, 100, 70))  # wood
            pygame.draw.rect(picture, (250, 241, 219), (14, 14, 372, 612))  # paper
            for x in range(14, 400, 93):
                pygame.draw.line(picture, (150, 100, 70), (x, 14), (x, 626), 6)
            for y in range(14, 640, 102):
                pygame.draw.line(picture, (150, 100, 70), (14, y), (386, y), 6)
            pygame.draw.rect(picture, (110, 70, 50), (0, 0, 400, 640), 8)
        door_pictures[key] = picture
    return door_pictures[key]

door_open_t0 = 0

def draw_door():
    global door_start, door_pending, door_open_t0
    if door_start == 0:
        return
    now = pygame.time.get_ticks()
    t = now - door_start
    opening = door_open_t0 != 0
    if opening:
        p = 1 - (now - door_open_t0) / door_open_ms
        if p <= 0:
            door_start = 0
            door_open_t0 = 0
            return
    else:
        p = min(1, t / door_close_ms)
    p = p * p * (3 - 2 * p)
    screen.blit(door_panel("left"), (int(-400 + 400 * p), 0))
    screen.blit(door_panel("right"), (int(800 - 400 * p), 0))
    if not opening and t >= door_close_ms * 0.8:  # the plate with the stage and the title
        plate_path = find_picture("plate_" + door_country + ".png")
        plate = ui_img(plate_path) if plate_path else None
        if plate is not None:
            screen.blit(plate, plate.get_rect(center=(400, 320)))
        else:
            pygame.draw.rect(screen, (250, 241, 219), (200, 270, 400, 100), border_radius=14)
            pygame.draw.rect(screen, PLUM, (200, 270, 400, 100), 4, border_radius=14)
        color = door_plate_color[door_country] if plate is not None else PLUM
        if door_stage != "":
            ui_text(door_stage, small_font, color, center=(400, 305))
        ui_text(door_text, game_font(34), color, center=(400, 338 if door_stage != "" else 320), max_width=340)
    if not opening and t >= door_close_ms + door_hold_now:
        if door_pending is not None:
            action = door_pending
            door_pending = None
            action()
        sfx("door_open")
        door_open_t0 = pygame.time.get_ticks()

def next_step():
    "after a game: the next game of the round, or the end of the round"
    global seq_pos
    if door_pending is not None:  # the door is already on its way
        return
    seq_pos += 1
    if seq_pos < len(round_steps):
        if round_steps[seq_pos] in door_titles:
            start_door(door_titles[round_steps[seq_pos]], go_step, "Stage " + str(seq_pos + 1), "stage_" + str(seq_pos + 1) + "_" + round_steps[seq_pos])
        else:
            go_step()
    else:
        finish_round()

def round_intro():
    "the guide explains the round only the first time"
    if rnd in seen_rounds:
        sfx("round_begin")
        guide_say_later("round_" + str(rnd + 1))
        start_round()
    else:
        seen_rounds.add(rnd)
        start_talk("round_" + str(rnd + 1), "round")

def finish_round():
    global in_round, state, ask_kind, city_note, city_note_time, ask_start
    in_round = False
    play_music("audio/music/" + country[language] + ".ogg")
    ask_kind = "harder" if rnd < 2 else "last"
    state = "ask"
    ask_start = pygame.time.get_ticks()
    star_done.clear()

def next_game():
    "the name of the game that comes after this one in the round (cards are skipped if this place has none)"
    k = seq_pos + 1
    while k < len(round_steps):
        step = round_steps[k]
        if step == "cards" and len([r for r in df if r["category"] == adventure and r["model_class"] != ""]) == 0:
            k += 1
            continue
        return step
    return "round"

next_lines = {
    "speak": ["Now let's play Speak!", "Say each word out loud."],
    "hunt":  ["Now let's play Hunt!", "Find it with the camera."],
    "cards": ["Now it's card time!", "Show me your card."],
    "round": ["You finished the round!", "Let's get your stamp."],
}

def will_explain():
    "the next game has a how-to talk the kid has not seen yet"
    step = next_game()
    if step == "round":
        return False
    key = "howto_" + step + "_" + str(rnd + 1)
    if key not in talks:
        key = "howto_" + step
    return key not in seen_howto

def result_ready():
    "the stamp animation is over (or this game has no stamp)"
    return mode != "round" or pygame.time.get_ticks() - result_time >= 5200 + stamp_wait

def box_label():
    "the little pink tab of the dialogue box"
    if state == "talk" and talk_key.startswith("round_"):
        return "Round " + talk_key[-1]
    if state == "talk" and talk_key.startswith("howto_"):
        return talk_key[6:].split("_")[0].capitalize()
    if in_round:
        return "Round " + str(rnd + 1)
    return "Guide"

say_seen = 0  # the last time the guide was drawn here
say_start = 0

def draw_say(lines, jump=0, pose=""):
    "the guide with the dialogue box, like in the talks"
    global bob_phase, bob_speed, bob_last
    now = pygame.time.get_ticks()
    bob_speed += (1 / 600 - bob_speed) * 0.08
    bob_phase += min(now - bob_last, 100) * bob_speed
    bob_last = now
    picture = guide_big[guide]
    if pose != "":  # another pose of the guide (sad)
        other = ui_img(("images/guide/guide_boy_" if guide == "boy" else "images/guide/guide_") + pose + ".png", (380, 507))
        if other is not None:
            picture = other
    screen.blit(picture, picture.get_rect(midbottom=(160, 645 + int(math.sin(bob_phase) * 4))))
    screen.blit(dialogue_panel, box_pos)
    if write_guide:
        guide_tag = tag_font.render(box_label(), True, (255, 255, 255))
        screen.blit(guide_tag, guide_tag.get_rect(center=(box_pos[0] + tag_pos[0], box_pos[1] + tag_pos[1])))
    room = box_size[0] - text_pos[0] - 40
    for i, line in enumerate(lines):
        text = (font if i == 0 else small_font).render(line, True, TEXT_DARK)
        if text.get_width() > room:
            text = pygame.transform.smoothscale(text, (room, text.get_height()))
        y = box_pos[1] + text_pos[1] + (0 if i == 0 else 44 + (i - 1) * line_gap)
        screen.blit(text, (box_pos[0] + text_pos[0], y))

bob_phase = 0  # where the guide is in her bounce
bob_speed = 1 / 200
bob_last = 0

overview = [("learn", "Learn", "see it"), ("speak", "Speak", "say it"), ("hunt", "Hunt", "find it"), ("cards", "Cards", "show it")]

def draw_round_overview():
    "the 4 games of the round, next to each other, at the start of the round talk"
    for k, (m, a, b) in enumerate(overview):
        x = 340 + k * 105
        screen.blit(mode_icon[m], mode_icon[m].get_rect(center=(x, 235)))
        name_text = small_font.render(a, True, TEXT_DARK)
        screen.blit(name_text, name_text.get_rect(center=(x, 292)))
        verb_text = r_small_font.render(b, True, (140, 120, 150))
        screen.blit(verb_text, verb_text.get_rect(center=(x, 318)))

def draw_talk(now):
    global talk_channel, bob_phase, bob_speed, bob_last
    page = talk_pages[talk_page]
    letters = (now - talk_start) // 45  # 1 letter every 45 ms
    typing = letters < sum(len(line) for line in page)
    bob_speed += ((1 / 200 if typing else 1 / 600) - bob_speed) * 0.08  # she slows down slowly, no jump
    bob_phase += min(now - bob_last, 100) * bob_speed
    bob_last = now
    bob = int(math.sin(bob_phase) * 4)
    blip = get_effect("talk_soft")
    if blip is not None and not talk_has_voice:
        if typing and (talk_channel is None or not talk_channel.get_busy()):
            talk_channel = blip.play(-1)  # loop
        elif not typing and talk_channel is not None:
            talk_channel.stop()
            talk_channel = None
    if talk_key.startswith("round_"):
        draw_round_overview()
    picture = guide_big[guide]
    screen.blit(picture, picture.get_rect(midbottom=(160, 645 + bob)))
    screen.blit(dialogue_panel, box_pos)
    if write_guide:
        guide_tag = tag_font.render(box_label(), True, (255, 255, 255))
        screen.blit(guide_tag, guide_tag.get_rect(center=(box_pos[0] + tag_pos[0], box_pos[1] + tag_pos[1])))
    for i, line in enumerate(page):
        text = small_font.render(line[:max(0, letters)], True, TEXT_DARK)
        room = box_size[0] - text_pos[0] - 40
        full = small_font.size(line)[0]
        if full > room:  # long line, shrink it to fit the box
            text = pygame.transform.smoothscale(text, (text.get_width() * room // full, text.get_height()))
        screen.blit(text, (box_pos[0] + text_pos[0], box_pos[1] + text_pos[1] + i * line_gap))
        letters -= len(line)
    if talk_key.startswith(("round_", "howto_")):
        back_icon()
    last = talk_page == len(talk_pages) - 1
    small_button(talk_next_btn, "I'm ready!" if last else "Next", talk_btn_font)
    if not last:
        small_button(talk_skip_btn, "Skip", talk_btn_font)

def small_button(rect, label, f=button_font):
    hover = rect.collidepoint(pygame.mouse.get_pos())
    if hover:
        hover_sound(rect)
    pygame.draw.rect(screen, (255, 140, 190) if hover else (240, 100, 160), rect, border_radius=16)
    pygame.draw.rect(screen, OUTLINE_PINK, rect, 3, border_radius=16)
    text = f.render(label, True, (255, 255, 255))
    screen.blit(text, text.get_rect(center=rect.center))

def passport_button(rect, label):  # red like the passport
    hover = rect.collidepoint(pygame.mouse.get_pos())
    if hover:
        hover_sound(rect)
    pygame.draw.rect(screen, (240, 120, 120) if hover else (225, 95, 95), rect, border_radius=16)
    pygame.draw.rect(screen, (60, 30, 45), rect, 4, border_radius=16)
    text = mid_font.render(label, True, (255, 255, 255))
    screen.blit(text, text.get_rect(center=rect.center))

def tip(text, rect):
    if rect.collidepoint(pygame.mouse.get_pos()):
        surface = small_font.render(text, True, (255, 255, 255))
        box = surface.get_rect(center=(rect.centerx, rect.top - 24 if rect.top > 50 else rect.bottom + 24)).inflate(20, 10)
        pygame.draw.rect(screen, OUTLINE_PINK, box, border_radius=10)
        screen.blit(surface, surface.get_rect(center=box.center))


# the setup lines of play (moved here so learn can use them too)
def listens_of():
    "how many listens this game gives (None = no limit)"
    if mode == "learn":
        return None
    return levels[rnd]["speak" if mode == "speak" else "hunt"]["listens"]

cards_per_place = 7

fixed_words = True
my_items = {"Home Adventure": ["cup", "key"],
            "School Adventure": ["book", "pencil case", "pencil", "glue", "eraser", "scissors"],
            "Outdoor Adventure": ["ball", "stone", "flower"]}
my_order = {a: {m: items for m in ("learn", "speak", "hunt", "cards")} for a, items in my_items.items()}

diag_mode = 1
diag = {"hunt": "-", "speak": "-", "cards": "-"}
back_from = -1
came_to = -1  # the word we went back to
card_accuracy = {"car": .96, "ball": .95, "pencil_case": .94, "chair": .94, "stone": .93, "cloud": .92, "cup": .92, "pillow": .91, "book": .91,
                 "tree": .90, "sun": .90, "backpack": .90, "towel": .89, "apple": .88, "clock": .88, "road": .86, "lamp": .86, "paper": .85,
                 "pencil": .85, "key": .84, "scissors": .83, "glue": .83, "bowl": .81, "teddy_bear": .80, "calculator": .79, "ruler": .78,
                 "shoe": .73, "spoon": .73, "banana": .72, "flower": .71, "toothbrush": .68, "house": .68, "bicycle": .68, "eraser": .66}  # from the model tests

def start_play():
    global back_from, came_to
    back_from = -1
    came_to = -1
    global word_results, words, index, score, stamped, reward_tier, menu_message, state, message, heard_text, recording, timer_index, listens_left, in_round, kid_talking_until, word_play_at
    mine = my_order.get(adventure, {}).get(mode, [])
    words = [r for r in df if r["category"] == adventure]
    if mode == "cards":
        words = [r for r in words if r["model_class"] != ""]
        best = sorted({r["model_class"] for r in words}, key=lambda c: -card_accuracy.get(c, 0))[:cards_per_place]
        words = [r for r in words if r["model_class"] in best or r["english"] in mine]
    if mode == "hunt":
        words = [r for r in words if r["english"] not in ("apple", "banana") or r["english"] in mine]  # no apple and banana in Hunt
    first = [r for name_ in mine for r in words if r["english"] == name_]
    rest = [r for r in words if r["english"] not in mine]
    if not fixed_words:
        random.shuffle(rest)
    words = (first + rest)[:10]
    index=0
    word_results = [None] * len(words)
    timer_index = -1
    if listens_of() is None:
        listens_left = None
    else:
        listens_left = int(len(words) * listens_of())
    score=0
    stamped=False
    reward_tier=None
    menu_message= "" 
    kid_talking_until = 0
    if len(words) == 0:
        state = "city"
        in_round = False
        menu_message = "Coming soon!"
    # speak
    elif mode == "speak":
        message = ""
        heard_text=""
        recording=False
    # learn
    elif mode=="learn":
        message=""
        if listens_left is None:
            word_play_at = max(kid_talking_until, pygame.time.get_ticks() + 2000)  # 2 seconds to look first
    # hunt
    elif mode == "hunt":
        message = ""
    else:
        message = ""

def stamp_spot(i):
    "where stamp number i is in the book (9 on each page), None if it is on another spread"
    i -= passport_page * 18
    if i < 0 or i >= 18:
        return None
    page_x = (112, 413)[i // 9]
    k = 760 / 700  # the book is bigger now
    return (int(20 + (page_x + (i % 9 % 3) * 92 + 10 - 50) * k), int(65 + (150 + (i % 9 // 3) * 108 - 75) * k))

stamp_size = 78

def passport_stamps():
    "every stamp of this kid as (slot, tier), one for each color he won"
    out = []
    for slot in passport:
        if slot.startswith(name + "|"):
            for tier in city_tier:
                if tier in passport[slot]:
                    out.append((slot, tier))
    return out

def draw_icon(rect, icon):
    if rect.collidepoint(pygame.mouse.get_pos()):
        hover_sound(rect)
    r = rect.inflate(10, 10) if rect.collidepoint(pygame.mouse.get_pos()) else rect
    key = (id(icon), r.size)
    if key not in icon_cache:
        icon_cache[key] = pygame.transform.smoothscale(icon, r.size)
    screen.blit(icon_cache[key], r)

def back_icon():
    draw_icon(back_btn, icon_back)
    tip("Back", back_btn)

city_btn = [pygame.Rect(0, 0, 104, 128) for i in range(3)]
city_spots = {"japanese": ((465, 400), (330, 455), (530, 170)),
              "french": ((400, 260), (560, 380), (430, 540)),
              "spanish": ((400, 330), (620, 260), (240, 500))}
city_sprites = {}
for c in ("japan", "france", "spain"):
    for n in (1, 2, 3):
        sprite_file = "images/ui/city_" + c + "_" + str(n) + ".png"
        if os.path.exists(sprite_file):
            city_sprites[(c, n)] = pygame.image.load(sprite_file).convert_alpha()
kit_ok = os.path.exists("images/city_kit/city_map_bg.png")
kit_tips = ((313, 630), (654, 497), (995, 364))
kit_land = {}

def kit(path, height):
    "load a kit picture and make it this tall (the width follows)"
    pic = pygame.image.load("images/city_kit/" + path).convert_alpha()
    return pygame.transform.smoothscale(pic, (int(pic.get_width() * height / pic.get_height()), height))
pin_height = 84
land_height = 120
star_height = 26

if kit_ok:
    kit_bg = pygame.transform.smoothscale(pygame.image.load("images/city_kit/city_map_bg.png").convert(), (800, 640))
    kit_pin = {n: kit("pins/pin_" + n + ".png", pin_height) for n in ("open", "open_2", "locked", "done")}
    kit_star = {n: kit("stars/star_" + n + ".png", star_height) for n in ("full", "empty")}

def land_pic(i, locked):
    "the picture of stop i: japan_home.png, japan_school.png, japan_outdoor.png (the old city ones if missing)"
    for file in (country[language] + "_" + stop_label[i].lower(), country[language] + "_" + city_names[language][i].lower()):
        if file not in kit_land:
            path = "images/city_kit/landmarks/" + file + ".png"
            kit_land[file] = kit("landmarks/" + file + ".png", land_height) if os.path.exists(path) else None
        if kit_land[file] is not None:
            return kit_land[file]
    return None

bus_img = pygame.image.load("images/ui/bus.png").convert_alpha() if os.path.exists("images/ui/bus.png") else None
if bus_img is not None:
    bus_img = pygame.transform.scale(bus_img, (72, 42))

def kit_tip(i):
    return (int(kit_tips[i][0] * 800 / 1152), int(kit_tips[i][1] * 640 / 928))

def draw_bus():
    "the bus waits at its stop, or drives to the stop you picked"
    if bus_start > 0:
        t = min(1, (pygame.time.get_ticks() - bus_start) / bus_time)
        a = kit_tip(bus_from)
        b = kit_tip(bus_to)
        x = lerp(a[0], b[0], t) + 62
        y = lerp(a[1], b[1], t) + 10 - abs(math.sin(t * 40)) * 3  # a little bounce
    else:
        x = kit_tip(bus_at)[0] + 62
        y = kit_tip(bus_at)[1] + 10
    if bus_img is not None:
        screen.blit(bus_img, bus_img.get_rect(midbottom=(x, y)))
    else:
        pygame.draw.rect(screen, (90, 20, 80), (x - 37, y - 37, 74, 32), border_radius=8)  # body (outline)
        pygame.draw.rect(screen, (255, 214, 90), (x - 34, y - 34, 68, 26), border_radius=6)
        for k in range(3):
            pygame.draw.rect(screen, (170, 220, 245), (x - 28 + k * 20, y - 30, 15, 12))  # windows
        pygame.draw.rect(screen, (240, 100, 160), (x - 34, y - 14, 68, 6))  # pink stripe
        for wx in (-20, 20):
            pygame.draw.circle(screen, (90, 20, 80), (x + wx, y - 5), 7)  # wheels
            pygame.draw.circle(screen, (255, 255, 255), (x + wx, y - 5), 3)

def draw_stars(n, y, height=46, elapsed=99999, cx=400, quiet=False):
    "3 stars in a row, n of them full. The full ones pop in one by one"
    for k in range(3):
        x = cx + (k - 1) * (height + 14)
        t = elapsed - 500 - k * 500  # time since this star showed up
        full = k < n and t >= 0
        grow = 1.0
        if full:
            if not quiet and k not in star_done:
                star_done.add(k)
                if get_effect("star") is not None:
                    sfx("star")
                else:
                    play_correct()
            if t < 400 and not quiet:
                grow = 1 + 0.7 * math.sin(math.pi * t / 400)  # pop
        size = int(height * grow)
        if kit_ok:
            pic = kit_star["full" if full else "empty"]
            pic = pygame.transform.scale(pic, (int(pic.get_width() * size / pic.get_height()), size))
            screen.blit(pic, pic.get_rect(center=(x, y)))
        else:
            pygame.draw.circle(screen, (255, 200, 60) if full else (200, 190, 200), (x, y), size // 2)
        if full and k == n - 1 and t < 900 and not quiet:  # little sparkles around the new star
            for a in range(6):
                ang = a * math.pi / 3 + t / 300
                r = height * 0.6 + t / 12
                pygame.draw.rect(screen, (255, 230, 120), (int(x + math.cos(ang) * r) - 3, int(y + math.sin(ang) * r) - 3, 6, 6))

stamp_facts = {
    ("japan", "home"): "In Japan, people take their shoes off at home.",
    ("japan", "school"): "Japanese students clean their classroom every day.",
    ("japan", "outdoor"): "Parks in Japan are full of cherry blossoms in spring.",
    ("france", "home"): "Many French families eat bread with every meal.",
    ("france", "school"): "French students get a long lunch break at school.",
    ("france", "outdoor"): "France has big parks and gardens in every city.",
    ("spain", "home"): "In Spain, dinner is often late, around 9 pm.",
    ("spain", "school"): "Spanish kids often greet with two kisses on the cheeks.",
    ("spain", "outdoor"): "Spanish towns have a plaza where everyone meets.",
}
stamp_text = {"bronze": "Bronze stamp: you finished Round 1!",
              "silver": "Silver stamp: you finished Round 2!",
              "gold": "Gold stamp: you finished all 3 rounds!"}

def draw_city_kit(i):
    tip = (int(kit_tips[i][0] * 800 / 1152), int(kit_tips[i][1] * 640 / 928))
    is_open = True
    stars = stars_of(i)
    if stars >= 3:
        pin = kit_pin["done"]
    elif i == bus_at or city_btn[i].collidepoint(pygame.mouse.get_pos()):
        pin = kit_pin["open_2"] if (pygame.time.get_ticks() // 400) % 2 else kit_pin["open"]  # the pin of the bus bounces
    else:
        pin = kit_pin["open"]
    land = land_pic(i, not is_open)
    land_rect = pygame.Rect(0, 0, 0, 0)
    if land is not None:
        land_rect = land.get_rect(bottomright=(tip[0] - 38, tip[1] + 6))  # a bit left and below the pin
        screen.blit(land, land_rect)
    pin_rect = pin.get_rect(midbottom=tip)
    screen.blit(pin, pin_rect)
    if is_open:
        for k in range(3):
            star = kit_star["full" if k < stars else "empty"]
            screen.blit(star, star.get_rect(center=(tip[0] + (k - 1) * 30, tip[1] - pin_height - 18)))
    draw_outlined(stop_label[i], map_label_font, PLUM, (min(max(tip[0], 80), 720), tip[1] + 32))
    city_btn[i] = land_rect.union(pin_rect)  # click on the landmark or the pin
    if is_open and city_btn[i].collidepoint(pygame.mouse.get_pos()):
        hover_sound(city_btn[i])

locked_cache = {}
def locked_sprite(key):
    if key not in locked_cache:
        grey = city_sprites[key].copy()
        for x in range(grey.get_width()):  # make every pixel grey (done once)
            for y in range(grey.get_height()):
                r, g, b, a = grey.get_at((x, y))
                if a > 0:
                    v = int((r + g + b) / 3 * 0.8 + 40)
                    grey.set_at((x, y), (v, v, v + 10, a))
        locked_cache[key] = grey
    return locked_cache[key]

def draw_star(cx, cy, size, color):
    points = []
    for k in range(10):
        angle = -math.pi / 2 + k * math.pi / 5
        radius = size if k % 2 == 0 else size * 0.45
        points.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
    pygame.draw.polygon(screen, color, points)
    pygame.draw.polygon(screen, TEXT_DARK, points, 2)

pin_cache = {}
def pin_sprite(color):
    "a pixel map pin: drawn small, then scaled up so it stays pixel art"
    if color not in pin_cache:
        small = pygame.Surface((26, 34), pygame.SRCALPHA)
        pygame.draw.circle(small, TEXT_DARK, (13, 13), 13)
        pygame.draw.polygon(small, TEXT_DARK, [(2, 19), (24, 19), (13, 34)])
        pygame.draw.circle(small, color, (13, 13), 10)
        pygame.draw.polygon(small, color, [(5, 19), (21, 19), (13, 30)])
        pygame.draw.circle(small, (255, 255, 255), (8, 8), 2)  # little shine
        pin_cache[color] = pygame.transform.scale(small, (78, 102))
    return pin_cache[color]

def draw_city(i):
    if kit_ok:
        draw_city_kit(i)
        return
    r = city_btn[i]
    is_open = city_open(i)
    hover = r.collidepoint(pygame.mouse.get_pos()) and is_open
    lift = 0
    if hover:
        hover_sound(r)
        lift = -8
    stars = stars_of(i)
    key = (country[language], i + 1)
    if key in city_sprites:
        pic = city_sprites[key] if is_open else locked_sprite(key)
        screen.blit(pic, pic.get_rect(midbottom=(r.centerx, r.bottom + lift)))
        if is_open:
            pygame.draw.circle(screen, (240, 100, 160), (r.left + 8, r.top + 16 + lift), 18)
            pygame.draw.circle(screen, TEXT_DARK, (r.left + 8, r.top + 16 + lift), 18, 3)
            number = small_font.render(str(i + 1), True, (255, 255, 255))
            screen.blit(number, number.get_rect(center=(r.left + 8, r.top + 16 + lift)))
            for k in range(3):
                draw_star(r.centerx + (k - 1) * 30, r.bottom + 34, 13, tier_color[city_tier[i]] if k < stars else (200, 195, 210))
        else:
            draw_lock((r.centerx, r.centery + lift))
        tag(city_names[language][i], (r.centerx, r.bottom + 72))
        return
    # no picture file: a map pin instead
    top = r.centery - 39 + lift
    screen.blit(pin_sprite((240, 100, 160) if is_open else (150, 150, 160)), (r.centerx - 39, top))
    head = (r.centerx, top + 39)
    if is_open:
        number = mid_font.render(str(i + 1), True, (255, 255, 255))
        screen.blit(number, number.get_rect(center=head))
    else:
        draw_lock((head[0], head[1] + 4))
    if is_open:
        for k in range(3):
            draw_star(r.centerx + (k - 1) * 30, top + 116, 14, tier_color[city_tier[i]] if k < stars else (200, 195, 210))
    tag(city_names[language][i], (r.centerx, top + 150))

box_images = {}
for box_name in ("box_card", "box_card_hover", "box_wide", "box_wide_hover"):
    if os.path.exists("images/ui/" + box_name + ".png"):
        box_images[box_name] = pygame.image.load("images/ui/" + box_name + ".png").convert_alpha()

def box_picture(box_name, size):
    "the box picture in the size we need (None if the file is missing)"
    if box_name not in box_images:
        return None
    key = (box_name, size)
    if key not in scaled_cache:
        scaled_cache[key] = pygame.transform.smoothscale(box_images[box_name], size)
    return scaled_cache[key]

def draw_lock(center):
    pygame.draw.arc(screen, (255, 255, 255), (center[0] - 14, center[1] - 34, 28, 34), 0, math.pi, 6)
    pygame.draw.rect(screen, (255, 255, 255), (center[0] - 22, center[1] - 8, 44, 34), border_radius=6)

def draw_box(rect, icon, lines, selected=False, locked=False, done=False, stars=None):
    hover = rect.collidepoint(pygame.mouse.get_pos()) and not locked
    r = rect
    if hover:
        hover_sound(rect)
        r = r.move(0, -8)
    picture = box_picture("box_card_hover" if hover else "box_card", r.size)
    if picture is not None:
        screen.blit(picture, r)
    else:  # no picture: draw the box
        pygame.draw.rect(screen, (251, 246, 236), r, border_radius=28)
        pygame.draw.rect(screen, (240, 100, 160) if hover else OUTLINE_PINK, r, 3, border_radius=28)
    screen.blit(icon, icon.get_rect(center=(r.centerx, r.top + 98)))
    for i, line in enumerate(lines):
        text = small_font.render(line, True, TEXT_DARK)
        screen.blit(text, text.get_rect(center=(r.centerx, r.top + 184 + i * 30)))
    if stars is not None:  # the stars of this stop
        draw_stars(stars, r.top + 30, 26, cx=r.centerx, quiet=True)
    if locked:
        shade = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (60, 60, 70, 170), shade.get_rect(), border_radius=28)
        screen.blit(shade, r)
        draw_lock(r.center)

def draw_bar(rect, icons, label):
    hover = rect.collidepoint(pygame.mouse.get_pos())
    if hover:
        hover_sound(rect)
    picture = box_picture("box_wide_hover" if hover else "box_wide", rect.size)
    if picture is not None:
        screen.blit(picture, rect)
    else:
        pygame.draw.rect(screen, (251, 246, 236), rect, border_radius=28)
        pygame.draw.rect(screen, (240, 100, 160) if hover else OUTLINE_PINK, rect, 3, border_radius=28)
    x = rect.x + 24
    for icon in icons:
        screen.blit(icon, (x, rect.centery - 32))
        x += 70
    text = font.render(label, True, TEXT_DARK)
    screen.blit(text, text.get_rect(midleft=(x + 14, rect.centery)))

def stop_mic():
    global recording
    if recording:
        sd.stop()
        recording = False

def icons_on():
    if in_round or (state == "talk" and talk_key.startswith("round")):
        return False  # in a round only the back button
    return state not in ("stamps", "dictionary") and state in menu_states or (state == "talk" and talk_key != "welcome")

def go_home():
    global state, in_round
    in_round = False
    stop_mic()
    pygame.mixer.stop()
    state = "start" if state == "language" else "language"  # on the map, home = main menu
    play_music("audio/music/menu.ogg")

def stop_background():
    "background of the stop we are at (None if there is none)"
    if language in country and adventure != "":
        return backgrounds.get((country[language], adventure.split()[0].lower()))
    return None

# SPEACH FUNCTIONS
jp_font = jp_font_of(30)  # small font that can show Japanese


def clean_ja(text): 
    text = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text.lower())
    out = ""
    for c in text:
        if c == "ー":  # long sound mark
            continue
        if c == "う" and out != "" and out[-1] in "おこそとのほもよろをごぞどぼぽょうくすつぬふむゆるぐずづぶぷゅ":  # じょうぎ = ジョーギー
            continue
        if c == "い" and out != "" and out[-1] in "えけせてねへめれげぜでべぺ":  # せんせい = センセー
            continue
        out += c
    return "".join(c for c in out.replace("っ", "") if c.isalnum())

def check_japanese(row, heard):
    for column in ["ja_show", "ja_kanji", "ja_hiragana", "ja_katakana", "romaji", "accept_ja"]:
        for answer in str(row[column]).split("|"):
            if answer.strip() != "" and clean_ja(answer) in clean_ja(heard):
                return True
    return False

def clean_other(text):
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return "".join(c for c in text if c.isalnum())

def check_other(row, language, heard):
    if language == "french":
        columns = ["french", "accept_fr"]
    else:
        columns = ["spanish", "accept_es"]
    for column in columns:
        for answer in str(row[column]).split("|"):
            if answer.strip() != "" and clean_other(answer) in clean_other(heard):
                return True
    return False
    
mic_picture = pygame.image.load("images/ui/mode_speak.png").convert_alpha()
def draw_mic():
    size = 120
    if recording:
        size += int(math.sin(pygame.time.get_ticks() / 120) * 10)  # the mic pulses while recording
    icon = pygame.transform.smoothscale(mic_picture, (size, size))
    screen.blit(icon, icon.get_rect(center=mic_btn.center))

def draw_listen():
    "listen button: how many are left, no button when there are none"
    if listens_left is None:
        button(listen_btn, "Listen")
    elif listens_of() > 0:
        button(listen_btn, "Listen " + str(listens_left))

def fit_word(text, max_width):
    "a long word is made smaller so it stays inside the box"
    if text.get_width() <= max_width:
        return text
    return pygame.transform.smoothscale(text, (max_width, int(text.get_height() * max_width / text.get_width())))

def draw_clue(row):
    "what the kid sees for this word (depends on the game and the round)"
    if mode == "learn":
        clue = ["word", "romaji", "english"]
    else:
        clue = levels[rnd]["speak" if mode == "speak" else "hunt"]["clue"]
    if "audio" in clue:  # hunt, round 3: only the sound
        draw_panel(pygame.Rect(215, 124, 370, 100))
        write("Listen and find it!", 150, mid_font)
        write("Press Listen to hear it again.", 195, small_font)
        return
    small = []
    if "romaji" in clue and language == "japanese":
        small.append(row["romaji"])
    if "english" in clue:
        small.append(row["english"])
    picture = word_picture(row["english"]) if "picture" in clue else None
    if mode == "speak":
        if "word" in clue:
            word_text = fit_word(word_font.render(row[show_column[language]], True, TEXT_DARK), 400)
            if picture is not None:
                picture = pygame.transform.scale(picture, (72, 72))
            width = word_text.get_width() + (72 + 14 if picture else 0)
            box_width = max(370, width + 50)  # the box grows with the word
            draw_panel(pygame.Rect(400 - box_width // 2, 124, box_width, 138))
            left = 400 - width // 2
            screen.blit(word_text, word_text.get_rect(midleft=(left, 178)))
            if picture:
                screen.blit(picture, picture.get_rect(midleft=(left + word_text.get_width() + 14, 178)))
        elif picture is not None:  # round 3: only the picture
            draw_panel(pygame.Rect(300, 124, 200, 160))
            picture = pygame.transform.scale(picture, (130, 130))
            screen.blit(picture, picture.get_rect(center=(400, 204)))
        if small:
            write("  -  ".join(small), 240, small_font)
        return
    else:
        if picture is not None:
            picture = pygame.transform.scale(picture, (72, 72))
        word_text = fit_word(word_font.render(row[show_column[language]], True, TEXT_DARK), 400)
        width = word_text.get_width() + (72 + 14 if picture else 0)
        box_width = max(370, width + 50)  # the box grows with the word
        draw_panel(pygame.Rect(400 - box_width // 2, 124, box_width, 130 if mode == "learn" else 112))
        left = 400 - width // 2  # word and picture are centered together
        screen.blit(word_text, word_text.get_rect(midleft=(left, 152)))
        if picture:
            screen.blit(picture, picture.get_rect(midleft=(left + word_text.get_width() + 14, 152)))
        write("  -  ".join(small), 208, small_font)
        if mode == "learn":
            write(instructions[mode], 233, small_font)

def is_correct(row, language, heard):
    if language == "japanese":
        return check_japanese(row, heard)
    return check_other(row, language, heard)

speech_provider = "openrouter"
local_backup = False
AUDIO_KEY = os.getenv("AUDIO_KEY") or KEY
GROQ_KEY = ""  # (only if you use groq)
speech_url = {"groq": "https://api.groq.com/openai/v1/audio/transcriptions",
              "openrouter": "https://openrouter.ai/api/v1/audio/transcriptions"}
speech_model = {"groq": "whisper-large-v3-turbo", "openrouter": "openai/whisper-large-v3"}
speech_key = {"groq": GROQ_KEY, "openrouter": AUDIO_KEY}

def listen_api(audio):
    "send the recording to the whisper api and return the text"
    save_wav(audio, "speech.wav")
    with open("speech.wav", "rb") as f:
        resp = requests.post(speech_url[speech_provider],
                             headers={"Authorization": "Bearer " + speech_key[speech_provider]},
                             files={"file": ("speech.wav", f, "audio/wav")},
                             data={"model": speech_model[speech_provider], "language": codes[language]},
                             timeout=15)
    resp.raise_for_status()
    return resp.json()["text"]

def listen_local(audio):
    segments, info = whisper.transcribe(audio, language=codes[language], beam_size=1)  # beam_size 1 = faster
    return "".join(s.text for s in segments)

def run_speech(audio, row):
    global checking, result, heard_text
    try:
        audio = np.nan_to_num(audio)  # no broken numbers
        start = time.time()
        if speech_provider == "local" or speech_key.get(speech_provider, "") == "":
            heard_text = listen_local(audio)
        else:
            try:
                heard_text = listen_api(audio)
            except Exception as error:
                print("api failed, trying again:", error)  # one more try
                try:
                    heard_text = listen_api(audio)
                except Exception as error:
                    print("api failed again:", error)
                    heard_text = listen_local(audio) if local_backup else ""
        print("heard:", heard_text, "|", round(time.time() - start, 2), "seconds")
        result = is_correct(row, language, heard_text)
        source = "local" if (speech_provider == "local" or speech_key.get(speech_provider, "") == "") else speech_provider
        with open("speech_log.csv", "a", encoding="utf-8") as f:
            f.write(",".join([language, row["english"], heard_text.replace(",", " ").strip(), str(round(time.time() - start, 2)), source, str(result)]) + "\n")
    except Exception as error:
        print("speech problem:", error)
        result = False
    checking = False

# VOICE CLONING FUNCTIONS
headers = {
    "X-Api-Key": os.getenv("HEYGEN_KEY"),  # keep it secret
    "Content-Type": "application/json",
}
def create_voice(wav_path):
    API_URL = "https://api.heygen.com/v3/models/audio/voices"
    with open(wav_path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    body = {
        "mode": "instant",
        "name": "LingoQuest guide",
        "language": "en",
        "audio": [{"type": "base64", "media_type": "audio/x-wav", "data": data}],
    }
    resp = requests.post(API_URL, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    return resp.json()["data"]["voice_id"]


def wait_for_voice(voice_id):
    for attempt in range(40):
        resp = requests.get("https://api.heygen.com/v3/models/audio/voices/" + voice_id,
                            headers=headers, timeout=30)
        voice = resp.json()
        voice = voice.get("data", voice)
        if voice["status"] == "ACTIVE":
            return True
        if voice["status"] == "FAILED":
            return False
        time.sleep(3)
    return False


def text_to_speech(voice_id, text, filename):
    API_URL = "https://api.heygen.com/v3/models/audio/tts"
    if text[-1] not in ".!?":
        text += "."
    body = {
        "model": "heygen-voice-1-turbo-free",
        "voice_id": voice_id,
        "text": text,
        "language": "en",
    }
    for attempt in range(5):
        resp = requests.post(API_URL, headers=headers, json=body, timeout=120)
        if resp.status_code != 429:
            break
        time.sleep(int(resp.headers.get("Retry-After", 2 ** attempt)))

    resp.raise_for_status()
    answer = resp.json()
    audio_url = answer.get("data", answer)["audio_url"]

    audio = requests.get(audio_url, timeout=120)
    audio.raise_for_status()
    with open(filename, "wb") as f:
        f.write(audio.content)


def save_wav(audio, path):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("int16")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(pcm.tobytes())


def play_voice(name):
    path = "audio/voice/" + voice_profile + "/" + name + ".wav"
    if not os.path.exists(path):
        path = "audio/voice/default/" + name + ".wav"
    if os.path.exists(path):
        make_sound(path).play()


def kid_say(name):
    "the kid talks to himself: audio/voice/default/kid_<name>_1.wav, _2, _3 (one of them, random)"
    for folder in (voice_profile, "default"):
        files = ["audio/voice/" + folder + "/kid_" + name + "_" + str(k) + ".wav" for k in range(1, 5)]
        files = [f for f in files if os.path.exists(f)]
        if files:
            make_sound(random.choice(files)).play()
            return True
    return False

def guide_say(name):
    "a line of the step / stamp: the kid's voice (or the default one)"
    play_voice(name)

def good_length(path, text):
    "a cloned line that is far too long (repeats) or too short (cut) is thrown away, the default voice plays instead"
    try:
        with wave.open(path, "rb") as f:
            seconds = f.getnframes() / f.getframerate()
    except Exception:
        return True  # not a wav file: keep it
    expected = len(text) * 0.075  # about 13 letters per second
    return expected * 0.4 <= seconds <= expected * 1.8 + 0.6

def run_voice():
    "runs on the side: clone the voice, then make every line"
    global voice_done, voice_profile, voice_status
    try:
        voice_id = create_voice("my_voice.wav")
        if not wait_for_voice(voice_id):
            raise Exception("the voice failed")
        os.makedirs("audio/voice/kid", exist_ok=True)
        for line_name, text in voice_lines.items():
            voice_status = "Making: " + line_name
            text_to_speech(voice_id, text, "audio/voice/kid/" + line_name + ".wav")
            if not good_length("audio/voice/kid/" + line_name + ".wav", text):
                print("bad clone, using the default voice for:", line_name)
                os.remove("audio/voice/kid/" + line_name + ".wav")
        voice_profile = "kid"
    except Exception as error:
        print("voice problem:", error)
        voice_profile = "default"  # if anything fails, use my voice
    voice_done = True
# ----------- buttons-------------------
next_btn = pygame.Rect(300, 400, 200, 70)
jp_btn = pygame.Rect(430, 55, 330, 215)  # top right
fr_btn = pygame.Rect(35, 70, 240, 240)  # top left
es_btn = pygame.Rect(295, 420, 300, 210)  # bottom middle


learn_btn = pygame.Rect(240, 190, 320, 70)
cards_btn = pygame.Rect(240, 280, 320, 70)
hunt_btn = pygame.Rect(240, 370, 320, 70)
speack_btn = pygame.Rect(240, 460, 320, 70)

back_btn = pygame.Rect(60, 560, 200, 60)
check_btn= pygame.Rect(314, 575, 150, 50)
next_word_btn = pygame.Rect(634, 575, 150, 50)
listen_btn = pygame.Rect(474, 575, 150, 50)
play_btn = pygame.Rect(260,510,280,96)
girl_btn = pygame.Rect(110, 170, 270, 360)
boy_btn = pygame.Rect(420, 170, 270, 360)

yes_btn = pygame.Rect(240, 335, 320, 70)
skip_voice_btn = pygame.Rect(240, 425, 320, 70)

mic_btn= pygame.Rect(340,330,120,120)
waiting_until=0  # time from word to worn in round

# rects
click_area = {}
for c in countries:
    click_area[c] = pygame.Rect(0, 0, country_size[c][0], country_size[c][1])
    click_area[c].center = country_pos[c]
jp_btn = click_area["japan"]
fr_btn = click_area["france"]
es_btn = click_area["spain"]
talk_next_btn = pygame.Rect(box_pos[0] + box_size[0] - 140, box_pos[1] + box_size[1] + 8, 125, 38)  # under the box, ends with it
talk_skip_btn = pygame.Rect(talk_next_btn.x - 135, talk_next_btn.y, 125, 38)
talk_box = pygame.Rect(box_pos, box_size)
collection_btn = pygame.Rect(240, 480, 320, 50)
round_btn = pygame.Rect(594, 575, 190, 50)
say_btn = talk_next_btn  # Next under the guide's box
confirm_box = pygame.Rect(150, 190, 500, 230)
confirm_yes = pygame.Rect(190, 330, 190, 60)
confirm_no = pygame.Rect(420, 330, 190, 60)
confirm_ask = False  # "are you sure?" is open
confirm_what = ""  # Next / Try again at the end of a game
def round_done_rects(n):
    "the buttons of the round done popup (2 in a row)"
    return [pygame.Rect(215, 405, 180, 52), pygame.Rect(405, 405, 180, 52)]

def ask_rects(n):
    "the buttons of the ask screen (2 or 3 in a row)"
    if n == 2:
        return [pygame.Rect(160, 360, 220, 70), pygame.Rect(420, 360, 220, 70)]
    return [pygame.Rect(110, 360, 180, 70), pygame.Rect(310, 360, 180, 70), pygame.Rect(510, 360, 180, 70)]
page_prev_btn = pygame.Rect(640, 560, 50, 34)
page_next_btn = pygame.Rect(700, 560, 50, 34)  # under the book

adventure_box = {
    "Home Adventure": pygame.Rect(50, 185, 220, 260),
    "School Adventure": pygame.Rect(290, 185, 220, 260),
    "Outdoor Adventure": pygame.Rect(530, 185, 220, 260),
}
learn_bar = pygame.Rect(120, 215, 560, 110)
play_bar = pygame.Rect(120, 355, 560, 110)
cards_btn = pygame.Rect(120, 190, 560, 100)
hunt_btn = pygame.Rect(120, 305, 560, 100)
speack_btn = pygame.Rect(120, 420, 560, 100)
learn_btn = pygame.Rect(-300, -300, 1, 1)  # learn is on its own page now

back_btn = pygame.Rect(16, 570, 60, 60)
menu_btn = pygame.Rect(86, 570, 60, 60)
passport_btn = pygame.Rect(156, 570, 60, 60)
dict_btn = pygame.Rect(226, 570, 60, 60)
dict_from = "language"
dict_cat = 0  # 0 home, 1 school, 2 outdoor
dict_lang = "japanese"
dict_cats = ["Home Adventure", "School Adventure", "Outdoor Adventure"]
dict_cat_names = ["Home", "School", "Outdoor"]
dict_langs = ["japanese", "french", "spanish"]
dict_lang_names = ["Japanese", "French", "Spanish"]
dict_back = pygame.Rect(14, 12, 60, 60)  # back: top left
dict_cat_rects = [pygame.Rect(235 + k * 112, 82, 104, 34) for k in range(3)]  # the 3 places: below the title
dict_lang_rects = [pygame.Rect(290 + k * 80, 584, 64, 44) for k in range(3)]  # the 3 flags: under the book
dict_jp_font = jp_font_of(21)
dict_word_font = soft_font(20)

def dict_cells():
    "the words of this place: 7 in the left column, 7 in the right"
    rows = [r for r in df if r["category"] == dict_cats[dict_cat]]
    cells = []
    for i, row in enumerate(rows):
        cells.append((pygame.Rect(106 + (i // 7) * 326, 168 + (i % 7) * 52, 262, 46), row))
    return cells

def draw_speaker(center, strong):
    "the round pink speaker button of a word"
    pygame.draw.circle(screen, (225, 212, 200) if strong else (240, 232, 222), center, 12)
    x, y = center
    pygame.draw.polygon(screen, (66, 40, 76), [(x - 6, y - 3), (x - 2, y - 3), (x + 3, y - 7), (x + 3, y + 7), (x - 2, y + 3), (x - 6, y + 3)])

def draw_dictionary():
    "all the words in a small open book. Click a word to hear it"
    draw_title_box("My Dictionary", 38)
    # the book: red cover, two cream pages, a pink ribbon
    pygame.draw.rect(screen, (190, 60, 80), (70, 142, 660, 424), border_radius=20)
    pygame.draw.rect(screen, (225, 90, 100), (70, 138, 660, 424), border_radius=20)
    for page_x in (82, 408):
        pygame.draw.rect(screen, (252, 244, 228), (page_x, 150, 310, 400), border_radius=12)
        pygame.draw.rect(screen, (236, 205, 195), (page_x + 7, 157, 296, 386), 2, border_radius=9)
    pygame.draw.polygon(screen, (225, 90, 100), [(670, 150), (688, 150), (688, 176), (679, 168), (670, 176)])
    for k, r in enumerate(dict_cat_rects):  # on top: where the words are from
        hover = r.collidepoint(pygame.mouse.get_pos())
        chosen = k == dict_cat
        pygame.draw.rect(screen, (240, 100, 160) if chosen else (255, 235, 245) if hover else (255, 255, 255), r, border_radius=20)
        ui_text(dict_cat_names[k], label_small_font, (255, 255, 255) if chosen else PLUM, center=r.center)
    for k, r in enumerate(dict_lang_rects):
        hover = r.collidepoint(pygame.mouse.get_pos())
        if dict_langs[k] == dict_lang or hover:
            pygame.draw.rect(screen, (255, 255, 255), r, border_radius=10)
            pygame.draw.rect(screen, (240, 100, 160), r, 4, border_radius=10)
        flag = ui_img("cards/flag_" + ("japan", "france", "spain")[k] + ".png", (44, 30))
        if flag is not None:
            screen.blit(flag, flag.get_rect(center=r.center))
    for rect, row in dict_cells():
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            pygame.draw.rect(screen, (255, 238, 225), rect, border_radius=10)
        picture = ui_word_picture(row["english"], 28)
        if picture is not None:
            screen.blit(picture, picture.get_rect(center=(rect.x + 18, rect.centery)))
        ui_text(row[show_column[dict_lang]], dict_jp_font if dict_lang == "japanese" else dict_word_font, PLUM, midleft=(rect.x + 42, rect.y + 15), max_width=170)
        small = row["english"] + (" . " + row["romaji"] if dict_lang == "japanese" else "")
        ui_text(small, r_city_font, LIGHT_PLUM, midleft=(rect.x + 42, rect.y + 34), max_width=170)
        draw_speaker((rect.right - 16, rect.centery), hover)
    draw_icon(dict_back, icon_back)
    tip("Back", dict_back)


# --GAME MAIN LOOP --
play_music("audio/music/menu.ogg")
PLUM = (66, 40, 76)
LIGHT_PLUM = (128, 104, 136)
PINK_ROMAJI = (196, 70, 122)
show_cards_step = True
ui_cache = {}
def ui_img(name, size=None):
    "a picture from images/ui (or a full path). None if the file is missing, so the game still runs"
    key = (name, size)
    if key not in ui_cache:
        path = name if name.startswith("images/") else "images/ui/" + name
        if os.path.exists(path):
            picture = pygame.image.load(path).convert_alpha()
            if size is not None:
                picture = pygame.transform.smoothscale(picture, size)
            ui_cache[key] = picture
        else:
            ui_cache[key] = None
    return ui_cache[key]

def ui_blit(name, center=None, topleft=None, size=None):
    "draws a picture and gives back its rect"
    picture = ui_img(name, size)
    if picture is None:
        return None
    rect = picture.get_rect(center=center) if center is not None else picture.get_rect(topleft=topleft)
    screen.blit(picture, rect)
    return rect

r_title_font = game_font(28)
r_word_font = jp_font_of(50)
r_romaji_font = soft_font(22)
r_small_font = soft_font(17)
r_city_font = soft_font(15)
r_button_font = game_font(24)
r_meaning_font = soft_font(26)
r_find_font = jp_font_of(26)  # can show Japanese

def ui_text(text, f, color, center=None, midleft=None, max_width=None):
    surface = f.render(text, True, color)
    if max_width is not None and surface.get_width() > max_width:
        surface = pygame.transform.smoothscale(surface, (max_width, int(surface.get_height() * max_width / surface.get_width())))
    rect = surface.get_rect(center=center) if center is not None else surface.get_rect(midleft=midleft)
    screen.blit(surface, rect)

def white_text(text, f, center):
    "white text with a plum edge"
    edge = f.render(text, True, PLUM)
    white = f.render(text, True, (255, 255, 255))
    rect = white.get_rect(center=center)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2), (2, -2), (-2, 2), (2, 2)):
        screen.blit(edge, rect.move(dx, dy))
    screen.blit(white, rect)

def ui_message(text, center):
    "white text with a plum edge: shows on the green floor too"
    edge = r_small_font.render(text, True, PLUM)
    white = r_small_font.render(text, True, (255, 255, 255))
    rect = white.get_rect(center=center)
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, -1), (1, -1), (-1, 1), (1, 1)):
        screen.blit(edge, rect.move(dx, dy))
    screen.blit(white, rect)

def ui_button(name, center, label="", scale=1.0):
    "a button with its _hover picture. gives back the rect for the clicks"
    picture = ui_img("buttons/" + name + ".png")
    if picture is not None and scale != 1.0:
        picture = ui_img("buttons/" + name + ".png", (int(picture.get_width() * scale), int(picture.get_height() * scale)))
    if picture is None:  # no picture: a plain pink pill
        rect = pygame.Rect(0, 0, 170, 56)
        rect.center = center
        pygame.draw.rect(screen, (240, 100, 160), rect, border_radius=28)
    else:
        rect = picture.get_rect(center=center)
        if rect.collidepoint(pygame.mouse.get_pos()):
            hover_sound(rect)
            hover_picture = ui_img("buttons/" + name + "_hover.png")
            if hover_picture is not None:
                picture = pygame.transform.smoothscale(hover_picture, picture.get_size())
        screen.blit(picture, rect)
    if label != "":
        dark_text = name == "btn_white"
        ui_text(label, r_button_font, PLUM if dark_text else (255, 255, 255), center=rect.center)
    return rect

def ui_pulse(name, center, speed, scale=1.0):
    "the white ring behind the mic / shutter: grows and shrinks"
    ring = ui_img("buttons/pulse_ring.png")
    if ring is None:
        return
    grow = 1 + 0.07 * math.sin(pygame.time.get_ticks() / speed)
    size = (int(ring.get_width() * grow * scale), int(ring.get_height() * grow * scale))
    ring = pygame.transform.smoothscale(ring, size)
    screen.blit(ring, ring.get_rect(center=center))

pic_cache = {}
def ui_word_picture(english, size):
    "the vocab picture of a word in the size we need"
    key = (english, size)
    if key not in pic_cache:
        path = "images/vocab/" + english + ".png"
        if os.path.exists(path):
            pic_cache[key] = pygame.transform.smoothscale(pygame.image.load(path).convert_alpha(), (size, size))
        else:
            pic_cache[key] = None
    return pic_cache[key]

word_results = []
wrong_until = 0
prev_btn = pygame.Rect(0, 0, 0, 0)

sign_of_stop = ["signs/sign_japan.png", "signs/sign_japan.png", "signs/sign_france.png"]  # the sign of home, school, outdoor
round_titles = {"learn": "Learn the words!", "speak": "Say the word!", "hunt": "Find it!", "cards": "Show your card!"}  # also the big text on the door
road = ["learn", "speak", "hunt", "cards"]

def draw_round_top():
    "the top of every round screen: sign, 3 stars, the step road and the 10 dots"
    c = country[language]
    ui_blit(sign_of_stop[stop], topleft=(261, 14))
    ui_text(round_titles.get(mode, ""), r_title_font, (255, 255, 255), center=(400, 58), max_width=230)
    ui_blit("progress/stars_bar.png", topleft=(618, 28))
    got = stars_of(stop)
    for k, x in enumerate((646, 697, 748)):
        ui_blit("progress/star_gold.png" if k < got else "progress/star_grey.png", center=(x, 53))
        if k == rnd:
            ui_blit("progress/star_now_ring.png", center=(x, 53))
    steps = [s for s in road if s != "cards" or show_cards_step]
    here = steps.index(mode) if mode in steps else 0
    for k, s in enumerate(steps):
        x = int(400.5 - 33.5 * (len(steps) - 1) + 67 * k)
        ui_blit("progress/step_" + ("done" if k < here else "now" if k == here else "todo") + ".png", center=(x, 123))
        icon = ui_img("mode_" + s + ".png", (28, 28))
        if icon is not None:
            screen.blit(icon, icon.get_rect(center=(x, 123)))
        if k < len(steps) - 1:
            ui_blit("progress/step_line_" + ("done" if k < here else "todo") + ".png", topleft=(x + 20, 120))
        if k < here:
            ui_blit("progress/tick.png", center=(x + 14, 106))
    n = len(words)
    for k in range(n):
        x = 400 - (n - 1) * 11 + k * 22
        done = word_results[k] if k < len(word_results) else None
        if mode == "learn":
            kind = "right" if k < index else "now" if k == index else "todo"
        elif done is True:
            kind = "right"
        elif done is False:
            kind = "wrong"
        else:
            kind = "now" if k == index else "todo"
        ui_blit("progress/dot_" + kind + ".png", center=(x, 161))

def dot_rect(k):
    "the circle of word k at the top of a round screen"
    n = len(words)
    x = 400 - (n - 1) * 11 + k * 22
    return pygame.Rect(x - 11, 150, 22, 22)

help_btn = pygame.Rect(742, 98, 40, 40)

def draw_help_button():
    "the ? button: the guide explains the round again"
    hover = help_btn.collidepoint(pygame.mouse.get_pos())
    if hover:
        hover_sound(help_btn)
    pygame.draw.circle(screen, (255, 140, 190) if hover else (240, 100, 160), help_btn.center, 20)
    pygame.draw.circle(screen, OUTLINE_PINK, help_btn.center, 20, 3)
    mark = r_title_font.render("?", True, (255, 255, 255))
    screen.blit(mark, mark.get_rect(center=help_btn.center))

def draw_round_guide():
    "the guide stands in the room on the left: idle, happy, oops or thinking"
    now = pygame.time.get_ticks()
    if now < wrong_until:
        pose = "oops"
    elif state == "result" and in_round and not game_passed:
        pose = "oops"  # sad
    elif waiting_until > 0 or (state == "result" and in_round):
        pose = "happy"
    elif checking:
        pose = "thinking"
    else:
        pose = "idle"
    prefix = "images/guide/guide_boy_" if guide == "boy" else "images/guide/guide_"
    picture = ui_img(prefix + pose + ".png") or ui_img(prefix + "idle.png")
    if picture is None:
        return
    height = 380
    key = (prefix + pose, "guide")
    if key not in ui_cache:
        ui_cache[key] = pygame.transform.smoothscale(picture, (int(picture.get_width() * height / picture.get_height()), height))
    small = ui_cache[key]
    bob = int(abs(math.sin(now / 150)) * 12) if pose == "happy" else 0  # jumps when happy
    screen.blit(small, small.get_rect(midbottom=(108, 640 - bob)))

def draw_round_card(row):
    "Learn and Speak: the word card"
    global listen_btn, mic_btn, next_word_btn, prev_btn
    now = pygame.time.get_ticks()
    clue = ["picture", "word", "romaji", "english"] if mode == "learn" else levels[rnd]["speak"]["clue"]
    only_picture = "word" not in clue
    right = waiting_until > 0
    wrong = now < wrong_until
    card = "cards/card_picture" if only_picture else "cards/card_word"
    ui_blit(card + ("_right" if right else "_wrong" if wrong else "") + ".png", center=(400, 312))
    c = country[language]
    if not only_picture:
        ui_blit("cards/flag_" + c + ".png", topleft=(240, 195))
        ui_text(city_names[language][stop].upper(), r_city_font, LIGHT_PLUM, midleft=(274, 205))
    if listens_left is None or listens_left > 0:
        listen_btn = ui_button("btn_speaker", (538, 216))
    else:
        listen_btn = pygame.Rect(-100, -100, 1, 1)
    english = row["english"]
    if only_picture:
        picture = ui_word_picture(english, 180)
        if picture is not None:
            screen.blit(picture, picture.get_rect(center=(400, 312)))
    else:
        picture = ui_word_picture(english, 70 if rnd == 1 and mode == "speak" else 96) if "picture" in clue else None
        if picture is not None:
            screen.blit(picture, picture.get_rect(center=(400, 252)))
        ui_text(row[show_column[language]], r_word_font, PLUM, center=(400, 324), max_width=290)
        two_lines = "romaji" in clue and language == "japanese" and "english" in clue
        if "romaji" in clue and language == "japanese":
            ui_text(row["romaji"], r_romaji_font if two_lines else r_meaning_font, PINK_ROMAJI, center=(400, 382 if two_lines else 395))
        if "english" in clue:
            ui_text(english, r_romaji_font if two_lines else r_meaning_font, LIGHT_PLUM, center=(400, 410 if two_lines else 395))
        elif mode == "speak":
            ui_text("say it!", r_meaning_font, LIGHT_PLUM, center=(400, 395))
    if right:
        ui_blit("stamps/stamp_" + c + "_right.png", center=(515, 392), size=(120, 120))
    if mode == "learn":  # back / next word
        prev_btn = ui_button("btn_white", (300, 505), "Back")
        next_word_btn = ui_button("btn_pink", (500, 505), "Next")
    else:
        ui_pulse("mic", (400, 524), 120 if recording else 300)
        mic_btn = ui_button("btn_mic", (400, 524))
        next_word_btn = ui_button("btn_white", (690, 592), "Skip")
    if message != "" and mode == "speak":
        ui_message(message, (400, 612))

def draw_round_camera(row):
    "Hunt and Cards: the 'find this' card, the camera in the polaroid and the shutter"
    global listen_btn, check_btn, next_word_btn
    now = pygame.time.get_ticks()
    clue = levels[rnd]["hunt"]["clue"]
    c = country[language]
    ui_blit("cards/card_find.png", center=(400, 210))
    english = row["english"]
    if "audio" in clue:  # round 3: only listen
        listen_btn = ui_button("btn_speaker", (340, 207))
        ui_text("Listen!", r_title_font, PLUM, center=(430, 207))
    else:
        picture = ui_word_picture(english, 40) if "picture" in clue else None
        if picture is not None:
            screen.blit(picture, picture.get_rect(center=(304, 207)))
        ui_text(row[show_column[language]], r_find_font, PLUM, midleft=(336, 197), max_width=150)
        small = []
        if "romaji" in clue and language == "japanese":
            small.append(row["romaji"])
        if "english" in clue:
            small.append(english)
        if small:
            ui_text(" . ".join(small), r_small_font, LIGHT_PLUM, midleft=(336, 222), max_width=150)
        listen_btn = ui_button("btn_speaker", (509, 207))
    asking = checking and waiting_until == 0  # waiting for the answer
    if not cam_on:  # the camera is not open yet
        pygame.draw.rect(screen, (60, 55, 65), (289, 273, 222, 208))
        ui_text("Press the pink button", r_small_font, (255, 255, 255), center=(400, 360), max_width=200)
        ui_text("to open the camera", r_small_font, (255, 255, 255), center=(400, 385), max_width=200)
    ui_blit("camera/viewfinder.png", topleft=(289, 273))
    ui_blit("camera/polaroid_frame.png", topleft=(268, 252))
    if waiting_until > 0:  # right: a light green border
        pygame.draw.rect(screen, (120, 215, 140), pygame.Rect(289, 273, 222, 208).inflate(16, 16), 6, border_radius=10)
    elif now < wrong_until:  # wrong: a light red border
        pygame.draw.rect(screen, (235, 120, 120), pygame.Rect(289, 273, 222, 208).inflate(16, 16), 6, border_radius=10)
    if now < flash_until:  # white flash
        flash = ui_img("camera/flash.png")
        if flash is not None:
            flash = flash.copy()
            flash.set_alpha(int(255 * (flash_until - now) / 200))
            screen.blit(flash, (289, 273))
    if asking:
        ui_blit("camera/checking_veil.png", topleft=(289, 273))
        ui_text("checking", r_small_font, PLUM, midleft=(355, 503))
        for k in range(3):
            bounce = int(abs(math.sin(now / 200 + k * 0.6)) * 8)
            pygame.draw.circle(screen, (240, 100, 160), (435 + k * 14, 506 - bounce), 4)
    if now < wrong_until:
        ui_blit("popups/try_again.png", center=(400, 377))
    if waiting_until > 0:
        ui_blit("stamps/stamp_" + c + "_right.png", center=(470, 330))
    ui_pulse("shutter", (400, 592), 300, 0.65)
    check_btn = ui_button("btn_shutter", (400, 592), "", 0.65)
    next_word_btn = ui_button("btn_white", (690, 592), "Skip cards" if mode == "cards" else "Skip")
    if message not in ("", "Checking object...", "Checking card...", "Try again!") and not asking:
        ui_text(message, r_small_font, PLUM, center=(400, 503), max_width=210)  # in the white strip of the polaroid

def draw_play_ui(row):
    "the whole round screen (Learn, Speak, Hunt, Cards)"
    draw_round_guide()
    if in_round:
        draw_help_button()
    draw_round_top()
    if mode in ("hunt", "cards"):
        draw_round_camera(row)
    else:
        draw_round_card(row)
    back_icon()
# ---------- end of the new round screen ----------

clock = pygame.time.Clock()
running = True
async def main():
    global back_from, came_to, diag_mode, adv, angle, back_btn, best, big, book, box, bus_at, bus_from, bus_start, bus_to, c, cam_on, captured, checking, confirm_ask, confirm_what, dark, dict_cat, dict_from, dict_lang, e, elapsed, event, f, flag_drag, flash_until, frame, g, game_passed, guide, happy, heard_text, hold_until, hover_before, hover_now, hovered, i, icon, in_round, index, k, key, label, labels, lang, language, last_frame, last_state, later_line, left, line, lines, listens_left, lq_kind, lq_state, lq_text, m, md, message, mine, mode, moment, n, name, now, over, parts, passport_page, pic, picture, place, praised, r, record_buffer, record_start, recording, rect, result, result_time, reward_tier, rnd, row, running, scale, score, seq_pos, sfx_done, shift, shown, size, slot, small_book, small_page, sound, sound_path, spot, stamp_saved, stamped, stamps_bg, stamps_from, state, steps, sx, sy, t, talk_page, talk_start, time_left, timer_index, tool_y, total, travel_country, travel_start, typed, viewing, voice_done, voice_profile, voice_status, waiting_until, wave_pic, who, word, word_play_at, wrong_until, x, x2, y, y2
    while running:
        back_btn = pygame.Rect(22, 22, 60, 60) if state == "play" else pygame.Rect(16, 552, 60, 60) if state == "stamps" else pygame.Rect(16, 570, 60, 60)
        # webcam for hunt + card mode
        frame=None
        
        # 1: events : what did the player do?
        for event in pygame.event.get():
            if door_start != 0 and event.type != pygame.QUIT:  # the door is moving: no clicks
                continue
            if event.type == pygame.QUIT:
                running = False

            if test_mode and state == "language":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    for c in flag_rect:
                        if flag_rect[c].collidepoint(event.pos):
                            flag_drag = c
                    if flag_drag != "":
                        continue
                if event.type == pygame.MOUSEMOTION and flag_drag != "":
                    place = click_area[flag_drag]
                    flag_spot[flag_drag] = (event.pos[0] - place.centerx, event.pos[1] - place.centery)
                    continue
                if event.type == pygame.MOUSEBUTTONUP and flag_drag != "":
                    flag_drag = ""
                    print("flag_spot =", flag_spot)
                    continue

            if confirm_ask:  # only the two buttons work now
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if clicked(confirm_yes, event):
                        confirm_ask = False
                        stop_mic()
                        pygame.mixer.stop()
                        in_round = False
                        if confirm_what == "home":
                            go_home()
                        else:
                            state = "city"
                            play_music("audio/music/" + country[language] + ".ogg")
                    elif clicked(confirm_no, event):
                        confirm_ask = False
                continue
            if (in_round and state in ("play", "result", "ask", "banner") or state == "talk" and talk_key.startswith(("round_", "howto_"))) \
                    and (clicked(back_btn, event) or clicked(menu_btn, event)):
                confirm_ask = True
                confirm_what = "home" if clicked(menu_btn, event) else "back"
                continue

            if event.type == pygame.KEYDOWN and event.key == pygame.K_d:  # status: hidden -> dots -> codes
                diag_mode = (diag_mode + 1) % 3
            if test_mode and event.type == pygame.KEYDOWN and event.mod & pygame.KMOD_CTRL:
                if event.key == pygame.K_w and state == "play":  # win this round
                    score = len(words)
                    index = len(words)
                    state = "result"
                if event.key == pygame.K_s:  # all 3 rounds of this stop
                    for r in range(3):
                        slot = name + "|" + language + "|" + stop_adv[stop] + "|round"
                        if city_tier[r] not in passport.get(slot, []):
                            passport.setdefault(slot, []).append(city_tier[r])
                    with open("passport_city.json", "w") as f:
                        json.dump(passport, f)
                if event.key == pygame.K_r:
                    for slot in list(passport):
                        if slot.startswith(name + "|"):
                            del passport[slot]
                    with open("passport_city.json", "w") as f:
                        json.dump(passport, f)

            # menu and passport icons
            if icons_on() and event.type == pygame.MOUSEBUTTONDOWN:
                if clicked(menu_btn, event):
                    go_home()
                    continue
                if clicked(dict_btn, event):
                    stop_mic()
                    dict_from = state
                    dict_lang = language if language != "" else "japanese"
                    dict_cat = 0
                    state = "dictionary"
                    sfx("click")
                    continue
                if clicked(passport_btn, event) and state != "stamps":
                    stop_mic()
                    stamps_from = state
                    state = "stamps"
                    viewing = -1
                    passport_page = 0
                    sfx("book_open")
                    play_voice("stamps")
                    continue
                # -----START--------
            if state =="start":
                if clicked(play_btn,event):
                    sfx("click")
                    state="character"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    state = "character"
                # ------CHARACTER---------
            elif state == "character":
                if clicked(girl_btn,event):
                    sfx("click")
                    guide="girl"
                    voice_profile = "default"  # no voice cloning, straight to the name
                    state = "name"
                    play_voice("welcome")
                if clicked(boy_btn,event):
                    sfx("click")
                    guide="boy"
                    voice_profile = "default"
                    state = "name"
                    play_voice("welcome")
                # -----NAME-----
            elif state == "name":  # allow user to enter  name
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        name= name[:-1]  # remove last letter
                    elif len(name)<12 and event.unicode.isprintable():
                        name += event.unicode
                if clicked(pygame.Rect(150, 230, 500, 60), event):
                    typed = platform.window.prompt("What is your name?", name)
                    if typed and str(typed) != "None":
                        name = str(typed)[:12]
                if clicked(next_btn,event) and name !="":
                    start_talk("welcome", "language")
                # -----VOICE--------
            elif state == "voice":
                if clicked(yes_btn,event):
                    voice_profile = "default"
                    state = "name"
                    play_voice("welcome")
                if clicked(skip_voice_btn,event):
                    voice_profile = "default"
                    state= "name"
                    play_voice("welcome")
                # ------CLONE--------
            elif state == "record":
                if clicked(mic_btn,event) and not recording:
                    recording = True
                    record_start = pygame.time.get_ticks()
                    record_buffer = np.zeros((voice_sec*16000,1), dtype="float32")
                    sd.rec(out=record_buffer, samplerate=16000, channels=1)
                if clicked(back_btn, event) and not recording:
                    state = "voice"
            
                # -----LANGUAGE-----
            elif state == "language":
                if clicked(jp_btn,event):
                    language = "japanese"
                    state = "adventure"
                    play_music("audio/music/japan.ogg")
                    play_voice("adventure")  # clone
                if clicked(fr_btn,event):
                    language = "french"
                    state = "adventure"
                    play_music("audio/music/france.ogg")
                    play_voice("adventure")

                if clicked(es_btn,event):
                    language = "spanish"
                    state = "adventure"
                    play_voice("adventure")
                    play_music("audio/music/spain.ogg")


               # -----ADVENTURE-----
            elif state == "city":
                for i in range(3):
                    if clicked(city_btn[i], event) and bus_start == 0:
                        sfx("click")
                        if i == bus_at:
                            go_stop(i)
                        else:
                            bus_from = bus_at
                            bus_to = i
                            bus_start = pygame.time.get_ticks()
                            play_voice("bus_go")
                if clicked(back_btn, event):
                    state = "adventure"

            elif state == "adventure":
                for box in adventure_box:
                    if clicked(adventure_box[box], event):
                        sfx("click")
                        bus_at = list(adventure_box).index(box)
                        kid_say(("home", "school", "outdoor")[bus_at])
                        state = "city"
                if clicked(back_btn, event):
                    state = "language"
                    play_music("audio/music/menu.ogg")

            elif state == "ask":
                for k, r in enumerate((ask_rects if ask_kind in ("revise", "cards") else round_done_rects)(len(ask_texts[ask_kind][1]))):
                    if clicked(r, event):
                        sfx("click")
                        if ask_kind == "revise":
                            if k == 0:
                                mode = "learn"
                                state = "play"
                                begin_game()
                            else:
                                seq_pos += 1
                                go_step()
                        elif ask_kind == "cards":
                            if k == 0:
                                mode = "cards"
                                state = "play"
                                begin_game()
                            else:
                                seq_pos += 1
                                go_step()
                        else:  # harder / last
                            if ask_kind == "harder" and k == 0:
                                rnd += 1
                                round_intro()
                            elif k == len(ask_texts[ask_kind][1]) - 1:
                                state = "city"
                            else:
                                start_round()  # again
                if clicked(back_btn, event):
                    in_round = False
                    state = "city"

               # -----MOOD-----
            elif state == "mode":
                if clicked (learn_btn, event):
                    sfx("click")
                    mode ="learn"
                    state = "play"
                if clicked (cards_btn, event):
                    sfx("click")
                    mode ="cards"
                    state = "play"
                if clicked (hunt_btn, event):
                    sfx("click")
                    mode ="hunt"
                    state = "play"
                if clicked (speack_btn, event):
                    sfx("click")
                    mode ="speak"
                    state = "play"
                if clicked(back_btn,event):
                    state = "choose"

                    # play
                if state == "play":
                    begin_game()

            elif state == "play":
                if clicked(back_btn, event):
                    state = "city"
                    in_round = False
                    pygame.mixer.stop()
                    if recording:
                        sd.stop()
                        recording= False
                if in_round and clicked(help_btn, event) and not checking and not recording:
                    start_talk("round_" + str(rnd + 1), "back")  # the guide explains the round again
                    continue
                if mode in ("hunt", "cards", "speak") and clicked(listen_btn, event) and (listens_left is None or listens_left > 0):
                    play_word(words[index])
                    if listens_left is not None:
                        listens_left -= 1
                if mode in ("learn", "hunt", "speak") and not checking and not recording and event.type == pygame.MOUSEBUTTONDOWN:
                    for k in range(len(words)):  # press a circle: go back to that word
                        if k != index and dot_rect(k).collidepoint(event.pos) and (mode == "learn" or (k < len(word_results) and word_results[k] is False)):
                            if mode != "learn":
                                if back_from < 0:
                                    back_from = index  # remember where we were
                                came_to = k
                            index = k
                            message = ""
                            word_results[k] = None if mode != "learn" else word_results[k]
                            if mode == "learn":
                                play_word(words[index])
                            break
                # HUNT AND CARDS MOOD
                if mode in ("hunt", "cards"):
                    if clicked(check_btn, event) and not checking:
                        checking = True
                        word = words[index]["english"]
                        if cam_on:  # camera is open, take the photo
                            message = "Checking object..." if mode == "hunt" else "Checking card..."
                            lq_kind = "hunt"
                            if mode == "cards":
                                platform.window.lq_snap(words[index]["model_class"], SERVER, "/card")  # the model on the server
                            else:
                                platform.window.lq_snap(word, SERVER)
                        else:  # first press opens the camera
                            message = "Opening the camera..."
                            platform.window.lq_wake(SERVER)
                            lq_kind = "open"
                            platform.window.lq_open()
                    if clicked(next_word_btn, event) and not checking:
                        if mode == "cards":  # skip the whole cards game
                            next_step()
                        else:
                            word_results[index] = False
                            index += 1
                            message = "Skipped"
                            if index == len(words):
                                state = "result"
                # (old card mood, not used on the web)
                elif False:
                    if clicked(check_btn, event) and frame is not None and not checking:
                        checking = True
                        captured = frame.copy()
                        flash_until = pygame.time.get_ticks() + 200
                        hold_until = pygame.time.get_ticks() + 1500
                        if detect_card(frame, words[index]["model_class"]):
                            score = update_score(score, True)
                            word_results[index] = True
                            message = "Correct! +1"
                            play_correct()
                            play_word(words[index])
                            checking= True
                            waiting_until = pygame.time.get_ticks() + 4000  # 4sec: time to enjoy it

                        else:
                            message = "Try again!"
                            wrong_until = pygame.time.get_ticks() + 2000
                            play_wrong()
                            kid_say("oops")
                    if clicked(next_word_btn, event) and not checking:  # skip the whole cards game
                        next_step()
                # LEARN MOOD
                elif mode == "learn":
                    if clicked(listen_btn, event) and (listens_left is None or listens_left > 0):
                        play_word(words[index])
                        if listens_left is not None:
                            listens_left -= 1
                    if clicked(prev_btn, event) and index > 0:
                        index -= 1
                        play_word(words[index])
                    if clicked(next_word_btn, event):
                        index += 1
                        if index == len(words):
                            state = "result"
                        elif listens_left is None:
                            play_word(words[index])
                # SPEACK MODE
                elif mode == "speak":
                    if clicked(mic_btn,event) and not checking and not recording:
                        recording= True
                        heard_text=""
                        record_start= pygame.time.get_ticks()
                        message= "Speak Now!"
                        lq_kind = "speak"  # the browser records 3 seconds
                        platform.window.lq_speak(codes[language], SERVER, record_seconds)
 
                    if clicked(next_word_btn,event) and not checking and not recording:
                        word_results[index] = False
                        index +=1
                        message="Skipped"
                        if index == len(words):
                            state="result"

            elif state == "result":
                if in_round and result_ready() and clicked(round_btn if mode == "round" else say_btn, event):
                    if mode in ("hunt", "speak") and not game_passed:  # not enough right: play this game again
                        state = "play"
                        begin_game()
                    else:
                        next_step()
                if not in_round and mode != "round" and clicked(say_btn, event):  # cards game from the map
                    state = "city"
                if clicked(back_btn,event):
                    state = "city"
                    in_round = False
                if mode == "round" and clicked(collection_btn, event) and result_ready():
                    stamps_from = "result"
                    state = "stamps"
                    viewing = -1
                    passport_page = 0
                    sfx("book_open")
                    play_voice("stamps")

            # screens: choose, travel, arrive, stamps
            elif state == "choose":
                if clicked(learn_bar, event):
                    sfx("click")
                    mode = "learn"
                    state = "play"
                    begin_game()
                if clicked(play_bar, event):
                    sfx("click")
                    state = "mode"
                if clicked(back_btn, event):
                    state = "adventure"

            elif state == "travel":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    travel_start = -99999  # click skips the flight

            elif state == "talk":
                if clicked(talk_skip_btn, event) and talk_page < len(talk_pages) - 1:
                    finish_talk()
                elif clicked(talk_next_btn, event) or clicked(talk_box, event) or (event.type == pygame.KEYDOWN and event.key in (pygame.K_SPACE, pygame.K_RETURN)):
                    total = sum(len(line) for line in talk_pages[talk_page])
                    if (pygame.time.get_ticks() - talk_start) // 45 < total:
                        talk_start = pygame.time.get_ticks() - total * 45  # show the whole page
                    elif talk_page == len(talk_pages) - 1:
                        finish_talk()
                    else:
                        talk_page += 1
                        talk_start = pygame.time.get_ticks()
                        play_talk(talk_key, talk_page)

            elif state == "dictionary":
                if clicked(dict_back, event):
                    state = dict_from
                for k, r in enumerate(dict_cat_rects):
                    if clicked(r, event):
                        dict_cat = k
                        sfx("click")
                for k, r in enumerate(dict_lang_rects):
                    if clicked(r, event):
                        dict_lang = dict_langs[k]
                        sfx("click")
                for rect, row in dict_cells():
                    if clicked(rect, event):
                        sound_path = row[audio_column[dict_lang]]
                        if os.path.exists(sound_path):
                            make_sound(sound_path).play()
            elif state == "stamps":
                if viewing >= 0:
                    if event.type == pygame.MOUSEBUTTONDOWN:  # any click closes the big stamp
                        viewing = -1
                else:
                    if clicked(back_btn, event):
                        sfx("book_close")
                        state = stamps_from
                    mine = passport_stamps()
                    if clicked(page_prev_btn, event) and passport_page > 0:
                        passport_page -= 1
                    if clicked(page_next_btn, event) and (passport_page + 1) * 18 < len(mine):
                        passport_page += 1
                    for i in range(len(mine)):
                        spot = stamp_spot(i)
                        if spot is not None and clicked(pygame.Rect(spot, (stamp_size, stamp_size)), event):
                            viewing = i

        # trip logic
        now = pygame.time.get_ticks()
        if state == "adventure" and last_state == "language":
            state = "travel"
            travel_start = now
            travel_country = country[language]
            pygame.mixer.stop()
            sfx("airplane")
            play_voice("travel_" + travel_country)
        if state == "travel" and now - travel_start >= travel_time:
            start_talk("country_" + language, "adventure")
        last_state = state
        if state == "city" and not kit_ok:
            for i in range(3):
                city_btn[i].midbottom = city_spots[language][i]

        if back_from >= 0 and state == "play" and index > came_to:
            index = back_from
            back_from = -1
        # difficulty timer (not in learn)
        if state == "play" and index != timer_index:
            timer_index = index
            time_left = levels[rnd]["timer"] * 1000
            if not (mode == "learn" and index == 0):
                word_play_at = 0
            if mode != "learn" and listens_left is None and index < len(words):  # no limit: each word plays by itself
                if index == 0 and pygame.time.get_ticks() < kid_talking_until:
                    word_play_at = kid_talking_until
                else:
                    play_word(words[index])
        if word_play_at > 0 and pygame.time.get_ticks() >= word_play_at:
            word_play_at = 0
            if state == "play" and index < len(words):
                play_word(words[index])
        if state == "play" and mode != "learn" and levels[rnd]["timer"] > 0 and not checking and not recording and waiting_until == 0:
            time_left -= clock.get_time()
            if time_left <= 0:
                message = "Time's up!"
                play_wrong()
                index += 1
                if index == len(words):
                    state = "result"

        # ask the browser how the camera / mic / server is doing
        if lq_kind != "":
            lq_state, lq_text = lq_read()
            if lq_kind == "open":
                if lq_state == "live":
                    cam_on = True
                    checking = False
                    message = "Press Capture to take the photo"
                    lq_kind = ""
                elif lq_state == "error":
                    message = "Camera not allowed"
                    checking = False
                    lq_kind = ""
            elif lq_kind == "hunt":
                if lq_state == "busy":
                    message = "Waking the helper, wait..." if lq_text == "waking" else "Checking object..."
                elif lq_state == "done":
                    result = (lq_text == "yes")
                    diag["cards" if mode == "cards" else "hunt"] = "200 " + lq_text
                    checking = False
                    lq_kind = ""
                elif lq_state == "error":
                    message = "Try again! " + lq_text[:40]  # the reason, to find problems
                    print("hunt error:", lq_text)
                    diag["cards" if mode == "cards" else "hunt"] = lq_text.split("server ")[1][:3] if "server " in lq_text else "ERR"
                    checking = False
                    lq_kind = ""
            elif lq_kind == "speak":
                if lq_state == "busy":
                    recording = False
                    checking = True
                    message = "Waking the helper, wait..." if lq_text == "waking" else "Listening.."
                elif lq_state == "done":
                    heard_text = lq_text
                    diag["speak"] = "200"
                    print("heard:", heard_text)
                    result = is_correct(words[index], language, heard_text)
                    recording = False
                    checking = False
                    lq_kind = ""
                elif lq_state == "error":
                    message = "Try again!"
                    diag["speak"] = lq_text.split("server ")[1][:3] if "server " in lq_text else "ERR"
                    recording = False
                    checking = False
                    lq_kind = ""
        if cam_on and not (state == "play" and mode in ("hunt", "cards")):  # left the Hunt screen, close the camera
            platform.window.lq_close()
            cam_on = False
           # USE API
        if result is not None:
            if state == "play":
                score= update_score(score,result)
                hold_until = pygame.time.get_ticks() + 1500  # keep the captured picture for a moment
                if result:
                    word_results[index] = True
                    message= "Correct! " + words[index]["english"].capitalize() + "!"
                    play_correct()
                    play_word(words[index])
                    checking = True
                    waiting_until = pygame.time.get_ticks() + 4000
                else:
                    message="Try again!"
                    wrong_until = pygame.time.get_ticks() + 2000
                    play_wrong()
                    kid_say("oops")
            result = None
            # say good job 1.5 sec before moving
        if waiting_until > 0 and not praised and pygame.time.get_ticks() >= waiting_until -1500:
            kid_say("yes")
            praised=True
            # after 3 sec next card
        if waiting_until > 0 and pygame.time.get_ticks() >= waiting_until:
            waiting_until = 0
            checking = False
            praised = False
            heard_text = ""
            index += 1
            if index == len(words):
                state = "result"
            elif mode == "speak":
                message = ""
            elif mode == "hunt":
                message = ""
            else:
                message = ""
    
            # record button
        if state=="play" and recording:  # countdown on the screen
            message = "Speak now!  " + str(max(1, record_seconds - (pygame.time.get_ticks() - record_start) // 1000))

            # CLONING
        if state == "record" and recording and pygame.time.get_ticks() - record_start >= voice_sec*1000 + 200:
            sd.wait()
            recording = False
            save_wav(record_buffer[:, 0], "my_voice.wav")
            voice_done = False
            voice_status = "Creating your voice..."
            state = "creating"
            threading.Thread(target=run_voice, daemon=True).start()

        if state == "creating" and voice_done:
            state = "name"
            play_voice("welcome")
        # result
        if state == "result" and stamped and in_round and mode != "round" and (mode == "learn" or game_passed) and not confirm_ask \
                and pygame.time.get_ticks() - result_time > 3000:
            next_step()  # a passed game goes on by itself
        if state == "result" and stamped and in_round and mode in ("hunt", "speak") and not game_passed and not confirm_ask \
                and pygame.time.get_ticks() - result_time > 4500:
            state = "play"  # lost: play the game again
            begin_game()
        if later_line[0] != "" and pygame.time.get_ticks() >= later_line[1]:
            guide_say(later_line[0])
            later_line = ("", 0)
        if state== "result" and not stamped:  # after game no result yet
            reward_tier = None
            game_passed = True
            if mode == "round":  # end of the round: the stamp
                reward_tier = city_tier[rnd]
                stamp_saved = False
                guide_say("stamp_" + reward_tier)
            elif mode not in ("learn", "cards"):
                game_passed = get_tier(score, len(words)) is not None
            if mode != "round":  # sound for the end of a game
                if game_passed:
                    play_correct()
                    guide_say("passed")
                else:
                    play_wrong()
                    guide_say("failed")
            stamped= True
            result_time =pygame.time.get_ticks()  # when round end
            sfx_done = set()

        if state == "result" and mode == "round" and reward_tier is not None and not stamp_saved and result_ready():
            save_stamp(reward_tier)
            stamp_saved = True
    
        # the round picture shows 2 seconds
        if state == "banner" and pygame.time.get_ticks() - banner_start >= 2000:
            seq_pos += 1
            go_step()
        # the bus arrived
        if state == "city" and bus_start > 0 and pygame.time.get_ticks() - bus_start >= bus_time:
            bus_start = 0
            bus_at = bus_to
            go_stop(bus_at)
        if state == "play" and mode == "speak":
            pygame.mixer.music.set_volume(0)
        else:
            pygame.mixer.music.set_volume(0.15)  # normal music everywhere else

    # 2:draw
        # change bg based on state
        if state == "start":
            screen.blit(bg_home,(0,0))
        elif state in ("name", "character", "voice", "record", "creating"):  # <- changed
            screen.blit(bg_welcome,(0,0))
        elif state in ("language", "travel"):
            screen.blit(bg_map,(0,0))
        elif state == "talk" and talk_key == "welcome":
            screen.blit(bg_welcome,(0,0))
        elif state in ("talk", "ask") and (state == "ask" or talk_key.startswith(("round_", "howto_"))) and stop_background() is not None:
            screen.blit(stop_background(),(0,0))
        elif state == "city" and kit_ok:
            screen.blit(kit_bg,(0,0))
        elif state == "city" and country[language] in city_maps:
            screen.blit(city_maps[country[language]],(0,0))
        elif state in ("talk", "city", "adventure", "choose", "mode") and country[language] in intros:
            screen.blit(intros[country[language]],(0,0))
        elif state in ("city","adventure","mode","choose","talk"):
            if plain_menu:
                screen.fill(BLUE)
            else:
                screen.blit(menus[country[language]],(0,0))
        elif state in ("stamps", "dictionary"):
            if stamps_bg is None:  # blur the page we came from (once)
                if last_frame is not None:
                    small_page = pygame.transform.smoothscale(last_frame, (64, 51))
                    stamps_bg = pygame.transform.smoothscale(small_page, (800, 640))
                else:
                    stamps_bg = pygame.Surface((800, 640))
                    stamps_bg.fill(BLUE)
            screen.blit(stamps_bg, (0, 0))
            screen.blit(stamps_veil, (0, 0))
        else:
            key = (country[language], adventure.split()[0].lower())
            if key in backgrounds:
                screen.blit(backgrounds[key],(0,0))
            else:
                screen.fill(BLUE)

        # Start
        if state == "start":
            image_button(play_btn,play_normal,play_hover)

        # CHARACTER
        elif state == "character":
            draw_title_box("Pick your guide!", 70)
            for rect, picture, who in ((girl_btn, girl_img, "girl"), (boy_btn, boy_img, "boy")):
                if rect.collidepoint(pygame.mouse.get_pos()):
                    hover_sound(rect)
                    wave_pic = wave_frames[who][(pygame.time.get_ticks() // 300) % 2]  # waves, a bit bigger
                    screen.blit(wave_pic, wave_pic.get_rect(midbottom=(rect.centerx, rect.bottom + 15)))
                else:
                    screen.blit(picture, rect)
          # Voice
        elif state == "voice":  # <- new
            write("Use your own voice for the guide?", 130)
            write("Ask a parent first.", 195, jp_font)
            write("Your recording is sent to HeyGen",235,jp_font)
            write("to make the voice.", 275, jp_font)
            button(yes_btn, "Yes, record")
            button(skip_voice_btn, "Skip")

        elif state == "record":  # <- new
            write("Press the mic and read out loud:", 70)
            write("Hello! I am your new friend.", 130, jp_font)
            write("I love to learn new words.", 175, jp_font)
            write("Today I will find a pillow, a book", 220, jp_font)
            write("and a pencil. Let's have fun!", 265, jp_font)
            draw_mic()
            if recording:
                left = voice_sec - (pygame.time.get_ticks() - record_start) // 1000
                write(str(max(left, 0)) + " seconds left", 440, jp_font)
            else:
                back_icon()

        elif state == "creating":                                   
            write("Creating your voice...", 250)
            write(voice_status, 320, jp_font)
         # NAME SELECTION
        elif state == "name":
            write("What is your name?", 150)
            write (name + "|" if name != "" else "Tap here to type", 260)
            button(next_btn,"Next")

        # SELECT LANG
        elif state == "language":
            draw_title_box(name + ", pick your country!")
            over = draw_countries()
            if over != "" and over != hovered:
                play_voice("hover_" + over)
            hovered = over
        # SELECT ADVENTURE
        elif state == "city":
            draw_title_box("Where do you want to go?", 42)
            if city_note != "" and pygame.time.get_ticks() - city_note_time < 4000:  # star / city open message
                tag(city_note, (400, 100))
            for i in range(2):  # the path between the cities
                if not kit_ok:  # the kit map has its own road
                    pygame.draw.line(screen, (255, 190, 210), city_btn[i].midbottom, city_btn[i + 1].midbottom, 10)
            for i in range(3):
                draw_city(i)
            if bus_at >= 0:
                draw_bus()
            back_icon()
        elif state == "adventure":
            draw_title_box(name + ", pick your adventure!")
            for box in adventure_box:
                if adventure_box[box].collidepoint(pygame.mouse.get_pos()) and tuple(adventure_box[box]) not in hover_before:
                    play_voice("hover_" + ("home", "school", "outdoor")[list(adventure_box).index(box)])
                draw_box(adventure_box[box], adventure_icon[box], box_text[box], locked=False, stars=stars_of(list(adventure_box).index(box)))
            back_icon()
        # QUESTION (revise / cards / harder)
        elif state == "ask":
            lines, labels = ask_texts[ask_kind]
            if ask_kind in ("harder", "last"):  # the round done popup
                n = stars_of(stop)
                draw_panel(pygame.Rect(190, 110, 420, 380))
                write("Round " + str(rnd + 1) + " done!" if n < 3 else "All 3 stars!", 155)
                steps = [m for m in road if m != "cards" or show_cards_step]
                for k, m in enumerate(steps):  # the games of the round, all ticked
                    x = int(400.5 - 29 * (len(steps) - 1) + 58 * k)
                    ui_blit("progress/step_done.png", center=(x, 215))
                    icon = ui_img("mode_" + m + ".png", (28, 28))
                    if icon is not None:
                        screen.blit(icon, icon.get_rect(center=(x, 215)))
                    ui_blit("progress/tick.png", center=(x + 14, 198))
                draw_stars(n, 295, 58, pygame.time.get_ticks() - ask_start)
                if n >= 3:
                    write("You are a star!", 365, small_font)
                else:
                    write(str(3 - n) + (" round to go" if n == 2 else " rounds to go"), 365, small_font)
                if ask_kind == "harder":
                    labels = ["Round " + str(rnd + 2), "Map"]
                for k, r in enumerate(round_done_rects(len(labels))):
                    button(r, labels[k])
            else:
                draw_panel(pygame.Rect(80, 170, 640, 300))
                write(lines[0], 245)
                write(lines[1], 295)
                for k, r in enumerate(ask_rects(len(labels))):
                    button(r, labels[k])
            back_icon()
        # ROUND picture
        elif state == "banner":
            draw_say(["Round " + str(rnd + 1), "Let's go!"], abs(math.sin(pygame.time.get_ticks() / 250)) * 25)
            back_icon()
        # LEARN OR PLAY
        elif state == "choose":
            draw_title_box("Learn or play?", 42)
            write(menu_message if menu_message != "" else " ".join(box_text[adventure]), 95)
            tag(city_names[language][city], (400, 160))
            draw_bar(learn_bar, [mode_icon["learn"]], "Learn the words" if city == 0 else "Revise the words")
            draw_bar(play_bar, [mode_icon["cards"], mode_icon["hunt"], mode_icon["speak"]], "Play games")
            back_icon()
        # SELECT MODE
        elif state == "mode":
            draw_title_box("Choose your game", 42)
            write(menu_message if menu_message != "" else " ".join(box_text[adventure]), 95)
            tag(city_names[language][city], (400, 150))
            draw_bar(cards_btn, [mode_icon["cards"]], "Find the Card")
            draw_bar(hunt_btn, [mode_icon["hunt"]], "Treasure Hunt")
            draw_bar(speack_btn, [mode_icon["speak"]], "Say It Out Loud")
            back_icon()
        # FLIGHT
        elif state == "travel":
            t = min(1, (now - travel_start) / travel_time)
            e = t * t * (3 - 2 * t)
            g = min(1, (now - travel_start) / 700)
            c = travel_country
            scale = 1 + 0.3 * g
            pic = scaled_country(c, int(country_size[c][0] * scale), int(country_size[c][1] * scale))
            place = pic.get_rect(center=(lerp(country_pos[c][0], 400, g), lerp(country_pos[c][1], 330, g)))
            screen.blit(pic, place)
            draw_flag(c, place, int(96 * scale), True, True, scale)  # the flag stays where it was on the map
            for i in range(25):
                x, y = plane_pos(e * i / 25)
                pygame.draw.circle(screen, (255, 255, 255), (int(x), int(y)), 4)
            x, y = plane_pos(e)
            x2, y2 = plane_pos(min(1, e + 0.02))
            angle = math.degrees(math.atan2(-(y2 - y), x2 - x))
            pic = pygame.transform.rotozoom(plane_img, angle, 1 - 0.4 * e)
            screen.blit(pic, pic.get_rect(center=(x, y)))
            draw_title_box("Traveling to " + c.capitalize() + "...", 42)
        # GUIDE TALKS
        elif state == "talk":
            if talk_key.startswith("country"):
                tag("Welcome to " + travel_country.capitalize() + "!", (400, 40))
            draw_talk(now)
        # PASSPORT
        elif state == "stamps":
            mine = passport_stamps()
            total = len(mine)
            draw_title_box(name + "'s Passport", 40)
            write("Stamps collected: " + str(total), 92, small_font)
            if passport_book is not None:
                screen.blit(passport_book, (20, 65))
            if total == 0:
                write("No stamps yet. Play to win one!", 300)
            for i, (slot, best) in enumerate(mine):
                spot = stamp_spot(i)
                if spot is None:
                    continue
                sx, sy = spot
                parts = slot.split("|")
                lang, adv, md = parts[-3], parts[-2], parts[-1]
                picture = stamp_images.get((country[lang], "city", stop_adv.index(adv)), stamp_images.get((country[lang], md)))
                if picture is not None:
                    key = (id(picture), best)
                    if key not in stamp_cache:
                        stamp_cache[key] = pygame.transform.scale(tinted(picture, tier_color[best]), (stamp_size, stamp_size))
                    screen.blit(stamp_cache[key], (sx, sy))
                else:
                    pygame.draw.circle(screen, tier_color[best], (sx + stamp_size // 2, sy + stamp_size // 2), stamp_size // 2)
                label = tiny_font.render(city_names[lang][stop_adv.index(adv)], True, TEXT_DARK)
                screen.blit(label, label.get_rect(center=(sx + stamp_size // 2, sy + stamp_size + 12)))
                if i == viewing:
                    shown = (picture, best, adv, lang)
            if len(mine) > 18:
                small_button(page_prev_btn, "<")
                small_button(page_next_btn, ">")
            back_icon()
            if viewing >= 0:  # big stamp on a paper circle
                pygame.draw.circle(screen, (250, 241, 219), (400, 345), 165)
                pygame.draw.circle(screen, (232, 190, 185), (400, 345), 165, 4)
                picture, best, adv, lang = shown
                if picture is not None:
                    key = (id(picture), best, "big")
                    if key not in stamp_cache:
                        stamp_cache[key] = pygame.transform.scale(tinted(picture, tier_color[best]), (300, 300))
                    big = stamp_cache[key]
                    screen.blit(big, big.get_rect(center=(400, 345)))
                else:
                    pygame.draw.circle(screen, tier_color[best], (400, 345), 150)
                white_text(city_names[lang][stop_adv.index(adv)] + " - " + adv, tag_font, (400, 562))
                white_text(best.capitalize() + " stamp", small_font, (400, 594))
        elif state == "dictionary":
            draw_dictionary()
        elif state == "play":
            draw_play_ui(words[index])
        elif state == "result" and mode != "round" and in_round and game_passed:
            draw_play_ui(words[len(words) - 1])
        elif state == "result" and mode != "round":
            happy = mode == "learn" or game_passed
            if mode in ("hunt", "speak") and not game_passed:
                lines = ["Oh no! Let's do it again.", "We need more to pass the round."]
            elif in_round and will_explain():
                lines = ["Well done!"]  # the how-to talk comes next
            elif in_round:
                lines = next_lines[next_game()]  # the guide says what comes next
            elif mode == "learn":
                lines = ["Well done!", "You learned the words!"]
            elif mode == "cards":
                lines = ["Cards done!", "Nice finding!"]
            else:
                lines = ["Great job!", "Let's keep going!"]
            draw_say(lines, abs(math.sin(pygame.time.get_ticks() / 250)) * 35 if happy else 0, "oops" if mode in ("hunt", "speak") and not game_passed else "")
            if mode in ("hunt", "speak") and not game_passed:
                if not in_round:
                    small_button(say_btn, "Try again", talk_btn_font)
            else:
                small_button(say_btn, "Skip" if in_round else "Next", talk_btn_font)
            back_icon()
        elif state == "result":
            elapsed = pygame.time.get_ticks() - result_time
            if reward_tier is not None:
                elapsed -= stamp_wait
            elif mode == "learn":
                write("Well done! You learned all the words!", 100)
            else:
                write("You got " + str(score) + " out of " + str(len(words)), 100)

            if elapsed <600:
                book=passport_frames[0]  # closed
            elif elapsed <1200:
                book =passport_frames[1]  # mid
            elif reward_tier is None or elapsed <4600:
                book=passport_frames[2]  # open
            elif elapsed < 5200:
                book = passport_frames[1]  # mid
            else:
                book= passport_frames[0]
            for moment, sound in ((600, "book_open"), (2000, "stamp"), (4600, "book_close")):
                if elapsed >= moment and sound not in sfx_done and (reward_tier is not None or sound == "book_open"):
                    sfx(sound)
                    sfx_done.add(sound)
            if elapsed >= 0:
                shift = (-closed_shift, -closed_shift // 2, 0)[passport_frames.index(book)]  # closed book in the middle
                small_book = pygame.transform.scale(book, (int(book.get_width() * 0.9), int(book.get_height() * 0.9)))
                screen.blit(small_book, small_book.get_rect(center=book_spot(400 + shift, 290)))
    
            if reward_tier is None:
                write("Good try! Play again to win a stamp",545)
            else:
                # -------stamp animation ------
                if 1700<= elapsed <4600:
                    if elapsed < 3900:
                        k=phase(elapsed,2500,700)
                    else:
                        k = 1 -phase(elapsed,3900,600)
                    size = int(lerp(180,320,k) * 0.9)
                    x, y = book_spot(lerp(525,400,k), lerp(290,280,k))
                    picture= stamp_images.get((country[language], "city", city), stamp_images.get((country[language],mode)))
                    if picture is not None:
                        picture=pygame.transform.scale(tinted(picture, tier_color[reward_tier]),(size,size))
                        screen.blit(picture, picture.get_rect(center=(x,y)))
                    else:
                        pygame.draw.circle(screen, tier_color[reward_tier], (int(x), int(y)), size // 2)  # image not found just circle w color

                # tool
                if 1200 <= elapsed < 2500:
                    if elapsed < 2000:
                        tool_y = lerp(110, 270, phase(elapsed, 1200, 500))  # down
                    else:
                        tool_y = lerp(270, 110, phase(elapsed, 2000, 500))  # up
                    draw_tool(*book_spot(525, tool_y))

            if elapsed >= 5200:  # after the book closed
                if reward_tier is not None:
                    tag("Congratulations!", (400, 100), font, (226, 96, 96))
                    write("You got the " + reward_tier + " stamp!", 152, small_font)
                passport_button(collection_btn, "Show my collection")
                if in_round:
                    button(round_btn, "Continue")
            back_icon()

        if test_mode:
            screen.blit(tiny_font.render("TEST: Ctrl+W win  Ctrl+S 3 stamps  Ctrl+R reset", True, (220, 50, 50)), (8, 2))
        if diag_mode > 0:
            parts = [("Speak", diag["speak"]), ("Hunt", diag["hunt"]), ("Card", diag["cards"])]
            x = 8
            if diag_mode == 2:
                bar = pygame.Surface((800, 18), pygame.SRCALPHA)
                bar.fill((0, 0, 0, 150))
                screen.blit(bar, (0, 0))
            for n_, (label, value) in enumerate(parts):
                if value in ("-", "..."):
                    color = (170, 170, 170)  # not used yet
                elif value.startswith("200"):
                    color = (110, 230, 130)  # good
                else:
                    color = (255, 100, 100)  # a problem
                if diag_mode == 1:
                    pygame.draw.circle(screen, color, (738 + 18 * n_, 9), 5)
                else:
                    text = tiny_font.render(label + " " + value, True, color)
                    screen.blit(text, (x, 1))
                    x += text.get_width() + 22
        if icons_on():
            draw_icon(menu_btn, icon_menu)
            draw_icon(passport_btn, icon_passport)
            draw_icon(dict_btn, icon_dictionary)
            tip("Main menu" if state == "language" else "Home", menu_btn)
            tip("Passport", passport_btn)
            tip("Dictionary", dict_btn)
        if confirm_ask:
            dark = pygame.Surface((800, 640), pygame.SRCALPHA)
            dark.fill((0, 0, 0, 120))
            screen.blit(dark, (0, 0))
            draw_panel(confirm_box)
            write("Leave this round?", 245)
            write("You will lose your progress.", 295, small_font)
            button(confirm_yes, "Yes")
            button(confirm_no, "No")
        if state not in ("stamps", "dictionary"):
            last_frame = screen.copy()  # the passport blurs this page
            stamps_bg = None
        draw_door()
        hover_before = hover_now
        hover_now = set()
        pygame.display.flip()
        clock.tick(60)
        await asyncio.sleep(0)  # pygbag: let the browser breathe
pygame.quit()

asyncio.run(main())