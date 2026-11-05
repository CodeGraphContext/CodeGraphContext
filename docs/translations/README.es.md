> **Nota:** Esta es una traducción parcial. Para la documentación completa y actualizada, consulta la versión en inglés: [../../README.md](../../README.md)

# 🏗️ CodeGraphContext (CGC)

**Convierte repositorios de código en un grafo consultable para agentes de IA.**

<p align="center">
  <br>
  <b>Conecta grafos de código profundos con el contexto de la IA.</b>
  <br><br>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/v/codegraphcontext?style=flat-square&logo=pypi" alt="PyPI Version">
  </a>
  <a href="https://pypi.org/project/codegraphcontext/">
    <img src="https://img.shields.io/pypi/dm/codegraphcontext?style=flat-square" alt="PyPI Downloads">
  </a>
  <a href="../../LICENSE">
    <img src="https://img.shields.io/github/license/CodeGraphContext/CodeGraphContext?style=flat-square" alt="License">
  </a>
  <img src="https://img.shields.io/badge/MCP-Compatible-green?style=flat-square" alt="MCP Compatible">
  <a href="https://discord.gg/VCwUdCnn">
    <img src="https://img.shields.io/discord/1421769154507309150?label=Discord&logo=discord&logoColor=white&style=flat-square" alt="Discord">
  </a>
  <br><br>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/stargazers">
    <img src="https://img.shields.io/github/stars/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Stars">
  </a>
  <a href="https://github.com/CodeGraphContext/CodeGraphContext/network/members">
    <img src="https://img.shields.io/github/forks/CodeGraphContext/CodeGraphContext?style=flat-square&logo=github" alt="Forks">
  </a>
</p>

🌐 **Idiomas:**
- GB [English](../../README.md)
- CN [中文](./README.zh-CN.md)
- KR [한국어](./README.kor.md)
- UA [Українська](./README.uk.md)
- RU [Русский](./README.ru-RU.md)
- JP [日本語](./README.ja.md)
- ES **Español**
- IN [தமிழ்](./README.ta.md)

---

## ✨ Características

- **Indexación de Código:** Analiza el código y construye un grafo de conocimiento de sus componentes.
- **Análisis de Relaciones:** Consulta llamadores (callers), llamados (callees), jerarquías de clases, cadenas de llamadas y más.
- **Bundles Pre-indexados:** Carga repositorios famosos al instante con bundles `.cgc` - ¡sin necesidad de indexar!
- **Observación de Archivos en Vivo:** Observa directorios en busca de cambios y actualiza automáticamente el grafo en tiempo real (`cgc watch`).
- **Modo Dual:** Funciona como un **toolkit CLI** independiente para desarrolladores y como un **servidor MCP** para agentes de IA.
- **Soporte Multi-lenguaje:** Soporte completo para 23 lenguajes de programación.
- **Backend de Base de Datos Flexible:** FalkorDB Lite (por defecto), KuzuDB, o Neo4j.

## 🚀 Instalación y Inicio Rápido

1. **Instala el toolkit:**
```bash
pip install codegraphcontext
```

2. **Solución de problemas (Comando no encontrado):** Si el comando `codegraphcontext` no se encuentra, ejecuta esta solución:
```bash
curl -sSL https://raw.githubusercontent.com/CodeGraphContext/CodeGraphContext/main/scripts/post_install_fix.sh | bash
```

3. **Configuración de Base de Datos (Automática):** CodeGraphContext usa una base de datos de grafos integrada por defecto.
   - **FalkorDB Lite:** Backend por defecto.
   - **KuzuDB:** Backend integrado multiplataforma.
   - **Neo4j:** Ejecuta `codegraphcontext neo4j setup` para usar un servidor externo.

## 🌍 Lenguajes de Programación Soportados

CodeGraphContext proporciona análisis completo para: Python, JavaScript, TypeScript, Java, C/C++, C#, Go, Rust, Ruby, PHP, Swift, Kotlin, Dart, Perl y más.

Cada parser extrae funciones, clases, métodos, parámetros, relaciones de herencia, llamadas a funciones e importaciones para construir un grafo de código completo.

## 🐳 Docker (No se requiere Python)

```bash
docker pull codegraphcontext/codegraphcontext:latest
docker run --rm -v "$(pwd):/workspace" codegraphcontext/codegraphcontext cgc index .
```

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor revisa `../../CONTRIBUTING.md` para más detalles.

## 📄 Licencia

MIT License - ver archivo ../../LICENSE para más detalles.
