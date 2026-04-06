# 🏗️ CodeGraphContext (CGC)

**Перетворюйте кодові репозиторії на граф, який можуть запитувати AI-агенти.**

🌐 **Мови:**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇰🇷 [한국어](README.kor.md)
- 🇺🇦 [Українська](README.uk.md)
- 🇷🇺 Русский (README.ru-RU.md)
- 🇯🇵 日本語 (Незабаром)
- 🇪🇸 Español (Незабаром)

🌍 **Допоможіть перекласти CodeGraphContext вашою мовою, створивши issue та PR на https://github.com/Shashankss1205/CodeGraphContext/issues!**

<p align="center">
  <br>
  <b>Усуньте розрив між глибокими графами коду та AI-контекстом.</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="Версія PyPI">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="Завантаження з PyPI">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="Ліцензія">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="Сумісно з MCP">
  <a href="https://discord.gg/VCwUdCnn">
    <img src="https://img.shields.io/discord/1421769154507309150?label=Discord&logo=discord&logoColor=white&style=flat-square">
  </a>
  <br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/stargazers">
    <img src="https://img.shields.io/github/stars/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Зірки">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/network/members">
    <img src="https://img.shields.io/github/forks/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Форки">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/issues">
    <img src="https://img.shields.io/github/issues-raw/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Issues">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/pulls">
    <img src="https://img.shields.io/github/issues-pr/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="PR">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/graphs/contributors">
    <img src="https://img.shields.io/github/contributors/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Учасники">
  </a>
<br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/test.yml/badge.svg" alt="Тести">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml">
    <img src="https://github.com/CodeGraphContext/CodeGraphContext/actions/workflows/e2e-tests.yml/badge.svg" alt="E2E тести">
  </a>
  <a href="http://codegraphcontext.vercel.app/">
    <img src="https://img.shields.io/badge/website-up-brightgreen?style=flat-square" alt="Вебсайт">
  </a>
  <a href="https://CodeGraphContext.github.io/CodeGraphContext/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Документація">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="Демо на YouTube">
  </a>
</p>


Потужний **MCP-сервер** і **CLI-інструментарій**, який індексує локальний код у графову базу даних, щоб надавати контекст AI-асистентам і розробникам. Використовуйте його як окремий CLI для глибокого аналізу коду або підключайте до улюбленого AI IDE через MCP для AI-підсиленого розуміння кодової бази.

---

