# 🏗️ CodeGraphContext (CGC)

**コードリポジトリを AI エージェントが問い合わせ可能なグラフに変換します。**

🌐 **言語:**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇰🇷 [한국어](README.kor.md)
- 🇺🇦 [Українська](README.uk.md)
- 🇷🇺 [Русский](README.ru-RU.md)
- 🇯🇵 [日本語](README.ja.md)
- 🇪🇸 Español (準備中)

🌍 **CodeGraphContext をあなたの言語に翻訳することにご協力ください！ https://github.com/Shashankss1205/CodeGraphContext/issues で Issue と PR を作成してください！**

<p align="center">
  <br>
  <b>深いコードグラフと AI のコンテキストの橋渡しを行います。</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="PyPI バージョン">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="PyPI ダウンロード数">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="ライセンス">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="MCP 互換">
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
    <img src="https://img.shields.io/github/contributors/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="コントリビューター">
  </a>
<br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml/badge.svg" alt="テスト">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml/badge.svg" alt="E2E テスト">
  </a>
  <a href="http://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/website-up-brightgreen?style=flat-square" alt="ウェブサイト">
  </a>
  <a href="https://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="ドキュメント">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube デモ">
  </a>
</p>


ローカルのコードをグラフデータベースにインデックスし、AI アシスタントや開発者にコンテキストを提供する強力な **MCP サーバー** および **CLI ツールキット** です。スタンドアロンの CLI として包括的なコード解析を行うこともできれば、MCP 経由でお気に入りの AI IDE と接続して、AI による高度なコード理解を実現することもできます。

---

