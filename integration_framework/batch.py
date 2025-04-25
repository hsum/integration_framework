import asyncio
import click
import importlib
import logging
import multiprocessing
import sqlite3
import sys
import time
import json
import traceback
from datetime import datetime, timedelta
from pathlib import Path
import collections.abc
import csv
import hashlib
import fnmatch

import yaml
from integration_framework.integrations import Integration
from integration_framework.sql_query_manager import SQLQueryManager
from integration_framework.support_manager import SupportManager
from integration_framework.telemetry import TelemetryManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def _run_integration(integration_name: str, verbose: bool, integrations_dir: Path) -> None:
    """Run a single integration in a separate process.

    Args:
        integration_name (str): Name of the integration.
        verbose (bool): If True, log detailed output.
        integrations_dir (Path): Directory containing integrations.
    """
    support = SupportManager()
    telemetry = TelemetryManager("telemetry.db")
    
    config_path = integrations_dir / integration_name / "config.yaml"
    try:
        with config_path.open() as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"Config file not found for {integration_name}")
        return
    except yaml.YAMLError as e:
        logger.error(f"Invalid config for {integration_name}: {e}")
        return

    if not config.get("enabled", False):
        logger.info(f"Integration {integration_name} is disabled")
        return

    module_name = f"integration_framework.integrations.{integration_name}"
    try:
        module = importlib.import_module(module_name)
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Integration) and attr != Integration:
                integration_class = attr
                break
        else:
            logger.warning(f"No Integration subclass found in {integration_name}")
            return
    except ImportError as e:
        error_msg = f"Failed to load integration {integration_name}: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_msg)
        return

    start_time = time.time()
    try:
        integration = integration_class(config, support, integration_name)
        data = integration.fetch_data()
        processed_data = integration.postprocess_data(data)
        integration.deliver_results(processed_data)
        duration = time.time() - start_time
        support.notify(f"Completed {integration_name} in {duration:.2f}s")
        telemetry.log_run(integration_name, "success", duration)
        if verbose:
            logger.info(f"Completed {integration_name} in {duration:.2f}s")
    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Integration {integration_name} failed: {e}"
        logger.error(error_msg)
        telemetry.log_run(integration_name, "failed", duration, str(e))
        if verbose:
            logger.error(error_msg)

def _run_integration_wrapper(args: tuple[str, bool, Path]) -> None:
    """Wrapper for multiprocessing to run integrations.

    Args:
        args (tuple[str, bool, Path]): Integration name, verbose flag, and integrations directory.
    """
    integration_name, verbose, integrations_dir = args
    _run_integration(integration_name, verbose, integrations_dir)

