# LingoQuest

**A language-learning game where kids learn Japanese, French and Spanish words by listening, finding real objects, speaking, and showing cards to the camera, and collect passport stamps along the way.**

*Data Science Capstone, General Assembly. Nouf Almutawea.*

**Play it:** [LingoQuest web version](https://nalmutaweaa.github.io/Lingoquest-live/web/) (works in a browser, including on an iPad)
**Demo video:** [Watch the video]()

---

## Problem Statement & Motivation

Young children acquire new languages most easily early in life, yet most digital language-learning apps are built around screen-based flashcards and memorization. They ignore how children naturally learn, through playing, moving and exploring, and they give little feedback on what a child actually sees or says.

Many children today also grow up in multilingual households, hearing two or three languages from family and caregivers. Most apps do not reflect this reality, and families lack a playful, hands-on way to practice vocabulary that checks the child's answer in the real world.

Gen Alpha children are surrounded by technology, and research suggests that they pick up new languages faster when they start young. LingoQuest connects the words to the child's real surroundings (home, school and outdoors) using the camera and the child's own voice.

This project asks whether **computer vision** and **speech recognition** can turn everyday objects and spoken words into a **game that checks itself**.

## How the Game Works

The child picks a language and a country, travels there with a guide, and chooses one of three adventures: **Home**, **School** or **Outdoor**. Each adventure has three rounds, and each round is made of four games:

| Game | What the child does | Technology |
|---|---|---|
| **Learn** | Sees and hears each word | Vocabulary file, Edge TTS audio |
| **Speak** | Says the word out loud | Whisper speech recognition |
| **Hunt** | Finds the real object and shows it to the camera | Vision-language model |
| **Cards** | Holds up the printed card of the word | YOLO object detection |

Passing a round gives a bronze, silver or gold stamp in the child's **passport**. A **dictionary** lets the child revise all the words at any time.

## Dataset Description & Sources

**1. Custom image dataset (Cards)**
- **1,758 images** of **34 different classes**, covering the three adventures (for example apple, backpack, book, chair, clock, cup, car, tree and more)
- Personally collected photos, labeled and augmented using Roboflow
- Split: **82% training, 12% validation, 6% test**
- Augmentations applied: *(add the list from your Roboflow screenshot, for example flip, rotation, brightness, blur, noise)*

**2. Vocabulary dataset (`vocab_final.csv`)**
- Japanese, French and Spanish
- Three adventures (Home, School, Outdoor) with 10 words each
- Words, translations and pronunciation (Japanese kanji, hiragana and romaji)
- Multiple accepted word variations for speech matching
- Image and audio file paths, and the YOLO class for the card words

**3. Voice data**
- A default voice sample
- The child's recording, used for personalized voice generation (desktop version)
- Speech input for vocabulary recognition

## Model Architecture & Training Pipeline

| Component | Model / Service | Purpose |
|---|---|---|
| Object Detection | YOLO26s (Ultralytics) | Recognizes the printed vocabulary cards (Cards game) |
| Image Understanding | NVIDIA Nemotron 3.5 Super VL, through the OpenRouter API | Checks real objects in the camera image (Hunt game) |
| Speech Recognition | OpenAI Whisper (`whisper-large-v3`), through the OpenRouter API (paid, pay-per-use) | Recognizes the spoken word (Speak game) |
| Voice Cloning | HeyGen API | Personalizes the game guide's voice (desktop version) |
| Text-to-Speech | Edge TTS | Pronounces the vocabulary words |
| Game and camera | pygame, OpenCV | Game screens and webcam |
| Web version | pygbag (pygame in the browser), GitHub Pages | Runs the same game in any browser |
| Server | FastAPI on Render, ONNX Runtime | Hosts the API for the web version |

**Training pipeline (Cards):** photos of the printed cards, taken in different places and lighting → labeled and augmented in Roboflow → split into training, validation and test sets → YOLO26s trained on Google Colab (T4 GPU) with Ultralytics → `best.pt` (desktop) → exported to `best.onnx` (web server).

Training settings: image size 512, SGD optimizer, learning rate 0.001, up to 40 epochs with early stopping (patience 10)

**Real objects and speech** use pre-trained models through APIs, so no training was needed for them.


## Evaluation & Baseline Comparison

### Cards: Object Detection (YOLO26s, 34 classes)

| Metric | Validation set | Test set |
|---|---|---|
| mAP50 | **85.3%** | **81.3%** |

*Confusion matrix:* 

<img width="3000" height="2250" alt="image" src="https://github.com/user-attachments/assets/22823dd5-1cd1-4804-a773-785a1649b0f5" />

*Training results:* 

<img width="250" height="254" alt="image" src="https://github.com/user-attachments/assets/a1484a53-f5c1-4e62-bf8f-4798d4601856" />


**Findings**
- The cards that the model finds hardest are eraser, bicycle, house, toothbrush, flower, banana, spoon, shoe, ruler and calculator. The game uses the most reliable cards for each adventure.
- Our first version had only 12 classes and reached 97.3% mAP50. Going to 34 classes with more varied images is a harder task, so the score is lower, but the model now covers all the vocabulary.

**Baseline:** our first approach was fine-tuning YOLO on a Roboflow real-object dataset of about 13,000 images. It gave poor accuracy, precision and recall. That is why the project uses YOLO on printed cards, where we control the data and the results are reliable, and a vision-language model for real objects.

### Hunt: Real Object Recognition (Nemotron API)

Manual test: each word was shown to the camera with the object really there (y) and not there (n), and we compared the API's answer.

| Word | Really there | API answer | Seconds |
|---|---|---|---|
| cup | y | yes | 2.1 |
| cup | n | no | 1.5 |
| spoon | y | yes | 1.7 |
| spoon | n | no | 1.7 |
| pillow | y | yes | 1.6 |
| pillow | n | no | 1.6 |
| chair | y | yes | 11.9 |
| chair | n | no | 1.9 |
| toothbrush | y | yes | 1.9 |
| toothbrush | y | yes | 1.6 |
| toothbrush | n | no | 1.6 |
| clock | y | **no** (missed) | 1.8 |

Additional cases we tried on purpose, to see how strict the model is:

| Word | What we showed | API answer |
|---|---|---|
| towel | a tissue | **yes** (accepted wrongly) |
| cup | a glass | **yes** (accepted wrongly) |

**Findings**
- Most answers came back in about 1.5–2 seconds. The slowest (11.9 seconds) depends on the internet connection.
- The model is accurate on clear objects, but **lenient**: it can accept a similar object (a tissue as a towel, a glass as a cup). It can also miss a real object (the clock).
- **Request limits:** on the free tier, the number of requests is limited. After adding $10 of credit to the OpenRouter account, the limit stopped blocking us and our test requests were not stopped.

### Speak: Speech Recognition (Whisper API)

Manual test: we tested the words in all three languages (Japanese, French and Spanish), speaking each word ourselves in a medium-quiet room.

| | Baseline: local Faster-Whisper small | Whisper API (OpenRouter) larg |
|---|---|---|
| Accuracy | about 7 out of 10 words | about 7 out of 10 words on the first try, in all three languages |
| Response time | about 15–20 seconds per word | 2–6 seconds, depending on the internet |
| Internet needed | No | Yes (otherwise the game asks to try again) |

**Findings**
- Moving from the local model to the API reduced the wait from about 20 seconds to about 2–6 seconds.
- Longer words (for example the Spanish word for toothbrush) often needed a repeat, but when the word was heard the answer was accurate.
- Recording time was set to 3 seconds, which is enough for the vocabulary words.

## How to Run

**Play online (easiest):** open the [web version]([PASTE-WEB-LINK-HERE](https://nalmutaweaa.github.io/Lingoquest-live/web/]) in a browser. The first request after a quiet period can take up to a minute while the server wakes up.

**Run the full desktop version**

You need: Python, a webcam, a microphone, and an internet connection.

1. Download or clone the repository and open a terminal in the project folder.
2. Install the libraries:
   ```
   pip install -r requirements.txt
   ```
3. Create a file named `.env` (copy `.env.example`) and add your own API keys:
   ```
   OPENROUTER_KEY=your key
   HEYGEN_KEY=your key
   ```
4. Put the project assets (the model weights, the vocabulary file, and the images and audio folders) in the same folder as `app.py`.
5. Run the game:
   ```
   python app.py
   ```

## Repo Structure

```
Prototype/
├── app.py              # the desktop game: screens, games and API calls
├── best.pt             # trained YOLO26s card detector
├── vocab_final.csv     # vocabulary for Japanese, French and Spanish
├── requirements.txt    # Python libraries
├── .env.example        # names of the API keys to add in .env
├── .gitignore          # files Git should not upload (such as .env)
├── images/             # backgrounds, guide, passport, stamps, word pictures
├── audio/              # word audio, music and sound effects
├── notebooks/          # data preparation and training notebooks
├── web/                # the browser version (pygbag)
└── server/             # the Render API (hunt, speak, card)
```
## Game Architecture

The desktop version runs everything on the child's computer. The web version cannot run the heavy models inside the browser, so a small server on Render does that work. The API keys live only on the server, never in the browser.

<img width="2800" height="1260" alt="architecture" src="https://github.com/user-attachments/assets/37e4f7ce-7775-4eeb-86b2-42991ab18979" />

**What each part does**
- **Web browser:** shows the game, takes the camera picture and the voice recording, and sends them to the server.
- **Render server:** receives the request, runs the card model itself (`/card`), or calls OpenRouter with the secret key for the vision (`/hunt`) and speech (`/speak`) models, then sends a simple answer back to the game.
- **YOLO on the server:** the trained PyTorch model is too large for the free Render plan (512 MB of memory), so it was exported to ONNX, which is about 19 MB and runs fast on a normal CPU.
- **OpenRouter:** one API that gives access to the vision and speech models.

## Limitations

- **Internet dependency:** Hunt, Speak and voice cloning use external APIs, so the game needs a stable internet connection. Without it, the answers fail and the child is asked to try again. Response times change with the connection speed.
- **API cost and limits:** the services depend on third-party platforms, with request limits on free plans and a cost for higher usage.
- **Free server:** the Render server is on the free plan, so it goes to sleep after a period without use. The first request then takes longer while it wakes up. The free plan also has only 512 MB of memory, which is why the card model runs as a small ONNX version.
- **Web version differences:** voice cloning only works in the desktop version. The web version uses the default voices.
- **Card model:** it is more accurate for some cards than others (see the evaluation), and it was trained on photos taken in a limited number of places.
- **Lenient object checking:** the vision model can accept objects that look similar, or miss a real one.
- **Speech recognition:** longer words may need to be repeated, and the tests were done with an adult voice in a quiet room, not with children.
- **Limited testing:** more testing is needed with children, particularly for speech recognition across French, Spanish and Japanese.

## Future Work

- **Voice cloning for the web version:** run the cloning on the server so every child can hear the guide in their own voice in the browser.
- **Responsive design:** adjust the game size automatically to the screen, so it fits any phone or tablet.
- **Offline capabilities:** explore locally running AI models, so the game depends less on APIs and the internet.
- **Further evaluation:** assess learning progress, engagement and gameplay experience with children.
- **Content expansion:** add more vocabulary, languages and adventures.
- **Progress tracking:** add player profiles and achievement records that are saved online.

## Screenshots
<img width="595" height="474" alt="Screenshot 2026-11-24 025527" src="https://github.com/user-attachments/assets/e790a621-7240-468e-b576-4784ed43ef0e" />
<img width="594" height="478" alt="Screenshot 2026-11-24 025533" src="https://github.com/user-attachments/assets/b66454c4-caeb-465d-80c1-a61970bceb89" />
<img width="593" height="475" alt="Screenshot 2026-11-24 025538 - Copy - Copy" src="https://github.com/user-attachments/assets/a6f0adf5-8d3a-4a44-9860-de2552070f1a" />
<img width="596" height="475" alt="Screenshot 2026-11-24 025545 - Copy - Copy" src="https://github.com/user-attachments/assets/6c8e3b9f-7b0e-4849-8ca5-338616c63fae" />
<img width="592" height="475" alt="Screenshot 2026-11-24 025551" src="https://github.com/user-attachments/assets/6d37ae2c-d99d-48fc-8a23-2d94c3fbcae3" />
<img width="593" height="474" alt="Screenshot 2026-11-24 025714 - Copy" src="https://github.com/user-attachments/assets/4430050f-ffdd-4e80-9fed-6dcb81ccc873" />
<img width="590" height="475" alt="Screenshot 2026-11-24 025719" src="https://github.com/user-attachments/assets/8b631c9f-911f-4da4-8414-be55da765882" />
<img width="594" height="477" alt="Screenshot 2026-11-24 025724" src="https://github.com/user-attachments/assets/d930a290-407c-49d9-866d-ebe76bdc9a7a" />
<img width="595" height="479" alt="Screenshot 2026-11-24 025731" src="https://github.com/user-attachments/assets/1cac066a-3c0f-4458-93cc-3f1e5f2d0f55" />
<img width="593" height="480" alt="Screenshot 2026-11-24 025738" src="https://github.com/user-attachments/assets/a978f36b-6019-42f0-a115-aa83ddf0fef4" />
<img width="590" height="475" alt="Screenshot 2026-11-24 025743 - Copy" src="https://github.com/user-attachments/assets/2fff311f-fc86-483c-ba97-7761103ac653" />
<img width="588" height="471" alt="Screenshot 2026-11-24 025747" src="https://github.com/user-attachments/assets/33528a50-c3fe-47cd-8a0d-02c3bcbd3ada" />
<img width="588" height="473" alt="Screenshot 2026-11-24 025757" src="https://github.com/user-attachments/assets/9bde8743-87cd-40a1-9618-f55ee6ef589e" />
<img width="596" height="474" alt="Screenshot 2026-11-24 025811 - Copy" src="https://github.com/user-attachments/assets/f1711197-4b94-4233-a41e-47d88bddc9c7" />
<img width="594" height="480" alt="Screenshot 2026-11-24 025827 - Copy" src="https://github.com/user-attachments/assets/b4497680-9127-42f7-96c9-2b1348f37e39" />
<img width="591" height="470" alt="Screenshot 2026-11-24 025835 - Copy" src="https://github.com/user-attachments/assets/5ab4e9a5-8bd5-4669-b8f4-5042002fc771" />
<img width="585" height="473" alt="Screenshot 2026-11-24 025908 - Copy" src="https://github.com/user-attachments/assets/4046d1aa-78da-4cc2-9bda-3d949b0c5756" />
<img width="591" height="473" alt="Screenshot 2026-11-24 025920 - Copy" src="https://github.com/user-attachments/assets/e698426d-0613-44c9-931a-42377123e794" />
<img width="600" height="473" alt="Screenshot 2026-11-24 030000 - Copy" src="https://github.com/user-attachments/assets/e8c10b00-0be1-415d-96ff-ff68b67f1576" />
<img width="585" height="470" alt="Screenshot 2026-11-24 030010 - Copy" src="https://github.com/user-attachments/assets/fa3dcec6-5445-4bf5-82e9-4a895ee46f2f" />
<img width="584" height="479" alt="Screenshot 2026-11-24 030017 - Copy" src="https://github.com/user-attachments/assets/0d25b300-5d10-415f-b7bb-94bf16e63520" />
<img width="581" height="464" alt="Screenshot 2026-11-24 030022 - Copy" src="https://github.com/user-attachments/assets/8297681f-10d9-4673-8840-932ecdb966fd" />
<img width="593" height="475" alt="Screenshot 2026-11-24 030034 - Copy" src="https://github.com/user-attachments/assets/df31dc1c-b79e-4e27-b705-eb073dcfa039" />
<img width="588" height="473" alt="Screenshot 2026-11-24 030041 - Copy" src="https://github.com/user-attachments/assets/42ecad91-4774-4fc4-acce-55bbba0cec2a" />




## Acknowledgments

General Assembly and our instructors Jubran, Miriam and Ali; Ultralytics (YOLO); Roboflow; OpenAI Whisper; OpenRouter; NVIDIA Nemotron; HeyGen; Edge TTS; Render; pygame, pygbag and OpenCV; ONNX Runtime.
