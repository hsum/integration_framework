# Integration Framework

A Python-based framework for running modular integrations, paying attention to reliability, extensibility, performance and QoL for both developers and support operators.

## Overview

The Integration Framework is designed to execute data integrations with APIs and other data sources (e.g., databases, files), with a focus on reliability, extensibility, performance and QoL. It supports enterprise clients by providing a plugin architecture for modular integrations, robust telemetry, and a developer-friendly CLI. Most APIs require credentials (e.g., API keys, tokens), which are securely managed via environment variables in `.env`. The framework supports both publicly available APIs (e.g., OpenWeatherMap, NewsAPI), private APIs (e.g., Salesforce), and non-API sources (e.g., internal data generators). Built with Python 3.12.7, it leverages virtual environments (`pyenv`/`virtualenv`) and quality tools (`pytest`, `ruff`, `mypy`) to ensure maintainability and performance for integration pipelines.

The framework’s architecture prioritizes **reliability** through structured logging, telemetry stored in a local SQLite database (`telemetry.db`) via `SQLQueryManager`, and error handling with support ticket placeholders via `SupportManager`. **Extensibility** is achieved through modular integrations (e.g., `hello_world`, `weather_news`) and reusable vendor utilities (e.g., `vendor/http_client`, `vendor/salesforce`). **Optimization** uses iterator-based pipelines, dependency injection via `config.yaml`, validation caching (`cache/validation_cache.json`), news caching (`cache/news_cache.json` with 60-minute TTL), and parallel execution with `asyncio` or `multiprocessing`. Quality-of-life features include a `Makefile` and a CLI for running integrations, validating configurations, tagging, and generating telemetry reports.

Key features include:
- **Reliability**:
  - Structured logging and telemetry with `SQLQueryManager` for safe, SQL injection-free queries.
  - Type annotations with static type checking via `mypy`, reducing runtime errors and ensuring robust, maintainable integrations.
  - Error handling with `SupportManager` for issue logging and ticketing placeholders.
  - Unit tests with >80% coverage via `pytest`.
- **Modular Integrations**: Self-contained modules with `fetch_data`, `postprocess_data`, and `deliver_results` phases.
- **Parallel Execution**: Run integrations concurrently using `asyncio` (I/O-bound) via `make run-asyncio` or `multiprocessing` (CPU-bound) via `make run-multiprocessing`.
- **Telemetry and Reporting**: Logs run metadata (e.g., status, duration, error rates) and generates CSV reports.
- **Safe SQL Handling**: `SQLQueryManager` supports raw SQL queries, returning dictionaries for flexible data merging.
- **Vendor Utilities**: Reusable modules (e.g., `vendor/http_client`) standardize tasks.
- **Caching**: Validation cache (`cache/validation_cache.json`) and news cache (`cache/news_cache.json`, 60-minute TTL) reduce API calls.
- **Developer Tools**: `Makefile` for automation, `ruff` for linting with auto-fix, and a CLI for streamlined workflows.
- **Future Vision**: Concepts like a unified customer data lake, product categorization, and PostgreSQL migration (see `docs/FUTURE.md`) enable advanced analytics and scalability.

## Plugin Architecture

The framework is built around a plugin architecture to ensure modularity and extensibility. Each integration is a self-contained module under `integrations/`, with the following structure:

- **`__init__.py`**: Defines an integration class inheriting from `Integration` (in `__init__.py`), implementing:
  - `fetch_data()`: Retrieves raw data (e.g., from APIs, databases, or internal sources).
  - `postprocess_data()`: Transforms data into a desired format.
  - `deliver_results()`: Outputs results (e.g., to YAML files).
- **`config.yaml`**: Configuration file specifying parameters (e.g., API endpoints, output paths, tags).
- **`metadata.yaml`**: Metadata specifying version and tags for the integration.
- **`tests/`**: Unit tests for the integration, ensuring reliability.

The `Integration` base class provides a flexible interface, defaulting the integration `name` to the package name (e.g., `hello_world`) if not specified in `config.yaml`. `SupportManager` provides issue logging with a placeholder for external ticketing systems. `SQLQueryManager` ensures safe SQL queries with flexible result formats. The CLI (`batch.py`) dynamically discovers integrations by scanning `integrations/`, allowing new integrations to be added without modifying core code. Vendor utilities (`vendor/`) provide reusable components (e.g., HTTP clients, Salesforce connectors) shared across integrations, supporting both external and internal data sources.

This architecture enables:
- **Scalability**: Add new integrations by creating a new directory with `__init__.py`, `config.yaml`, `metadata.yaml`, and `tests/`.
- **Reusability**: Share utilities like `vendor/http_client` across integrations.
- **Maintainability**: Isolate integration logic, with tests ensuring >80% coverage.

