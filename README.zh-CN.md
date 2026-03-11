# 🏗️ CodeGraphContext (CGC)

**将代码仓库转换为 AI 智能体可查询的图图谱。**

🌐 **语言 (Languages):**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇯🇵 日本語 (即将推出)
- 🇷🇺 Русский (即将推出)
- 🇪🇸 Español (即将推出)

🌍 **帮助我们将 CodeGraphContext 翻译成您的语言！**


<p align="center">
  <br>
  <b>连接深层代码图与 AI 上下文。</b>
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
  <img src="https://img.shields.io/badge/MCP-兼容-green?style=flat-square" alt="MCP Compatible">
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
  <a href="https://CodeGraphContext.github.io/CodeGraphContext/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Docs">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube Demo">
  </a>
</p>

这是一个强大的 **MCP 服务端** 和 **CLI 工具包**，它将本地代码索引到图数据库中，为 AI 助手和开发者提供上下文信息。你可以将其作为独立的 CLI 进行全面的代码分析，或者通过 MCP 将其连接到你最喜欢的 AI IDE，实现 AI 驱动的代码理解。

---

## 📍 快速导航
* [🚀 快速入门](#快速入门) 
* [🌐 支持的编程语言](#支持的编程语言) 
* [🛠️ CLI 工具包模式](#cli-工具包模式) 
* [🤖 MCP 服务端模式](#mcp-服务端模式) 
* [🗄️ 数据库选项](#数据库选项)

---

## ✨ 体验 CGC


### 👨🏻‍💻 安装与 CLI
> 使用 pip 在几秒钟内完成安装，解锁强大的代码图分析 CLI。
![立即安装并解锁 CLI](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ 秒级索引
> CLI 智能解析 tree-sitter 节点以构建代码图。
![使用 MCP 客户端进行索引](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 赋能你的 AI 助手
> 使用自然语言通过 MCP 查询复杂的调用链。
![使用 MCP 服务端](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## 项目详情
- **版本:** 0.3.0
- **作者:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **许可证:** MIT License (详见 [LICENSE](LICENSE))
- **网站:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 维护者
**CodeGraphContext** 由以下人员创建并积极维护：

**Shashank Shekhar Singh**  
- 📧 邮箱: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 网站: [codegraphcontext.vercel.app](http://codegraphcontext.vercel.app/)

*非常欢迎贡献和反馈！如有任何疑问、建议或合作机会，请随时联系。*

---

## Star 历史
[![Star 历史图表](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## 功能特性
-   **代码索引:** 分析代码并构建其组件的知识图谱。
-   **关系分析:** 查询调用者、被调用者、类层次结构、调用链等。
-   **预索引包:** 使用 `.cgc` 包即时加载知名仓库 - 无需索引！([了解更多](docs/BUNDLES.md))
-   **实时文件监控:** 监控目录更改并实时自动更新代码图 (`cgc watch`)。
-   **交互式设置:** 用户友好的命令行向导，轻松完成设置。
-   **双重模式:** 既可以作为开发者的独立 **CLI 工具包**，也可以作为 AI 智能体的 **MCP 服务端**。
-   **多语言支持:** 全面支持 14 种编程语言。
-   **灵活的数据库后端:** KùzuDB（默认，所有平台零配置）、FalkorDB Lite（仅限 Unix）、FalkorDB Remote 或 Neo4j（通过 Docker/原生支持所有平台）。

---

## 支持的编程语言

CodeGraphContext 为以下语言提供全面的解析和分析：

| | 语言 | | 语言 | | 语言 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🏗️ | **C / C++** | #️⃣ | **C#** |
| 🐹 | **Go** | 🦀 | **Rust** | 💎 | **Ruby** |
| 🐘 | **PHP** | 🍎 | **Swift** | 🎨 | **Kotlin** |
| 🎯 | **Dart** | 🐪 | **Perl** | | |

每个语言解析器都会提取函数、类、方法、参数、继承关系、函数调用和导入，以构建全面的代码图。

---

## 数据库选项

CodeGraphContext 支持多种图数据库后端以适应你的环境：

| 特性 | KùzuDB (默认) | FalkorDB Lite | Neo4j |
| :--- | :--- | :--- | :--- |
| **设置** | 零配置 / 嵌入式 | 零配置 / 进程内 | Docker / 外部 |
| **平台** | **所有 (Windows 原生, macOS, Linux)** | 仅限 Unix (Linux/macOS/WSL) | 所有平台 |
| **用例** | 桌面、IDE、本地开发 | 专门的 Unix 开发 | 企业、大规模图调研 |
| **要求**| `pip install kuzu` | `pip install falkordblite` | Neo4j 服务端 / Docker |
| **速度** | ⚡ 极快 | ⚡ 快速 | 🚀 可扩展 |
| **持久化**| 是 (保存至磁盘) | 是 (保存至磁盘) | 是 (保存至磁盘) |

---

## 谁在用
CodeGraphContext 已经吸引了开发者和项目在以下方面的探索：

- **AI 助手中的静态代码分析**
- **项目的图化可视化**
- **死代码和复杂度检测**

_如果你正在项目中使用 CodeGraphContext，欢迎提交 PR 并添加到这里！ 🚀_

---

## 依赖
- `neo4j>=5.15.0`
- `watchdog>=3.0.0`
- `stdlibs>=2023.11.18`
- `typer[all]>=0.9.0`
- `rich>=13.7.0`
- `inquirerpy>=0.3.4`
- `python-dotenv>=1.0.0`
- `tree-sitter>=0.21.0`
- `tree-sitter-language-pack>=0.6.0`
- `pyyaml`
- `pytest`
- `nbformat`
- `nbconvert>=7.16.6`
- `pathspec>=0.12.1`

**注意:** 支持 Python 3.10-3.14。

---

## 快速入门
### 安装核心工具包
```
pip install codegraphcontext
```

### 如果找不到 'cgc' 命令，请运行我们的一键修复：
```
curl -sSL [https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh](https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh) | bash
```

---

## 入门指南

### 📋 了解 CodeGraphContext 模式
CodeGraphContext 以 **两种模式** 运行，你可以使用其中一种或同时使用：

#### 🛠️ 模式 1：CLI 工具包 (独立使用)
将 CodeGraphContext 作为**强大的命令行工具包**进行代码分析：
- 直接从终端索引和分析代码库
- 查询代码关系，查找死代码，分析复杂度
- 可视化代码图和依赖关系
- 非常适合希望通过 CLI 命令直接控制的开发者

#### 🤖 模式 2：MCP 服务端 (AI 驱动)
将 CodeGraphContext 作为 AI 助手的 **MCP 服务端** 使用：
- 连接到 AI IDE（VS Code, Cursor, Windsurf, Claude, Kiro 等）
- 让 AI 智能体使用自然语言查询你的代码库
- 自动进行代码理解和关系分析
- 非常适合 AI 辅助开发工作流

**你可以同时使用这两种模式！** 安装一次后，既可以直接使用 CLI 命令，也可以连接到你的 AI 助手。

### 安装 (两种模式通用)

1.  **安装:** `pip install codegraphcontext`
    <details>
    <summary>⚙️ 故障排除: 如果找不到 <code>cgc</code> 命令</summary>

    如果在安装后遇到 <i>"cgc: command not found"</i>，请运行 PATH 修复脚本：
    
    **Linux/Mac:**
    ```bash
    # 下载修复脚本
    curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh
    
    # 添加可执行权限
    chmod +x post_install_fix.sh
    
    # 运行脚本
    ./post_install_fix.sh
    
    # 重启终端或重新加载 shell 配置
    source ~/.bashrc  # 或对于 zsh 用户 source ~/.zshrc
    ```
    
    **Windows (PowerShell):**
    ```powershell
    # 下载修复脚本
    curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh
    
    # 使用 bash 运行 (需要 Git Bash 或 WSL)
    bash post_install_fix.sh
    
    # 重启 PowerShell 或重新加载配置文件
    . $PROFILE
    ``` 
    </details>

2.  **数据库设置 (自动)**
    
    - **KùzuDB (默认):** 在 Windows、macOS 和 Linux 上原生运行，无需任何设置。只需 `pip install kuzu` 即可！
    - **FalkorDB Lite (替代方案):** 支持 Unix/macOS/WSL 上的 Python 3.12+。
    - **Neo4j (替代方案):** 如果你想使用 Neo4j，或者倾向于基于服务端的方案，请运行：`cgc neo4j setup`

---

### CLI 工具包模式

**立即开始使用 CLI 命令：**
```bash
# 索引当前目录
cgc index .

# 列出所有已索引的仓库
cgc list

# 分析谁调用了某个函数
cgc analyze callers my_function

# 查找复杂代码
cgc analyze complexity --threshold 10

# 查找死代码
cgc analyze dead-code

# 监控实时更改 (可选)
cgc watch .

# 查看所有命令
cgc help
```

**查看完整的 [CLI 命令指南](CLI_Commands.md) 以获取所有可用命令和使用场景。**

### 🎨 高级交互式可视化
CodeGraphContext 可以为你的代码生成精美的交互式知识图谱。不同于静态图表，这些是高级的基于 Web 的浏览器：

- **精美美学**: 暗黑模式、毛玻璃效果和现代字体 (Outfit/JetBrains Mono)。
- **交互式检查**: 点击任何节点即可打开包含符号信息、文件路径和上下文的详细侧边栏。
- **快速搜索**: 通过实时搜索即时查找图中的特定符号。
- **智能布局**: 力导向和分层布局，使复杂的关系清晰易读。
- **零依赖查看**: 独立的 HTML 文件，可在任何现代浏览器中运行。

```bash
# 可视化函数调用
cgc analyze calls my_function --viz

# 探索类层次结构
cgc analyze tree MyClass --viz

# 可视化搜索结果
cgc find pattern "Auth" --viz
```


---

### 🤖 MCP 服务端模式

**配置你的 AI 助手使用 CodeGraphContext：**
1.  **设置:** 运行 MCP 设置向导来配置你的 IDE/AI 助手：
    
    ```bash
    cgc mcp setup
    ```
    
    该向导可以自动检测并配置：
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

    配置成功后，`cgc mcp setup` 将生成并放置必要的配置文件：
    *   在当前目录创建一个 `mcp.json` 文件供参考。
    *   将你的数据库凭据安全地存储在 `~/.codegraphcontext/.env`。
    *   更新你选择的 IDE/CLI 的设置文件（例如 `.claude.json` 或 VS Code 的 `settings.json`）。

2.  **启动:** 启动 MCP 服务端：    
    ```bash
    cgc mcp start
    ```

3.  **使用:** 现在可以通过自然语言与你的 AI 助手交互来探索代码库了！请参阅下面的示例。

---

## 忽略文件 (`.cgcignore`)

你可以通过在项目根目录创建一个 `.cgcignore` 文件来告知 CodeGraphContext 忽略特定的文件和目录。该文件使用与 `.gitignore` 相同的语法。

**`.cgcignore` 文件示例：**
```
# 忽略构建产物
/build/
/dist/

# 忽略依赖
/node_modules/
/vendor/

# 忽略日志
*.log
```

---

## MCP 客户端配置

`cgc mcp setup` 命令尝试自动配置你的 IDE/CLI。如果你选择不使用自动设置，或者你的工具不受支持，你可以进行手动配置。

将以下服务端配置添加到客户端的设置文件中（例如 VS Code 的 `settings.json` 或 `.claude.json`）：

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
        "NEO4J_URI": "你的_NEO4J_URI",
        "NEO4J_USERNAME": "你的_NEO4J_用户名",
        "NEO4J_PASSWORD": "你的_NEO4J_密码"
      },
      "disabled": false,
      "alwaysAllow": []
    }
  }
}
```

---

## 自然语言交互示例

服务端运行后，你可以使用普通的英语（或中文，取决于 AI 助手）与其交互。以下是一些交互示例：

### 索引和监控文件

-   **索引新项目:**
    -   "请索引 `/path/to/my-project` 目录中的代码。"
    或
    -   "将位于 `~/dev/my-other-project` 的项目添加到代码图中。"


-   **开始监控目录的实时更改:**
    -   "监控 `/path/to/my-active-project` 目录的更改。"
    或
    -   "为我在 `~/dev/main-app` 处理的项目保持代码图更新。"

    当你要求监控一个目录时，系统会同时执行两个操作：
    1.  启动全量扫描以索引该目录中的所有代码。此过程在后台运行，你会收到一个 `job_id` 来追踪进度。
    2.  开始监控目录中的任何文件更改，以实时保持代码图更新。

    这意味着你可以直接告诉系统监控一个目录，它会自动处理初始索引和持续更新。

### 查询和理解代码

-   **查找代码定义位置:**
    -   "`process_payment` 函数在哪里定义的？"
    -   "帮我找一下 `User` 类。"
    -   "显示任何与 'database connection' 相关的代码。"

-   **分析关系和影响:**
    -   "还有哪些函数调用了 `get_user_by_id` 函数？"
    -   "如果我修改了 `calculate_tax` 函数，代码的其他哪些部分会受到影响？"
    -   "显示 `BaseController` 类的继承层次结构。"
    -   "`Order` 类有哪些方法？"

-   **探索依赖关系:**
    -   "哪些文件导入了 `requests` 库？"
    -   "查找 `render` 方法的所有实现。"

-   **高级调用链和依赖追踪（跨越数百个文件）:**
    CodeGraphContext 擅长追踪庞大代码库中复杂的执行流和依赖关系。利用图数据库的力量，它可以识别直接和间接的调用者与被调用者，即使函数是通过多层抽象或跨越多层文件调用的。这对于以下方面非常有价值：
    -   **影响分析:** 了解修改核心函数带来的完整涟漪效应。
    -   **调试:** 追踪从入口点到特定 bug 的执行路径。
    -   **代码理解:** 掌握大型系统中不同部分的交互方式。

    -   "显示从 `main` 函数到 `process_data` 的完整调用链。"
    -   "查找所有直接或间接调用 `validate_input` 的函数。"
    -   "列出 `initialize_system` 最终会调用的所有函数。"
    -   "追踪 `DatabaseManager` 模块的依赖关系。"

-   **代码质量与维护:**
    -   "这个项目中是否有任何死代码或未使用的代码？"
    -   "计算 `src/utils.py` 中 `process_data` 函数的圈复杂度。"
    -   "查找代码库中最复杂的 5 个函数。"

-   **仓库管理:**
    -   "列出所有当前已索引的仓库。"
    -   "删除位于 `/path/to/old-project` 的已索引仓库。"

---

## 贡献

欢迎贡献！ 🎉  
请参阅我们的 [CONTRIBUTING.md](CONTRIBUTING.md) 以获取详细准则。
如果你有新功能、集成或改进的想法，请开启 [issue](https://github.com/CodeGraphContext/CodeGraphContext/issues) 或提交 Pull Request。

加入讨论，共同塑造 CodeGraphContext 的未来。
