# LingoQuest

**A language-learning game where kids learn Japanese, French and Spanish words by listening, finding real objects, speaking, and scanning cards, and collect passport stamps along the way.**

*Data Science Capstone, General Assembly. Nouf Almutawea.*

---

## Problem Statement & Motivation

Young children acquire new languages most easily early in life, yet most digital language-learning apps are built around screen-based flashcards and memorization. They ignore how children naturally learn, through playing, moving and exploring, and they give little feedback on what a child actually sees or says.

Many children today also grow up in multilingual households, hearing two or three languages from family and caregivers. Most apps do not reflect this reality, and families lack a playful, hands-on way to practice vocabulary that checks the child's answer in the real world.

Gen Alpha children are surrounded by technology, and research suggests that they pick up new languages faster when they start young. LingoQuest connects the words to the child's real surroundings (home, school and outdoors) using the camera and the child's own voice.

This project asks whether **computer vision** and **speech recognition** can turn everyday objects and spoken words into a **game that checks itself**.

## Dataset Description & Sources

**1. Custom image dataset (Cards)**
- 12 everyday object classes, printed as cards
- 1,224 training images and 153 validation images
- Personally collected photos, labeled using Roboflow

**2. Vocabulary dataset (`vocab_final.csv`)**
- Japanese, French and Spanish
- Three adventures (Home, School, Outdoor) with 10 words each
- Words, translations and pronunciation (Japanese kanji, hiragana and romaji)
- Multiple accepted word variations for speech matching
- Image and audio file paths, and the YOLO class for the card words

**3. Voice data**
- A default voice sample
- The child's recording, used for personalized voice generation
- Speech input for vocabulary recognition

## Model Architecture & Training Pipeline

| Component | Model / Service | Purpose |
|---|---|---|
| Object Detection | YOLO26s (Ultralytics) | Recognizes the printed vocabulary cards (Cards mode) |
| Image Understanding | NVIDIA Nemotron 3.5 Super VL, through the OpenRouter API | Checks real objects in the camera image (Hunt mode) |
| Speech Recognition | OpenAI Whisper (`whisper-large-v3`), through the OpenRouter API (paid, pay-per-use) | Recognizes the spoken word (Speak mode) |
| Voice Cloning | HeyGen API | Personalizes the game guide's voice |
| Text-to-Speech | Edge TTS | Pronounces the vocabulary words |
| Game and camera | pygame, OpenCV | Game screens and webcam |

**Training pipeline (Cards):** personally collected photos of the 12 printed cards, taken in different places → labeled in Roboflow → split into 1,224 training and 153 validation images → YOLO26s trained with Ultralytics → `best.pt` → loaded by the game to detect the card shown to the webcam.

**Real objects and speech** use pre-trained models through APIs, so no training was needed for them.

## Evaluation & Baseline Comparison

### Cards: Object Detection (YOLO26s)

| Metric | Result |
|---|---|
| mAP50 | **97.3%** |
| Recall | **97.7%** |

*Confusion matrix:*
<img width="580" height="478" alt="image" src="https://github.com/user-attachments/assets/c00e6a16-a1f6-4ef8-b283-fa271e8836e1" />


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

| | Baseline: local Faster-Whisper | Whisper API (OpenRouter) |
|---|---|---|
| Accuracy | about 7 out of 10 words | about 7 out of 10 words on the first try, in all three languages |
| Response time | about 15–20 seconds per word | 2–6 seconds, depending on the internet |
| Internet needed | No | Yes (otherwise the game asks to try again) |

**Findings**
- Moving from the local model to the API reduced the wait from about 20 seconds to about 2–6 seconds.
- Longer words (for example the Spanish word for toothbrush) often needed a repeat, but when the word was heard the answer was accurate.
- Recording time was set to 3 seconds, which is enough for the vocabulary words.

## How to Run

