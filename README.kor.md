# 🏗️ CodeGraphContext (CGC)

**코드 저장소를 AI 에이전트가 쿼리할 수 있는 그래프로 변환합니다.**

🌐 **언어:**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇰🇷 [한국어](README.kor.md)
- 🇺🇦 [Українська](README.uk.md)
- 🇷🇺 [Русский](README.ru-RU.md)
- 🇯🇵 日本語 (준비 중)
- 🇪🇸 Español (준비 중)

🌍 **CodeGraphContext를 여러분의 언어로 번역하는 데 도움을 주세요! https://github.com/Shashankss1205/CodeGraphContext/issues 에서 이슈와 PR을 생성해 주세요!**

<p align="center">
  <br>
  <b>딥 코드 그래프와 AI 컨텍스트 사이의 간극을 해소합니다.</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="PyPI 버전">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="PyPI 다운로드">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="라이선스">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="MCP 호환">
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
    <img src="https://img.shields.io/github/issues-raw/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="이슈">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/pulls">
    <img src="https://img.shields.io/github/issues-pr/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="PR">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="기여자">
  </a>
<br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml/badge.svg" alt="테스트">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml/badge.svg" alt="E2E 테스트">
  </a>
  <a href="http://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/website-up-brightgreen?style=flat-square" alt="웹사이트">
  </a>
  <a href="https://CodeGraphContext.github.io/CodeGraphContext/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="문서">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube 데모">
  </a>
</p>


로컬 코드를 그래프 데이터베이스에 인덱싱하여 AI 어시스턴트와 개발자에게 컨텍스트를 제공하는 강력한 **MCP 서버** 및 **CLI 도구 모음**입니다. 포괄적인 코드 분석을 위한 독립 실행형 CLI로 사용하거나, MCP를 통해 선호하는 AI IDE에 연결하여 AI 기반 코드 이해를 수행할 수 있습니다.

---

