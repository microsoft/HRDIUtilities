from azure.identity import DefaultAzureCredential, ClientSecretCredential
import logging
class AuthClient():
    """
    Initialize the AuthClient with the specified authentication method.

    Parameters:
        auth_type (str): The authentication method to use. Supported values include
                         'managed_identity' and 'service_principal'.

    Keyword Args:
        tenant_id (str): Required if auth_type is 'service_principal'.
        client_id (str): Required if auth_type is 'service_principal'.
        client_secret (str): Required if auth_type is 'service_principal'.

    Raises:
        ValueError: If credential setup fails.
    """

    def __init__(self, auth_type = '', **kwargs):
        try:
            logging.info('Called AuthClient constructor')
            self.set_credentials(auth_type, **kwargs)
        except Exception as e:
            raise ValueError(e)

    def set_credentials(self, auth_type='', **kwargs):
        """
        Set authentication credentials based on the specified authentication type.

        Parameters:
            auth_type (str): The method of authentication. Supported values:
                            - 'managed_identity': Uses DefaultAzureCredential.
                            - 'service_principal': Uses ClientSecretCredential.

        Keyword Args:
            tenant_id (str): Required if auth_type is 'service_principal'.
            client_id (str): Required if auth_type is 'service_principal'.
            client_secret (str): Required if auth_type is 'service_principal'.

        Raises:
            ValueError: If credential initialization fails.
        """
        try:
            if auth_type.casefold().strip() == 'service_principal':
                logging.info('AuthClient: Set Credentials - service_principal')
                self.credential = ClientSecretCredential(kwargs.get('tenant_id'), kwargs.get('client_id'), kwargs.get('client_secret'))
            elif auth_type.casefold().strip() == 'managed_identity':
                logging.info('AuthClient: Set Credentials - managed_identity')
                self.credential = DefaultAzureCredential(exclude_shared_token_cache_credential = True)
            else:
                # Passthrough/AD/Service Account Authentication
                pass
        except Exception as e:
            raise ValueError(e)