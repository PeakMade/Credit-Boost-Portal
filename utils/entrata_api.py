"""
Entrata API Integration for Resident Verification and Data Retrieval
Handles communication with Entrata PMS to verify resident data and retrieve lease information.

=== CONFIGURATION ===
This module uses environment variables from .env file:
- ENTRATA_API_KEY: API key for authentication (get from Entrata support)
- ENTRATA_ORG_SUBDOMAIN: Organization subdomain (e.g., peakmade-test-17291)
- ENTRATA_PROPERTY_ID: (Optional) Specific property ID, omit for portfolio-wide access

=== TO DISABLE ENTRATA INTEGRATION ===
1. In .env, set: USE_SHAREPOINT_VERIFICATION=true
2. This will use SharePoint verification instead of Entrata API
3. See app.py and verify_resident_signup() endpoint for integration points

=== TO REMOVE ENTRATA INTEGRATION COMPLETELY ===
1. Delete this file: utils/entrata_api.py
2. Remove imports in app.py: from utils.entrata_api import get_entrata_client
3. Remove any calls to get_entrata_client() in the codebase
4. Keep USE_SHAREPOINT_VERIFICATION=true in .env

See ENTRATA_API_INTEGRATION_GUIDE.md for complete API documentation.
"""
import os
import json
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class EntrataAPIClient:
    """Client for interacting with Entrata Property Management System API"""
    
    def __init__(self):
        # API Key authentication (preferred method)
        self.api_key = os.environ.get('ENTRATA_API_KEY')
        self.org_subdomain = os.environ.get('ENTRATA_ORG_SUBDOMAIN', 'peakmade-test-17291')
        self.base_url = f"https://apis.entrata.com/ext/orgs/{self.org_subdomain}/v1"
        
        # Legacy username/password (fallback for older API endpoints)
        self.username = os.environ.get('ENTRATA_API_USERNAME')
        self.password = os.environ.get('ENTRATA_API_PASSWORD')
        
        # Optional property ID filter
        self.property_id = os.environ.get('ENTRATA_PROPERTY_ID')
        
        if not self.api_key and not (self.username and self.password):
            logger.warning("⚠️ Entrata API credentials not configured (need ENTRATA_API_KEY or username/password)")
        else:
            logger.info(f"✅ Entrata API configured: {self.base_url}")
            if self.api_key:
                logger.info(f"   Auth method: API Key")
            else:
                logger.info(f"   Auth method: Username/Password (legacy)")
                logger.info(f"   Username: {self.username}")
            logger.info(f"   Property ID: {self.property_id if self.property_id else 'Portfolio-level access'}")
    
    def _make_request(self, method_name, group, params=None, version=None, use_api_key=True):
        """
        Make authenticated request to Entrata API
        
        Args:
            method_name: API method name (e.g., 'getLeases', 'getResidents')
            group: API group/endpoint (e.g., 'residents', 'leases')
            params: Dictionary of parameters
            version: API version (e.g., 'r2' for getLeases)
            use_api_key: Use API key auth (True) or username/password (False)
            
        Returns:
            Response data or None on error
        """
        # Determine which auth method to use
        if use_api_key and not self.api_key:
            logger.error("❌ Entrata API key not configured")
            return None
        elif not use_api_key and not (self.username and self.password):
            logger.error("❌ Entrata username/password not configured")
            return None
        
        # Build full endpoint URL with group
        endpoint_url = f"{self.base_url}/{group}"
        
        # Build headers
        headers = {'Content-Type': 'application/json'}
        if use_api_key:
            headers['X-Api-Key'] = self.api_key
        
        # Build method object
        method_obj = {
            "name": method_name,
            "params": params or {}
        }
        if version:
            method_obj["version"] = version
        
        # Build auth object
        if use_api_key:
            auth_obj = {"type": "apikey"}
        else:
            auth_obj = {
                "type": "basic",
                "credentials": {
                    "username": self.username,
                    "password": self.password
                }
            }
        
        # Build complete payload
        payload = {
            "auth": auth_obj,
            "requestId": str(int(datetime.now().timestamp())),
            "method": method_obj
        }
        
        try:
            logger.info(f"🔍 Calling Entrata API: {method_name} at {endpoint_url}")
            logger.info(f"   Auth: {'API Key' if use_api_key else 'Username/Password'}")
            logger.info(f"   Version: {version if version else 'default'}")
            
            response = requests.post(
                endpoint_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            # Log response details
            logger.info(f"   Response status: {response.status_code}")
            
            if response.status_code != 200:
                logger.error(f"❌ HTTP {response.status_code}: {response.text}")
                return None
            
            data = response.json()
            
            # Check for API-level errors
            response_code = data.get('response', {}).get('code')
            if response_code != 200:
                error = data.get('response', {}).get('error', {})
                logger.error(f"❌ Entrata API error {response_code}: {error.get('message', 'Unknown error')}")
                return None
            
            # Return the result data
            result = data.get('response', {}).get('result', {})
            logger.info(f"✅ API call successful")
            return result
                
        except requests.exceptions.Timeout:
            logger.error("❌ Entrata API request timeout (30s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Entrata API request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"❌ Entrata API invalid JSON response: {e}")
            return None
    
    def verify_resident(self, email, first_name, last_name, date_of_birth):
        """
        Verify a resident exists in Entrata with matching details
        
        Args:
            email: Resident email address
            first_name: Resident first name
            last_name: Resident last name
            date_of_birth: Date of birth (YYYY-MM-DD format or datetime object)
            
        Returns:
            dict with 'verified': bool, 'resident_id': str/None, 'message': str
        """
        # Normalize inputs
        email = email.lower().strip()
        first_name = first_name.strip()
        last_name = last_name.strip()
        
        # Parse DOB if string
        if isinstance(date_of_birth, str):
            try:
                dob = datetime.strptime(date_of_birth, '%Y-%m-%d')
            except ValueError:
                logger.error(f"❌ Invalid date format: {date_of_birth}")
                return {
                    'verified': False,
                    'resident_id': None,
                    'message': 'Invalid date of birth format'
                }
        else:
            dob = date_of_birth
        
        # Query Entrata for residents matching email
        # Build params - only include propertyId if it's configured
        params = {"email": email}
        if self.property_id:
            params["propertyId"] = self.property_id
            logger.info(f"   Querying with property ID: {self.property_id}")
        else:
            logger.info(f"   Querying portfolio-wide (no property ID filter)")
        
        result = self._make_request('getResidents', 'residents', params)
        
        if result is None:
            logger.error("❌ Failed to query Entrata API")
            return {
                'verified': False,
                'resident_id': None,
                'message': 'Unable to verify at this time. Please try again later.'
            }
        
        # Check if we got any residents back
        residents = result.get('Residents', {}).get('Resident', [])
        if not residents:
            logger.info(f"❌ No residents found with email: {email}")
            return {
                'verified': False,
                'resident_id': None,
                'message': 'The data you provided could not be verified.'
            }
        
        # Ensure residents is a list (API returns dict for single result)
        if isinstance(residents, dict):
            residents = [residents]
        
        # Verify matching criteria
        for resident in residents:
            # Check name match (case-insensitive)
            res_first = resident.get('FirstName', '').strip().lower()
            res_last = resident.get('LastName', '').strip().lower()
            
            if res_first != first_name.lower() or res_last != last_name.lower():
                continue
            
            # Check DOB match
            res_dob_str = resident.get('DateOfBirth', '')
            if res_dob_str:
                try:
                    res_dob = datetime.strptime(res_dob_str, '%Y-%m-%d')
                    if res_dob.date() != dob.date():
                        continue
                except ValueError:
                    logger.warning(f"⚠️ Invalid DOB in Entrata: {res_dob_str}")
                    continue
            
            # Match found!
            resident_id = resident.get('ResidentId') or resident.get('CustomerId')
            logger.info(f"✅ Resident verified: {email} (ID: {resident_id})")
            return {
                'verified': True,
                'resident_id': str(resident_id),
                'message': 'Resident verified successfully'
            }
        
        # No match found
        logger.info(f"❌ Resident found but details don't match: {email}")
        return {
            'verified': False,
            'resident_id': None,
            'message': 'The data you provided could not be verified.'
        }
    
    def get_leases(self, property_id=None, move_in_from=None, move_in_to=None, 
                   include_demographics=True, include_ar_transactions=True):
        """
        Retrieve lease data from Entrata with optional demographics and AR transactions
        
        Args:
            property_id: Specific property ID (int), or None for portfolio-wide
            move_in_from: Move-in date filter start (MM/DD/YYYY format)
            move_in_to: Move-in date filter end (MM/DD/YYYY format)
            include_demographics: Include resident profile data (default: True)
            include_ar_transactions: Include AR transaction history (default: True)
            
        Returns:
            List of lease dictionaries, or None on error
        """
        # Build parameters
        params = {
            "includeDemographics": "1" if include_demographics else "0",
            "includeArTransactions": "1" if include_ar_transactions else "0"
        }
        
        # Use instance property_id if not specified
        if property_id is None and self.property_id:
            property_id = int(self.property_id)
        
        if property_id:
            params["propertyId"] = int(property_id)
            logger.info(f"   Querying property ID: {property_id}")
        else:
            logger.info(f"   Querying portfolio-wide")
        
        # Add date filters if provided
        if move_in_from:
            params["moveInDateFrom"] = move_in_from
        if move_in_to:
            params["moveInDateTo"] = move_in_to
        
        # Make API call using getLeases v2 (r2)
        result = self._make_request('getLeases', 'leases', params=params, version='r2', use_api_key=True)
        
        if result is None:
            logger.error("❌ Failed to retrieve leases from Entrata API")
            return None
        
        # Extract leases from result
        leases = result.get('leases', {}).get('lease', [])
        
        # Ensure leases is a list (API returns dict for single result)
        if isinstance(leases, dict):
            leases = [leases]
        
        logger.info(f"✅ Retrieved {len(leases)} leases from Entrata")
        return leases


# Singleton instance
_entrata_client = None

def get_entrata_client():
    """Get singleton Entrata API client"""
    global _entrata_client
    if _entrata_client is None:
        _entrata_client = EntrataAPIClient()
    return _entrata_client