class BatchRunner:
    """Manages batch processing of integrations.

    Provides methods to load, run, validate, and filter integrations, with support for parallel execution using asyncio or multiprocessing.
    """
    def __init__(self) -> None:
        """Initialize the BatchRunner with integration directory and managers."""
        self.integrations_dir = Path(__file__).parent / "integrations"
        self.support = SupportManager()
        self.sql_manager = SQLQueryManager("telemetry.db")
        self.telemetry = TelemetryManager("telemetry.db")
        self.cache_file = Path("validation_cache.json")
        self.cache_ttl = timedelta(hours=24)
        self._is_test = False

    def load_integration(self, integration_name: str) -> type[Integration] | None:
        """Load an integration class by name.

        Args:
            integration_name (str): Name of the integration to load.

        Returns:
            type[Integration] | None: The integration class if found, else None.
        """
        package_prefix = "test_integration_framework" if self._is_test else "integration_framework"
        module_name = f"{package_prefix}.integrations.{integration_name}"
        try:
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                logger.warning(f"Module {module_name} not found")
                try:
                    module = importlib.import_module(module_name)
                except ImportError as e:
                    logger.error(f"Fallback import failed for {module_name}: {str(e)}")
                    return None
            else:
                module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Integration) and attr != Integration:
                    return attr
            logger.warning(f"No Integration subclass found in {integration_name}")
            return None
        except ImportError as e:
            error_msg = f"Failed to load integration {integration_name}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            return None

    def load_config(self, integration_name: str) -> dict:
        """Load the configuration for an integration.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            dict: Configuration dictionary, or empty dict if not found or invalid.
        """
        config_path = self.integrations_dir / integration_name / "config.yaml"
        try:
            with config_path.open() as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found for {integration_name}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Invalid config for {integration_name}: {e}")
            return {}

    def load_metadata(self, integration_name: str) -> dict:
        """Load the metadata for an integration.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            dict: Metadata dictionary, or empty dict if not found or invalid.
        """
        metadata_path = self.integrations_dir / integration_name / "metadata.yaml"
        try:
            with metadata_path.open() as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Metadata file not found for {integration_name}")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Invalid metadata for {integration_name}: {e}")
            return {}

    def load_validation_cache(self) -> dict:
        """Load the validation cache from file.

        Returns:
            dict: Cached validation data, or default empty cache if not found or invalid.
        """
        if not self.cache_file.exists():
            return {"integrations": {}}
        try:
            with self.cache_file.open() as f:
                return json.load(f) or {"integrations": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load validation cache: {e}")
            return {"integrations": {}}

    def save_validation_cache(self, cache: dict) -> None:
        """Save the validation cache to file.

        Args:
            cache (dict): Validation cache data to save.
        """
        try:
            with self.cache_file.open("w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save validation cache: {e}")

    def get_last_updated(self, integration_name: str) -> str:
        """Get the last updated timestamp for an integration.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            str: ISO timestamp or 'N/A' if not available.
        """
        query = """
            SELECT MAX(timestamp)
            FROM telemetry
            WHERE integration_name = ?
        """
        try:
            with self.sql_manager as sql:
                result = sql.execute_query(query, [integration_name])
                timestamp = next(result, {}).get("MAX(timestamp)")
                if timestamp:
                    return timestamp
        except sqlite3.Error:
            pass

        metadata = self.load_metadata(integration_name)
        if "last_updated" in metadata:
            return metadata["last_updated"]
        
        integration_dir = self.integrations_dir / integration_name
        if integration_dir.exists():
            return datetime.fromtimestamp(integration_dir.stat().st_mtime).isoformat()
        return "N/A"

    def validate_integration(self, integration_name: str) -> bool:
        """Validate an integration's configuration and class.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            bool: True if valid, False otherwise.
        """
        cache = self.load_validation_cache()
        integrations_cache = cache.get("integrations", {})
        
        if integration_name in integrations_cache:
            cached = integrations_cache[integration_name]
            try:
                cache_time = datetime.fromisoformat(cached["timestamp"])
                if datetime.now() - cache_time < self.cache_ttl:
                    return cached["valid"]
            except (KeyError, ValueError):
                pass

        config = self.load_config(integration_name)
        if not config.get("enabled", False):
            valid = True
        else:
            integration_class = self.load_integration(integration_name)
            if not integration_class:
                valid = False
            else:
                try:
                    integration = integration_class(config, self.support, integration_name)
                    valid = True
                except Exception:
                    valid = False

        integrations_cache[integration_name] = {
            "valid": valid,
            "timestamp": datetime.now().isoformat()
        }
        cache["integrations"] = integrations_cache
        self.save_validation_cache(cache)
        return valid

    def run_integration(self, integration_name: str, verbose: bool = False) -> None:
        """Run a single integration.

        Args:
            integration_name (str): Name of the integration.
            verbose (bool): If True, log detailed output.
        """
        config = self.load_config(integration_name)
        if not config.get("enabled", False):
            logger.info(f"Integration {integration_name} is disabled")
            return

        integration_class = self.load_integration(integration_name)
        if not integration_class:
            return

        start_time = time.time()
        try:
            integration = integration_class(config, self.support, integration_name)
            data = integration.fetch_data()
            processed_data = integration.postprocess_data(data)
            integration.deliver_results(processed_data)
            duration = time.time() - start_time
            self.support.notify(f"Completed {integration_name} in {duration:.2f}s")
            self.telemetry.log_run(integration_name, "success", duration)
            if verbose:
                logger.info(f"Completed {integration_name} in {duration:.2f}s")
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Integration {integration_name} failed: {e}"
            logger.error(error_msg)
            self.telemetry.log_run(integration_name, "failed", duration, str(e))
            if verbose:
                logger.error(error_msg)

    async def run_integration_async(self, integration_name: str, verbose: bool = False) -> None:
        """Run a single integration asynchronously.

        Args:
            integration_name (str): Name of the integration.
            verbose (bool): If True, log detailed output.
        """
        self.run_integration(integration_name, verbose)

    def get_integrations(self) -> list[str]:
        """Get a list of available integration names.

        Returns:
            list[str]: List of integration directory names.
        """
        return [
            d.name
            for d in self.integrations_dir.iterdir()
            if d.is_dir() and (d / "__init__.py").exists() and (d / "config.yaml").exists()
        ]

    def filter_integrations(
        self,
        name: str | None = None,
        partial_name: str | None = None,
        tags: list[str] | None = None,
        business_contact: str | None = None,
        technical_contact: str | None = None,
        last_updated_before: str | None = None,
        last_updated_after: str | None = None,
        description_contains: str | None = None
    ) -> tuple[list[str], str]:
        """Filter integrations based on criteria.

        Args:
            name (str | None): Exact integration name.
            partial_name (str | None): Partial name (wildcard).
            tags (list[str] | None): List of tags to match.
            business_contact (str | None): Business contact email.
            technical_contact (str | None): Technical contact email.
            last_updated_before (str | None): Last updated before (YYYY-MM-DD).
            last_updated_after (str | None): Last updated after (YYYY-MM-DD).
            description_contains (str | None): Substring in description.

        Returns:
            tuple[list[str], str]: Filtered integration names and criteria hash.
        """
        integrations = self.get_integrations()
        filtered = []
        criteria = {
            "name": name,
            "partial_name": partial_name,
            "tags": tags,
            "business_contact": business_contact,
            "technical_contact": technical_contact,
            "last_updated_before": last_updated_before,
            "last_updated_after": last_updated_after,
            "description_contains": description_contains
        }
        criteria_json = json.dumps(criteria, sort_keys=True)
        criteria_hash = hashlib.sha256(criteria_json.encode()).hexdigest()[:8]

        for integration_name in integrations:
            metadata = self.load_metadata(integration_name)
            config = self.load_config(integration_name)
            last_updated = self.get_last_updated(integration_name)

            if name and integration_name != name:
                continue
            if partial_name and not fnmatch.fnmatch(integration_name, f"*{partial_name}*"):
                continue
            if tags:
                integration_tags = metadata.get("tags", [])
                if not all(tag in integration_tags for tag in tags):
                    continue
            if business_contact and metadata.get("business_contact") != business_contact:
                continue
            if technical_contact and metadata.get("technical_contact") != technical_contact:
                continue
            if last_updated_before:
                try:
                    if last_updated != "N/A" and datetime.fromisoformat(last_updated) > datetime.fromisoformat(last_updated_before):
                        continue
                except ValueError:
                    continue
            if last_updated_after:
                try:
                    if last_updated == "N/A" or datetime.fromisoformat(last_updated) < datetime.fromisoformat(last_updated_after):
                        continue
                except ValueError:
                    continue
            if description_contains and description_contains.lower() not in metadata.get("description", "").lower():
                continue

            filtered.append(integration_name)

        return filtered, criteria_hash

    async def run_filtered(
        self,
        name: str | None = None,
        partial_name: str | None = None,
        tags: list[str] | None = None,
        business_contact: str | None = None,
        technical_contact: str | None = None,
        last_updated_before: str | None = None,
        last_updated_after: str | None = None,
        description_contains: str | None = None,
        criteria_hash: str | None = None,
        verbose: bool = False,
        parallel: str = "none"
    ) -> None:
        """Run filtered integrations with specified parallelism.

        Args:
            name (str | None): Exact integration name.
            partial_name (str | None): Partial name (wildcard).
            tags (list[str] | None): List of tags to match.
            business_contact (str | None): Business contact email.
            technical_contact (str | None): Technical contact email.
            last_updated_before (str | None): Last updated before (YYYY-MM-DD).
            last_updated_after (str | None): Last updated after (YYYY-MM-DD).
            description_contains (str | None): Substring in description.
            criteria_hash (str | None): Criteria hash for filtering.
            verbose (bool): If True, log detailed output.
            parallel (str): Parallelism mode ('none', 'asyncio', 'multiprocessing').
        """
        if criteria_hash:
            logger.info(f"Running integrations with criteria hash: {criteria_hash}")
        integrations, _ = self.filter_integrations(
            name, partial_name, tags, business_contact, technical_contact,
            last_updated_before, last_updated_after, description_contains
        )
        if not integrations:
            logger.warning("No integrations match the specified criteria")
            return

        if parallel == "asyncio":
            tasks = [self.run_integration_async(name, verbose) for name in integrations]
            await asyncio.gather(*tasks, return_exceptions=True)
        elif parallel == "multiprocessing":
            with multiprocessing.Pool() as pool:
                pool.map(_run_integration_wrapper, [(name, verbose, self.integrations_dir) for name in integrations])
        else:
            for name in integrations:
                self.run_integration(name, verbose)

    def list_integrations(
        self,
        name: str | None = None,
        partial_name: str | None = None,
        tags: list[str] | None = None,
        business_contact: str | None = None,
        technical_contact: str | None = None,
        last_updated_before: str | None = None,
        last_updated_after: str | None = None,
        description_contains: str | None = None,
        order_by: str = "name",
        order: str = "asc"
    ) -> None:
        """List integrations matching the specified criteria.

        Args:
            name (str | None): Exact integration name.
            partial_name (str | None): Partial name (wildcard).
            tags (list[str] | None): List of tags to match.
            business_contact (str | None): Business contact email.
            technical_contact (str | None): Technical contact email.
            last_updated_before (str | None): Last updated before (YYYY-MM-DD).
            last_updated_after (str | None): Last updated after (YYYY-MM-DD).
            description_contains (str | None): Substring in description.
            order_by (str): Field to order by ('name', 'last_updated').
            order (str): Order direction ('asc', 'desc').
        """
        integrations, criteria_hash = self.filter_integrations(
            name, partial_name, tags, business_contact, technical_contact,
            last_updated_before, last_updated_after, description_contains
        )
        if not integrations:
            click.echo("No integrations match the specified criteria.")
            return

        integration_data = []
        for integration_name in integrations:
            metadata = self.load_metadata(integration_name)
            integration_data.append({
                "name": integration_name,
                "business_contact": metadata.get("business_contact", "N/A"),
                "technical_contact": metadata.get("technical_contact", "N/A"),
                "last_updated": self.get_last_updated(integration_name),
                "description": metadata.get("description", "N/A"),
                "version": metadata.get("version", "N/A"),
                "valid_status": self.validate_integration(integration_name),
                "tags": metadata.get("tags", [])
            })

        reverse = (order == "desc")
        if order_by == "last_updated":
            integration_data.sort(key=lambda x: x["last_updated"] or "", reverse=reverse)
        else:
            integration_data.sort(key=lambda x: x["name"], reverse=reverse)

        click.echo(f"\nCriteria Hash: {criteria_hash}")
        click.echo("Integrations:")
        click.echo("-" * 140)
        click.echo(f"{'Name':<20} {'Business Contact':<25} {'Technical Contact':<25} {'Last Updated':<20} {'Description':<20} {'Version':<10} {'Valid':<10} {'Tags':<20}")
        click.echo("-" * 140)
        for item in integration_data:
            description = item["description"][:17] + "..." if len(item["description"]) > 17 else item["description"]
            tags = ",".join(item["tags"])[:17] + "..." if len(",".join(item["tags"])) > 17 else ",".join(item["tags"])
            click.echo(f"{item['name']:<20} {item['business_contact']:<25} {item['technical_contact']:<25} {item['last_updated']:<20} {description:<20} {item['version']:<10} {str(item['valid_status']):<10} {tags:<20}")
        click.echo("-" * 140)

    def validate(self) -> None:
        """Validate all available integrations."""
        integrations = self.get_integrations()
        for name in integrations:
            valid = self.validate_integration(name)
            status = "valid" if valid else "invalid"
            logger.info(f"Integration {name} is {status}")

    def report_issue(self, issue_type: str, message: str, integration_name: str | None = None) -> None:
        """Report an issue for an integration or generally.

        Args:
            issue_type (str): Type of issue (e.g., 'bug', 'feature').
            message (str): Description of the issue.
            integration_name (str | None): Name of the related integration, if any.
        """
        integration = integration_name if integration_name else "general"
        self.support.report_issue(issue_type, message, integration)
        click.echo(f"Issue reported: {issue_type} - {message}")

    def generate_telemetry_report(self, period: str) -> None:
        """Generate a telemetry report for the specified period.

        Args:
            period (str): Period for the report (YYYY-MM).
        """
        self.telemetry.generate_report(period)

@click.group()
def cli():
    """Command-line interface for managing integrations."""
    pass

@cli.command(name="run")
@click.option('--name', help='Exact integration name')
@click.option('--partial-name', help='Partial integration name (wildcard)')
@click.option('--tag', multiple=True, help='Filter by tag (multiple allowed)')
@click.option('--business-contact', help='Filter by business contact email')
@click.option('--technical-contact', help='Filter by technical contact email')
@click.option('--last-updated-before', help='Filter by last updated before (YYYY-MM-DD)')
@click.option('--last-updated-after', help='Filter by last updated after (YYYY-MM-DD)')
@click.option('--description-contains', help='Filter by description substring')
@click.option('--criteria-hash', help='Run integrations matching a criteria hash')
@click.option('--parallel', type=click.Choice(['none', 'asyncio', 'multiprocessing']), default='none')
@click.option('--verbose', is_flag=True)
def run_integration(name, partial_name, tag, business_contact, technical_contact,
                    last_updated_before, last_updated_after, description_contains,
                    criteria_hash, parallel, verbose):
    """Run integrations matching the specified criteria."""
    runner = BatchRunner()
    asyncio.run(runner.run_filtered(
        name=name,
        partial_name=partial_name,
        tags=list(tag) if tag else None,
        business_contact=business_contact,
        technical_contact=technical_contact,
        last_updated_before=last_updated_before,
        last_updated_after=last_updated_after,
        description_contains=description_contains,
        criteria_hash=criteria_hash,
        verbose=verbose,
        parallel=parallel
    ))

@cli.command(name="list")
@click.option('--name', help='Exact integration name')
@click.option('--partial-name', help='Partial integration name (wildcard)')
@click.option('--tag', multiple=True, help='Filter by tag (multiple allowed)')
@click.option('--business-contact', help='Filter by business contact email')
@click.option('--technical-contact', help='Filter by technical contact email')
@click.option('--last-updated-before', help='Filter by last updated before (YYYY-MM-DD)')
@click.option('--last-updated-after', help='Filter by last updated after (YYYY-MM-DD)')
@click.option('--description-contains', help='Filter by description substring')
@click.option('--order-by', type=click.Choice(['name', 'last_updated']), default='name')
@click.option('--order', type=click.Choice(['asc', 'desc']), default='asc')
def list_integration(name, partial_name, tag, business_contact, technical_contact,
                     last_updated_before, last_updated_after, description_contains,
                     order_by, order):
    """List integrations matching the specified criteria."""
    runner = BatchRunner()
    runner.list_integrations(
        name=name,
        partial_name=partial_name,
        tags=list(tag) if tag else None,
        business_contact=business_contact,
        technical_contact=technical_contact,
        last_updated_before=last_updated_before,
        last_updated_after=last_updated_after,
        description_contains=description_contains,
        order_by=order_by,
        order=order
    )

@cli.command(name="validate")
def validate():
    """Validate all integrations."""
    runner = BatchRunner()
    runner.validate()

@cli.command(name="report-issue")
@click.option('--issue-type', required=True, help='Type of issue (e.g., bug, feature)')
@click.option('--message', required=True, help='Issue or feature request description')
@click.option('--integration-name', help='Related integration (optional)')
def report_issue(issue_type, message, integration_name):
    """Report an issue for an integration."""
    runner = BatchRunner()
    runner.report_issue(issue_type, message, integration_name)

@cli.command(name="generate-telemetry-report")
@click.option('--period', required=True, help='Period for report (YYYY-MM)')
def generate_telemetry_report(period):
    """Generate a telemetry report for the specified period."""
    runner = BatchRunner()
    runner.generate_telemetry_report(period)

if __name__ == "__main__":
    cli()