## 📍 빠른 탐색
* [🚀 빠른 시작](#빠른-시작)
* [🌐 지원 프로그래밍 언어](#지원-프로그래밍-언어)
* [🛠️ CLI 도구 모음](#cli-도구-모음-모드)
* [🤖 MCP 서버](#-mcp-서버-모드)
* [🗄️ 데이터베이스 옵션](#데이터베이스-옵션)

---

## ✨ CGC 체험하기


### 👨🏻‍💻 설치 및 CLI
> pip으로 몇 초 만에 설치하고 강력한 코드 그래프 분석 CLI를 사용하세요.
![CLI를 즉시 설치하고 사용하기](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ 몇 초 만에 인덱싱
> CLI가 tree-sitter 노드를 지능적으로 파싱하여 그래프를 구축합니다.
![MCP 클라이언트를 사용한 인덱싱](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 AI 어시스턴트 지원
> 자연어를 사용하여 MCP를 통해 복잡한 호출 체인을 쿼리하세요.
![MCP 서버 사용](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## 프로젝트 세부 정보
- **버전:** 0.3.9
- **저자:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **라이선스:** MIT License (자세한 내용은 [LICENSE](LICENSE) 참조)
- **웹사이트:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 메인테이너
**CodeGraphContext**는 다음에 의해 제작 및 적극적으로 유지 관리됩니다:

**Shashank Shekhar Singh**
- 📧 이메일: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 웹사이트: [codegraphcontext.vercel.app](http://codegraphcontext.vercel.app/)

*기여와 피드백은 언제나 환영합니다! 질문, 제안 또는 협업 기회에 대해 자유롭게 연락해 주세요.*

---

## Star 기록
[![Star History Chart](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## 기능
-   **코드 인덱싱:** 코드를 분석하고 구성 요소의 지식 그래프를 구축합니다.
-   **관계 분석:** 호출자, 피호출자, 클래스 계층 구조, 호출 체인 등을 쿼리합니다.
-   **사전 인덱싱된 번들:** `.cgc` 번들로 유명한 저장소를 즉시 로드합니다 - 인덱싱이 필요 없습니다! ([자세히 알아보기](docs/BUNDLES.md))
-   **실시간 파일 감시:** 디렉토리의 변경 사항을 감시하고 그래프를 실시간으로 자동 업데이트합니다 (`cgc watch`).
-   **대화형 설정:** 쉬운 설정을 위한 사용자 친화적인 명령줄 마법사.
-   **듀얼 모드:** 개발자를 위한 독립 실행형 **CLI 도구 모음**과 AI 에이전트를 위한 **MCP 서버**로 작동합니다.
-   **다국어 지원:** 14개 프로그래밍 언어 완벽 지원.
-   **유연한 데이터베이스 백엔드:** KùzuDB (기본, 모든 플랫폼에서 설정 불필요), FalkorDB Lite (Unix 전용), FalkorDB Remote, 또는 Neo4j (Docker/네이티브를 통한 모든 플랫폼).

---

## 지원 프로그래밍 언어

CodeGraphContext는 다음 언어에 대한 포괄적인 파싱 및 분석을 제공합니다:

| | 언어 | | 언어 | | 언어 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🏗️ | **C / C++** | #️⃣ | **C#** |
| 🐹 | **Go** | 🦀 | **Rust** | 💎 | **Ruby** |
| 🐘 | **PHP** | 🍎 | **Swift** | 🎨 | **Kotlin** |
| 🎯 | **Dart** | 🐪 | **Perl** | | |

각 언어 파서는 함수, 클래스, 메서드, 매개변수, 상속 관계, 함수 호출 및 임포트를 추출하여 포괄적인 코드 그래프를 구축합니다.

---

## 데이터베이스 옵션

CodeGraphContext는 사용 환경에 맞는 다양한 그래프 데이터베이스 백엔드를 지원합니다:

| 기능 | KùzuDB (기본) | FalkorDB Lite | Neo4j |
| :--- | :--- | :--- | :--- |
| **설정** | 설정 불필요 / 임베디드 | 설정 불필요 / 인프로세스 | Docker / 외부 |
| **플랫폼** | **모든 플랫폼 (Windows, macOS, Linux)** | Unix 전용 (Linux/macOS/WSL) | 모든 플랫폼 |
| **사용 사례** | 데스크톱, IDE, 로컬 개발 | 특화된 Unix 개발 | 엔터프라이즈, 대규모 그래프 |
| **요구 사항**| `pip install kuzu` | `pip install falkordblite` | Neo4j Server / Docker |
| **속도** | ⚡ 매우 빠름 | ⚡ 빠름 | 🚀 확장 가능 |
| **영속성**| 예 (디스크) | 예 (디스크) | 예 (디스크) |

---

## 사용 사례

CodeGraphContext는 이미 다음과 같은 용도로 개발자와 프로젝트에서 활용되고 있습니다:

- **AI 어시스턴트에서의 정적 코드 분석**
- **프로젝트의 그래프 기반 시각화**
- **데드 코드 및 복잡도 탐지**

_프로젝트에서 CodeGraphContext를 사용하고 계시다면, PR을 생성하여 여기에 추가해 주세요! 🚀_

---

## 의존성

- `neo4j>=5.15.0`
- `watchdog>=3.0.0`
- `stdlibs>=2023.11.18`
- `typer[all]>=0.9.0`
- `rich>=13.7.0`
- `inquirerpy>=0.3.7`
- `python-dotenv>=1.0.0`
- `tree-sitter>=0.21.0`
- `tree-sitter-language-pack>=0.6.0`
- `pyyaml`
- `pytest`
- `nbformat`
- `nbconvert>=7.16.6`
- `pathspec>=0.12.1`

**참고:** Python 3.10-3.14이 지원됩니다.

---

## 빠른 시작
### 핵심 도구 모음 설치
```
pip install codegraphcontext
```

### 'cgc' 명령어를 찾을 수 없는 경우, 다음 한 줄 수정 스크립트를 실행하세요:
```
curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
```

---

## 시작하기

### 📋 CodeGraphContext 모드 이해하기
CodeGraphContext는 **두 가지 모드**로 작동하며, 둘 중 하나 또는 모두 사용할 수 있습니다:

#### 🛠️ 모드 1: CLI 도구 모음 (독립 실행형)
CodeGraphContext를 코드 분석을 위한 **강력한 명령줄 도구 모음**으로 사용하세요:
- 터미널에서 직접 코드베이스를 인덱싱하고 분석
- 코드 관계 쿼리, 데드 코드 찾기, 복잡도 분석
- 코드 그래프 및 의존성 시각화
- CLI 명령을 통한 직접 제어를 원하는 개발자에게 적합

#### 🤖 모드 2: MCP 서버 (AI 기반)
CodeGraphContext를 AI 어시스턴트를 위한 **MCP 서버**로 사용하세요:
- AI IDE (VS Code, Cursor, Windsurf, Claude, Kiro 등) 연결
- AI 에이전트가 자연어를 사용하여 코드베이스를 쿼리
- 자동 코드 이해 및 관계 분석
- AI 지원 개발 워크플로에 적합

**두 모드 모두 사용 가능합니다!** 한 번 설치하면 CLI 명령을 직접 사용하거나 AI 어시스턴트에 연결할 수 있습니다.

### 설치 (모든 모드)

1.  **설치:** `pip install codegraphcontext`
    <details>
    <summary>⚙️ 문제 해결: <code>cgc</code> 명령어를 찾을 수 없는 경우</summary>

    설치 후 <i>"cgc: command not found"</i> 오류가 발생하면 PATH 수정 스크립트를 실행하세요:

    **Linux/Mac:**
    ```bash
    # 수정 스크립트 다운로드
    curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh

    # 실행 권한 부여
    chmod +x post_install_fix.sh

    # 스크립트 실행
    ./post_install_fix.sh

    # 터미널을 재시작하거나 셸 설정을 다시 로드
    source ~/.bashrc  # zsh 사용자는 ~/.zshrc
    ```

    **Windows (PowerShell):**
    ```powershell
    # 수정 스크립트 다운로드
    curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh

    # bash로 실행 (Git Bash 또는 WSL 필요)
    bash post_install_fix.sh

    # PowerShell을 재시작하거나 프로필을 다시 로드
    . $PROFILE
    ```
    </details>

2.  **데이터베이스 설정 (자동)**

    - **KùzuDB (기본):** Windows, macOS, Linux에서 설정 없이 기본적으로 실행됩니다. `pip install kuzu`만 하면 준비 완료!
    - **FalkorDB Lite (대안):** Python 3.12+의 Unix/macOS/WSL에서 지원됩니다.
    - **Neo4j (대안):** Neo4j를 사용하거나 서버 기반 접근 방식을 선호하는 경우: `cgc neo4j setup` 실행

---

### CLI 도구 모음 모드

**CLI 명령으로 즉시 사용 시작:**
```bash
# 현재 디렉토리 인덱싱
cgc index .

# 모든 인덱싱된 저장소 목록 조회
cgc list

# 함수를 호출하는 곳 분석
cgc analyze callers my_function

# 복잡한 코드 찾기
cgc analyze complexity --threshold 10

# 데드 코드 찾기
cgc analyze dead-code

# 실시간 변경 사항 감시 (선택 사항)
cgc watch .

# 모든 명령어 보기
cgc help
```

**사용 가능한 모든 명령어와 사용 시나리오는 [CLI 명령 가이드](CLI_Commands.md)를 참조하세요.**

### 🎨 프리미엄 대화형 시각화
CodeGraphContext는 코드의 멋진 대화형 지식 그래프를 생성할 수 있습니다. 정적 다이어그램과 달리 프리미엄 웹 기반 탐색기입니다:

- **프리미엄 미학**: 다크 모드, 글래스모피즘, 모던 타이포그래피 (Outfit/JetBrains Mono).
- **대화형 검사**: 노드를 클릭하면 심볼 정보, 파일 경로 및 컨텍스트가 포함된 상세 사이드 패널이 열립니다.
- **빠른 검색**: 그래프에서 특정 심볼을 즉시 찾을 수 있는 실시간 검색.
- **지능형 레이아웃**: 복잡한 관계를 읽기 쉽게 만드는 힘 기반 및 계층적 레이아웃.
- **무의존성 보기**: 모든 최신 브라우저에서 작동하는 독립 실행형 HTML 파일.

```bash
# 함수 호출 시각화
cgc analyze calls my_function --viz

# 클래스 계층 구조 탐색
cgc analyze tree MyClass --viz

# 검색 결과 시각화
cgc find pattern "Auth" --viz
```


---

### 🤖 MCP 서버 모드

**AI 어시스턴트에서 CodeGraphContext를 사용하도록 설정:**
1.  **설정:** MCP 설정 마법사를 실행하여 IDE/AI 어시스턴트를 구성합니다:

    ```bash
    cgc mcp setup
    ```

    마법사가 자동으로 감지하고 구성할 수 있는 도구:
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

    성공적으로 구성되면 `cgc mcp setup`이 필요한 설정 파일을 생성하고 배치합니다:
    *   현재 디렉토리에 참조용 `mcp.json` 파일을 생성합니다.
    *   데이터베이스 자격 증명을 `~/.codegraphcontext/.env`에 안전하게 저장합니다.
    *   선택한 IDE/CLI의 설정 파일(예: `.claude.json` 또는 VS Code의 `settings.json`)을 업데이트합니다.

2.  **시작:** MCP 서버를 실행합니다:
    ```bash
    cgc mcp start
    ```

3.  **사용:** 이제 AI 어시스턴트를 통해 자연어로 코드베이스와 상호작용하세요! 아래 예시를 참조하세요.

---

## 파일 무시하기 (`.cgcignore`)

프로젝트 루트에 `.cgcignore` 파일을 만들어 CodeGraphContext가 특정 파일과 디렉토리를 무시하도록 설정할 수 있습니다. 이 파일은 `.gitignore`와 동일한 구문을 사용합니다.

**`.cgcignore` 파일 예시:**
```
# 빌드 산출물 무시
/build/
/dist/

# 의존성 무시
/node_modules/
/vendor/

# 로그 무시
*.log
```

---

## MCP 클라이언트 설정

`cgc mcp setup` 명령은 IDE/CLI를 자동으로 구성하려고 시도합니다. 자동 설정을 사용하지 않거나 도구가 지원되지 않는 경우 수동으로 구성할 수 있습니다.

클라이언트의 설정 파일(예: VS Code의 `settings.json` 또는 `.claude.json`)에 다음 서버 설정을 추가하세요:

```json
{
  "mcpServers": {
    "CodeGraphContext": {
      "command": "cgc",
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

---

## 자연어 상호작용 예시

서버가 실행 중이면 AI 어시스턴트를 통해 일반 한국어로 상호작용할 수 있습니다. 다음은 사용할 수 있는 예시입니다:

### 인덱싱 및 파일 감시

-   **새 프로젝트를 인덱싱하려면:**
    -   "`/path/to/my-project` 디렉토리의 코드를 인덱싱해 주세요."
    또는
    -   "`~/dev/my-other-project`에 있는 프로젝트를 코드 그래프에 추가해 주세요."


-   **실시간 변경 사항을 위해 디렉토리 감시를 시작하려면:**
    -   "`/path/to/my-active-project` 디렉토리의 변경 사항을 감시해 주세요."
    또는
    -   "`~/dev/main-app`에서 작업 중인 프로젝트의 코드 그래프를 최신 상태로 유지해 주세요."

    디렉토리 감시를 요청하면 시스템이 두 가지 작업을 동시에 수행합니다:
    1.  해당 디렉토리의 모든 코드를 인덱싱하기 위한 전체 스캔을 시작합니다. 이 프로세스는 백그라운드에서 실행되며, 진행 상황을 추적하기 위한 `job_id`를 받게 됩니다.
    2.  그래프를 실시간으로 최신 상태로 유지하기 위해 파일 변경 사항 감시를 시작합니다.

    즉, 시스템에 디렉토리를 감시하라고 지시하기만 하면 초기 인덱싱과 지속적인 업데이트를 모두 자동으로 처리합니다.

### 코드 쿼리 및 이해

-   **코드가 정의된 위치 찾기:**
    -   "`process_payment` 함수는 어디에 있나요?"
    -   "`User` 클래스를 찾아 주세요."
    -   "'데이터베이스 연결'과 관련된 코드를 보여 주세요."

-   **관계 및 영향도 분석:**
    -   "`get_user_by_id` 함수를 호출하는 다른 함수는 무엇인가요?"
    -   "`calculate_tax` 함수를 변경하면 코드의 어떤 부분이 영향을 받나요?"
    -   "`BaseController` 클래스의 상속 계층 구조를 보여 주세요."
    -   "`Order` 클래스에는 어떤 메서드가 있나요?"

-   **의존성 탐색:**
    -   "`requests` 라이브러리를 임포트하는 파일은 어떤 것이 있나요?"
    -   "`render` 메서드의 모든 구현을 찾아 주세요."

-   **고급 호출 체인 및 의존성 추적 (수백 개의 파일에 걸쳐):**
    CodeGraphContext는 광범위한 코드베이스에서 복잡한 실행 흐름과 의존성을 추적하는 데 뛰어납니다. 그래프 데이터베이스의 힘을 활용하여 함수가 여러 추상화 계층이나 수많은 파일을 통해 호출되는 경우에도 직접 및 간접 호출자와 피호출자를 식별할 수 있습니다. 이는 다음과 같은 경우에 매우 유용합니다:
    -   **영향도 분석:** 핵심 함수 변경의 전체 파급 효과를 이해합니다.
    -   **디버깅:** 진입점에서 특정 버그까지의 실행 경로를 추적합니다.
    -   **코드 이해:** 대규모 시스템의 여러 부분이 어떻게 상호작용하는지 파악합니다.

    -   "`main` 함수에서 `process_data`까지의 전체 호출 체인을 보여 주세요."
    -   "`validate_input`을 직접 또는 간접적으로 호출하는 모든 함수를 찾아 주세요."
    -   "`initialize_system`이 최종적으로 호출하는 모든 함수는 무엇인가요?"
    -   "`DatabaseManager` 모듈의 의존성을 추적해 주세요."

-   **코드 품질 및 유지보수:**
    -   "이 프로젝트에 사용되지 않는 데드 코드가 있나요?"
    -   "`src/utils.py`의 `process_data` 함수의 순환 복잡도를 계산해 주세요."
    -   "코드베이스에서 가장 복잡한 함수 5개를 찾아 주세요."

-   **저장소 관리:**
    -   "현재 인덱싱된 모든 저장소를 나열해 주세요."
    -   "`/path/to/old-project`에 있는 인덱싱된 저장소를 삭제해 주세요."

---

## 기여하기

기여를 환영합니다! 🎉
자세한 가이드라인은 [CONTRIBUTING.md](CONTRIBUTING.md)를 참조하세요.
새로운 기능, 통합 또는 개선에 대한 아이디어가 있으시면 [이슈](https://github.com/CodeGraphContext/CodeGraphContext/issues)를 열거나 Pull Request를 제출해 주세요.

토론에 참여하고 CodeGraphContext의 미래를 함께 만들어 가세요.
