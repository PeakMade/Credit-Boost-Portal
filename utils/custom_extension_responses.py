"""
Response builders for Microsoft Entra External ID custom authentication extensions
Constructs proper response payloads for OnAttributeCollectionSubmit events
"""
import logging

logger = logging.getLogger(__name__)


def build_continue_response():
    """
    Build a response that allows the user to continue with sign-up
    
    Used when resident verification succeeds
    
    Returns:
        dict: Formatted response for Entra custom authentication extension
    """
    return {
        "data": {
            "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
            "actions": [
                {
                    "@odata.type": "#microsoft.graph.attributeCollectionSubmit.continueWithDefaultBehavior"
                }
            ]
        }
    }


def build_validation_error_response(message, attribute_errors=None):
    """
    Build a response that shows validation errors to the user
    
    Used when resident verification fails or required fields are missing
    
    Args:
        message: General error message shown at top of form
        attribute_errors: Optional dict mapping attribute names to error messages
                         e.g., {"email": "Email not found in our system"}
    
    Returns:
        dict: Formatted response for Entra custom authentication extension
    """
    response = {
        "data": {
            "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
            "actions": [
                {
                    "@odata.type": "#microsoft.graph.attributeCollectionSubmit.showValidationError",
                    "message": message
                }
            ]
        }
    }
    
    # Add attribute-specific errors if provided
    if attribute_errors:
        response["data"]["actions"][0]["attributeErrors"] = [
            {
                "attribute": attr_name,
                "message": error_msg
            }
            for attr_name, error_msg in attribute_errors.items()
        ]
    
    return response


def build_block_page_response(message):
    """
    Build a response that blocks the user from signing up
    
    Used for hard blocks (e.g., service unavailable)
    
    Args:
        message: Error message to display to user
    
    Returns:
        dict: Formatted response for Entra custom authentication extension
    """
    return {
        "data": {
            "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
            "actions": [
                {
                    "@odata.type": "#microsoft.graph.attributeCollectionSubmit.showBlockPage",
                    "message": message
                }
            ]
        }
    }


def build_modify_attributes_response(attribute_modifications):
    """
    Build a response that modifies user attributes before account creation
    
    Future use: Could be used to normalize data, add computed fields, etc.
    
    Args:
        attribute_modifications: Dict mapping attribute names to new values
                                e.g., {"city": "Corrected City", "postalCode": "12345"}
    
    Returns:
        dict: Formatted response for Entra custom authentication extension
    """
    response = {
        "data": {
            "@odata.type": "microsoft.graph.onAttributeCollectionSubmitResponseData",
            "actions": [
                {
                    "@odata.type": "#microsoft.graph.attributeCollectionSubmit.modifyAttributeValues",
                    "attributes": attribute_modifications
                }
            ]
        }
    }
    
    return response


