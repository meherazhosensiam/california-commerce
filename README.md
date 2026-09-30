# California Commerce
This app contains AI assisted code. with my own modification. 
California Commerce is a deliberately vulnerable, synthetic e-commerce/business-services application for **isolated, authorized OWASP Top 10:2025 training**. It is not a secure reference implementation.

OWASP Top 10:2025 defines A01 Broken Access Control, A02 Security Misconfiguration, A03 Software Supply Chain Failures, A04 Cryptographic Failures, A05 Injection, A06 Insecure Design, A07 Authentication Failures, A08 Software or Data Integrity Failures, A09 Security Logging and Alerting Failures, and A10 Mishandling of Exceptional Conditions.

## Quick start

```bash
docker compose up --build
```
Open `http://localhost:8080`.

Synthetic lab accounts all use password `LabPass123!`:
- admin@californiacommerce.test
- manager@californiacommerce.test
- employee@californiacommerce.test
- alice@californiacommerce.test
- bob@californiacommerce.test

These are **lab-only credentials** and must not be reused anywhere else.

## Safety
Run on localhost, a private VM, or an isolated lab network. Do not publish port 8080 to the Internet. The diagnostics endpoint deliberately contains command-injection behavior; it is confined to the unprivileged API container. No real credentials, payment data, external services, persistence, malware, or credential theft are included.

## Author files
See `docs/DEPLOYMENT.md`, `docs/ARCHITECTURE.md`, `docs/LAB_AUTHOR_GUIDE.md`, `docs/API_DOCUMENTATION.md`, and `docs/VULNERABILITY_MAPPING.md`.
