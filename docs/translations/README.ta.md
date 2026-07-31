# 🏗️ CodeGraphContext (CGC)

**குறியீட் களஞ்சியங்களை AI முகவர்களுக்கான கேள்வி கேட்கக்கூடிய வரைபடமாக மாற்றவும்.**

🌐 **மொழிகள்:**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇰🇷 [한국어](README.kor.md)
- 🇺🇦 [Українська](README.uk.md)
- 🇷🇺 [Русский](README.ru-RU.md)
- 🇯🇵 [日本語](README.ja.md)
- 🇮🇳 [தமிழ்](README.ta.md)
- 🇪🇸 Español (விரைவில்)

🌍 **[GitHub Issues](https://github.com/Shashankss1205/CodeGraphContext/issues) இல் ஒரு சிக்கலை உயர்த்தி CodeGraphContext ஐ உங்கள் மொழியில் மொழிபெயர்க்க உதவுங்கள்!**

<p align="center">
  <br>
  <b>ஆழமான குறியீட் வரைபடங்களுக்கும் AI சூழலுக்கும் இடையிலான வெளியை குறைக்கவும்.</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="PyPI பதிப்பு">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="PyPI பதிவிறக்கங்கள்">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="உரிமம்">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="MCP இணக்கமான">
  <a href="https://discord.gg/VCwUdCnn">
    <img src="https://img.shields.io/discord/1421769154507309150?label=Discord&logo=discord&logoColor=white&style=flat-square">
  </a>
  <br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/stargazers">
    <img src="https://img.shields.io/github/stars/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="நட்சத்திரங்கள்">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/network/members">
    <img src="https://img.shields.io/github/forks/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="கிளைகள்">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/issues">
    <img src="https://img.shields.io/github/issues-raw/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="சிக்கல்கள்">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/pulls">
    <img src="https://img.shields.io/github/issues-pr/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="இழுப்பு கோரிக்கைகள்">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="பங்களிப்பாளர்கள்">
  </a>
<br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml/badge.svg" alt="சோதனைகள்">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml/badge.svg" alt="E2E சோதனைகள்">
  </a>
  <a href="http://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/website-up-brightgreen?style=flat-square" alt="இணையதளம்">
  </a>
  <a href="https://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="ஆவணங்கள்">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube விளக்கப்பட்டு">
  </a>
</p>


ஒரு சக்திशாली **MCP சேவயளி** மற்றும் **CLI கருவிக்கட்டு** என்பது உள்ளூர் குறியீட்டைக் கிராஃப்பு தரவுத்தளத்தில் அட்டவணைப்படுத்திக்கொண்டு AI உதவியாளர்கள் மற்றும் மேம்பாட்டாளர்களுக்கு சூழலை வழங்குகிறது. இதை ஒரு உறுப்பிலற்ற CLI என்பதாகப் பயன்படுத்தி விரிவான குறியீட் பகுப்பாய்வு செய்யலாம் அல்லது MCP மூலம் உங்கள் விருப்பமான AI IDE உடன் இணைத்து AI இயக்கிய குறியீட் புரிதலை பெறலாம்.

---

## 📍 விரைவு வழிசெலுத்தல்
* [🚀 விரைவு தொடக்கம்](#-நிறுவல்--விரைவு-தொடக்கம்) 
* [📋 முன்நிபந்தனைகள்](#-முன்நிபந்தனைகள்)
* [🏃 தொகுதியை உள்ளூரில் இயக்குவது](#-தொகுதியை-உள்ளூரில்-இயக்குவது)
* [🌐 ஆதரிக்கப்படும் நிரல் மொழிகள்](#ஆதரிக்கப்படும்-நிரல்-மொழிகள்) 
* [🛠️ CLI கருவிக்கட்டு](#cli-கருவிக்கட்டு-முறைக்கான) 
* [🤖 MCP சேவயளி](#-mcp-சேவயளி-முறைக்கான) 
* [🗄️ தரவுத்தள விருப்பங்கள்](#தரவுத்தள-விருப்பங்கள்)
* [🔬 SCIP அட்டவணைப்படுத்தல் (விருப்பம்)](#scip-அட்டவணைப்படுத்தல்விருப்பம்)

---

## ✨ CGC அनुभव பெறுங்கள்


### 👨🏻‍💻 நிறுவல் மற்றும் CLI
> pip மூலம் சில நொடிகளில் நிறுவி, குறியீட் வரைபட பகுப்பாய்வுக்கான சக்திशाली CLI ஐ திறக்கவும்.
![CLI ஐ உடனடியாக நிறுவி திறக்கவும்](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ நொடிகளில் அட்டவணைப்படுத்தல்
> CLI உங்கள் tree-sitter முனைகளை புத்திமான்திலாக பாகுபடுத்தி வரைபடத்தை உருவாக்குகிறது.
![MCP கிளையன்ட் ஐப் பயன்படுத்தி அட்டவணைப்படுத்தல்](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 உங்கள் AI உதவியாளரைக் குறிப்பிடவும்
> MCP மூலம் சிக்கலான அழைப்பு-சங்கிலிகளைப் பூர்ண நிலையில் கேட்கவும்.
![MCP சேவயளியைப் பயன்படுத்தி](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## தொகுதி விவரங்கள்
- **பதிப்பு:** 0.5.1
- **ஆசிரியர்கள்:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **உரிமம்:** MIT உரிமம் (விவரங்களுக்கு [LICENSE](LICENSE) பார்க்கவும்)
- **இணையதளம்:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 பரிபாலனையாளர்
**CodeGraphContext** பின்வருபவர் மூலம் உருவாக்கப்பட்டது மற்றும் செயலுற்றுத் தொடர்ந்து பரிபாலிக்கப்படுகிறது:

**Shashank Shekhar Singh**  
- 📧 மின்னஞ்சல்: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 இணையதளம்: [codegraphcontext.vercel.app](https://codegraphcontext.vercel.app/)

*பங்களிப்புகள் மற்றும் கருத்துக்கள் எப்போதுமே வரவேற்கப்படுகின்றன! கேள்விகள், பரிந்துரைகள் அல்லது ஒத்துழைப்பு வாய்ப்புகளுக்கு எட்டிப்பிடிக்கவும்.*

---

## நட்சத்திர வரலாறு
[![Star History Chart](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## அம்சங்கள்
-   **குறியீட் அட்டவணைப்படுத்தல்:** குறியீட்டை பகுப்பாய்வு செய்து அதன் கூறுகளின் அறிவு வரைபடத்தை உருவாக்குகிறது.
-   **உறவு பகுப்பாய்வு:** அழைப்பு வந்தவர்கள், அழைப்பு செய்தவர்கள், வகுப்பு படிநிலைகள், அழைப்பு சங்கிலிகள் மற்றும் பலவற்றுக்கு கேள்வி கேட்கவும்.
-   **பூர்வ-அட்டவணைப்படுத்தப்பட்ட கட்டுப்பு:** `.cgc` கட்டுப்பு மூலம் புகழ்பெற்ற களஞ்சியங்களை உடனடியாக ஏற்றவும் - அட்டவணைப்படுத்தல் தேவைப்பட்டாலும்! ([மேலும் தெரிந்துகொள்ளுங்கள்](docs/docs/guides/bundles.md))
-   **உயிருள்ள கோப்பு கண்காணிப்பு:** மாற்றங்களுக்கான கோப்புறையை கண்காணிக்கவும் மற்றும் வரைபடத்தை நிழலில் தானாக புதுப்பிக்கவும் (`cgc watch`).
-   **ஊடாடும் அமைப்பு:** பயனர் நட்பான கட்டளை-வரி மந்திரிக்கு உறவு அமைப்பு.
-   **இரட்டை முறை:** மேம்பாட்டாளர்களுக்கு உறுப்பிலற்ற **CLI கருவிக்கட்டு** ஆக வேலை செய்கிறது மற்றும் AI முகவர்களுக்கு **MCP சேவயளி** ஆக.
-   **பல-மொழி ஆதரவு:** 23 நிரல் மொழிகளுக்கு முழு ஆதரவு.
-   **நমনীய தரவுத்தள பின்அமைப்பு:** FalkorDB Lite (இயல்பு), KuzuDB, LadybugDB, FalkorDB சொல்லலாம், Nornic DB, அல்லது Neo4j (Docker/பூர்ணப்பிரணிலுக்கு அனைத்து தளங்கள்).


---

## ஆதரிக்கப்படும் நிரல் மொழிகள்

CodeGraphContext பின்வரும் மொழிகளுக்கு விரிவான பாகுபடுத்தல் மற்றும் பகுப்பாய்வு வழங்குகிறது:

| | மொழி | | மொழி | | மொழி |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🔵 | **C** | ➕ | **C++** |
| #️⃣ | **C#** | 🐹 | **Go** | 🦀 | **Rust** |
| 💎 | **Ruby** | 🐘 | **PHP** | 🍎 | **Swift** |
| 🎨 | **Kotlin** | 🎯 | **Dart** | 🐪 | **Perl** |
| 🌙 | **Lua** | 🚀 | **Scala** | λ | **Haskell** |
| 💧 | **Elixir** | 📜 | **Emacs Lisp (elisp)** | 🌐 | **HTML** |
| 🎨 | **CSS** | ⚛️ | **TSX** | | |

ஒவ்வொரு மொழி பாகுபடுத்தியும் செயல்பாடுகள், வகுப்புகள், முறைகள், அளவுருக்கள், மரபுர்க் உறவுகள், செயல்பாட்டு அழைப்புகள் மற்றும் இறக்குமதிகளை பிரித்தெடுத்து விரிவான குறியீட் வரைபடத்தை உருவாக்குகிறது.

---

## தரவுத்தள விருப்பங்கள்

CodeGraphContext உங்கள் சூழலுக்குத் தகுந்த பல வரைபட தரவுத்தள பின்அமைப்புகளை ஆதரிக்கிறது:

| அம்சம் | KuzuDB | LadybugDB | FalkorDB Lite | Neo4j / Nornic DB |
| :--- | :--- | :--- | :--- | :--- |
| **வழக்கிய இயல்பு** | FalkorDB Lite கிடைக்கவில்லை போது குறுக்கு-தளம் முன்சரப்பு | விருப்பம் உட்பதிக்கப்பட்ட பின்அமைப்பு | **Unix இல் இயல்பு** (Python 3.12+, `falkordblite` நிறுவப்பட்டபோது) | `cgc config db` மூலம் வெளிப்படையாக கட்டமைக்கப்பட்டபோது |
| **அமைப்பு** | பூஜ்ய-கட்டமைப்பு / உட்பதிக்கப்பட்ட | பூஜ்ய-கட்டமைப்பு / உட்பதிக்கப்பட்ட | பூஜ்ய-கட்டமைப்பு / உட்செயல்பாட்டு | Docker / வெளிப்புற |
| **தளம்** | **அனைத்தும் (Windows பூர்ணப்பிரணி, macOS, Linux)** | **அனைத்தும் (Windows பூர்ணப்பிரணி, macOS, Linux)** | Unix-மட்டும் (Linux/macOS/WSL) | அனைத்து தளங்கள் |
| **பயன்பாட்டு சந்தர்ப்பம்** | மேசைக்கணினி, IDE, உள்ளூர் மேம்பாடு | தனிப்பயன் গবேஷணை தொகுதிகள் | பிரத்यેक Unix மேம்பாடு | கழுநொடி, ப்রच்சண்ட வரைபடங்கள் |
| **தேவை**| `pip install kuzu` | `pip install ladybug` | `pip install falkordblite` | Neo4j சேவயளி / Docker / Nornic Cloud |
| **வேகம்** | ⚡ அत்यন்த வேக | ⚡ வேக | 🚀 அளவிடக்கூடிய |
| **நிலைப்பாடு**| ஆம் (வட்டிக்கு) | ஆம் (வட்டிக்கு) | ஆம் (வட்டிக்கு) |

---

## SCIP அட்டவணைப்படுத்தல் (விருப்பம்)

உங்கள் CGC கட்டமைப்பில் `SCIP_INDEXER=true` போது (`~/.codegraphcontext/.env`), சில மொழிகள் Tree-sitter விளக்கப்பு தனிதனாக விட கூடுதல் கணிப்பான அழைப்புகள் மற்றும் மரபுரு வேண்டுமான வெளிப்புற **SCIP** அட்டவணைப்படுத்தி பயன்படுத்தும்.

**C மற்றும் C++** **scip-clang** ஐ பயன்படுத்தும், இது **`compile_commands.json`** கோப்பு (ஒரு [JSON সংকलन தரவுத்தளம்](https://clang.llvm.org/docs/JSONCompilationDatabase.html)): ஒரு உபயோகிப்பு ஒவ்வொரு மொழிபெயர்ப்பு ஒன்றுடன் பூர்ணப்பிரணி சংকலன அறிவுரை (சேர்க்கை பாதைகள், `-D` வரையறைகள், `-std`, முதலியன) தேவை. இது இல்லாமல், scip-clang இயங்க முடியாது; CGC எச்சரிக்கை பதிவு செய்து **அந்த களஞ்சியத்தில் Tree-sitter க்கு வழங்கிவிட** வேண்டும். வழக்கிய குறிப்பிடல் முறைகள்: **CMake** `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` உடன், அல்லது உங்கள் பூர்ணப்பிரணி கட்டு மூலம் **[Bear](https://github.com/rizsotto/Bear)** (eg `bear -- make`). CGC `build/` மற்றும் `cmake-build-*/` கீழ் பகுதியை தேடும்.

**C#** **scip-dotnet** (Roslyn) ஐ பயன்படுத்தும்; உங்களுக்கு ஒரு பொதுவான **`.csproj` / `.sln`** மற்றும் வெற்றிகரமான மற்றக்கை தேவை—`compile_commands.json` நிறைவு ஆவசியம் இல்லை.

SCIP **எந்த வரைபட தரவுத்தளத்தை பயன்படுத்தினாலும் இருந்தாலும்** சுயசம்பந்தமாக (Kuzu, Neo4j, முதலியன); அதே கொடி அனைத்து பின்அமைப்புக்களுக்கு பொருந்தும்.

---

## பயன்படுத்தப்பட்டது

CodeGraphContext ஏற்கனவே மேம்பாட்டாளர்கள் மற்றும் தொகுதிகளால் பின்வருவனவற்றுக்கு ஆராயப்படுகிறது:

- **AI உதவியாளர்களில் நிலையான குறியீட் பகுப்பாய்வு**
- **தொகுதிகளின் வரைபட-அவசர-அடிப்படை ஒளிக்காட்டுகை**
- **இறந்த குறியீடு மற்றும் சிக்கல்தன்மை கண்டறிதல்**

_உங்கள் தொகுதியில் CodeGraphContext ஐ பயன்படுத்துகிறீர்கள் என்றால், PR திறந்து இங்கே சேர்க்கவும்! 🚀_

---

## சார்பியங்கள்

- `neo4j>=5.15.0`
- `watchdog>=3.0.0`
- `stdlibs>=2023.11.18`
- `typer>=0.9.0`
- `rich>=13.7.0`
- `inquirerpy>=0.3.4`
- `python-dotenv>=1.0.0`
- `tree-sitter>=0.21.0` (Python 3.13 இல் நிறுவப்படவில்லை)
- `tree-sitter-language-pack>=0.6.0` (Python 3.13 இல் நிறுவப்படவில்லை)
- `pyyaml`
- `pathspec>=0.12.1`
- `falkordb>=1.0,<1.6`
- `falkordblite>=0.7,<0.10` (Unix மட்டும், Python 3.12+)
- `kuzu` (KuzuDB இயন்திரம்)
- `fastapi>=0.100.0`
- `uvicorn>=0.22.0`
- `requests>=2.28.0`
- `protobuf>=3.20,<3.21`

**குறிப்பு:** Python 3.10-3.14 ஆதரிக்கப்படுகிறது.

---

### 🚀 நிறுவல் & விரைவு தொடக்கம்

1.  **கருவிக்கட்டை நிறுவுங்கள்:**
    ```bash
    pip install codegraphcontext
    ```

2.  **பிழையிலிருந்து விடுபடுங்கள் (கட்டளை கண்டுபிடிக்கப்படவில்லை):**
    `codegraphcontext` கட்டளை கண்டுபிடிக்கப்படவில்லை என்றால், இந்த ஒற்றை-வரி பிரளயத்தை இயக்கவும்:
    ```bash
    curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
    ```

3.  **தரவுத்தள அமைப்பு (தானாக):**
    CodeGraphContext உட்பதிக்கப்பட்ட வரைபட தரவுத்தளத்தை இயல்பாகப் பயன்படுத்துகிறது.
    - **FalkorDB Lite:** இயல்பு பின்அமைப்பு.
    - **KuzuDB:** குறுக்கு-தளம் உட்பதிக்கப்பட்ட பின்அமைப்பு.
    - **Neo4j:** வெளிப்புற சேவயளி பயன்படுத்த `codegraphcontext neo4j setup` இயக்கவும்.

---

## 📋 முன்நிபந்தனைகள்

CodeGraphContext நிறுவுவதற்கு முன், உங்களிடம் இருந்து உறுதிப்படுத்தவும்:

* Python 3.10 அல்லது பிறகு
* pip தொகுதி மேலாளர்
* Git (விருப்பம், களஞ்சியங்களை குறிப்பாகக் கொடி செய்வதற்கு)

உங்கள் Python நிறுவலை உறுதிப்படுத்தவும்:

```bash
python --version
```

---

## 🚀 பদ-நிர-பூவ அமைப்பு வழிமுறை

### படி 1: CodeGraphContext நிறுவுங்கள்

```bash
pip install codegraphcontext
```

இந்த கட்டளை CodeGraphContext மற்றும் அனைத்து தேவைப்பட்ட சார்பியங்களை நிறுவும்.

### படி 2: நிறுவலை சரிபார்க்கவும்

```bash
codegraphcontext --help
```

கட்டளை கிடைக்கப்பட்ட CLI கட்டளைகளை காட்டினால், நிறுவல் வெற்றிகரமாக இருந்தது.

### படி 3: தரவுத்தள அமைப்பு

CodeGraphContext உட்பதிக்கப்பட்ட தரவுத்தளத்தை இயல்பாகப் பயன்படுத்துகிறது, எனவே பெரும்பாலான பயனர்களுக்கு கூடுதல் கட்டமைப்பு தேவைப்படாது.

---

## 🏃 தொகுதியை உள்ளூரில் இயக்குவது

### களஞ்சியத்தை அட்டவணைப்படுத்தவும்

```bash
codegraphcontext index .
```

இது தற்போதைய தொகுதியை ஸ্கேன் செய்து தேடப்பட்ட குறியீட் வரைபடத்தை உருவாக்குகிறது.

### அட்டவணைப்படுத்தப்பட்ட களஞ்சியங்களைக் காட்டவும்

```bash
codegraphcontext list
```

CodeGraphContext மூலம் தற்போது அட்டவணைப்படுத்தப்பட்ட அனைத்து களஞ்சியங்களை காட்டுகிறது.

### குறியீட்டைப் பகுப்பாய்வு செய்யவும்

```bash
codegraphcontext analyze dead-code
```

அட்டவணைப்படுத்தப்பட்ட களஞ்சியத்தில் கிடைக்கக்கூடிய பயன்படுத்தாத குறியீடை கண்டுபிடிக்கிறது.

---

## ✅ அனைத்துமே செயல்பட்டுக் கொண்டுள்ளதை சரிபார்க்கவும்

களஞ்சியத்தை அட்டவணைப்படுத்திய பிறகு, இயக்கவும்:

```bash
codegraphcontext list
```

கட்டளை வெற்றிகரமாக இயக்கப்பட்டு அட்டவணைப்படுத்தப்பட்ட களஞ்சியங்களைக் காட்டினால், உங்கள் அமைப்பு முடிந்துவிட்டது மற்றும் CodeGraphContext பயன்பாட்டுக்கு தயாரை உள்ளது.

### CLI கருவிக்கட்டு முறைக்கான

**உடனடியாக CLI கட்டளைகளுடன் பயன்பாடு தொடங்கவும்:**
```bash
# உங்கள் தற்போதைய கோப்புறையை அட்டவணைப்படுத்தவும்
codegraphcontext index .

# அட்டவணைப்படுத்தப்பட்ட களஞ்சியங்களைப் பட்டியலிடவும்
codegraphcontext list

# ஒரு செயல்பாட்டுக்கு அழைப்பு கொண்ட மக்களை பகுப்பாய்வு செய்யவும்
codegraphcontext analyze callers my_function

# சிக்கலான குறியீட்டைக் கண்டுபிடிக்கவும்
codegraphcontext analyze complexity --threshold 10

# இறந்த குறியீட்டைக் கண்டுபிடிக்கவும்
codegraphcontext analyze dead-code

# உயிருள்ள மாற்றங்களுக்கு கண்காணிக்கவும் (விருப்பம்)
codegraphcontext watch .

# அனைத்து கட்டளைகளைக் காண
codegraphcontext help
```

  **அனைத்து கிடைக்கப்பட்ட கட்டளைகள் மற்றும் பயன்பாட்டு சூழ்நிலைகளுக்கு [CLI கட்டளைகள் வழிமுறை](docs/CLI_COMPLETE_REFERENCE.md) ஐக் காணவும்.**

### 🎨 பிரீமியம் ஊடாடும் ஒளிக்காட்டுகை
CodeGraphContext உங்கள் குறியீட்டின் அழகான, ஊடாடும் அறிவு வரைபடங்களை உருவாக்கக்கூடும். நிலையான வரைபடங்களை மாறாக, இவை பிரீமியம் இணையத்தளம் அடிப்படை ஆய்வுபரணை:

- **பிரீமியம் பாணிமுறை**: அন்தாரி பெயர்ப்பு, கண்ணாடிமுறை மற்றும் நவீன வர்ணனை (Outfit/JetBrains Mono).
- **ஊடாடும் ஆய்வு**: எந்த கணு கொடுக்க நிலையான பக்க பேनலை திறக்க சின்ன தகவல்கள், கோப்பு பாதைகள் மற்றும் சூழல் மூலம்.
- **விரைவு தேடலாய்தல்**: வரைபடம் முழுவதுமாக உயிருள்ள தேடலாய்தல் வழியாக குறிப்பிட்ட சின்னங்களை வெகுவிரைவில் கண்டுபிடிக்கவும்.
- **புத்திमान் அமைப்பு**: வலு-നির்देশিত மற்றும் படிநிலை அமைப்பிகள் சிக்கலான সம்பந்தங்களை வாசிக்கக்கூடிய செய்கிறது.
- **பூஜ்ய-சார்பியம் காட்டியல்**: எந்த நவீன உலாவியும் செயல்பாடுகள் உறுப்பு HTML கோப்புக்கள்.

```bash
# செயல்பாட்டு அழைப்புகளை ஒளிக்காட்டவும்
codegraphcontext analyze calls my_function --viz

# வகுப்பு படிநிலைகளை ஆராயவும்
codegraphcontext analyze tree MyClass --viz

# தேடல் விளைவுகளை ஒளிக்காட்டவும்
codegraphcontext find pattern "Auth" --viz
```


---

### 🤖 MCP சேவயளி முறைக்கான

**உங்கள் AI உதவியாளரை CodeGraphContext பயன்படுத்த கட்டமைக்கவும்:**
1.  **அமைப்பு:** MCP அமைப்பு மந்திரியை உங்கள் IDE/AI உதவியாளரை கட்டமைக்க இயக்கவும்:
    
    ```bash
    codegraphcontext mcp setup
    ```
    
    மந்திரி தானாக கண்டறிந்து கட்டமைக்கக்கூடும்:
    *   VS Code
    *   Cursor
    *   Windsurf
    *   Zed
    *   Claude
    *   Gemini CLI
    *   ChatGPT Codex
    *   Cline
    *   RooCode
    *   Amazon Q Developer
    *   Kiro
    *   Goose
    *   OpenCode

    வெற்றிகரமான கட்டமைப்பைத் தொடர்ந்து, `codegraphcontext mcp setup` தேவைப்படுத்திய கட்டமைப்பு கோப்புக்களை உருவாக்கி வைக்கிறது:
    *   உங்கள் தற்போதைய கோப்புறைতে ஒரு `mcp.json` கோப்பு உருவாக்குகிறது.
    *   உங்கள் தரவுத்தள நிலைப்பாட்டுக்களை `~/.codegraphcontext/.env` இல் பாதுகாப்புமாக சேமிக்கிறது.
    *   உங்கள் தேர்ந்தெடுக்கப்பட்ட IDE/CLI இன் அமைப்பு கோப்புக்களை புதுப்பிக்கிறது (எ.கா. `.claude.json` அல்லது VS Code இன் `settings.json`).

2.  **தொடக்கம்:** MCP சேவயளி உயிர்ப்பிக்கவும்:    
    ```bash
    codegraphcontext mcp start
    ```

3.  **பயன்பாடு:** இப்போது உங்கள் AI உதவியாளি மூலம் உங்கள் குறியீட்டுடன் பூர்ண நிலையில் ஊடாடவும்! கீழ்க் கண்ணோட்டங்களைக் காணவும்.

---

## கோப்புக்களை புறக்கணிக்கவும் (`.cgcignore`)

ஒரு `.cgcignore` கோப்புக்களை உங்கள் தொகுதியின் வேருக்கு உருவாக்கிக் கொடுத்துக்கொண்டு CodeGraphContext குறிப்பிட்ட கோப்புக்கள் மற்றும் கோப்புறைகளைப் புறக்கணிக்கக் உறுப்பு ஆகக்கூடும். இந்த கோப்பு `.gitignore` இன் சாதாரணமான தொழுவாய்தல்ஐ பயன்படுத்துகிறது.

**உதாரண `.cgcignore` கோப்பு:**
```
# நிர্மாण கணிப்பு புறக்கணிக்கவும்
/build/
/dist/

# சார்பியங்களை புறக்கணிக்கவும்
/node_modules/
/vendor/

# பதிவுக்களை புறக்கணிக்கவும்
*.log
```

---

## MCP கிளையன்ட் கட்டமைப்பு

`codegraphcontext mcp setup` கட்டளை உங்கள் IDE/CLI ஐ தானாக கட்டமைக்க முயற்சி செய்கிறது. நீங்கள் தானாக அமைப்பு பயன்படுத்த விரும்பவில்லை அல்லது உங்கள் கருவி ஆதரிக்கப்படவில்லை என்றால், நீங்கள் இதை கையேடாக கட்டமைக்கலாம்.

உங்கள் கிளையன்ட் உறுப்பு கட்டமைப்பு கோப்புக்குக் பின்வரும் சேவயளி கட்டமைப்பு சேர்க்கவும் (எ.கா. VS Code இன் `settings.json` அல்லது `.claude.json`):

```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "codegraphcontext",
      "args": [
        "mcp",
        "start"
      ],
      "env": {
        "NEO4J_URI": "YOUR_NEO4J_URI",
        "NEO4J_USERNAME": "YOUR_NEO4J_USERNAME",
        "NEO4J_PASSWORD": "YOUR_NEO4J_PASSWORD"
      },
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

#### OpenCode கட்டமைப்பு

OpenCode உடன் MCP சேவயளிகளை நிறுவி கட்டமைப்பதற்கான அறிவுரைகளுக்கு, [OpenCode MCP வழிமுறை](https://opencode.ai/docs/ko/mcp-servers/#_top) ஐக் காணவும்.

#### pipx மூலம் நிறுவப்பட்ட என்றால்

CodeGraphContext ஐ `pipx` ஐ பயன்படுத்தி நிறுவினால், பதிலாக பின்வரும் கட்டமைப்பு பயன்படுத்தவும்:
```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "pipx",
      "args": [
        "run",
        "codegraphcontext",
        "mcp",
        "start"
      ],
      "env": {
        "NEO4J_URI": "YOUR_NEO4J_URI",
        "NEO4J_USERNAME": "YOUR_NEO4J_USERNAME",
        "NEO4J_PASSWORD": "YOUR_NEO4J_PASSWORD"
      },
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

---

## பூர்ண நிலை மொழி ஊடாட்ட உதாரணங்கள்

சேவயளி இயங்கிக் கொண்டுள்ளபோது, உங்கள் AI உதவியாளி மூலம் தெளிவான ஆங்கிலத்தை பயன்படுத்தி ஊடாட்டு செய்யக்கூடும். இங்கே நீங்கள் சொல்லலாம் என்ற உதாரணங்கள் உள்ளன:

### அட்டவணைப்படுத்தல் மற்றும் கோப்புறைகளை கண்காணிக்கவும்

-   **ஒரு புதிய தொகுதியை அட்டவணைப்படுத்த:**
    -   "தயவுசெய்து `/path/to/my-project` கோப்புறைতுள்ள குறியீட்டை அட்டவணைப்படுத்தவும்."
    அல்லது
    -   "தொகுதியை `~/dev/my-other-project` ல் குறியீட் வரைபடத்தில் சேர்க்கவும்."


-   **உயிருள்ள மாற்றங்களுக்கான கோப்புறையை கண்காணிக்க தொடங்க:**
    -   "மாற்றங்களுக்கான `/path/to/my-active-project` கோப்புறையை கண்காணிக்கவும்."
    அல்லது
    -   "நான் `~/dev/main-app` இல் வேலை செய்கிறேன் என்ற தொகுதிக்கு குறியீட் வரைபடத்தை புதுப்பிக்கப்பிடிக்கவும்."

    நீங்கள் கோப்புறையை கண்காணிக்க கூறும் போது, கணினி இரண்டு செயல்பாடுகளை ஒரே நேரத்தில் செய்கிறது:
    1.  அந்த கோப்புறைதுள்ள அனைத்து குறியீட்டை அட்டவணைப்படுத்த ஒரு முழு ஸ்கேன் உதயப்படுத்தி கொண்டுள்ளது. இந்த செயல்பாடு பின்நிலையில் இயங்கிக் கொண்டுள்ளது மற்றும் நீங்கள் ஒரு `job_id` பெறுவீர்கள்.
    2.  வரைபடத்தை நிழலில் புதுப்பிக்க கோப்பு மாற்றங்களுக்கு கண்காணிக்க தொடங்கிக் கொண்டுள்ளது.

    இது நீங்கள் எளிமையாக ஒரு கோப்புறையை கண்காணிக்க சொல்லத் தொடங்கினால் கணினி ஆரம்ப அட்டவணைப்படுத்தல் மற்றும் தொடர் புதுப்பிப்புகளை தனியுமாக பை கொண்டு செல்கிறது என்பதாம்.

### குறியீட்டை கேட்பது மற்றும் புரிந்துகொள்ளல்

-   **குறியீடு வரையறுக்கப்பட்ட மிக முக்கியமாக:**
    -   "`process_payment` செயல்பாடு எங்கே உள்ளது?"
    -   "எனக்கு `User` வகுப்பை கண்டறியவும்."
    -   "'தரவுத்தளத் தொடர்பு' சம்பந்தப்பட்ட எதாவது குறியீட்டை எனக்குக் காட்டவும்."

-   **உறவுகளை பகுப்பாய்வு மற்றும் தாக்கம்:**
    -   "`get_user_by_id` செயல்பாட்டை வேறு எந்த செயல்பாடுகள் அழைக்கும்?"
    -   "நான் `calculate_tax` செயல்பாட்டை மாற்றினால், குறியீட்டின் வேறு எந்த பகுதிகள் பாதிக்கப்படும்?"
    -   "`BaseController` வகுப்பின் மரபுர் படிநிலையை எனக்குக் காட்டவும்."
    -   "`Order` வகுப்பில் என்ன முறைகள் உள்ளன?"

-   **சார்பியங்களை ஆராய:**
    -   "`requests` நூலகத்தை எந்த கோப்புக்கள் இறக்குமதி செய்கிறது?"
    -   "`render` முறையின் அனைத்து செயல்படுத்தைகள் கண்டுபிடிக்கவும்."

-   **உன்னத அழைப்பு சங்கிலி மற்றும் சார்பியம் கண்டறிதல் (நூற்றுக்கணக்கான கோப்புக்கள் விவரம்):**
    CodeGraphContext சிக்கலான செயல்பாட்டு பாதைகள் மற்றும் சார்பியங்களை বিশাল குறியீட் களஞ்சியம் முழுவதுமாக சுவடுக் சித்த கொள்ளும். வரைபட தரவுத்தளங்களின் சக்திக்கு பயன்படுத்தி, அது நேரடி மற்றும் மறைமுக பேசிக் மக்கள் மற்றும் அழைப்பு செய்யப்பட்டவர்கள் கணிக்க முடியும், செயல்பாடு பல அபிலாஷ் அடுக்குகள் அல்லது பல்நாட்காட்சி குறியீடுகளுக்கு முழு அழைக்கப்பட்டாலும் கூட. இது பொண்ணை தகுந்த:
    -   **தாக்கம் பகுப்பாய்வு:** ஒரு முக்கிய செயல்பாட்டுக்கு மாற்றத்தின் முழு சரளை விளைவு புரிந்துகொள்ளவும்.
    -   **பிழைதிருத்தல்:** ஒரு உள்ளுष்ठி புள்ளியிலிருந்து ஒரு குறிப்பிட்ட பிழைக்கு செயல்பாட்டுப் பாதை சுவடுக் செய்யவும்.
    -   **குறியீட் புரிதல்:** ஒரு பெரிய கணினியின் வெவ்வேறு பகுதிகள் எப்படி ஊடாடுகிறது புரிந்துகொள்ளவும்.

    -   "`main` செயல்பாட்டிலிருந்து `process_data` க்கு முழு அழைப்பு சங்கிலியை எனக்குக் காட்டவும்."
    -   "`validate_input` ஐ நேரடி அல்லது மறைமுக ஆக அழைக்கும் அனைத்து செயல்பாடுகளைக் கண்டுபிடிக்கவும்."
    -   "`initialize_system` இறுதியாக அழைக்கும் அனைத்து செயல்பாடுகள் என்ன?"
    -   "`DatabaseManager` தொகுதியின் சார்பியங்களை சுவடுக் செய்யவும்."

-   **குறியீட் மஞ்சம் மற்றும் பரிப்பாலனை:**
    -   "இந்த தொகுதியில் உள்ள இறந்த அல்லது பயன்படுத்தாத குறியீடு உள்ளதா?"
    -   "`src/utils.py` இல் `process_data` செயல்பாட்டின் சுழற்சிய சிக்கல்தன்மை கணக்கிடவும்."
    -   "குறியீட் களஞ்சியத்தில் 5 பெரும்பாலான சிக்கலான செயல்பாடுகளைக் கண்டுபிடிக்கவும்."

-   **களஞ்சிய மேலாணமை:**
    -   "தற்போது அட்டவணைப்படுத்தப்பட்ட அனைத்து களஞ்சியங்களைப் பட்டியலிடவும்."
    -   "`/path/to/old-project` இல் அட்டவணைப்படுத்தப்பட்ட களஞ்சியத்தை நீக்கவும்."

---

## பங்களிப்பு

பங்களிப்புக்கள் வரவேற்கப்படுகின்றன! 🎉  
விபரணை வழிமுறைகளுக்கு [CONTRIBUTING.md](.github/CONTRIBUTING.md) பார்க்கவும்.
உங்களிடம் புதிய பண்புக்கூறு, ஒருங்கிணைப்புக்கள் அல்லது சுधार கருதுவ தோல்வி இருந்தால், [சிக்கல்](https://github.com/CodeGraphContext/CodeGraphContext/issues) திறந்து அல்லது இழுப்பு கோரிக்கை சமர்ப்பிக்கவும்.

விவாதங்களில் பங்கு பெறவும் மற்றும் CodeGraphContext இன் ভவிஷ்யத்தை வடிவமைக்க உதவ பெறவும்.
