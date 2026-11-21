# LingoQuest

**A language-learning game where kids explore Japanese, French and Spanish by learning words, hunting real objects, speaking, and scanning cards, then collecting passport stamps.**


---

## Problem Statement & Motivation

Young children acquire new languages most easily early in life, yet most language-learning apps are built around screen-based flashcards with little feedback on what a child actually sees or says. Families raising children with more than one language lack a playful, hands-on way to practice vocabulary that checks the child's answer in the real world.

This project asks whether **computer vision** and **speech recognition** can turn everyday objects and spoken words into a **game that checks itself**.

**Meet Ahmed.** He is 6 years old. He hears French from his mom, Japanese from his aunt, and Filipino from his nanny. He is curious about cultures, and he learns by playing, not by sitting with flashcards.

- **Early years matter:** research suggests children pick up new languages more easily when they start young. The earlier they practice, the more natural it feels.
- **Live in the moment:** children learn best by looking, touching and moving. A real object in their hand makes a new word easy to remember.

## How the Game Works

1. **Clone your voice:** the kid records a short text, and the guide speaks in a cloned voice (or a default voice if skipped).
2. **Pick a language and an adventure:** Japanese, French or Spanish, then Home, School or Outdoor.
3. **Pick a mode:**

| Mode | What the kid does | AI used |
|---|---|---|
| Learn | Sees the word and picture, listens to the pronunciation | Edge TTS audio |
| Cards | Shows a printed LingoQuest card to the camera | YOLO26s |
| Hunt | Finds the real object at home and shows it to the camera | Vision-language model API |
| Speak | Says the word into the microphone | Whisper |

4. **Collect stamps:** a good score earns a bronze, silver or gold passport stamp for that country and mode.

## Dataset & Data Collection

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
- The kid's recording, used for personalized voice generation
- Speech input for vocabulary recognition

## AI Models & Services

| Component | Model / Service | Purpose |
|---|---|---|
| Object Detection | YOLO26s (Ultralytics) | Recognizes the printed vocabulary cards |
| Image Understanding | NVIDIA Nemotron 3.5 Super VL, through the OpenRouter API | Checks real objects through camera images (Hunt) |
| Speech Recognition | OpenAI Whisper (`whisper-large-v3`), through the OpenRouter API (paid, pay-per-use). The earlier version used local Faster-Whisper | Recognizes spoken vocabulary (Speak) |
| Voice Cloning | HeyGen API | Personalizes the game guide's voice |
| Text-to-Speech | Edge TTS | Pronounces the vocabulary words |
| Game and camera | pygame, OpenCV | Game screens, webcam |

### Training Pipeline (Cards)
Personally collected photos of the 12 printed cards, taken in different places → labeled in Roboflow → split into 1,224 training and 153 validation images → YOLO26s trained with Ultralytics → `best.pt` → loaded in the game to detect the card shown to the webcam.

## Evaluation

### Cards: Object Detection (YOLO26s)

| Metric | Result |
|---|---|
| mAP50 | **97.3%** |
| Recall | **97.7%** |

The confusion matrix shows that almost every card is detected as the right class; the few mistakes mostly involve the background class. (Add `images/confusion_matrix.png` here.)

**Baseline comparison:** our first approach was fine-tuning YOLO on a Roboflow real-object dataset of about 13,000 images. It gave poor accuracy, precision and recall. That is why the project now uses two approaches: YOLO trained on printed cards, where we control the data and the results are reliable, and a vision-language model for real objects, which needs no training.

### Hunt: Real Object Recognition (Nemotron API)
Manual test: we showed each word to the camera with the object really there ("y") and not there ("n"), and compared the API's answer.

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

- **11 of 12 answers were correct.** The one miss was a real clock that the API said was not there.
- Most answers came back in about 1.5–2 seconds; one took 11.9 seconds (internet speed).
- The API is lenient: it accepted a glass as a cup and a tissue as a towel.

### Speak: Speech Recognition (Whisper)
Manual test: we tested the words in all three languages (Japanese, French and Spanish), speaking each word ourselves in a medium-quiet room, and compared two options.

| | Local Faster-Whisper (small) | Whisper API (OpenRouter) |
|---|---|---|
| Accuracy | about 7 out of 10 words | about 7 out of 10 words on the first try, in all three languages |
| Speed | about 15 seconds per word | 2–6 seconds, depending on the internet |
| Internet needed | No | Yes (otherwise the game says "Try again") |

- Longer words (for example the Spanish word for toothbrush) often needed a repeat, but when the word was heard the answer was accurate.
- Because the local model was slow, we moved speech recognition to the Whisper API.

## How to Run

**You need:** Python, a webcam, a microphone, and an internet connection.

1. Download or clone this repository, then open a terminal in the project folder.
2. (Optional) Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install the libraries:
   ```
   pip install -r requirements.txt
   ```
4. Create your keys file. Copy `.env.example` to a new file named `.env` and fill in your own keys:
   ```
   OPENROUTER_KEY=your key
   HEYGEN_KEY=your key
   ```
5. Make sure `app.py`, `best.pt`, `vocab_final.csv`, `images/` and `audio/` are in the same folder.
6. Start the game:
   ```
   python app.py
   ```

## Repo Structure

```
Prototype/
├── app.py              # the game (pygame main loop, modes, API calls)
├── best.pt             # trained YOLO26s card detector
├── vocab_final.csv     # vocabulary for Japanese, French, Spanish
├── requirements.txt    # Python libraries
├── .env.example        # names of the API keys you need to add in .env
├── .gitignore          # files Git should not upload (like .env)
├── images/             # backgrounds, guide, passport, stamps, word pictures
├── audio/              # word audio, music, sound effects
└── notebooks/          # data preparation and training notebooks
```

## Limitations

- **Limited dataset:** the model was trained on a limited number of images and object categories (12 cards).
- **External dependencies:** some game features rely on external APIs and an internet connection.
- **Limited testing:** more testing is needed with children, particularly for speech recognition across French, Spanish and Japanese.
- The vision API can be too lenient with objects that look alike.
- The game is built with pygame, which runs on a computer, so it can't be deployed as a normal website yet.

## Future Work

- **Further evaluation:** assess learning progress, engagement and gameplay experience.
- **Content expansion:** add more vocabulary, languages and adventures.
- **Enhanced interaction:** introduce more dialogues and interactive activities (for example, introductions about countries and cultures).
- **Progress tracking:** add player profiles and achievement records.
- **Offline capabilities:** explore locally running AI models.
- **Wider accessibility:** develop mobile and web versions.

## Screenshots

<!-- Add screenshots or a demo link here -->

## License

MIT License. You may use and change this code if you give credit.

## Acknowledgments

General Assembly and our instructors; Ultralytics (YOLO); Roboflow; OpenAI Whisper and Faster-Whisper; OpenRouter; NVIDIA Nemotron; HeyGen; Edge TTS; pygame and OpenCV. The pixel-art game images were created with AI image tools.