## Directory Structure

- `integrations/`: Integration modules (e.g., `hello_world`, `weather_news`).
- `vendor/`: Reusable utility modules (e.g., `http_client`, `salesforce`).
- `cache/`: Caches (`validation_cache.json`, `news_cache.json`).
- `output/`: Integration outputs (e.g., YAML files).
- `tests/`: CLI and framework tests.
- `batch.py`: CLI for running integrations, validating, and generating reports.
- `support_manager.py`: Issue logging with ticketing placeholder.
- `sql_executor.py`: Safe SQL query execution with dictionary results.
- `telemetry.py`: Telemetry storage and reporting.
- `telemetry.db`: SQLite database for run telemetry.
- `.env.example`: Template for environment variables (e.g., API keys).
- `metadata.yaml`: Project metadata (version, license, tags).
- `Makefile`: Automation for testing and running integrations.
- `README.md`: This file.
- `docs/`: Documentation (`SUPPORT.md`, `FUTURE.md`).

## Setup

1. Ensure `pyenv` is installed:
   ```bash
   curl https://pyenv.run | bash
   ```
2. Run the initialization scripts:
   ```bash
   bash init_integration_framework_part1.sh
   bash init_integration_framework_part2.sh
   ```
   These create the project, install Python 3.12.7, set up a virtual environment (`integration_framework-3.12.7`), install dependencies, and create `.env` from `.env.example`. The scripts are idempotent and safe to run multiple times.
3. Activate the virtual environment:
   ```bash
   cd integration_framework
   source $(pyenv prefix)/bin/activate
   ```
4. Configure environment variables for integrations (e.g., `weather_news`) by editing `.env` with API keys, using `.env.example` as a guide:
   ```bash
   cp .env.example .env
   vim .env
   ```
   Example `.env`:
   ```
   OPENWEATHERMAP_API_KEY=your_openweathermap_api_key_here
   NEWS_API_KEY=your_newsapi_key_here
   SALESFORCE_INSTANCE_URL=your_salesforce_instance_url
   SALESFORCE_ACCESS_TOKEN=your_salesforce_access_token
   REPORT_ISSUES=false
   ```
   **OpenWeatherMap API Key**:
   - Go to https://openweathermap.org and click “Sign Up”.
   - Register with your email, username, and password, and complete the CAPTCHA.
   - Verify your email via the confirmation link (resend after 1 hour if needed).
   - Log in to https://home.openweathermap.org, go to “API keys”, and copy your key.
   - Add to `.env`: `OPENWEATHERMAP_API_KEY=your_api_key_here`.
   **NewsAPI Key**:
   - Go to https://newsapi.org and click “Get API Key”.
   - Register with your name, email, and password.
   - Find your API key in the dashboard or confirmation email.
   - Add to `.env`: `NEWS_API_KEY=your_api_key_here`.
5. Install dependencies:
   ```bash
   make install
   ```

## Usage

- Run all integrations:
  ```bash
  make run
  ```
- Run a single integration:
  ```bash
  make run-single
  ```
- Run integrations with a specific tag:
  ```bash
  make run-by-tag
  ```
- Run integrations in parallel (I/O-bound):
  ```bash
  make run-asyncio
  ```
- Run integrations in parallel (CPU-bound):
  ```bash
  make run-multiprocessing
  ```
- Validate integrations:
  ```bash
  make validate
  ```
- Generate telemetry report:
  ```bash
  make report
  ```
- Run tests:
  ```bash
  make test
  ```
- Lint and fix:
  ```bash
  make lint
  make lint-fix
  ```
- Type check:
  ```bash
  make typecheck
  ```

## Contributing

Contributions are welcome! Please submit pull requests or open issues on the repository (if available). Ensure new integrations include:
- A `config.yaml` with clear parameters and tags.
- A `metadata.yaml` with version and tags.
- Unit tests in `integrations/<name>/tests/` with >80% coverage.
- Type annotations for static type checking.
- Documentation in `README.md` or `docs/SUPPORT.md`.

## Future Concepts

See `docs/FUTURE.md` for visionary ideas, including:
- **Unified Customer Data Lake**: Aggregate data from multiple sources for customer insights and metrics.
- **Product/Service Categorization**: Enrich data with category metadata for advanced reporting.
- **Transaction Anomaly Detection**: Flag unusual transactions to improve data quality.
- **Integration Performance Dashboard**: Monitor integration health with telemetry reports.
- **Customer Segmentation**: Cluster customers for targeted strategies.
- **Event-Driven Integrations**: Enable real-time processing with message queues.
- **PostgreSQL Migration**: Transition to PostgreSQL for scalability and BI integration.

