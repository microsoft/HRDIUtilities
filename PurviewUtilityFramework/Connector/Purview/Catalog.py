import azure.purview.catalog as catalog
from Connector.Purview.Base import PurviewBaseClient
from azure.core.exceptions import HttpResponseError
import logging
from urllib.parse import urlencode


class PurviewCatalogClient(PurviewBaseClient):
    """
    Provides communication between the application and Azure Purview Catalog.

    This client wraps the Azure Purview Catalog SDK to simplify interactions such as querying,
    retrieving, and managing catalog assets.

    For more details, refer to the official documentation:
    https://learn.microsoft.com/en-us/python/api/overview/azure/purview-catalog-readme?view=azure-python-preview

    Parameters:
        purview_account_name (str): The name of the Purview account.
        auth_type (str): The authentication method to use. Supported values include 'managed_identity' and 'service_principal'.

    Keyword Args:
        tenant_id (str): Tenant ID for service principal authentication. Required if auth_type is 'service_principal'.
        client_id (str): Client ID for service principal authentication. Required if auth_type is 'service_principal'.
        client_secret (str): Client secret for service principal authentication. Required if auth_type is 'service_principal'.

    Returns:
        None
    """

    # region Constructor
    def __init__(self, purview_account_name, auth_type, **kwargs):
        logging.info('Called PurviewCatalogClient constructor')
        super().__init__(auth_type = auth_type, **dict(kwargs, purview_account_name = purview_account_name))
        purview_endpoint = 'https://{purview_account_name}.purview.azure.com'.format(purview_account_name = purview_account_name)
        self.client = catalog.PurviewCatalogClient(endpoint = purview_endpoint, credential=self.credential)
    # endregion

    # region Method(s)
    
    def get_asset_by_guid(self, guid):
        """
        Retrieve a single asset entity using its GUID.

        Parameters:
            guid (str): The unique identifier of the asset to retrieve.

        Returns:
            dict: The asset entity data corresponding to the provided GUID.

        Raises:
            ValueError: If the request fails due to an HTTP response error or any other exception.
        """
        try:
            response = self.client.entity.get_by_guid(guid = guid, min_ext_info=False)
            return response['entity']
        except HttpResponseError as e:
            raise ValueError(e)
        except Exception as e:
            raise ValueError(e)
        

    def list_asset_by_guid(self, guids, batch_size=100, min_batch_size=10, url_threshold=2000):
        """
        Retrieve asset entities by GUIDs, dynamically adjusting batch size to avoid URI Too Long errors.

        This method attempts to fetch asset metadata in batches. If the estimated URL length for a batch
        exceeds the specified threshold, the batch size is halved until it fits or reaches the minimum allowed size.

        Parameters:
            guids (List[str]): List of asset GUIDs to retrieve.
            batch_size (int): Initial number of GUIDs to include in each request batch (default is 100).
            min_batch_size (int): Minimum number of GUIDs allowed in a batch before failing (default is 10).
            url_threshold (int): Maximum allowed URL length to avoid HTTP 414 errors (default is 2000 characters).

        Returns:
            List[Dict]: A list of asset entity dictionaries retrieved from the catalog.

        Raises:
            ValueError: If a batch fails to fetch even at the minimum batch size.
            HttpResponseError: If an unexpected HTTP error occurs during the request.
        """
        try:
            all_entities = []
            i = 0

            while i < len(guids):
                current_batch_size = batch_size
                success = False

                while current_batch_size >= min_batch_size:
                    batch = guids[i: i + current_batch_size]
                    estimated_len = len(urlencode({"guid": batch}, doseq=True))

                    if estimated_len > url_threshold:
                        current_batch_size = current_batch_size // 2
                        continue

                    try:
                        response = self.client.entity.list_by_guids(guids=batch)
                        entities = response.get("entities", [])
                        all_entities.extend(entities)
                        i += current_batch_size
                        success = True
                        break
                    except HttpResponseError as e:
                        error_message = str(e).lower()
                        if "uri too long" in error_message:
                            current_batch_size = current_batch_size // 2
                        else:
                            raise  # Unexpected error, re-raise immediately

                if not success:
                    raise ValueError(f"Failed to fetch batch starting at index {i} even at min_batch_size={min_batch_size}.")

            return all_entities
        except HttpResponseError as e:
            raise ValueError(e)
        except Exception as e:
            raise ValueError(e)


    def move_assets(self, collection, guids):
        '''
        Move specified assets to a target collection.

        :param collection list:
            The target collection(s) to which the assets should be moved.
        :param guids list[str]:
            List of asset GUIDs to be moved.

        :return: None

        This method uses the client's collection API to move the specified assets
        into the given collection. It raises a ValueError if the operation fails
        due to an HTTP response error or any other exception.
        '''
        try:
            self.client.collection.move_entities_to_collection(collection = collection, move_entities_request = {'entityGuids': guids})
        except HttpResponseError as e:
            raise ValueError(e)
        except Exception as e:
            raise ValueError(e)
        
    def query_catalog(self, keyword, filter, limit=100):
        '''
        Query the catalog to identify assets based on a keyword.

        :param keyword str:
            Keyword to search for in the catalog.
        :param limit int, optional:
            Maximum number of assets to retrieve per request (default is 100).

        :return: List of asset data dictionaries matching the keyword.
        :rtype: list[dict]

        This method performs a paginated search using the provided keyword and aggregates
        all matching assets until no more results are returned. It handles HTTP response
        errors and general exceptions by raising a ValueError.
        '''
        try:
            all_assets = []
            
            search_request = {
                "keywords": keyword,
                "limit": limit,
                "filter": filter,
                "offset": 0  # Start from the beginning
            }

            while True:
                response = self.client.discovery.query(search_request)
                entities = response.get("value", [])
                
                if not entities:
                    break  # Stop when no more assets are found
                
                all_assets.extend(entities)
                search_request["offset"] += len(entities)  # Move to the next batch

            return all_assets
        except HttpResponseError as e:
            raise ValueError(e)
        except Exception as e:
            raise ValueError(e)
    
    def add_assets(self, collection_name, entities, batch_size=50):
        """
        Add assets to a specified collection in batches.

        This method splits the list of asset entities into batches and sends them to the
        Purview catalog for creation or update under the specified collection.

        Parameters:
            collection_name (str): The name of the collection where assets will be added.
            entities (List[dict]): A list of asset entity definitions to be added.
            batch_size (int, optional): Number of entities to include in each batch (default is 50).

        Returns:
            List[dict]: A list of successfully created or updated asset entities.

        Raises:
            ValueError: If an HTTP or unexpected error occurs during the operation.
        """
        try:
            all_assets = []

            #Split entities into batches
            for i in range(0, len(entities), batch_size):
                batch = entities[i : i + batch_size]
                payload =  {
                    "entities": batch
                }
                response = self.client.collection.create_or_update_bulk(collection = collection_name, entities = payload)
                created_entities = response.get("value", [])
                
                all_assets.extend(created_entities)

            return all_assets
        except HttpResponseError as e:
            raise ValueError(f"HTTP Error: {e}")
        except Exception as e:
            raise ValueError(f"Unexpected Error: {e}")
    # endregion