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

import yaml
from integration_framework.integrations import Integration
from integration_framework.sql_query_manager import SQLQueryManager
from integration_framework.support_manager import SupportManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class BatchRunner:
    """Manages running integrations with logging.

    Handles loading, validating, and executing integrations, with support for
    parallel execution and validation caching.
    """
    def __init__(self) -> None:
        """Initialize the BatchRunner with default settings."""
        self.integrations_dir = Path("integrations")
        self.support = SupportManager()
        self.sql_manager = SQLQueryManager("telemetry.db")
        self.cache_file = Path("validation_cache.json")
        self.cache_ttl = timedelta(hours=24)
        self._is_test = False  # Flag for test-specific behavior

    def load_integration(self, integration_name: str) -> type[Integration] | None:
        """Load an integration class by name.

        Args:
            integration_name (str): Name of the integration to load.

        Returns:
            type[Integration] | None: The integration class or None if not found.
        """
        # Use test-specific package name if in test mode
        package_prefix = "test_integration_framework" if self._is_test else "integration_framework"
        module_name = f"{package_prefix}.integrations.{integration_name}"
        try:
            # Check if module exists
            logger.debug(f"Checking spec for {module_name}, sys.path: {sys.path}")
            spec = importlib.util.find_spec(module_name)
            logger.debug(f"Spec for {module_name}: {spec}")
            if spec is None:
                logger.warning(f"Module {module_name} not found")
                # Attempt import as fallback
                try:
                    module = importlib.import_module(module_name)
                except ImportError as e:
                    logger.error(f"Fallback import failed for {module_name}: {str(e)}")
                    return None
            else:
                module = importlib.import_module(module_name)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                logger.debug(f"Checking attribute {attr_name} in {module_name}: {attr}")
                if isinstance(attr, type) and issubclass(attr, Integration) and attr != Integration:
                    logger.debug(f"Loaded integration class {attr.__name__} from {module_name}")
                    return attr
            logger.warning(f"No Integration subclass found in {integration_name}")
            return None
        except ImportError as e:
            error_msg = f"Failed to load integration {integration_name}: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.support.report_issue("config", error_msg)
            return None

    def load_config(self, integration_name: str) -> dict:
        """Load the config.yaml for an integration.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            dict: Configuration data or empty dict if not found.
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
            self.support.report_issue("config", f"Invalid config for {integration_name}: {e}")
            return {}

    def load_metadata(self, integration_name: str) -> dict:
        """Load the metadata.yaml for an integration.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            dict: Metadata or empty dict if not found.
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
            self.support.report_issue("config", f"Invalid metadata for {integration_name}: {e}")
            return {}

    def load_validation_cache(self) -> dict:
        """Load the validation cache from JSON.

        Returns:
            dict: Cache data or default structure if not found.
        """
        if not self.cache_file.exists():
            return {"integrations": {}}
        try:
            with self.cache_file.open("r") as f:
                return json.load(f) or {"integrations": {}}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to load validation cache: {e}")
            return {"integrations": {}}

    def save_validation_cache(self, cache: dict) -> None:
        """Save the validation cache to JSON.

        Args:
            cache (dict): Cache data to save.
        """
        try:
            with self.cache_file.open("w") as f:
                json.dump(cache, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save validation cache: {e}")

    def get_last_updated(self, integration_name: str) -> str:
        """Get the last update timestamp for an integration from telemetry or metadata.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            str: ISO timestamp or 'N/A' if not found.
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
        """Validate a single integration, using and updating the validation cache.

        Args:
            integration_name (str): Name of the integration.

        Returns:
            bool: True if valid or disabled, False otherwise.
        """
        cache = self.load_validation_cache()
        integrations_cache = cache.get("integrations", {})
        
        # Check cache
        if integration_name in integrations_cache:
            cached = integrations_cache[integration_name]
            try:
                cache_time = datetime.fromisoformat(cached["timestamp"])
                if datetime.now() - cache_time < self.cache_ttl:
                    return cached["valid"]
            except (KeyError, ValueError):
                pass  # Invalid cache entry, proceed to validate

        # Perform validation
        config = self.load_config(integration_name)
        if not config.get("enabled", False):
            valid = True  # Disabled integrations are valid
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

        # Update cache
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
            verbose (bool): Enable verbose logging.
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
            if verbose:
                logger.info(f"Completed {integration_name} in {duration:.2f}s")
        except Exception as e:
            duration = time.time() - start_time
            self.support.report_issue("runtime", f"Integration {integration_name} failed: {e}", integration_name)
            if verbose:
                logger.error(f"Failed {integration_name}: {e}")

    async def run_integration_async(self, integration_name: str, verbose: bool = False) -> None:
        """Run a single integration asynchronously.

        Args:
            integration_name (str): Name of the integration.
            verbose (bool): Enable verbose logging.
        """
        self.run_integration(integration_name, verbose)

    def run_integration_process(self, integration_name: str, verbose: bool = False) -> None:
        """Run a single integration in a separate process.

        Args:
            integration_name (str): Name of the integration.
            verbose (bool): Enable verbose logging.
        """
        self.run_integration(integration_name, verbose)

    def get_integrations(self) -> list[str]:
        """Get list of available integrations.

        Returns:
            list[str]: Names of available integrations.
        """
        return [
            d.name
            for d in self.integrations_dir.iterdir()
            if d.is_dir() and (d / "__init__.py").exists() and (d / "config.yaml").exists()
        ]

    async def run_all(self, verbose: bool = False, parallel: str = "none") -> None:
        """Run all enabled integrations.

        Args:
            verbose (bool): Enable verbose logging.
            parallel (str): Execution mode ('none', 'asyncio', 'multiprocessing').
        """
        integrations = self.get_integrations()
        if not integrations:
            logger.warning("No integrations found")
            return

        if parallel == "asyncio":
            tasks = [self.run_integration_async(name, verbose) for name in integrations]
            await asyncio.gather(*tasks, return_exceptions=True)
        elif parallel == "multiprocessing":
            with multiprocessing.Pool() as pool:
                pool.starmap(self.run_integration_process, [(name, verbose) for name in integrations])
        else:
            for name in integrations:
                self.run_integration(name, verbose)

    def run_single(self, integration_name: str, verbose: bool = False) -> None:
        """Run a single integration by name.

        Args:
            integration_name (str): Name of the integration.
            verbose (bool): Enable verbose logging.
        """
        if integration_name not in self.get_integrations():
            logger.error(f"Integration {integration_name} not found")
            self.support.report_issue("config", f"Integration {integration_name} not found")
            return
        self.run_integration(integration_name, verbose)

    def run_by_tag(self, tag: str, verbose: bool = False) -> None:
        """Run integrations with a specific tag.

        Args:
            tag (str): Tag to filter integrations.
            verbose (bool): Enable verbose logging.
        """
        integrations = self.get_integrations()
        for name in integrations:
            metadata = self.load_metadata(name)
            if tag in metadata.get("tags", []):
                self.run_integration(name, verbose)

    def validate(self) -> None:
        """Validate all integrations."""
        integrations = self.get_integrations()
        for name in integrations:
            valid = self.validate_integration(name)
            status = "valid" if valid else "invalid"
            logger.info(f"Integration {name} is {status}")

    def list_integrations(self, tag: str | None = None, business: str | None = None,
                         technical: str | None = None, order_by: str = "name",
                         order: str = "asc") -> None:
        """List integrations with optional filtering and ordering.

        Args:
            tag (str, optional): Filter by tag.
            business (str, optional): Filter by business contact email.
            technical (str, optional): Filter by technical contact email.
            order_by (str): Order by 'name' or 'last_updated'.
            order (str): Order direction ('asc' or 'desc').
        """
        integrations = self.get_integrations()
        if not integrations:
            click.echo("No integrations found.")
            return

        # Collect integration details
        integration_data = []
        for name in integrations:
            metadata = self.load_metadata(name)
            tags = metadata.get("tags", [])
            
            # Apply tag filter
            if tag and tag not in tags:
                continue
                
            # Apply contact filters
            business_contact = metadata.get("business_contact", "N/A")
            technical_contact = metadata.get("technical_contact", "N/A")
            if business and business_contact != business:
                continue
            if technical and technical_contact != technical:
                continue
                
            integration_data.append({
                "name": name,
                "business_contact": business_contact,
                "technical_contact": technical_contact,
                "last_updated": self.get_last_updated(name),
                "description": metadata.get("description", "N/A"),
                "version": metadata.get("version", "N/A"),
                "valid_status": self.validate_integration(name)
            })

        if not integration_data:
            click.echo("No integrations match the specified filters.")
            return

        # Sort data
        reverse = (order == "desc")
        if order_by == "last_updated":
            integration_data.sort(key=lambda x: x["last_updated"] or "", reverse=reverse)
        else:  # default to name
            integration_data.sort(key=lambda x: x["name"], reverse=reverse)

        # Display table
        click.echo("\nIntegrations:")
        click.echo("-" * 120)
        click.echo(f"{'Name':<20} {'Business Contact':<25} {'Technical Contact':<25} {'Last Updated':<20} {'Description':<20} {'Version':<10} {'Valid':<10}")
        click.echo("-" * 120)
        for item in integration_data:
            click.echo(f"{item['name']:<20} {item['business_contact']:<25} {item['technical_contact']:<25} {item['last_updated']:<20} {item['description'][:17] + '...' if len(item['description']) > 17 else item['description']:<20} {item['version']:<10} {str(item['valid_status']):<10}")
        click.echo("-" * 120)

@click.command()
@click.option('--run-all', is_flag=True, help='Run all integrations')
@click.option('--run-single', help='Run a single integration')
@click.option('--run-by-tag', help='Run integrations with a specific tag')
@click.option('--validate', is_flag=True, help='Validate all integrations')
@click.option('--list', is_flag=True, help='List all integrations')
@click.option('--tag', help='Filter integrations by tag')
@click.option('--business', help='Filter integrations by business contact email')
@click.option('--technical', help='Filter integrations by technical contact email')
@click.option('--order-by', type=click.Choice(['name', 'last_updated']), default='name',
              help='Order integrations by name or last_updated')
@click.option('--order', type=click.Choice(['asc', 'desc']), default='asc',
              help='Order direction (ascending or descending)')
@click.option('--parallel', type=click.Choice(['none', 'asyncio', 'multiprocessing']), default='none',
              help='Parallel execution mode')
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
def main(run_all: bool, run_single: str | None, run_by_tag: str | None, validate: bool,
         list: bool, tag: str | None, business: str | None, technical: str | None, order_by: str,
         order: str, parallel: str, verbose: bool) -> None:
    """Integration Framework CLI."""
    runner = BatchRunner()
    
    if run_all:
        asyncio.run(runner.run_all(verbose=verbose, parallel=parallel))
    elif run_single:
        runner.run_single(run_single, verbose=verbose)
    elif run_by_tag:
        runner.run_by_tag(run_by_tag, verbose=verbose)
    elif validate:
        runner.validate()
    elif list:
        runner.list_integrations(tag=tag, business=business, technical=technical,
                                order_by=order_by, order=order)
    else:
        click.echo(click.get_current_context().get_help())

if __name__ == "__main__":
    main()
