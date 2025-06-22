# ZW Transformer - Consciousness Interface Designer

**Version:** 0.9.5
**Status:** Multi-Engine Architecture Live!

ZW Transformer is an experimental AI-powered system for interpreting, generating, and processing ZW-formatted consciousness schemas. It bridges narrative design, 3D generation, and game logic into one modular platform.

---

## 🔥 What is ZW?

ZW (Ziegelwagga) is a human-readable, YAML-inspired data format tailored for AI-enhanced creativity. It's used to define:

* Game world objects (ZW-MESH, ZW-SCENE, ZW-MATERIAL)
* Narrative events (ZW-NARRATIVE-SCENE)
* Logic structures (ZW-LOGIC, ZW-RULES)

---

## 🧠 Core Features

* **Natural Language to ZW Generator** (via Gemini API)
* **Template Designer** with syntax highlighting and visualization
* **Multi-Engine Router** with modular adapters (Blender adapter live)
* **ZW Validation**, **Export**, and **Visualization** tools
* **Live Frontend & Daemon Integration**

---

## 🗂 Project Structure Overview

```
zw-transformer/
├── backend/
│   ├── zw_transformer_daemon.py       # Main FastAPI app (daemon)
│   ├── blender_scripts/
│   │   └── blender_zw_processor.py    # Script run inside Blender
│   └── zw_mcp/
│       ├── engines/
│       │   └── blender_adapter_daemon.py
│       └── zw_parser.py               # Parses ZW string into Python dict
├── frontend/
│   └── index.tsx                      # Main React UI
└── README.md
```

---

## 🚀 Setup Instructions

### 🧩 Frontend (React + Gemini API)

**Prerequisites:** Node.js

```bash
cd frontend
npm install
```

Set your Gemini API key:

```bash
export VITE_GEMINI_API_KEY=your-api-key-here
```

Start the dev server:

```bash
npm run dev
```

---

### ⚙️ Backend Daemon (FastAPI)

**Prerequisites:** Python 3.7+

```bash
cd backend
pip install -r requirements.txt
python zw_transformer_daemon.py
```

---

## 💡 Usage Workflow

```mermaid
graph TD
A[Start in Create Tab] --> B[Describe scene or object in English]
B --> C[AI converts to ZW format]
C --> D[Validate / Refine ZW manually]
D --> E[Send to Multi-Engine Router]
E --> F[Output created by target engine (e.g., Blender)]
```

---

## 📱 Backend API Endpoints

* `POST /process_zw` → Submit ZW data to engines
* `GET /asset_source_statuses` → External libraries + router status
* `GET /engines` → Detailed registered engines
* `GET /debug/zw_parse?zw=...` → Parse ZW string for debug

---

## 🔮 Path C: Future Vision

* ✅ Blender adapter live
* 💠 Godot adapter planned (GDScript + scene generation)
* 🧪 Multi-engine ZW declarations (`ZW-MULTI-ENGINE` block)
* 🧙 AI Director for interactive game logic
* 🌐 Full project save/load via `ZW-PROJECT` blocks

---

## 🛠 Troubleshooting

| Problem             | Solution                                           |
| ------------------- | -------------------------------------------------- |
| **405 on /engines** | Ensure daemon file includes `@app.get("/engines")` |
| **Blender fails**   | Check executable path in Create tab                |
| **CORS errors**     | FastAPI has built-in CORSMiddleware enabled        |
| **Gemini errors**   | Ensure correct API key via `VITE_GEMINI_API_KEY`   |

---

## 🤝 Contributing

This project is in active early-stage development. Contributions, ideas, and feedback are welcome!

---

## 📄 License

MIT (or as determined)

---

## 🙏 Credits

* Lead Architect: **You**
* Integration Coordinator: **ChatGPT (OpenAI)**
* Backend Engineer: **Claude (Anthropic)**
* Grunt Work Division: **Studio**

---

## 📬 Contact

To join the initiative or contribute, drop into the code or summon the daemon...