**You need:** Python, a webcam, a microphone, and an internet connection.

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
├── app.py              # the game: screens, modes and API calls
├── best.pt             # trained YOLO26s card detector
├── vocab_final.csv     # vocabulary for Japanese, French and Spanish
├── requirements.txt    # Python libraries
├── .env.example        # names of the API keys to add in .env
├── .gitignore          # files Git should not upload (such as .env)
├── images/             # backgrounds, guide, passport, stamps, word pictures
├── audio/              # word audio, music and sound effects
└── notebooks/          # data preparation and training notebooks
```

## Limitations

- **Internet dependency:** Hunt, Speak and voice cloning use external APIs, so the game needs a stable internet connection. Without it, the answers fail and the child is asked to try again. Response times change with the connection speed.
- **API cost and limits:** the services depend on third-party platforms, with request limits on free plans and a cost for higher usage.
- **Limited dataset:** the card model was trained on a limited number of images and only 12 object classes.
- **Lenient object checking:** the vision model can accept objects that look similar, or miss a real one.
- **Speech recognition:** longer words may need to be repeated, and the tests were done with an adult voice in a quiet room, not with children.
- **Limited testing:** more testing is needed with children, particularly for speech recognition across French, Spanish and Japanese.

## Future Work

- **Further evaluation:** assess learning progress, engagement and gameplay experience with children.
- **Content expansion:** add more vocabulary, languages and adventures.
- **Enhanced interaction:** introduce more dialogues and interactive activities (for example, introductions about countries and cultures).
- **Progress tracking:** add player profiles and achievement records.
- **Offline capabilities:** explore locally running AI models.
- **Wider accessibility:** develop mobile and web versions.

## Screenshots
<img width="602" height="500" alt="Screenshot 2026-11-22 010104" src="https://github.com/user-attachments/assets/76be9c15-2564-4eac-9bea-373b73aee2a4" />
<img width="599" height="495" alt="Screenshot 2026-11-22 010053" src="https://github.com/user-attachments/assets/1c217f7e-36ef-4617-9056-18667078b91d" />
<img width="595" height="497" alt="Screenshot 2026-11-22 010044" src="https://github.com/user-attachments/assets/a112be9b-07e1-430e-a6cf-3e95d0c3ff8c" />
<img width="596" height="497" alt="Screenshot 2026-11-22 010038" src="https://github.com/user-attachments/assets/2f67ab7f-e542-49c7-838a-24047e5ab353" />
<img width="592" height="494" alt="Screenshot 2026-11-22 010032" src="https://github.com/user-attachments/assets/db12db30-99e7-4fc1-958c-81e60fc5d2cb" />
<img width="598" height="500" alt="Screenshot 2026-11-22 010025" src="https://github.com/user-attachments/assets/13552822-113f-4e5a-ab95-88baa6a79b0e" />
<img width="602" height="497" alt="Screenshot 2026-11-22 010018" src="https://github.com/user-attachments/assets/94727ae9-6d20-4e71-8482-104fac2f9393" />
<img width="593" height="496" alt="Screenshot 2026-11-22 010006" src="https://github.com/user-attachments/assets/0de83653-e369-4c8c-8830-3162df45828a" />
<img width="595" height="499" alt="Screenshot 2026-11-22 010000" src="https://github.com/user-attachments/assets/5a76def3-5fe4-4eea-9a89-101b79f3b0d9" />
<img width="596" height="502" alt="Screenshot 2026-11-22 005953" src="https://github.com/user-attachments/assets/f752289b-6f48-4972-bd85-5c4b7e3c7d12" />
<img width="593" height="499" alt="Screenshot 2026-11-22 010229" src="https://github.com/user-attachments/assets/3a5def44-7af6-4630-86cb-e628a0ba014c" />
<img width="595" height="494" alt="Screenshot 2026-11-22 010222" src="https://github.com/user-attachments/assets/508ee373-e496-4e35-8cf1-112ba3608f57" />
<img width="595" height="491" alt="Screenshot 2026-11-22 010216" src="https://github.com/user-attachments/assets/cc4b15c5-2b98-43d9-a445-d7de1d83ac17" />
<img width="596" height="499" alt="Screenshot 2026-11-22 010207" src="https://github.com/user-attachments/assets/9450dc89-3c4e-4089-9810-71b71a10506f" />
<img width="599" height="501" alt="Screenshot 2026-11-22 010148" src="https://github.com/user-attachments/assets/660b824f-cb55-43ed-9719-f64b72b67764" />


## Acknowledgments

General Assembly and our instructors; Ultralytics (YOLO); Roboflow; OpenAI Whisper; OpenRouter; NVIDIA Nemotron; HeyGen; Edge TTS; pygame and OpenCV.
