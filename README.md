# LingoQuest

A language-learning game where kids (4–12) explore Japanese, French and Spanish by learning, hunting real objects, speaking, and scanning cards, and earn passport stamps.

## Problem Statement & Motivation
- Most language apps focus on memorization and ignore how kids actually learn: by moving, playing and exploring.
- Many children grow up in multilingual homes and are curious about the words around them.
- Gen Alpha kids pick up languages fast, and early exposure helps ([cite the paper from your presentation]).
- LingoQuest connects words to the child's real surroundings (home, school, outdoor) through a camera, voice and a travel adventure.

## How It Works
Pick a guide → pick a language → pick an adventure (Home / School / Outdoor) → choose a mode:
| Mode | What the kid does |
|---|---|
| Learn | See the picture and word, listen to it |
| Cards | Show a printed LingoQuest card to the camera |
| Hunt | Find the real object at home and show it to the camera |
| Speak | Say the word into the microphone |

Each round ends with a bronze, silver or gold stamp in the passport.

## Dataset
**Card images (YOLO):** [N] photos of 12 printed cards, taken in [different places/lighting]. Labeled in Roboflow, split [train/valid/test numbers]. Source: our own photos. [Roboflow link]

**Vocabulary file (`vocab_final.csv`):** one row per word. Columns: category (Home / School / Outdoor), English, translations (Japanese with kanji, hiragana, romaji; French; Spanish), accepted answers, audio file path, picture name, and the YOLO class for card words.

## Models & Tools
| Tool | Where from | Purpose |
|---|---|---|
| YOLO26s | Ultralytics, trained on our Roboflow dataset | Detects the 12 printed cards |
| Nemotron vision model (`nvidia/nemotron-3.5-super-vl:free`) | OpenRouter | Hunt: checks whether the object is in the camera photo |
| Whisper (faster-whisper, "small") | OpenAI Whisper, run locally | Speak: turns the kid's voice into text |
| HeyGen | HeyGen API | Clones the guide's voice |
| edge-tts | Microsoft Edge TTS | Generates the word audio |
| pygame / OpenCV | Open source | The game and the camera |

**Training pipeline:** photos → Roboflow labeling and augmentation → YOLO26s training → `best.pt` → used in the game with confidence 0.3.
[Add epochs, image size, and the training environment.]

## Evaluation
**YOLO (cards):** recall 97%, precision [x], mAP50 [x], on [test set]. Baseline: [e.g. the pretrained COCO model could not detect the cards or the real objects, which is why we trained our own]. 

**Speech and Hunt (manual testing):** we tested each language by hand, with the speaker saying each word in a medium-quiet room.
- Speak: [about 7 of 10 words accepted on the first try; longer words often needed a repeat]
- Hunt: [lenient, accepted a glass as a cup and a tissue as a towel]

[Add your small results table or graph from the presentation.]

## How to Run
Requirements: Python [version], a webcam, a microphone, an internet connection.
1. Clone the repo: `git clone [repo link]`
2. (Optional) Create a virtual environment: `python -m venv venv` then activate it.
3. Install the libraries: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and add your own keys:
   ```
   OPENROUTER_KEY=your key
   HEYGEN_KEY=your key
   ```
5. Keep `app.py`, `best.pt`, `vocab_final.csv`, `images/` and `audio/` in the same folder.
6. Run: `python app.py`

## Repo Structure
```
Prototype/
├── app.py              # the game
├── best.pt             # trained YOLO26s card model
├── vocab_final.csv     # vocabulary for all languages
├── requirements.txt
├── .env.example        # names of the keys needed
├── .gitignore
├── images/             # backgrounds, guide, passport, stamps, vocab pictures
├── audio/              # word audio, music, sound effects
└── notebooks/          # training and data notebooks
```

## Limitations & Future Work
- Needs an internet connection for Hunt and the voice cloning.
- Pygame is a desktop library, so the game can't be deployed as a normal website yet. Future work: deploy it, or move it to the web.
- Hunt can be too lenient; Speak can struggle with long words and noisy rooms.
- The card detector knows only 12 cards.
- Future: more languages and words, a special card stamp, more testing with real kids.

## Screenshots
[Add your screenshots or GIFs here.]

## License & Acknowledgments
License: MIT [or whichever your instructor prefers].
Thanks to Ultralytics (YOLO), Roboflow, OpenAI Whisper and faster-whisper, OpenRouter, HeyGen, edge-tts, pygame, [General Assembly and your instructor's name].
