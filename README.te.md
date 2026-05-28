# 🏗️ CodeGraphContext (CGC)

**AI ఏజెంట్ల కోసం కోడ్ రిపోజిటరీలను ప్రశ్నించగల గ్రాఫ్‌గా మార్చండి.**


🌐 **భాషలు:**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇰🇷 [한국어](README.kor.md)
- 🇺🇦 [Українська](README.uk.md)
- 🇷🇺 [Русский](README.ru-RU.md)
- 🇮🇳 [తెలుగు](README.te.md)
- 🇯🇵 日本語 (Soon)
- 🇪🇸 Español (Soon)

🌍 **మీ భాషలో CodeGraphContext ను అనువదించడంలో సహాయం చేయండి. ఇందుకోసం issue మరియు PR సృష్టించండి: https://github.com/Shashankss1205/CodeGraphContext/issues!**

<p align="center">
  <br>
  <b>డీప్ కోడ్ గ్రాఫ్‌లు మరియు AI సందర్భం మధ్య అంతరాన్ని తగ్గించండి.</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="PyPI Downloads">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="MCP Compatible">
  <a href="https://discord.gg/VCwUdCnn">
    <img src="https://img.shields.io/discord/1421769154507309150?label=Discord&logo=discord&logoColor=white&style=flat-square">
  </a>
  <br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/stargazers">
    <img src="https://img.shields.io/github/stars/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Stars">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/network/members">
    <img src="https://img.shields.io/github/forks/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Forks">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/issues">
    <img src="https://img.shields.io/github/issues-raw/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Issues">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/pulls">
    <img src="https://img.shields.io/github/issues-pr/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="PRs">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Contributors">
  </a>
<br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml/badge.svg" alt="Tests">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml/badge.svg" alt="E2E Tests">
  </a>
  <a href="http://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/website-up-brightgreen?style=flat-square" alt="Website">
  </a>
  <a href="https://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Docs">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube Demo">
  </a>
</p>


స్థానిక కోడ్‌ను గ్రాఫ్ డేటాబేస్‌లో ఇండెక్స్ చేసి AI అసిస్టెంట్లు మరియు డెవలపర్‌లకు సందర్భాన్ని అందించే శక్తివంతమైన **MCP సర్వర్** మరియు **CLI టూల్‌కిట్**. సమగ్ర కోడ్ విశ్లేషణ కోసం స్టాండ్‌అలోన్ CLI గా ఉపయోగించండి లేదా AI-ఆధారిత కోడ్ అవగాహన కోసం MCP ద్వారా మీ ఇష్టమైన AI IDE కి కనెక్ట్ చేయండి.

---

