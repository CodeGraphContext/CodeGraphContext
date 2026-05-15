# 🏗️ CodeGraphContext (CGC)

**Превратите репозитории кода в запрашиваемый граф для ИИ-агентов.**

🌐 **Языки:**
- 🇬🇧 [English](README.md)
- 🇨🇳 [中文](README.zh-CN.md)
- 🇰🇷 [한국어](README.kor.md)
- 🇺🇦 [Українська](README.uk.md)
- 🇷🇺 [Русский](README.ru-RU.md)
- 🇯🇵 日本語 (Скоро)
- 🇪🇸 Español (Скоро)

🌍 **Помогите перевести CodeGraphContext на ваш язык — создайте issue и Pull Request на https://github.com/Shashankss1205/CodeGraphContext/issues!**

<p align="center">
  <br>
  <b>Связующее звено между глубинными графами кода и контекстом для ИИ.</b>
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
  <a href="https://CodeGraphContext.github.io/CodeGraphContext/">
    <img src="https://img.shields.io/badge/docs-GitHub%20Pages-blue?style=flat-square" alt="Docs">
  </a>
  <a href="https://youtu.be/KYYSdxhg1xU">
    <img src="https://img.shields.io/badge/YouTube-Watch%20Demo-red?style=flat-square&logo=youtube" alt="YouTube Demo">
  </a>
</p>


Мощный **MCP-сервер** и **набор CLI-инструментов**, который индексирует локальный код в графовую базу данных, предоставляя контекст ИИ-ассистентам и разработчикам. Используйте его как независимую CLI-утилиту для глубокого анализа кода или подключите к любимой ИИ-IDE через протокол MCP для интеллектуального понимания кодовой базы.

---

