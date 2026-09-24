# 🛡️ Security Policy

## 📌 Supported Versions

We aim to keep `CodeGraphContext` up to date and secure. Please see below for the versions we currently support with security updates.

| Version | Supported          |
|---------|--------------------|
| Latest  | ✅ Yes              |
| Older   | ❌ No               |

---

## 📬 Reporting a Vulnerability

If you discover a security vulnerability, **please do not open an issue** on GitHub.

Instead, follow these steps:

1. **Email the maintainer directly**
2. Include the following details:
   - Description of the vulnerability
   - Steps to reproduce (if possible)
   - Potential impact
   - Any mitigation or workaround suggestions

⌛ We aim to respond to security reports **within 72 hours**.

---

## 🚫 Responsible Disclosure Guidelines

We ask that you:
- Do not publicly disclose the issue until it has been resolved.
- Avoid testing vulnerabilities in a way that could disrupt services.
- Act in good faith and with respect for user data and privacy.

---

## 📃 Disclosure Policy

- We follow a **coordinated disclosure** approach.
- We appreciate responsible reporting and will publicly disclose the issue only **after a fix has been released**.

--- 

## Security Best Practices

While using this project, we recommend you:

- Always run software in a secure and isolated environment.
- Keep your dependencies up to date.
- Avoid sharing sensitive API keys or credentials in `.env` or other public files.
- Enable `REDACT_SECRETS=true` before indexing repositories that may contain hardcoded secrets (API keys, tokens, passwords, connection strings). CGC scans string literals during indexing and can redact likely secrets before they are stored in the graph database.
- Review `.cgc` export bundles before sharing them — bundles may contain string literals and variable values from indexed source code. Use `REDACT_SECRETS=true` to minimize exposure.
- When using a shared or remote Neo4j/FalkorDB instance, ensure access controls are in place to prevent unauthorized reads of graph data that may include source-code literals.

---

## 🙏 Acknowledgments

We value the contributions from the community and encourage responsible disclosure to help keep `CodeGraphContext` safe and secure for all users.

---

## 🔒 Resources

- [GitHub Security Advisories](https://docs.github.com/en/code-security/security-advisories)
- [OpenSSF Best Practices](https://bestpractices.dev/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