## 📍 త్వరిత నావిగేషన్
* [🚀 త్వరిత ప్రారంభం](#quick-start) 
* [🌐 మద్దతు ఉన్న ప్రోగ్రామింగ్ భాషలు](#supported-programming-languages) 
* [🛠️ CLI టూల్‌కిట్](#for-cli-toolkit-mode) 
* [🤖 MCP సర్వర్](#-for-mcp-server-mode) 
* [🗄️ డేటాబేస్ ఎంపికలు](#database-options)
* [🔬 SCIP ఇండెక్సింగ్ (ఐచ్ఛికం)](#scip-indexing-optional)

---

## ✨ CGC ని అనుభవించండి


### 👨🏻‍💻 ఇన్‌స్టాలేషన్ మరియు CLI
> pip తో సెకన్లలో ఇన్‌స్టాల్ చేసి కోడ్ గ్రాఫ్ విశ్లేషణ కోసం శక్తివంతమైన CLI ని అన్‌లాక్ చేయండి.
![CLI ని తక్షణం ఇన్‌స్టాల్ చేసి అన్‌లాక్ చేయండి](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ సెకన్లలో ఇండెక్సింగ్
> CLI మీ tree-sitter నోడ్‌లను తెలివిగా పార్స్ చేసి గ్రాఫ్‌ను నిర్మిస్తుంది.
![MCP క్లయింట్ ఉపయోగించి ఇండెక్సింగ్](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 మీ AI అసిస్టెంట్‌ను శక్తివంతం చేయడం
> MCP ద్వారా సంక్లిష్ట కాల్-చెయిన్‌లను సహజ భాషలో ప్రశ్నించండి.
![MCP సర్వర్ ఉపయోగించడం](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## ప్రాజెక్ట్ వివరాలు
- **వెర్షన్:** 0.4.12
- **రచయితలు:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **లైసెన్స్:** MIT లైసెన్స్ (వివరాల కోసం [LICENSE](LICENSE) చూడండి)
- **వెబ్‌సైట్:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 నిర్వాహకుడు
**CodeGraphContext** ను సృష్టించి క్రియాశీలంగా నిర్వహిస్తున్నవారు:

**Shashank Shekhar Singh**  
- 📧 ఇమెయిల్: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 వెబ్‌సైట్: [codegraphcontext.vercel.app](https://codegraphcontext.vercel.app/)

*సహకారాలు మరియు అభిప్రాయాలు ఎల్లప్పుడూ స్వాగతం! ప్రశ్నలు, సూచనలు లేదా సహకార అవకాశాల కోసం సంప్రదించడానికి సంకోచించకండి.*

---

## స్టార్ చరిత్ర
[![స్టార్ చరిత్ర చార్ట్](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## ఫీచర్లు
-   **కోడ్ ఇండెక్సింగ్:** కోడ్‌ను విశ్లేషించి దాని భాగాల నాలెడ్జ్ గ్రాఫ్‌ను నిర్మిస్తుంది.
-   **సంబంధ విశ్లేషణ:** కాలర్లు, కాలీలు, క్లాస్ సోపానక్రమాలు, కాల్ చెయిన్‌లు మరియు మరిన్నింటి కోసం ప్రశ్నించండి.
-   **ముందుగా ఇండెక్స్ చేసిన బండిల్స్:** `.cgc` బండిల్స్ తో ప్రసిద్ధ రిపోజిటరీలను తక్షణమే లోడ్ చేయండి - ఇండెక్సింగ్ అవసరం లేదు! ([మరింత తెలుసుకోండి](docs/BUNDLES.md))
-   **లైవ్ ఫైల్ వాచింగ్:** డైరెక్టరీలలో మార్పుల కోసం చూసి గ్రాఫ్‌ను రియల్-టైమ్‌లో స్వయంచాలకంగా అప్‌డేట్ చేయండి (`codegraphcontext watch`).
-   **ఇంటరాక్టివ్ సెటప్:** సులభమైన సెటప్ కోసం వాడుకరి-స్నేహపూర్వక కమాండ్-లైన్ విజార్డ్.
-   **డ్యూయల్ మోడ్:** డెవలపర్ల కోసం స్టాండ్‌అలోన్ **CLI టూల్‌కిట్** గా మరియు AI ఏజెంట్ల కోసం **MCP సర్వర్** గా పని చేస్తుంది.
-   **బహుళ-భాషా మద్దతు:** 20 ప్రోగ్రామింగ్ భాషలకు పూర్తి మద్దతు.
-   **సౌకర్యవంతమైన డేటాబేస్ బ్యాకెండ్:** FalkorDB Lite (డిఫాల్ట్), KuzuDB, LadybugDB, FalkorDB Remote, Nornic DB, లేదా Neo4j (Docker/native ద్వారా అన్ని ప్లాట్‌ఫారమ్‌లు).


---

## మద్దతు ఉన్న ప్రోగ్రామింగ్ భాషలు

CodeGraphContext క్రింది భాషలకు సమగ్ర పార్సింగ్ మరియు విశ్లేషణను అందిస్తుంది:

| | భాష | | భాష | | భాష |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🏗️ | **C / C++** | #️⃣ | **C#** |
| 🐹 | **Go** | 🦀 | **Rust** | 💎 | **Ruby** |
| 🐘 | **PHP** | 🍎 | **Swift** | 🎨 | **Kotlin** |
| 🎯 | **Dart** | 🐪 | **Perl** | 🌙 | **Lua** |
| 🚀 | **Scala** | λ | **Haskell** | 💧 | **Elixir** |
| ⚛️ | **TSX** | | | | |

ప్రతి భాషా పార్సర్ సమగ్ర కోడ్ గ్రాఫ్‌ను నిర్మించడానికి ఫంక్షన్లు, క్లాస్‌లు, మెథడ్‌లు, పారామీటర్లు, వారసత్వ సంబంధాలు, ఫంక్షన్ కాల్‌లు మరియు ఇంపోర్ట్‌లను ఎక్స్‌ట్రాక్ట్ చేస్తుంది.

---

## డేటాబేస్ ఎంపికలు

CodeGraphContext మీ పర్యావరణానికి సరిపోయే బహుళ గ్రాఫ్ డేటాబేస్ బ్యాకెండ్‌లను మద్దతు ఇస్తుంది:

| ఫీచర్ | KuzuDB | LadybugDB | FalkorDB Lite | Neo4j / Nornic DB |
| :--- | :--- | :--- | :--- | :--- |
| **సాధారణ డిఫాల్ట్** | **ప్రామాణిక డిఫాల్ట్** (ఎంబెడెడ్, KuzuDB ద్వారా) | **ప్రత్యేక ఎంబెడెడ్** (Kuzu లాంటిది) | **Unix** (Python 3.12+, `falkordblite` పని చేసినప్పుడు) | స్పష్టంగా కాన్ఫిగర్ చేసినప్పుడు |
| **సెటప్** | జీరో-కాన్ఫిగ్ / ఎంబెడెడ్ | జీరో-కాన్ఫిగ్ / ఎంబెడెడ్ | జీరో-కాన్ఫిగ్ / ఇన్-ప్రాసెస్ | Docker / బాహ్య |
| **ప్లాట్‌ఫారమ్** | **అన్నీ (Windows Native, macOS, Linux)** | **అన్నీ (Windows Native, macOS, Linux)** | Unix-మాత్రమే (Linux/macOS/WSL) | అన్ని ప్లాట్‌ఫారమ్‌లు |
| **ఉపయోగ సందర్భం** | డెస్క్‌టాప్, IDE, స్థానిక అభివృద్ధి | అనుకూల పరిశోధన ప్రాజెక్ట్‌లు | ప్రత్యేక Unix అభివృద్ధి | ఎంటర్‌ప్రైజ్, భారీ గ్రాఫ్‌లు |
| **అవసరం**| `pip install kuzu` | `pip install ladybug` | `pip install falkordblite` | Neo4j Server / Docker / Nornic Cloud |
| **వేగం** | ⚡ చాలా వేగం | ⚡ వేగం | 🚀 స్కేలబుల్ |
| **నిలకడ**| అవును (డిస్క్‌కు) | అవును (డిస్క్‌కు) | అవును (డిస్క్‌కు) |

---

## SCIP ఇండెక్సింగ్ (ఐచ్ఛికం)

మీ CGC కాన్ఫిగ్ (`~/.codegraphcontext/.env`) లో `SCIP_INDEXER=true` ఉన్నప్పుడు, కొన్ని భాషలు Tree-sitter హ్యూరిస్టిక్స్ కంటే మరింత ఖచ్చితమైన కాల్‌లు మరియు వారసత్వం కోసం బాహ్య **SCIP** ఇండెక్సర్‌లను ఉపయోగిస్తాయి.

**C మరియు C++** **scip-clang** ను ఉపయోగిస్తాయి, దీనికి **`compile_commands.json`** ఫైల్ ([JSON కంపైలేషన్ డేటాబేస్](https://clang.llvm.org/docs/JSONCompilationDatabase.html)) అవసరం: ప్రతి ట్రాన్స్‌లేషన్ యూనిట్‌కు నిజమైన కంపైలర్ కమాండ్ (include paths, `-D` defines, `-std`, మొదలైనవి) తో ఒక ఎంట్రీ. ఇది లేకుండా, scip-clang నడవదు; CGC హెచ్చరిక లాగ్ చేసి ఆ రిపోకు **Tree-sitter కు ఫాల్‌బ్యాక్** అవుతుంది. ఫైల్‌ను ఉత్పత్తి చేసే సాధారణ మార్గాలు: `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` తో **CMake**, లేదా **[Bear](https://github.com/rizsotto/Bear)** తో మీ నిజమైన బిల్డ్‌ను ర్యాప్ చేయడం (ఉదా. `bear -- make`). CGC `build/` మరియు `cmake-build-*/` కింద కూడా ఆ ఫైల్ పేరును వెతుకుతుంది.

**C#** **scip-dotnet** (Roslyn) ను ఉపయోగిస్తుంది; మీకు సాధారణ **`.csproj` / `.sln`** మరియు విజయవంతమైన restore అవసరం—`compile_commands.json` అవసరం లేదు.

SCIP మీరు ఏ గ్రాఫ్ డేటాబేస్ (Kuzu, Neo4j, మొదలైనవి) ఉపయోగించినా **స్వతంత్రం**; అదే ఫ్లాగ్ అన్ని బ్యాకెండ్‌లకు వర్తిస్తుంది.

---

## Used By

CodeGraphContext is already being explored by developers and projects for:

- **Static code analysis in AI assistants**
- **Graph-based visualization of projects**
- **Dead code and complexity detection**

_If you’re using CodeGraphContext in your project, feel free to open a PR and add it here! 🚀_

---

## డిపెండెన్సీలు

- `neo4j>=5.15.0`
- `watchdog>=3.0.0`
- `stdlibs>=2023.11.18`
- `typer>=0.9.0`
- `rich>=13.7.0`
- `inquirerpy>=0.3.4`
- `python-dotenv>=1.0.0`
- `tree-sitter>=0.21.0` (Python 3.13 లో ఇన్‌స్టాల్ చేయబడదు)
- `tree-sitter-language-pack>=0.6.0` (Python 3.13 లో ఇన్‌స్టాల్ చేయబడదు)
- `pyyaml`
- `pathspec>=0.12.1`
- `falkordb>=0.1.0`
- `falkordblite>=0.1.0` (Unix మాత్రమే)
- `kuzu` (KuzuDB ఇంజిన్)
- `fastapi>=0.100.0`
- `uvicorn>=0.22.0`
- `requests>=2.28.0`
- `protobuf>=3.20,<3.21`

**గమనిక:** Python 3.10-3.14 మద్దతు ఇవ్వబడుతుంది.

---

### 🚀 ఇన్‌స్టాలేషన్ & త్వరిత ప్రారంభం

1.  **టూల్‌కిట్‌ను ఇన్‌స్టాల్ చేయండి:**
    ```bash
    pip install codegraphcontext
    ```

2.  **సమస్య పరిష్కారం (కమాండ్ కనుగొనబడలేదు):**
    `codegraphcontext` కమాండ్ కనుగొనబడకపోతే, ఈ ఒక-పంక్తి పరిష్కారాన్ని అమలు చేయండి:
    ```bash
    curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
    ```

3.  **డేటాబేస్ సెటప్ (స్వయంచాలకం):**
    CodeGraphContext డిఫాల్ట్‌గా ఎంబెడెడ్ గ్రాఫ్ డేటాబేస్‌ను ఉపయోగిస్తుంది.
    - **FalkorDB Lite:** డిఫాల్ట్ బ్యాకెండ్.
    - **KuzuDB:** క్రాస్-ప్లాట్‌ఫారమ్ ఎంబెడెడ్ బ్యాకెండ్.
    - **Neo4j:** బాహ్య సర్వర్‌ను ఉపయోగించడానికి `codegraphcontext neo4j setup` అమలు చేయండి.

---

### CLI టూల్‌కిట్ మోడ్ కోసం

**CLI కమాండ్‌లతో వెంటనే ఉపయోగించడం ప్రారంభించండి:**
```bash
# మీ ప్రస్తుత డైరెక్టరీని ఇండెక్స్ చేయండి
codegraphcontext index .

# ఇండెక్స్ చేయబడిన అన్ని రిపోజిటరీలను జాబితా చేయండి
codegraphcontext list

# ఒక ఫంక్షన్‌ను ఎవరు కాల్ చేస్తారో విశ్లేషించండి
codegraphcontext analyze callers my_function

# సంక్లిష్ట కోడ్‌ను కనుగొనండి
codegraphcontext analyze complexity --threshold 10

# డెడ్ కోడ్‌ను కనుగొనండి
codegraphcontext analyze dead-code

# లైవ్ మార్పుల కోసం వాచ్ చేయండి (ఐచ్ఛికం)
codegraphcontext watch .

# అన్ని కమాండ్‌లను చూడండి
codegraphcontext help
```

  **అన్ని అందుబాటులో ఉన్న కమాండ్‌లు మరియు ఉపయోగ సందర్భాల కోసం పూర్తి [CLI కమాండ్‌ల గైడ్](docs/CLI_COMPLETE_REFERENCE.md) చూడండి.**

### 🎨 ప్రీమియం ఇంటరాక్టివ్ విజువలైజేషన్
CodeGraphContext మీ కోడ్ యొక్క అద్భుతమైన, ఇంటరాక్టివ్ నాలెడ్జ్ గ్రాఫ్‌లను ఉత్పత్తి చేయగలదు. స్టాటిక్ డయాగ్రామ్‌ల కంటే భిన్నంగా, ఇవి ప్రీమియం వెబ్-ఆధారిత ఎక్స్‌ప్లోరర్‌లు:

- **ప్రీమియం సౌందర్యశాస్త్రం**: డార్క్ మోడ్, గ్లాస్‌మార్ఫిజం, మరియు ఆధునిక టైపోగ్రఫీ (Outfit/JetBrains Mono).
- **ఇంటరాక్టివ్ తనిఖీ**: సింబల్ సమాచారం, ఫైల్ పాత్‌లు మరియు సందర్భంతో వివరమైన సైడ్ ప్యానెల్‌ను తెరవడానికి ఏదైనా నోడ్‌ను క్లిక్ చేయండి.
- **త్వరిత శోధన**: నిర్దిష్ట సింబల్‌లను తక్షణమే కనుగొనడానికి గ్రాఫ్‌లో లైవ్-శోధన.
- **తెలివైన లేఅవుట్‌లు**: సంక్లిష్ట సంబంధాలను చదవగలిగేలా చేసే ఫోర్స్-డైరెక్టెడ్ మరియు హైరార్కికల్ లేఅవుట్‌లు.
- **జీరో-డిపెండెన్సీ వీక్షణ**: ఏదైనా ఆధునిక బ్రౌజర్‌లో పని చేసే స్టాండ్‌అలోన్ HTML ఫైల్‌లు.

```bash
# ఫంక్షన్ కాల్‌లను విజువలైజ్ చేయండి
codegraphcontext analyze calls my_function --viz

# క్లాస్ సోపానక్రమాలను అన్వేషించండి
codegraphcontext analyze tree MyClass --viz

# శోధన ఫలితాలను విజువలైజ్ చేయండి
codegraphcontext find pattern "Auth" --viz
```


---

### 🤖 MCP సర్వర్ మోడ్ కోసం

**CodeGraphContext ఉపయోగించడానికి మీ AI అసిస్టెంట్‌ను కాన్ఫిగర్ చేయండి:**
1.  **సెటప్:** మీ IDE/AI అసిస్టెంట్‌ను కాన్ఫిగర్ చేయడానికి MCP సెటప్ విజార్డ్‌ను అమలు చేయండి:
    
    ```bash
    codegraphcontext mcp setup
    ```
    
    విజార్డ్ స్వయంచాలకంగా గుర్తించి కాన్ఫిగర్ చేయగలదు:
    *   VS Code
    *   Cursor
    *   Windsurf
    *   Claude
    *   Gemini CLI
    *   ChatGPT Codex
    *   Cline
    *   RooCode
    *   Amazon Q Developer
    *   Kiro

    విజయవంతమైన కాన్ఫిగరేషన్ తర్వాత, `codegraphcontext mcp setup` అవసరమైన కాన్ఫిగరేషన్ ఫైల్‌లను ఉత్పత్తి చేసి ఉంచుతుంది:
    *   ఇది రిఫరెన్స్ కోసం మీ ప్రస్తుత డైరెక్టరీలో `mcp.json` ఫైల్‌ను సృష్టిస్తుంది.
    *   ఇది మీ డేటాబేస్ ఆధారాలను `~/.codegraphcontext/.env` లో సురక్షితంగా నిల్వ చేస్తుంది.
    *   ఇది మీరు ఎంచుకున్న IDE/CLI యొక్క సెట్టింగ్స్ ఫైల్‌ను అప్‌డేట్ చేస్తుంది (ఉదా., `.claude.json` లేదా VS Code యొక్క `settings.json`).

2.  **ప్రారంభించండి:** MCP సర్వర్‌ను లాంచ్ చేయండి:    
    ```bash
    codegraphcontext mcp start
    ```

3.  **ఉపయోగించండి:** ఇప్పుడు సహజ భాష ఉపయోగించి మీ AI అసిస్టెంట్ ద్వారా మీ కోడ్‌బేస్‌తో ఇంటరాక్ట్ చేయండి! క్రింద ఉదాహరణలు చూడండి.

---

## ఫైల్‌లను విస్మరించడం (`.cgcignore`)

మీ ప్రాజెక్ట్ మూలంలో `.cgcignore` ఫైల్‌ను సృష్టించడం ద్వారా నిర్దిష్ట ఫైల్‌లు మరియు డైరెక్టరీలను విస్మరించమని CodeGraphContext కు చెప్పవచ్చు. ఈ ఫైల్ `.gitignore` వలెనే సింటాక్స్‌ను ఉపయోగిస్తుంది.

**ఉదాహరణ `.cgcignore` ఫైల్:**
```
# బిల్డ్ ఆర్టిఫ్యాక్ట్‌లను విస్మరించండి
/build/
/dist/

# డిపెండెన్సీలను విస్మరించండి
/node_modules/
/vendor/

# లాగ్‌లను విస్మరించండి
*.log
```

---

## MCP క్లయింట్ కాన్ఫిగరేషన్

`codegraphcontext mcp setup` కమాండ్ మీ IDE/CLI ని స్వయంచాలకంగా కాన్ఫిగర్ చేయడానికి ప్రయత్నిస్తుంది. మీరు ఆటోమేటిక్ సెటప్‌ను ఉపయోగించకూడదనుకుంటే, లేదా మీ టూల్ మద్దతు ఇవ్వబడకపోతే, మీరు దాన్ని మాన్యువల్‌గా కాన్ఫిగర్ చేయవచ్చు.

మీ క్లయింట్ సెట్టింగ్స్ ఫైల్ (ఉదా., VS Code యొక్క `settings.json` లేదా `.claude.json`) కు క్రింది సర్వర్ కాన్ఫిగరేషన్‌ను జోడించండి:

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

#### pipx ద్వారా ఇన్‌స్టాల్ చేసి ఉంటే

మీరు `pipx` ఉపయోగించి CodeGraphContext ను ఇన్‌స్టాల్ చేసి ఉంటే, బదులుగా క్రింది కాన్ఫిగరేషన్‌ను ఉపయోగించండి:
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

## సహజ భాష ఇంటరాక్షన్ ఉదాహరణలు

సర్వర్ నడుస్తున్న తర్వాత, సాధారణ భాష ఉపయోగించి మీ AI అసిస్టెంట్ ద్వారా దానితో ఇంటరాక్ట్ చేయవచ్చు. మీరు చెప్పగలిగే కొన్ని ఉదాహరణలు ఇక్కడ ఉన్నాయి:

### ఫైల్‌లను ఇండెక్సింగ్ మరియు వాచింగ్

-   **కొత్త ప్రాజెక్ట్‌ను ఇండెక్స్ చేయడానికి:**
    -   "`/path/to/my-project` డైరెక్టరీలో ఉన్న కోడ్‌ను ఇండెక్స్ చేయండి."
    లేదా
    -   "`~/dev/my-other-project` లో ఉన్న ప్రాజెక్ట్‌ను కోడ్ గ్రాఫ్‌కు జోడించండి."


-   **లైవ్ మార్పుల కోసం డైరెక్టరీని వాచ్ చేయడం ప్రారంభించడానికి:**
    -   "`/path/to/my-active-project` డైరెక్టరీలో మార్పుల కోసం వాచ్ చేయండి."
    లేదా
    -   "`~/dev/main-app` లో నేను పని చేస్తున్న ప్రాజెక్ట్ కోసం కోడ్ గ్రాఫ్‌ను అప్‌డేట్ చేస్తూ ఉండండి."

    మీరు డైరెక్టరీని వాచ్ చేయమని అడిగినప్పుడు, సిస్టమ్ ఒకేసారి రెండు చర్యలు చేస్తుంది:
    1.  ఆ డైరెక్టరీలో ఉన్న అన్ని కోడ్‌ను ఇండెక్స్ చేయడానికి పూర్తి స్కాన్‌ను ప్రారంభిస్తుంది. ఈ ప్రక్రియ బ్యాక్‌గ్రౌండ్‌లో నడుస్తుంది, మరియు దాని ప్రగతిని ట్రాక్ చేయడానికి మీకు `job_id` అందుతుంది.
    2.  గ్రాఫ్‌ను రియల్-టైమ్‌లో అప్‌డేట్ చేయడానికి ఏవైనా ఫైల్ మార్పుల కోసం డైరెక్టరీని వాచ్ చేయడం ప్రారంభిస్తుంది.

    దీనర్థం మీరు సిస్టమ్‌కు డైరెక్టరీని వాచ్ చేయమని చెప్పడం ద్వారా ప్రారంభించవచ్చు, మరియు ఇది ప్రారంభ ఇండెక్సింగ్ మరియు నిరంతర అప్‌డేట్‌లు రెండింటినీ స్వయంచాలకంగా నిర్వహిస్తుంది.

### కోడ్‌ను ప్రశ్నించడం మరియు అర్థం చేసుకోవడం

-   **కోడ్ ఎక్కడ నిర్వచించబడిందో కనుగొనడం:**
    -   "`process_payment` ఫంక్షన్ ఎక్కడ ఉంది?"
    -   "నా కోసం `User` క్లాస్‌ను కనుగొనండి."
    -   "'database connection' కు సంబంధించిన ఏదైనా కోడ్‌ను చూపించండి."

-   **సంబంధాలు మరియు ప్రభావాన్ని విశ్లేషించడం:**
    -   "`get_user_by_id` ఫంక్షన్‌ను ఇతర ఏ ఫంక్షన్‌లు కాల్ చేస్తాయి?"
    -   "నేను `calculate_tax` ఫంక్షన్‌ను మార్చినట్లయితే, కోడ్ యొక్క ఇతర ఏ భాగాలు ప్రభావితమవుతాయి?"
    -   "`BaseController` క్లాస్ కోసం వారసత్వ సోపానక్రమాన్ని చూపించండి."
    -   "`Order` క్లాస్‌కు ఏ మెథడ్‌లు ఉన్నాయి?"

-   **డిపెండెన్సీలను అన్వేషించడం:**
    -   "`requests` లైబ్రరీని ఏ ఫైల్‌లు ఇంపోర్ట్ చేస్తాయి?"
    -   "`render` మెథడ్ యొక్క అన్ని ఇంప్లిమెంటేషన్‌లను కనుగొనండి."

-   **అధునాతన కాల్ చెయిన్ మరియు డిపెండెన్సీ ట్రాకింగ్ (వందల ఫైల్‌లలో):**
    CodeGraphContext విస్తారమైన కోడ్‌బేస్‌లలో సంక్లిష్ట ఎగ్జిక్యూషన్ ఫ్లోలు మరియు డిపెండెన్సీలను ట్రేస్ చేయడంలో అద్భుతంగా పని చేస్తుంది. గ్రాఫ్ డేటాబేస్‌ల శక్తిని ఉపయోగించి, ఫంక్షన్ బహుళ అమూర్తత పొరల ద్వారా లేదా అనేక ఫైల్‌లలో కాల్ చేయబడినప్పటికీ, ప్రత్యక్ష మరియు పరోక్ష కాలర్లు మరియు కాలీలను గుర్తించగలదు. ఇది దీని కోసం అమూల్యమైనది:
    -   **ప్రభావ విశ్లేషణ:** కోర్ ఫంక్షన్‌కు మార్పు యొక్క పూర్తి ప్రభావాన్ని అర్థం చేసుకోండి.
    -   **డీబగ్గింగ్:** ఎంట్రీ పాయింట్ నుండి నిర్దిష్ట బగ్ వరకు ఎగ్జిక్యూషన్ మార్గాన్ని ట్రేస్ చేయండి.
    -   **కోడ్ అవగాహన:** పెద్ద సిస్టమ్ యొక్క వివిధ భాగాలు ఎలా ఇంటరాక్ట్ అవుతాయో గ్రహించండి.

    -   "`main` ఫంక్షన్ నుండి `process_data` వరకు పూర్తి కాల్ చెయిన్‌ను చూపించండి."
    -   "`validate_input` ను ప్రత్యక్షంగా లేదా పరోక్షంగా కాల్ చేసే అన్ని ఫంక్షన్‌లను కనుగొనండి."
    -   "`initialize_system` చివరికి కాల్ చేసే అన్ని ఫంక్షన్‌లు ఏమిటి?"
    -   "`DatabaseManager` మాడ్యూల్ యొక్క డిపెండెన్సీలను ట్రేస్ చేయండి."

-   **కోడ్ నాణ్యత మరియు నిర్వహణ:**
    -   "ఈ ప్రాజెక్ట్‌లో ఏదైనా డెడ్ లేదా ఉపయోగించని కోడ్ ఉందా?"
    -   "`src/utils.py` లో `process_data` ఫంక్షన్ యొక్క సైక్లోమాటిక్ సంక్లిష్టతను లెక్కించండి."
    -   "కోడ్‌బేస్‌లో అత్యంత సంక్లిష్టమైన 5 ఫంక్షన్‌లను కనుగొనండి."

-   **రిపోజిటరీ నిర్వహణ:**
    -   "ప్రస్తుతం ఇండెక్స్ చేయబడిన అన్ని రిపోజిటరీలను జాబితా చేయండి."
    -   "`/path/to/old-project` వద్ద ఇండెక్స్ చేయబడిన రిపోజిటరీని తొలగించండి."

---

## సహకారం

సహకారాలు స్వాగతం! 🎉  
వివరమైన మార్గదర్శకాల కోసం దయచేసి మా [CONTRIBUTING.md](CONTRIBUTING.md) చూడండి.
కొత్త ఫీచర్లు, ఇంటిగ్రేషన్‌లు లేదా మెరుగుదలల కోసం ఆలోచనలు ఉంటే, [issue](https://github.com/CodeGraphContext/CodeGraphContext/issues) ఓపెన్ చేయండి లేదా Pull Request సమర్పించండి.

చర్చలలో చేరి CodeGraphContext భవిష్యత్తును రూపొందించడంలో సహాయపడండి.
