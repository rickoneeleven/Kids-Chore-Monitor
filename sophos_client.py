# File: sophos_client.py
"""
Client module for interacting with the Sophos Firewall API.

Handles connection, authentication, and firewall rule status management
using the sophosfirewall-python library.
"""

import logging
from typing import Optional, Dict, Any

# Import the main Sophos Firewall class and specific exceptions
from sophosfirewall_python.firewallapi import (
    SophosFirewall,
    SophosFirewallAuthFailure,
    SophosFirewallAPIError,
    SophosFirewallZeroRecords,
    SophosFirewallInvalidArgument,
    SophosFirewallOperatorError
)
# Import the utility for handling lists
from sophosfirewall_python.utils import Utils # Import added

# Initialize logger for this module
logger = logging.getLogger(__name__)

# --- Custom Exceptions ---
class SophosClientError(Exception):
    """Base exception for SophosClient specific errors."""
    pass

class SophosConfigurationError(SophosClientError):
    """Error related to client configuration (host, user, pass)."""
    pass

class SophosConnectionError(SophosClientError):
    """Error related to connecting or authenticating to the firewall."""
    pass

class SophosApiError(SophosClientError):
    """Error occurring during an API operation after connection."""
    pass

class SophosRuleNotFoundError(SophosClientError):
    """Error when a specified firewall rule cannot be found by name."""
    pass

