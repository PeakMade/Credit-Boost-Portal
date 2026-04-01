"""
Entrata API Integration for Resident Verification
Handles communication with Entrata PMS to verify resident data during sign-up.
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
        self.api_url = os.environ.get('ENTRATA_API_URL', 'https://api.entrata.com/api/v1')
        self.username = os.environ.get('ENTRATA_API_USERNAME')
        self.password = os.environ.get('ENTRATA_API_PASSWORD')
        self.property_id = os.environ.get('ENTRATA_PROPERTY_ID')
        
        if not all([self.username, self.password]):
            logger.warning("⚠️ Entrata API credentials not configured")
    
    def _make_request(self, method, endpoint_name, params=None):
        """
        Make authenticated request to Entrata API
        
        Args:
            method: API method name (e.g., 'getResidents')
            endpoint_name: Endpoint identifier
            params: Dictionary of parameters
            
        Returns:
            Response data or None on error
        """
        if not self.username or not self.password:
            logger.error("❌ Entrata API credentials not configured")
            return None
        
        # Entrata uses JSON-RPC style requests
        payload = {
            "auth": {
                "type": "basic",
                "credentials": {
                    "username": self.username,
                    "password": self.password
                }
            },
            "requestId": "verify_resident",
            "method": {
                "name": method,
                "params": params or {}
            }
        }
        
        try:
            logger.info(f"🔍 Calling Entrata API: {method}")
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Check for API errors
            if 'response' in data and 'result' in data['response']:
                return data['response']['result']
            else:
                logger.error(f"❌ Entrata API unexpected response format: {data}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error("❌ Entrata API request timeout")
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
        params = {
            "propertyId": self.property_id,
            "email": email
        }
        
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


# Singleton instance
_entrata_client = None

def get_entrata_client():
    """Get singleton Entrata API client"""
    global _entrata_client
    if _entrata_client is None:
        _entrata_client = EntrataAPIClient()
    return _entrata_client
