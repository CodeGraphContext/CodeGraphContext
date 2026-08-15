# 📊 CodeGraphContext (CGC)

Convierte repositorios de código en un grafo consultable para agentes de IA.

## Idiomas:

- 🇬🇧 [English](./README.md)
- 🇨🇳 [中文](./docs/translations/README.zh-CN.md)
- 🇰🇷 [한국어](./docs/translations/README.kor.md)
- 🇺🇦 [Українська](./docs/translations/README.uk.md)
- 🇷🇺 [Русский](./docs/translations/README.ru-RU.md)
- 🇯🇵 [日本語](./docs/translations/README.ja.md)
- 🇮🇳 [தமிழ்](./docs/translations/README.ta.md)
- 🇪🇸 [Español](./README.es.md)

Ayuda a traducir CodeGraphContext a tu idioma creando un Issue y un PR en GitHub Issues.

<p align="center">
  <br>
  <b>Conecta la brecha entre los grafos de código profundos y el contexto de IA.</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/"><img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="Versión de PyPI"></a>
  <a href="https://pypi.org/project/codegraphcontext/"><img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="Descargas de PyPI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="Licencia"></a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="Compatible con MCP">
  <a href="https://discord.gg/VCwUdCmn"><img src="https://img.shields.io/discord/14217691348073091507?label=Discord&logo=discord&logoColor=white&style=flat-square" alt="Discord"></a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/stargazers"><img src="https://img.shields.io/github/stars/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Estrellas"></a>
</p>

## ¿Qué es CodeGraphContext?

CodeGraphContext convierte cualquier repositorio de código en un grafo de código consultable que los agentes de IA pueden usar para comprender mejor las bases de código.

### El problema

Los agentes de IA como Claude, GPT-4 y Gemini tienen dificultades para comprender bases de código grandes. No pueden ver las relaciones entre archivos, funciones y clases. Esto lleva a:

- ❌ Respuestas imprecisas sobre la estructura del código
- ❌ Búsquedas ineficientes en bases de código
- ❌ Falta de contexto para las sugerencias de código
- ❌ Dificultad para rastrear dependencias

### La solución

CodeGraphContext analiza tu código y crea un grafo de conocimiento que muestra:

- ✅ Relaciones entre archivos y funciones
- ✅ Dependencias entre módulos
- ✅ Llamadas a funciones y referencias
- ✅ Estructura de clases y herencia

## Instalación

```bash
pip install codegraphcontext