class SophosClient:
    """
    A client for interacting with the Sophos Firewall API for rule management.
    """
    # Default API port for Sophos XG/SFOS
    DEFAULT_PORT = 4444

    def __init__(self, host: str, api_user: str, api_password: str, port: int = DEFAULT_PORT, verify_ssl: bool = False):
        """
        Initializes the SophosClient and establishes a connection.
        (Constructor remains the same as previous version)
        """
        if not all([host, api_user, api_password]):
            msg = "Sophos host, API user, and API password are required."
            logger.critical(msg)
            raise SophosConfigurationError(msg)

        self.host = host
        self.port = port
        self._api_user = api_user
        self._api_password = api_password

        logger.info("Initializing SophosFirewall client for host: %s:%d", host, port)
        try:
            self.client = SophosFirewall(
                hostname=host,
                username=api_user,
                password=api_password,
                port=port,
                verify=verify_ssl
            )
            self._test_connection()

        except SophosFirewallAuthFailure as e:
            msg = f"Authentication failed for Sophos host {host}:{port}. Check API credentials. Error: {e}"
            logger.critical(msg, exc_info=False)
            raise SophosConnectionError(msg) from e
        except SophosFirewallAPIError as e:
            msg = f"API error during initial connection to Sophos host {host}:{port}. Ensure API access is enabled and IP is allowed. Error: {e}"
            logger.critical(msg, exc_info=True)
            raise SophosConnectionError(msg) from e
        except ConnectionError as e:
             msg = f"Could not connect to Sophos host {host}:{port}. Check network connectivity and firewall status. Error: {e}"
             logger.critical(msg, exc_info=True)
             raise SophosConnectionError(msg) from e
        except Exception as e:
            msg = f"An unexpected error occurred during SophosClient initialization for {host}:{port}: {e}"
            logger.critical(msg, exc_info=True)
            raise SophosConnectionError(msg) from e

        logger.info("SophosClient initialized and connection verified successfully for host: %s:%d", host, port)

    def _test_connection(self):
        """
        Performs a basic API call to verify connectivity and authentication are working.
        (Remains the same as previous version)
        """
        logger.debug("Performing connection test call (login)...")
        try:
            response = self.client.login()
            if response.get('Response', {}).get('Login', {}).get('status') != 'Authentication Successful':
                raise SophosConnectionError(f"Connection test failed: Unexpected login response status: {response.get('Response', {}).get('Login', {})}")
            logger.debug("Connection test successful.")
        except (SophosFirewallAuthFailure, SophosFirewallAPIError, ConnectionError) as e:
             raise SophosConnectionError(f"Connection test API call failed: {e}") from e
        except Exception as e:
            raise SophosConnectionError(f"Unexpected error during connection test API call: {e}") from e

    def _get_full_rule_details(self, rule_name: str) -> Dict[str, Any]:
        """
        Retrieves the complete configuration dictionary for a rule. Internal helper.
        (Remains the same as previous version)
        """
        logger.debug("Fetching full details for rule: '%s'", rule_name)
        try:
            response = self.client.get_rule(name=rule_name, operator='=')
            rule_data = response.get('Response', {}).get('FirewallRule')
            if not rule_data:
                raise SophosRuleNotFoundError(f"Rule '{rule_name}' structure not found in response.")
            return rule_data
        except SophosFirewallZeroRecords:
            logger.warning("Firewall rule '%s' not found during full detail fetch.", rule_name)
            raise SophosRuleNotFoundError(f"Firewall rule '{rule_name}' not found.")
        except (SophosFirewallAuthFailure, SophosFirewallAPIError, ConnectionError) as e:
            msg = f"API/Connection error fetching full details for rule '{rule_name}': {e}"
            logger.error(msg)
            if isinstance(e, SophosFirewallAuthFailure) or isinstance(e, ConnectionError):
                raise SophosConnectionError(msg) from e
            else:
                raise SophosApiError(msg) from e
        except Exception as e:
            msg = f"Unexpected error fetching full details for rule '{rule_name}': {e}"
            logger.exception(msg, exc_info=True)
            raise SophosApiError(msg) from e


    def get_rule_status(self, rule_name: str) -> Optional[bool]:
        """
        Retrieves the current status (enabled/disabled) of a firewall rule by name.
        (Remains the same as previous version)
        """
        if not rule_name:
            raise ValueError("rule_name cannot be empty.")

        logger.debug("Attempting to get status for firewall rule: '%s'", rule_name)
        try:
            rule_data = self._get_full_rule_details(rule_name)
            status_str = rule_data.get('Status')

            if status_str:
                logger.info("Found status '%s' for rule '%s'", status_str, rule_name)
                if status_str.lower() == 'enable':
                    return True
                elif status_str.lower() == 'disable':
                    return False
                else:
                    logger.warning("Rule '%s' has an ambiguous status: '%s'. Returning None.", rule_name, status_str)
                    return None
            else:
                logger.error("Could not determine status for rule '%s'. 'Status' field missing in response: %s", rule_name, rule_data)
                return None
        except SophosRuleNotFoundError:
            raise
        except (SophosApiError, SophosConnectionError) as e:
             raise


    def set_rule_status(self, rule_name: str, target_enabled_state: bool) -> bool:
        """
        Sets the status (enabled or disabled) of a firewall rule by name.
        Checks the current state first and only performs an update if necessary.
        Fetches full rule details before updating and uses submit_template directly.

        Args:
            rule_name: The exact name of the firewall rule.
            target_enabled_state: True to enable the rule, False to disable it.

        Returns:
            True if the rule is successfully set to the target state (or already was).
            False if the rule could not be found or the update failed.

        Raises:
             ValueError: If rule_name is empty.
             SophosApiError: If an API error occurs during the set operation.
             SophosConnectionError: If authentication/connection issues arise.
        """
        if not rule_name:
            raise ValueError("rule_name cannot be empty.")

        target_status_str = "Enable" if target_enabled_state else "Disable"
        logger.debug("Attempting to set firewall rule '%s' to state: %s", rule_name, target_status_str)

        try:
            # 1. Get FULL current rule details
            exist_rule = self._get_full_rule_details(rule_name)
            current_status_str = exist_rule.get('Status', '').lower()

            # 2. Check idempotency
            if (target_enabled_state and current_status_str == 'enable') or \
               (not target_enabled_state and current_status_str == 'disable'):
                logger.info("Rule '%s' is already in the desired state (%s). No action needed.", rule_name, target_status_str)
                return True
            elif not current_status_str:
                 logger.warning("Could not determine current status for rule '%s'. Proceeding with update attempt.", rule_name)

            # 3. Prepare FULL parameters dictionary for the template
            logger.info("Rule '%s' needs state change. Current: %s, Target: %s. Preparing update...",
                        rule_name, current_status_str.capitalize() if current_status_str else 'Unknown', target_status_str)

            network_policy = exist_rule.get('NetworkPolicy', {})
            # *** This is the dictionary passed directly to submit_template ***
            template_vars = {
                'rulename': rule_name, # Template needs the name explicitly
                'status': target_status_str, # The only intended change
                # Carry over other essential fields expected by updatefwrule.j2
                'description': exist_rule.get('Description', ''),
                'action': network_policy.get('Action', 'Accept'), # Default if missing
                'log': network_policy.get('LogTraffic', 'Disable'), # Default if missing
                # Use Utils.ensure_list and handle missing keys gracefully -> empty list []
                'src_zones': Utils.ensure_list(network_policy.get('SourceZones', {}).get('Zone', [])) if network_policy.get('SourceZones') else [],
                'dst_zones': Utils.ensure_list(network_policy.get('DestinationZones', {}).get('Zone', [])) if network_policy.get('DestinationZones') else [],
                'src_networks': Utils.ensure_list(network_policy.get('SourceNetworks', {}).get('Network', [])) if network_policy.get('SourceNetworks') else [],
                'dst_networks': Utils.ensure_list(network_policy.get('DestinationNetworks', {}).get('Network', [])) if network_policy.get('DestinationNetworks') else [],
                'service_list': Utils.ensure_list(network_policy.get('Services', {}).get('Service', [])) if network_policy.get('Services') else [],
                # Add position if needed by the template (unlikely for simple status change)
                'position': exist_rule.get('Position', 'Bottom'), # Get existing position
                # Ensure after/before are not included unless explicitly moving
                'after_rulename': None,
                'before_rulename': None,
            }
            # Optional: Add logic here to include after/before if exist_rule['Position'] requires it

            # 4. Perform the update using submit_template directly
            logger.debug("Submitting template 'updatefwrule.j2' for rule '%s' with vars: %s", rule_name, template_vars)
            # *** Use submit_template instead of update_rule ***
            response = self.client.submit_template(filename='updatefwrule.j2', template_vars=template_vars)

            # 5. Check response (same as before)
            update_status = response.get('Response', {}).get('FirewallRule', {}).get('Status', {})
            status_code = update_status.get('@code')
            status_text = update_status.get('#text', 'Unknown Status')

            if status_code and status_code.startswith('2'):
                logger.info("Successfully updated rule '%s' status to %s. Response: %s",
                            rule_name, target_status_str, status_text)
                return True
            else:
                logger.error("Failed to update rule '%s' status via submit_template. Code: %s, Message: %s",
                             rule_name, status_code or 'N/A', status_text)
                # Check if the response indicates a specific API failure
                raise SophosApiError(f"Sophos API reported failure updating rule '{rule_name}' via template. Code: {status_code or 'N/A'}, Message: {status_text}")

        except SophosRuleNotFoundError:
             return False
        except (SophosApiError, SophosConnectionError) as e:
            logger.error("Failed operation for rule '%s': %s", rule_name, e)
            return False
        except Exception as e:
            msg = f"Unexpected error setting status for rule '{rule_name}': {e}"
            logger.exception(msg, exc_info=True)
            # Raise as API error as it happened during operation
            # Check if it's a jinja2 error, which might indicate a problem with template_vars construction
            if "jinja2" in str(type(e)).lower():
                 logger.error("Possible template rendering error. Check template_vars construction.")
            raise SophosApiError(msg) from e