def parse_custom_extension_request(request_data):
    """
    Parse the request payload from Entra custom authentication extension
    
    Expected structure:
    {
        "type": "microsoft.graph.authenticationEvent.attributeCollectionSubmit",
        "source": "<source>",
        "data": {
            "@odata.type": "microsoft.graph.onAttributeCollectionSubmitCalloutData",
            "tenantId": "<tenant-id>",
            "authenticationEventListenerId": "<listener-id>",
            "customAuthenticationExtensionId": "<extension-id>",
            "userPrincipalName": "user@domain.com",
            "attributes": {
                "email": "user@example.com",
                "givenName": "John",
                "surname": "Doe",
                "extension_<guid>_DateOfBirth": "1990-01-15",
                ...
            }
        }
    }
    
    Args:
        request_data: Parsed JSON request body from Entra
    
    Returns:
        dict: Extracted and normalized attributes, or None if parsing fails
    """
    try:
        event_type = request_data.get('type', '')
        logger.info(f"📥 Received custom extension event: {event_type}")
        
        # Validate event type
        if 'attributeCollectionSubmit' not in event_type:
            logger.warning(f"⚠️ Unexpected event type: {event_type}")
            return None
        
        # Extract the data payload
        data = request_data.get('data', {})
        
        if not data:
            logger.error("❌ Missing 'data' in custom extension request")
            return None
        
        # Extract tenant and extension IDs for logging
        tenant_id = data.get('tenantId', 'unknown')
        extension_id = data.get('customAuthenticationExtensionId', 'unknown')
        
        logger.info(f"Extension ID: {extension_id[:20]}...")
        logger.info(f"Tenant ID: {tenant_id[:20]}...")
        
        # Extract user signup info (External ID specific)
        user_signup_info = data.get('userSignUpInfo', {})
        if user_signup_info:
            logger.info(f"📋 userSignUpInfo keys: {list(user_signup_info.keys())}")
        
        # Extract user attributes
        # External ID format: attributes may be under data.userSignUpInfo.attributes
        # Standard format: attributes may be directly under data.attributes
        attributes = data.get('attributes', {})
        user_signup_info = data.get('userSignUpInfo', {})
        
        # Try External ID format if standard format is empty
        if not attributes and user_signup_info:
            attributes = user_signup_info.get('attributes', {})
            logger.info("📋 Using External ID format (data.userSignUpInfo.attributes)")
        
        if not attributes:
            logger.error("❌ Missing 'attributes' in custom extension request")
            logger.error(f"❌ Available data keys: {list(data.keys())}")
            return None
        
        # Log received attributes (safely, without full values)
        logger.info(f"📋 Received attributes: {list(attributes.keys())}")
        
        # Helper function to safely extract string values
        def safe_str(value, default=''):
            """Convert value to string safely, handling None, dicts, etc."""
            if value is None:
                return default
            if isinstance(value, dict):
                # If it's a dict, try to get a reasonable string representation
                return str(value.get('value', default)).strip()
            return str(value).strip()
        
        # Extract standard attributes
        # In External ID, email is typically in userSignUpInfo.identities array
        email = attributes.get('email')
        
        # Try userSignUpInfo fields if not in attributes
        if not email and user_signup_info:
            email = user_signup_info.get('userPrincipalName') or user_signup_info.get('email')
        
        # Try identities array (External ID format)
        if not email and user_signup_info:
            identities = user_signup_info.get('identities', [])
            logger.info(f"📧 Searching for email in {len(identities)} identities")
            for identity in identities:
                if isinstance(identity, dict):
                    sign_in_type = identity.get('signInType', '').lower()
                    if 'email' in sign_in_type:
                        email = identity.get('issuerAssignedId')
                        logger.info(f"📧 Found email in identities: {email[:5]}...@{email.split('@')[1] if '@' in str(email) else '?'}")
                        break
        
        email = safe_str(email)
        given_name = safe_str(attributes.get('givenName'))
        surname = safe_str(attributes.get('surname'))
        
        # Extract custom attributes
        # Custom attributes may be named like:
        # - extension_<guid>_DateOfBirth
        # - extension_DateOfBirth
        # - DateOfBirth
        # We'll search for DOB-related keys
        
        date_of_birth = None
        for key, value in attributes.items():
            key_lower = key.lower()
            if 'dateofbirth' in key_lower or 'dob' in key_lower:
                date_of_birth = safe_str(value)
                logger.info(f"Found DOB attribute: {key}")
                break
        
        # Extract property/unit if provided
        property_name = None
        for key, value in attributes.items():
            key_lower = key.lower()
            if 'property' in key_lower or 'unit' in key_lower or 'building' in key_lower:
                property_name = safe_str(value)
                logger.info(f"Found property attribute: {key}")
                break
        
        result = {
            'email': email,
            'given_name': given_name,
            'surname': surname,
            'date_of_birth': date_of_birth,
            'property': property_name,
            'raw_attributes': attributes  # Keep for debugging/future use
        }
        
        logger.info(f"✅ Parsed attributes: email={email}, name={given_name} {surname}, dob={'***' if date_of_birth else 'missing'}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Error parsing custom extension request: {e}")
        return None