## 📍 Швидка навігація
* [🚀 Швидкий старт](#швидкий-старт)
* [🌐 Підтримувані мови програмування](#підтримувані-мови-програмування)
* [🛠️ CLI-інструментарій](#для-режиму-cli-інструментарію)
* [🤖 MCP-сервер](#-для-режиму-mcp-сервера)
* [🗄️ Варіанти баз даних](#варіанти-баз-даних)

---

## ✨ Спробуйте CGC


### 👨🏻‍💻 Встановлення та CLI
> Встановіть за секунди через pip і отримайте потужний CLI для аналізу графа коду.
![Миттєво встановіть і відкрийте CLI](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ Індексація за секунди
> CLI інтелектуально розбирає вузли tree-sitter, щоб побудувати граф.
![Індексація через MCP-клієнт](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 Підсилення вашого AI-асистента
> Використовуйте природну мову, щоб запитувати складні ланцюжки викликів через MCP.
![Використання MCP-сервера](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## Деталі проєкту
- **Версія:** 0.3.9
- **Автори:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **Ліцензія:** MIT License (див. [LICENSE](LICENSE) для деталей)
- **Вебсайт:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 Мейнтейнер
**CodeGraphContext** створюється та активно підтримується:

**Shashank Shekhar Singh**
- 📧 Email: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 Website: [codegraphcontext.vercel.app](http://codegraphcontext.vercel.app/)

*Внески та відгуки завжди вітаються! Звертайтеся із запитаннями, пропозиціями чи ідеями для співпраці.*

---

## Історія зірок
[![Star History Chart](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## Можливості
- **Індексація коду:** Аналізує код і будує граф знань його компонентів.
- **Аналіз зв'язків:** Запитуйте викликачів, викликані функції, ієрархії класів, ланцюжки викликів та багато іншого.
- **Попередньо проіндексовані бандли:** Миттєво завантажуйте відомі репозиторії через `.cgc`-бандли без ручної індексації! ([Докладніше](docs/BUNDLES.md))
- **Живе відстеження файлів:** Слідкуйте за змінами в директоріях і автоматично оновлюйте граф у реальному часі (`cgc watch`).
- **Інтерактивне налаштування:** Зручний майстер командного рядка для швидкого старту.
- **Подвійний режим:** Працює як окремий **CLI-інструментарій** для розробників і як **MCP-сервер** для AI-агентів.
- **Підтримка багатьох мов:** Повна підтримка 14 мов програмування.
- **Гнучкі бекенди баз даних:** KùzuDB (типово, без конфігурації на всіх платформах), FalkorDB Lite (лише Unix), FalkorDB Remote або Neo4j (на всіх платформах через Docker або нативно).

---

## Підтримувані мови програмування

CodeGraphContext забезпечує повноцінний парсинг і аналіз для таких мов:

| | Мова | | Мова | | Мова |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🏗️ | **C / C++** | #️⃣ | **C#** |
| 🐹 | **Go** | 🦀 | **Rust** | 💎 | **Ruby** |
| 🐘 | **PHP** | 🍎 | **Swift** | 🎨 | **Kotlin** |
| 🎯 | **Dart** | 🐪 | **Perl** | | |

Парсери для кожної мови витягують функції, класи, методи, параметри, зв'язки наслідування, виклики функцій та імпорти, щоб побудувати повноцінний граф коду.

---

## Варіанти баз даних

CodeGraphContext підтримує кілька графових бекендів для різних середовищ:

| Можливість | KùzuDB (типово) | FalkorDB Lite | Neo4j |
| :--- | :--- | :--- | :--- |
| **Налаштування** | Zero-config / Embedded | Zero-config / In-process | Docker / External |
| **Платформа** | **Усі (Windows Native, macOS, Linux)** | Лише Unix (Linux/macOS/WSL) | Усі платформи |
| **Сценарій використання** | Desktop, IDE, локальна розробка | Спеціалізована Unix-розробка | Enterprise, дуже великі графи |
| **Вимога**| `pip install kuzu` | `pip install falkordblite` | Сервер Neo4j / Docker |
| **Швидкість** | ⚡ Дуже швидко | ⚡ Швидко | 🚀 Масштабується |
| **Збереження**| Так (на диск) | Так (на диск) | Так (на диск) |

---

## Хто вже використовує

CodeGraphContext уже досліджують і застосовують для:

- **Статичного аналізу коду в AI-асистентах**
- **Візуалізації проєктів на основі графа**
- **Пошуку мертвого коду та вимірювання складності**

_Якщо ви використовуєте CodeGraphContext у своєму проєкті, відкрийте PR і додайте себе сюди! 🚀_

---

## Залежності

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

**Примітка:** підтримуються Python 3.10-3.14.

---

## Швидкий старт
### Встановіть базовий інструментарій
```
pip install codegraphcontext
```

### Якщо команду `cgc` не знайдено, запустіть наш однорядковий фікс:
```
curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
```

---

## Початок роботи

### 📋 Розуміння режимів CodeGraphContext
CodeGraphContext працює у **двох режимах**, і ви можете використовувати будь-який із них або обидва:

#### 🛠️ Режим 1: CLI-інструментарій (окремо)
Використовуйте CodeGraphContext як **потужний інструментарій командного рядка** для аналізу коду:
- Індексуйте та аналізуйте кодові бази прямо з термінала
- Досліджуйте зв'язки в коді, шукайте мертвий код, аналізуйте складність
- Візуалізуйте графи коду та залежності
- Ідеально для розробників, яким потрібен прямий контроль через CLI-команди

#### 🤖 Режим 2: MCP-сервер (з AI)
Використовуйте CodeGraphContext як **MCP-сервер** для AI-асистентів:
- Підключайтеся до AI IDE (VS Code, Cursor, Windsurf, Claude, Kiro тощо)
- Дозвольте AI-агентам запитувати вашу кодову базу природною мовою
- Автоматичне розуміння коду та аналіз зв'язків
- Ідеально для AI-підсилених робочих процесів розробки

**Можна використовувати обидва режими!** Один раз встановіть інструмент, а потім або працюйте напряму через CLI, або підключайте його до AI-асистента.

### Встановлення (для обох режимів)

1. **Встановіть:** `pip install codegraphcontext`
   <details>
   <summary>⚙️ Усунення проблем: якщо команду <code>cgc</code> не знайдено</summary>

   Якщо після встановлення ви бачите помилку <i>"cgc: command not found"</i>, запустіть скрипт для виправлення PATH:

   **Linux/Mac:**
   ```bash
   # Завантажити скрипт виправлення
   curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh

   # Зробити його виконуваним
   chmod +x post_install_fix.sh

   # Запустити скрипт
   ./post_install_fix.sh

   # Перезапустити термінал або перезавантажити конфігурацію оболонки
   source ~/.bashrc  # або ~/.zshrc для користувачів zsh
   ```

   **Windows (PowerShell):**
   ```powershell
   # Завантажити скрипт виправлення
   curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh

   # Запустити через bash (потрібен Git Bash або WSL)
   bash post_install_fix.sh

   # Перезапустити PowerShell або перезавантажити профіль
   . $PROFILE
   ```
   </details>

2. **Налаштування бази даних (автоматично)**

   - **KùzuDB (типово):** працює нативно на Windows, macOS і Linux без додаткового налаштування. Достатньо `pip install kuzu`, і все готово.
   - **FalkorDB Lite (альтернатива):** підтримується на Unix/macOS/WSL для Python 3.12+.
   - **Neo4j (альтернатива):** якщо ви хочете використовувати Neo4j або віддаєте перевагу серверному підходу, запустіть: `cgc neo4j setup`

---

### Для режиму CLI-інструментарію

**Почніть користуватися одразу через CLI-команди:**
```bash
# Проіндексувати поточну директорію
cgc index .

# Перелічити всі проіндексовані репозиторії
cgc list

# Проаналізувати, хто викликає функцію
cgc analyze callers my_function

# Знайти складний код
cgc analyze complexity --threshold 10

# Знайти мертвий код
cgc analyze dead-code

# Стежити за змінами в реальному часі (необов'язково)
cgc watch .

# Переглянути всі команди
cgc help
```

**Дивіться повний [CLI Commands Guide](docs/CLI_COMPLETE_REFERENCE.md) з усіма доступними командами та сценаріями використання.**

### 🎨 Преміальна інтерактивна візуалізація
CodeGraphContext може генерувати ефектні інтерактивні графи знань для вашого коду. На відміну від статичних діаграм, це повноцінні веб-оглядачі:

- **Преміальна естетика:** темний режим, glassmorphism і сучасна типографіка (Outfit/JetBrains Mono).
- **Інтерактивне дослідження:** натисніть на вузол, щоб відкрити детальну бічну панель із символом, шляхом до файлу та контекстом.
- **Швидкий пошук:** живий пошук у графі, щоб миттєво знаходити потрібні символи.
- **Інтелектуальні макети:** силові та ієрархічні схеми, які роблять складні зв'язки читабельними.
- **Перегляд без зовнішніх залежностей:** автономні HTML-файли, що працюють у будь-якому сучасному браузері.

```bash
# Візуалізувати виклики функцій
cgc analyze calls my_function --viz

# Дослідити ієрархії класів
cgc analyze tree MyClass --viz

# Візуалізувати результати пошуку
cgc find pattern "Auth" --viz
```

---

### 🤖 Для режиму MCP-сервера

**Налаштуйте свого AI-асистента для роботи з CodeGraphContext:**
1. **Налаштування:** запустіть майстер налаштування MCP, щоб сконфігурувати IDE/AI-асистента:

   ```bash
   cgc mcp setup
   ```

   Майстер може автоматично виявити й налаштувати:
   * VS Code
   * Cursor
   * Windsurf
   * Claude
   * Gemini CLI
   * ChatGPT Codex
   * Cline
   * RooCode
   * Amazon Q Developer
   * Kiro

   Після успішного налаштування `cgc mcp setup` згенерує та розмістить потрібні конфігураційні файли:
   * створить `mcp.json` у поточній директорії як довідковий приклад;
   * безпечно збереже креденшли до бази даних у `~/.codegraphcontext/.env`;
   * оновить файл налаштувань вибраного IDE/CLI (наприклад, `.claude.json` або `settings.json` у VS Code).

2. **Запуск:** підніміть MCP-сервер:
   ```bash
   cgc mcp start
   ```

3. **Використання:** тепер взаємодійте зі своєю кодовою базою через AI-асистента природною мовою. Нижче наведені приклади.

---

## Ігнорування файлів (`.cgcignore`)

Ви можете сказати CodeGraphContext ігнорувати певні файли та директорії, створивши `.cgcignore` у корені проєкту. Файл використовує той самий синтаксис, що й `.gitignore`.

**Приклад файла `.cgcignore`:**
```
# Ігнорувати артефакти збірки
/build/
/dist/

# Ігнорувати залежності
/node_modules/
/vendor/

# Ігнорувати логи
*.log
```

---

## Конфігурація MCP-клієнта

Команда `cgc mcp setup` намагається автоматично налаштувати ваш IDE/CLI. Якщо ви не хочете використовувати автоматичне налаштування або ваш інструмент не підтримується, можна зробити це вручну.

Додайте таку конфігурацію сервера у файл налаштувань клієнта (наприклад, `settings.json` у VS Code або `.claude.json`):

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

## Приклади взаємодії природною мовою

Коли сервер запущено, ви можете взаємодіяти з ним через AI-асистента природною мовою. Ось кілька прикладів того, що можна сказати:

### Індексація та відстеження файлів

- **Щоб проіндексувати новий проєкт:**
  - "Please index the code in the `/path/to/my-project` directory."
  АБО
  - "Add the project at `~/dev/my-other-project` to the code graph."


- **Щоб почати відстежувати директорію на живі зміни:**
  - "Watch the `/path/to/my-active-project` directory for changes."
  АБО
  - "Keep the code graph updated for the project I'm working on at `~/dev/main-app`."

  Коли ви просите відстежувати директорію, система одночасно робить дві дії:
  1. Запускає повне сканування, щоб проіндексувати весь код у цій директорії. Процес іде у фоні, і ви отримаєте `job_id`, щоб відстежувати прогрес.
  2. Починає стежити за змінами файлів у директорії, щоб підтримувати граф актуальним у реальному часі.

  Тобто достатньо просто сказати системі стежити за директорією, а вона сама виконає і початкову індексацію, і безперервні оновлення.

### Запити й розуміння коду

- **Пошук місця, де визначено код:**
  - "Where is the `process_payment` function?"
  - "Find the `User` class for me."
  - "Show me any code related to 'database connection'."

- **Аналіз зв'язків і впливу:**
  - "What other functions call the `get_user_by_id` function?"
  - "If I change the `calculate_tax` function, what other parts of the code will be affected?"
  - "Show me the inheritance hierarchy for the `BaseController` class."
  - "What methods does the `Order` class have?"

- **Дослідження залежностей:**
  - "Which files import the `requests` library?"
  - "Find all implementations of the `render` method."

- **Розширене відстеження ланцюжків викликів і залежностей (через сотні файлів):**
  CodeGraphContext особливо сильний у трасуванні складних потоків виконання та залежностей у великих кодових базах. Використовуючи потужність графових баз даних, він може знаходити прямі й непрямі виклики та залежності, навіть якщо функція викликається через кілька рівнів абстракції або в багатьох файлах. Це особливо корисно для:
  - **Аналізу впливу:** зрозуміти повний ланцюг наслідків зміни базової функції.
  - **Налагодження:** простежити шлях виконання від точки входу до конкретного бага.
  - **Розуміння коду:** швидко зрозуміти, як взаємодіють частини великої системи.

  - "Show me the full call chain from the `main` function to `process_data`."
  - "Find all functions that directly or indirectly call `validate_input`."
  - "What are all the functions that `initialize_system` eventually calls?"
  - "Trace the dependencies of the `DatabaseManager` module."

- **Якість коду та підтримка:**
  - "Is there any dead or unused code in this project?"
  - "Calculate the cyclomatic complexity of the `process_data` function in `src/utils.py`."
  - "Find the 5 most complex functions in the codebase."

- **Керування репозиторіями:**
  - "List all currently indexed repositories."
  - "Delete the indexed repository at `/path/to/old-project`."

---

## Внесок у проєкт

Внески вітаються! 🎉
Будь ласка, перегляньте [CONTRIBUTING.md](CONTRIBUTING.md) для детальних правил.
Якщо у вас є ідеї щодо нових можливостей, інтеграцій чи покращень, відкрийте [issue](https://github.com/CodeGraphContext/CodeGraphContext/issues) або надішліть Pull Request.

Долучайтеся до обговорень і допомагайте формувати майбутнє CodeGraphContext.