## 📍 Быстрая навигация
* [🚀 Быстрый старт](#быстрый-старт) 
* [🌐 Поддерживаемые языки программирования](#поддерживаемые-языки-программирования) 
* [🛠️ CLI-инструментарий](#cli-инструментарий) 
* [🤖 MCP-сервер](#mcp-сервер) 
* [🗄️ Варианты баз данных](#варианты-баз-данных)

---

## ✨ CGC в действии


### 👨🏻‍💻 Установка и CLI
> Установка за пару секунд через pip открывает доступ к мощному CLI для анализа графов кода.
![Установка и запуск CLI](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/install&cli.gif)


### 🛠️ Мгновенная индексация
> CLI-утилита интеллектуально разбирает AST-узлы tree-sitter для построения графа.
![Индексация через MCP-клиент](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Indexing.gif)

### 🤖 Усиление вашего ИИ-ассистента
> Формируйте запросы к сложным цепочкам вызовов на естественном языке через MCP.
![Использование MCP-сервера](https://github.com/CodeGraphContext/CodeGraphContext/blob/main/images/Usecase.gif)

---

## Детали проекта
- **Версия:** 0.3.8
- **Авторы:** Shashank Shekhar Singh <shashankshekharsingh1205@gmail.com>
- **Лицензия:** MIT License (Подробнее см. в [LICENSE](LICENSE))
- **Веб-сайт:** [CodeGraphContext](http://codegraphcontext.vercel.app/)

---

## 👨‍💻 Мейнтейнер
Создатель и активный мейнтейнер проекта **CodeGraphContext**:

**Shashank Shekhar Singh**  
- 📧 Email: [shashankshekharsingh1205@gmail.com](mailto:shashankshekharsingh1205@gmail.com)
- 🐙 GitHub: [@Shashankss1205](https://github.com/Shashankss1205)
- 🔗 LinkedIn: [Shashank Shekhar Singh](https://www.linkedin.com/in/shashank-shekhar-singh-a67282228/)
- 🌐 Веб-сайт: [codegraphcontext.vercel.app](http://codegraphcontext.vercel.app/)

*Мы всегда рады вашему вкладу и отзывам! Смело обращайтесь с вопросами, предложениями или идеями для сотрудничества.*

---

## Динамика звезд
[![Star History Chart](https://api.star-history.com/svg?repos=CodeGraphContext/CodeGraphContext&type=Date)](https://www.star-history.com/#CodeGraphContext/CodeGraphContext&Date)

---

## Ключевые особенности
- **Индексация кода:** анализирует исходный код и строит граф знаний из его компонентов.
- **Анализ связей:** поиск вызывающих (callers) и вызываемых (callees) функций, построение иерархии классов, цепочек вызовов и многое другое.
- **Готовые индексы (Bundles):** мгновенная загрузка популярных репозиториев через `.cgc`-бандлы без необходимости их индексировать! ([Подробнее](docs/BUNDLES.md))
- **Отслеживание файлов в реальном времени:** мониторинг изменений в директориях и автоматическое обновление графа (команда `cgc watch`).
- **Интерактивная настройка:** удобный мастер для простой настройки через командную строку.
- **Двойной режим:** работает как независимый **набор CLI-инструментов** для разработчиков и как **MCP-сервер** для ИИ-агентов.
- **Мультиязычность:** полная поддержка 14 языков программирования.
- **Гибкий выбор СУБД:** KùzuDB (по умолчанию, работает «из коробки» на всех платформах), FalkorDB Lite (только для Unix), FalkorDB Remote или Neo4j (любые платформы через Docker или нативно).

---

## Поддерживаемые языки программирования

CodeGraphContext обеспечивает полноценный синтаксический анализ следующих языков:

| | Язык | | Язык | | Язык |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 🐍 | **Python** | 📜 | **JavaScript** | 🔷 | **TypeScript** |
| ☕ | **Java** | 🏗️ | **C / C++** | #️⃣ | **C#** |
| 🐹 | **Go** | 🦀 | **Rust** | 💎 | **Ruby** |
| 🐘 | **PHP** | 🍎 | **Swift** | 🎨 | **Kotlin** |
| 🎯 | **Dart** | 🐪 | **Perl** | | |

Парсер каждого языка извлекает функции, классы, методы, параметры, отношения наследования, вызовы функций и импорты, формируя исчерпывающий граф кода.

---

## Варианты баз данных

CodeGraphContext поддерживает несколько графовых СУБД под любые задачи и окружения:

| Параметр | KùzuDB (По умолчанию) | FalkorDB Lite | Neo4j |
| :--- | :--- | :--- | :--- |
| **Настройка** | Не требует настройки / Встроенная | Не требует настройки / Внутрипроцессная | Docker / Внешняя |
| **Платформа** | **Все (нативно Windows, macOS, Linux)** | Только Unix (Linux/macOS/WSL) | Все платформы |
| **Применение** | Десктоп, IDE, локальная разработка | Специализированная Unix-разработка | Enterprise, огромные графы |
| **Требования**| `pip install kuzu` | `pip install falkordblite` | Сервер Neo4j / Docker |
| **Скорость** | ⚡ Молниеносная | ⚡ Высокая | 🚀 Масштабируемая |
| **Хранение**| Да (на диск) | Да (на диск) | Да (на диск) |

---

## Где это используется

Разработчики и проекты уже изучают возможности CodeGraphContext для:

- **Статического анализа кода в ИИ-ассистентах**
- **Графовой визуализации проектов**
- **Поиска мертвого кода и оценки сложности**

_Если вы используете CodeGraphContext в своем проекте, смело открывайте PR и добавляйте его в этот список! 🚀_

---

## Зависимости

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

**Примечание:** Поддерживаются версии Python от 3.10 до 3.14.

---

## Быстрый старт
### Установка основного инструментария
```bash
pip install codegraphcontext
```

### Если команда 'cgc' не найдена, выполните скрипт исправления в одну строку:
```bash
curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
```

---

## Начало работы

### 📋 Режимы работы CodeGraphContext
CodeGraphContext функционирует в **двух режимах**, которые можно использовать как по отдельности, так и вместе:

#### 🛠️ Режим 1: CLI-инструментарий (Автономный)
Используйте CodeGraphContext как **мощный инструмент командной строки** для анализа кода:
- Индексируйте и анализируйте кодовые базы прямо из терминала.
- Запрашивайте связи в коде, ищите мертвый код, анализируйте цикломатическую сложность.
- Визуализируйте графы кода и зависимости.
- Идеально для разработчиков, которым нужен полный контроль через CLI-команды.

#### 🤖 Режим 2: MCP-сервер (На базе ИИ)
Используйте CodeGraphContext как **MCP-сервер** для ИИ-ассистентов:
- Подключайтесь к ИИ-ориентированным IDE (VS Code, Cursor, Windsurf, Claude, Kiro и др.).
- Позвольте ИИ-агентам выполнять запросы к вашей кодовой базе на естественном языке.
- Автоматическое осмысление кода и анализ взаимосвязей.
- Идеально для рабочих процессов с применением ИИ.

**Вы можете использовать оба режима!** Установите утилиту один раз, а затем используйте CLI-команды напрямую ИЛИ подключите её к ИИ-ассистенту.

### Установка (Оба режима)

1.  **Установка:** `pip install codegraphcontext`
    <details>
    <summary>⚙️ Решение проблем: Если команда <code>cgc</code> не найдена</summary>

    Если после установки вы получаете ошибку <i>"cgc: command not found"</i>, выполните скрипт для исправления переменной PATH:
    
    **Linux/Mac:**
    ```bash
    # Скачать скрипт исправления
    curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh
    
    # Сделать исполняемым
    chmod +x post_install_fix.sh
    
    # Запустить скрипт
    ./post_install_fix.sh
    
    # Перезапустить терминал или обновить конфигурацию shell
    source ~/.bashrc  # или ~/.zshrc для пользователей zsh
    ```
    
    **Windows (PowerShell):**
    ```powershell
    # Скачать скрипт исправления
    curl -O https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh
    
    # Запустить через bash (требуется Git Bash или WSL)
    bash post_install_fix.sh
    
    # Перезапустить PowerShell или обновить профиль
    . $PROFILE
    ``` 
    </details>

2.  **Настройка базы данных (Автоматически)**
    
    - **KùzuDB (По умолчанию):** Работает нативно на Windows, macOS и Linux без дополнительной настройки. Просто выполните `pip install kuzu` — и всё готово!
    - **FalkorDB Lite (Альтернатива):** Поддерживается на Unix/macOS/WSL для Python версии 3.12 и выше.
    - **Neo4j (Альтернатива):** Если вы предпочитаете Neo4j или серверную архитектуру, выполните: `cgc neo4j setup`

---

## 🛠️ CLI-инструментарий

**Начните использовать утилиту сразу через CLI-команды:**
```bash
# Индексация текущей директории
cgc index .

# Вывод списка всех проиндексированных репозиториев
cgc list

# Анализ того, кто вызывает конкретную функцию
cgc analyze callers my_function

# Поиск сложного для восприятия кода (цикломатическая сложность)
cgc analyze complexity --threshold 10

# Поиск мертвого (неиспользуемого) кода
cgc analyze dead-code

# Отслеживание изменений в реальном времени (опционально)
cgc watch .

# Просмотр всех команд
cgc help
```

  **Ознакомьтесь с полным [Руководством по CLI-командам](docs/CLI_COMPLETE_REFERENCE.md) для изучения всех доступных команд и сценариев использования.**

### 🎨 Интерактивная Premium-визуализация
CodeGraphContext умеет генерировать потрясающие интерактивные графы знаний вашего кода. В отличие от статичных диаграмм, это полноценные веб-обозреватели премиум-класса:

- **Премиальная эстетика**: темная тема, глассморфизм и современная типографика (Outfit / JetBrains Mono).
- **Интерактивный инспектор**: клик по любому узлу открывает детальную боковую панель с информацией о символе, путями к файлам и контекстом.
- **Быстрый поиск**: живой поиск по графу для мгновенного нахождения нужных символов.
- **Умная компоновка**: силовые алгоритмы отрисовки (force-directed) и иерархические структуры, делающие сложные связи читаемыми.
- **Работа без зависимостей**: автономные HTML-файлы, открывающиеся в любом современном браузере.

```bash
# Визуализация вызовов функций
cgc analyze calls my_function --viz

# Исследование иерархии классов
cgc analyze tree MyClass --viz

# Визуализация результатов поиска
cgc find pattern "Auth" --viz
```


---

### 🤖 MCP-сервер

**Настройка ИИ-ассистента для работы с CodeGraphContext:**
1.  **Настройка:** Запустите мастер настройки MCP для конфигурации вашей IDE / ИИ-ассистента:
    
    ```bash
    cgc mcp setup
    ```
    
    Мастер может автоматически определить и настроить:
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

    После успешной настройки команда `cgc mcp setup` сгенерирует и разместит необходимые конфигурационные файлы:
    *   Создаст файл `mcp.json` в текущей директории для справки.
    *   Надежно сохранит учетные данные БД в `~/.codegraphcontext/.env`.
    *   Обновит файл настроек выбранной IDE/CLI (например, `.claude.json` или `settings.json` в VS Code).

2.  **Запуск:** Запустите MCP-сервер:    
    ```bash
    cgc mcp start
    ```

3.  **Использование:** Теперь вы можете взаимодействовать с вашей кодовой базой через ИИ-ассистента, используя естественный язык! См. примеры ниже.

---

## Игнорирование файлов (`.cgcignore`)

Вы можете указать CodeGraphContext игнорировать определенные файлы и директории. Для этого создайте файл `.cgcignore` в корне проекта. Он использует тот же синтаксис, что и `.gitignore`.

**Пример файла `.cgcignore`:**
```
# Игнорировать артефакты сборки
/build/
/dist/

# Игнорировать зависимости
/node_modules/
/vendor/

# Игнорировать логи
*.log
```

---

## Конфигурация MCP-клиента

Команда `cgc mcp setup` пытается автоматически настроить вашу IDE/CLI. Если вы предпочитаете отказаться от автонастройки или ваш инструмент пока не поддерживается, вы можете настроить всё вручную.

Добавьте следующую конфигурацию сервера в файл настроек вашего клиента (например, `settings.json` в VS Code или `.claude.json`):

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

## Примеры запросов на естественном языке

После запуска сервера вы можете общаться с ним через ИИ-ассистента на обычном языке. Вот несколько примеров того, о чем можно спросить:

### Индексация и отслеживание файлов

-   **Для индексации нового проекта:**
    -   "Проиндексируй код в директории `/path/to/my-project`."
    ИЛИ
    -   "Добавь проект из `~/dev/my-other-project` в граф кода."


-   **Для начала отслеживания директории в реальном времени:**
    -   "Отслеживай изменения в директории `/path/to/my-active-project`."
    ИЛИ
    -   "Поддерживай актуальность графа кода для проекта, над которым я работаю в `~/dev/main-app`."

    Когда вы просите отслеживать директорию, система выполняет два действия одновременно:
    1.  Запускает полное сканирование для индексации всего кода в директории. Процесс идет в фоновом режиме, а вы получаете `job_id` для отслеживания прогресса.
    2.  Начинает мониторинг директории на предмет изменения файлов, чтобы обновлять граф в реальном времени.

    Это означает, что вам достаточно просто дать команду отслеживать директорию — система сама возьмет на себя как первичную индексацию, так и непрерывное обновление.

### Поиск и понимание кода

-   **Поиск определений кода:**
    -   "Где находится функция `process_payment`?"
    -   "Найди для меня класс `User`."
    -   "Покажи весь код, связанный с 'подключением к базе данных'."

-   **Анализ связей и оценка влияния (Impact Analysis):**
    -   "Какие еще функции вызывают функцию `get_user_by_id`?"
    -   "Если я изменю функцию `calculate_tax`, какие другие части кода будут затронуты?"
    -   "Покажи иерархию наследования для класса `BaseController`."
    -   "Какие методы есть у класса `Order`?"

-   **Исследование зависимостей:**
    -   "Какие файлы импортируют библиотеку `requests`?"
    -   "Найди все реализации метода `render`."

-   **Сложные цепочки вызовов и трассировка зависимостей (охват сотен файлов):**
    CodeGraphContext блестяще справляется с отслеживанием сложных потоков выполнения и зависимостей в огромных кодовых базах. Благодаря возможностям графовых БД, инструмент выявляет прямые и косвенные вызывающие (callers) и вызываемые (callees) функции, даже если функция вызывается через множество уровней абстракции или цепочка вызовов охватывает множество файлов. Это незаменимо для:
    -   **Оценки влияния (Impact Analysis):** понимание полного волнового эффекта от изменения ключевой функции.
    -   **Отладки:** трассировка пути выполнения от точки входа до конкретной ошибки.
    -   **Изучения кода:** понимание того, как взаимодействуют различные части большой системы.

    -   "Покажи полную цепочку вызовов от функции `main` до `process_data`."
    -   "Найди все функции, которые прямо или косвенно вызывают `validate_input`."
    -   "Какие функции в конечном итоге вызывает `initialize_system`?"
    -   "Проследи зависимости модуля `DatabaseManager`."

-   **Качество кода и сопровождение:**
    -   "Есть ли в этом проекте мертвый или неиспользуемый код?"
    -   "Рассчитай цикломатическую сложность функции `process_data` в файле `src/utils.py`."
    -   "Найди 5 самых сложных функций в кодовой базе."

-   **Управление репозиториями:**
    -   "Выведи список всех проиндексированных на данный момент репозиториев."
    -   "Удали проиндексированный репозиторий по пути `/path/to/old-project`."

---

## Участие в разработке

Будем рады вашему вкладу! 🎉  
Подробные инструкции смотрите в файле [CONTRIBUTING.md](CONTRIBUTING.md).
Если у вас есть идеи для новых функций, интеграций или улучшений, открывайте [issue](https://github.com/CodeGraphContext/CodeGraphContext/issues) или присылайте Pull Request.

Участвуйте в обсуждениях и помогайте формировать будущее CodeGraphContext.