## 📍 クイックナビゲーション
* [🚀 クイックスタート](#-インストール--クイックスタート)
* [🌐 サポートされているプログラミング言語](#サポートされているプログラミング言語)
* [🛠️ CLI ツールキット](#cli-ツールキットモード)
* [🤖 MCP サーバー](#-mcp-サーバーモード)
* [🗄️ データベースの選択肢](#データベースの選択肢)
* [🔬 SCIP インデックス（オプション）](#scip-インデックスオプション)

---

## ✨ CGC を体験する


### 👨🏻‍💻 インストールと CLI
> pip を使えば数秒でインストールでき、強力なコードグラフ解析 CLI を利用できます。
![インストールして CLI をすぐに使う](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ 数秒でインデックス
> CLI が tree-sitter のノードを賢く解析し、グラフを構築します。
![MCP クライアントを使ったインデックス処理](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 AI アシスタントの強化
> MCP を通じて、自然言語で複雑な呼び出しチェーンを問い合わせできます。
![MCP サーバーの利用例](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## プロジェクト概要
- **バージョン:** 0.4.13
- **作者:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **ライセンス:** MIT License（詳細は [LICENSE](LICENSE) を参照）
- **ウェブサイト:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 メンテナー
**CodeGraphContext** は次の人物によって作成・維持されています。

**Shashank Shekhar Singh**  
- 📧 メール: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 ウェブサイト: [codegraphcontext.vercel.app](https://codegraphcontext.vercel.app/)

*コントリビューションやフィードバックはいつでも歓迎します！ 質問、提案、コラボレーションの機会など、お気軽にご連絡ください。*

---

## Star History
[![Star History Chart](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## 機能
-   **コードのインデックス処理:** コードを解析し、その構成要素のナレッジグラフを構築します。
-   **関係性の解析:** 呼び出し元、呼び出し先、クラス階層、コールチェーンなどを問い合わせできます。
-   **事前インデックス済みバンドル:** `.cgc` バンドルで著名なリポジトリを即座にロード。インデックス不要！（[詳細](docs/BUNDLES.md)）
-   **ライブファイル監視:** ディレクトリの変更を監視し、グラフをリアルタイムで自動更新します（`codegraphcontext watch`）。
-   **インタラクティブなセットアップ:** ユーザーフレンドリーなコマンドラインウィザードで簡単に設定できます。
-   **デュアルモード:** 開発者向けのスタンドアロン **CLI ツールキット**、および AI エージェント向けの **MCP サーバー** の両方として動作します。
-   **マルチ言語サポート:** 20 のプログラミング言語に完全対応しています。
-   **柔軟なデータベースバックエンド:** FalkorDB Lite（デフォルト）、KuzuDB、LadybugDB、FalkorDB Remote、Nornic DB、または Neo4j（すべてのプラットフォームで Docker / ネイティブ動作）。


---

## サポートされているプログラミング言語

CodeGraphContext は以下の言語に対して包括的なパースと解析を提供します。

| | 言語 | | 言語 | | 言語 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🏗️ | **C / C++** | #️⃣ | **C#** |
| 🐹 | **Go** | 🦀 | **Rust** | 💎 | **Ruby** |
| 🐘 | **PHP** | 🍎 | **Swift** | 🎨 | **Kotlin** |
| 🎯 | **Dart** | 🐪 | **Perl** | 🌙 | **Lua** |
| 🚀 | **Scala** | λ | **Haskell** | 💧 | **Elixir** |
| ⚛️ | **TSX** | | | | |

各言語のパーサーは、関数・クラス・メソッド・パラメータ・継承関係・関数呼び出し・インポートを抽出し、包括的なコードグラフを構築します。

---

## データベースの選択肢

CodeGraphContext は、利用環境に合わせて複数のグラフデータベースバックエンドをサポートします。

| 特徴 | KuzuDB | LadybugDB | FalkorDB Lite | Neo4j / Nornic DB |
| :--- | :--- | :--- | :--- | :--- |
| **一般的なデフォルト** | **標準デフォルト**（KuzuDB ベースの組み込み） | **特化型組み込み**（Kuzu に類似） | **Unix**（Python 3.12+、`falkordblite` が動作する場合） | 明示的に設定した場合 |
| **セットアップ** | 設定不要 / 組み込み | 設定不要 / 組み込み | 設定不要 / プロセス内 | Docker / 外部 |
| **プラットフォーム** | **すべて（Windows ネイティブ、macOS、Linux）** | **すべて（Windows ネイティブ、macOS、Linux）** | Unix のみ（Linux / macOS / WSL） | すべてのプラットフォーム |
| **ユースケース** | デスクトップ、IDE、ローカル開発 | カスタムの研究プロジェクト | Unix に特化した開発 | エンタープライズ、大規模グラフ |
| **要件**| `pip install kuzu` | `pip install ladybug` | `pip install falkordblite` | Neo4j サーバー / Docker / Nornic Cloud |
| **速度** | ⚡ 非常に高速 | ⚡ 高速 | 🚀 スケーラブル |
| **永続化**| あり（ディスクへ） | あり（ディスクへ） | あり（ディスクへ） |

---

## SCIP インデックス（オプション）

CGC の設定（`~/.codegraphcontext/.env`）で `SCIP_INDEXER=true` を指定すると、一部の言語では Tree-sitter のヒューリスティクスだけよりも正確な呼び出しや継承関係を得るため、外部の **SCIP** インデクサーを利用します。

**C および C++** では **scip-clang** を使用し、**`compile_commands.json`** ファイル（[JSON コンパイルデータベース](https://clang.llvm.org/docs/JSONCompilationDatabase.html)）が必要です。これは翻訳単位ごとに 1 エントリで、実コンパイラのコマンド（include パス、`-D` 定義、`-std` など）を含みます。これが無いと scip-clang は動作せず、CGC は警告を出してそのリポジトリでは **Tree-sitter にフォールバック** します。一般的な生成方法としては、**CMake** で `-DCMAKE_EXPORT_COMPILE_COMMANDS=ON` を指定するか、実際のビルドを **[Bear](https://github.com/rizsotto/Bear)** でラップする（例: `bear -- make`）方法があります。CGC は `build/` や `cmake-build-*/` 配下のファイルも探索します。

**C#** では **scip-dotnet**（Roslyn）を使用します。通常の **`.csproj` / `.sln`** と、正常に完了した restore が必要です（`compile_commands.json` は不要）。

SCIP は **どのグラフデータベースを使うかとは独立** しており（Kuzu、Neo4j など）、同じフラグがすべてのバックエンドに適用されます。

---

## 採用事例

CodeGraphContext は、開発者やプロジェクトによって以下の用途で活用が進められています。

- **AI アシスタントによる静的コード解析**
- **プロジェクトのグラフベース可視化**
- **デッドコードや複雑度の検出**

_あなたのプロジェクトで CodeGraphContext を使用している場合は、ぜひ PR を出してこちらに追記してください！ 🚀_

---

## 依存関係

- `neo4j>=5.15.0`
- `watchdog>=3.0.0`
- `stdlibs>=2023.11.18`
- `typer>=0.9.0`
- `rich>=13.7.0`
- `inquirerpy>=0.3.4`
- `python-dotenv>=1.0.0`
- `tree-sitter>=0.21.0`（Python 3.13 ではインストールされません）
- `tree-sitter-language-pack>=0.6.0`（Python 3.13 ではインストールされません）
- `pyyaml`
- `pathspec>=0.12.1`
- `falkordb>=0.1.0`
- `falkordblite>=0.1.0`（Unix 限定）
- `kuzu`（KuzuDB エンジン）
- `fastapi>=0.100.0`
- `uvicorn>=0.22.0`
- `requests>=2.28.0`
- `protobuf>=3.20,<3.21`

**注:** Python 3.10〜3.14 がサポート対象です。

---

### 🚀 インストール & クイックスタート

1.  **ツールキットをインストール:**
    ```bash
    pip install codegraphcontext
    ```

2.  **トラブルシューティング（コマンドが見つからない場合）:**
    `codegraphcontext` コマンドが見つからない場合は、次のワンライナーで修正できます。
    ```bash
    curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
    ```

3.  **データベースのセットアップ（自動）:**
    CodeGraphContext はデフォルトで組み込み型のグラフデータベースを使用します。
    - **FalkorDB Lite:** デフォルトのバックエンド。
    - **KuzuDB:** クロスプラットフォームの組み込み型バックエンド。
    - **Neo4j:** 外部サーバーを利用する場合は `codegraphcontext neo4j setup` を実行してください。

---

### CLI ツールキットモード

**CLI コマンドですぐに使い始められます:**
```bash
# 現在のディレクトリをインデックス
codegraphcontext index .

# インデックス済みリポジトリを一覧表示
codegraphcontext list

# 関数の呼び出し元を解析
codegraphcontext analyze callers my_function

# 複雑度の高いコードを検出
codegraphcontext analyze complexity --threshold 10

# デッドコードを検出
codegraphcontext analyze dead-code

# ライブな変更を監視（任意）
codegraphcontext watch .

# すべてのコマンドを表示
codegraphcontext help
```

  **利用可能なすべてのコマンドと使用例については [CLI コマンドガイド](docs/CLI_COMPLETE_REFERENCE.md) を参照してください。**

### 🎨 プレミアムなインタラクティブ可視化
CodeGraphContext は、コードを表す美しくインタラクティブなナレッジグラフを生成できます。静的な図とは異なり、これらはプレミアム品質の Web ベースエクスプローラーです。

- **プレミアムなビジュアル**: ダークモード、グラスモーフィズム、モダンなタイポグラフィ（Outfit / JetBrains Mono）。
- **インタラクティブな調査**: ノードをクリックすると、シンボル情報・ファイルパス・コンテキストを表示する詳細サイドパネルが開きます。
- **クイック検索**: グラフ全体をライブ検索して特定のシンボルを瞬時に発見。
- **インテリジェントなレイアウト**: 力学的（force-directed）レイアウトや階層レイアウトにより、複雑な関係も読みやすく可視化。
- **依存ゼロでの閲覧**: モダンブラウザーで動作するスタンドアロンな HTML ファイル。

```bash
# 関数呼び出しを可視化
codegraphcontext analyze calls my_function --viz

# クラス階層を探索
codegraphcontext analyze tree MyClass --viz

# 検索結果を可視化
codegraphcontext find pattern "Auth" --viz
```


---

### 🤖 MCP サーバーモード

**AI アシスタントが CodeGraphContext を使用するように設定します:**
1.  **セットアップ:** MCP セットアップウィザードを実行して IDE / AI アシスタントを設定します。
    
    ```bash
    codegraphcontext mcp setup
    ```
    
    ウィザードは次のツールを自動検出・設定できます。
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

    設定が正常に完了すると、`codegraphcontext mcp setup` は必要な設定ファイルを生成・配置します。
    *   現在のディレクトリに参照用の `mcp.json` ファイルを作成します。
    *   データベース認証情報を `~/.codegraphcontext/.env` に安全に保存します。
    *   選択した IDE / CLI の設定ファイル（例: `.claude.json` や VS Code の `settings.json`）を更新します。

2.  **起動:** MCP サーバーを起動します。
    ```bash
    codegraphcontext mcp start
    ```

3.  **利用:** これで自然言語による AI アシスタント経由でコードベースを操作できます！ 例は下記を参照してください。

---

## ファイルの無視（`.cgcignore`）

プロジェクトのルートに `.cgcignore` ファイルを作成することで、CodeGraphContext に特定のファイルやディレクトリを無視させることができます。このファイルの構文は `.gitignore` と同じです。

**`.cgcignore` の例:**
```
# ビルド成果物を無視
/build/
/dist/

# 依存関係を無視
/node_modules/
/vendor/

# ログを無視
*.log
```

---

## MCP クライアントの設定

`codegraphcontext mcp setup` コマンドは IDE / CLI の自動設定を試みます。自動セットアップを使わない場合や、対応していないツールを使う場合は、手動で設定できます。

クライアントの設定ファイル（VS Code の `settings.json` や `.claude.json` など）に、次のサーバー設定を追加してください。

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

#### pipx でインストールした場合

`pipx` で CodeGraphContext をインストールした場合は、代わりに次の設定を使用してください。
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

## 自然言語での対話例

サーバーが起動したら、平易な日本語（英語）で AI アシスタントを通じて対話できます。指示の例をいくつか示します。

### インデックス処理とファイル監視

-   **新しいプロジェクトをインデックスする場合:**
    -   「`/path/to/my-project` ディレクトリのコードをインデックスしてください。」
    または
    -   「`~/dev/my-other-project` のプロジェクトをコードグラフに追加してください。」


-   **ライブな変更のためにディレクトリの監視を開始する場合:**
    -   「`/path/to/my-active-project` ディレクトリの変更を監視してください。」
    または
    -   「`~/dev/main-app` で作業中のプロジェクトについて、コードグラフを最新に保ってください。」

    ディレクトリの監視を依頼すると、システムは同時に 2 つの処理を行います。
    1.  そのディレクトリ内のすべてのコードをインデックスするためのフルスキャンを開始します。これはバックグラウンドで進行し、進捗を追跡するための `job_id` が返ります。
    2.  ファイルの変更を監視し始め、グラフをリアルタイムで最新に保ちます。

    つまり、ディレクトリを監視するように指示するだけで、初回のインデックス処理と継続的な更新の両方を自動的に行ってくれます。

### コードの問い合わせと理解

-   **コードの定義場所を探す:**
    -   「`process_payment` 関数はどこにありますか？」
    -   「`User` クラスを探してください。」
    -   「『データベース接続』に関連するコードを見せてください。」

-   **関係や影響範囲の解析:**
    -   「`get_user_by_id` 関数を呼んでいる関数は他にありますか？」
    -   「`calculate_tax` 関数を変更したら、コードのどの部分に影響しますか？」
    -   「`BaseController` クラスの継承階層を見せてください。」
    -   「`Order` クラスが持つメソッドは何ですか？」

-   **依存関係の調査:**
    -   「`requests` ライブラリをインポートしているファイルはどれですか？」
    -   「`render` メソッドのすべての実装を見つけてください。」

-   **高度なコールチェーンと依存追跡（数百ファイルにまたがる場合）:**
    CodeGraphContext は、大規模なコードベースを横断する複雑な実行フローや依存関係の追跡を得意としています。グラフデータベースの力を活用することで、関数が複数の抽象化レイヤーや数多くのファイルをまたいで呼び出されていても、直接的・間接的な呼び出し元と呼び出し先を特定できます。これは次のような用途で非常に役立ちます。
    -   **影響範囲の解析:** 中心的な関数を変更した際の波及効果を完全に把握する。
    -   **デバッグ:** エントリーポイントから特定のバグまでの実行経路を追跡する。
    -   **コード理解:** 大規模システムの異なる部分がどのように相互作用しているかを掴む。

    -   「`main` 関数から `process_data` までの完全なコールチェーンを見せてください。」
    -   「直接または間接に `validate_input` を呼び出している関数をすべて見つけてください。」
    -   「`initialize_system` が最終的に呼び出す関数をすべて教えてください。」
    -   「`DatabaseManager` モジュールの依存関係をトレースしてください。」

-   **コード品質と保守:**
    -   「このプロジェクトにデッドコードや未使用コードはありますか？」
    -   「`src/utils.py` の `process_data` 関数の循環的複雑度を計算してください。」
    -   「コードベースの中で最も複雑な関数を 5 つ見つけてください。」

-   **リポジトリの管理:**
    -   「現在インデックス済みのリポジトリをすべて一覧表示してください。」
    -   「`/path/to/old-project` のインデックス済みリポジトリを削除してください。」

---

## コントリビューション

コントリビューションを歓迎します！🎉  
詳細なガイドラインについては [CONTRIBUTING.md](CONTRIBUTING.md)（日本語版: [CONTRIBUTING.ja.md](CONTRIBUTING.ja.md)）を参照してください。
新機能、連携、改善のアイデアがあれば、[Issue を作成](https://github.com/CodeGraphContext/CodeGraphContext/issues)するか、Pull Request を送ってください。

ぜひディスカッションに参加し、CodeGraphContext の未来を一緒に作っていきましょう。
