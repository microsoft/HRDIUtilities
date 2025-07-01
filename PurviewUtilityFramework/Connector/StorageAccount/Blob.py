from io import BytesIO
from azure.storage.filedatalake import DataLakeServiceClient
from Connector.StorageAccount.Base import StorageAccountBaseClient
from azure.core.exceptions import HttpResponseError
import logging

class BlobClient(StorageAccountBaseClient):
    # region Constructor
    def __init__(self, storage_account_name, auth_type, **kwargs):
        """
        Initialize the BlobClient for interacting with Azure Data Lake Storage Gen2.

        Parameters:
            storage_account_name (str): The name of the Azure Storage account.
            auth_type (str): The authentication method to use (e.g., 'managed_identity', 'service_principal').

        Keyword Args:
            tenant_id (str): Required if auth_type is 'service_principal'.
            client_id (str): Required if auth_type is 'service_principal'.
            client_secret (str): Required if auth_type is 'service_principal'.

        Sets:
            self.client: An instance of DataLakeServiceClient for file system operations.
        """
        logging.info('Called BlobClient constructor')
        super().__init__(auth_type = auth_type, **dict(kwargs, storage_account_name = storage_account_name))
        account_endpoint = 'https://{storage_account_name}.dfs.core.windows.net'.format(storage_account_name = storage_account_name)
        self.client = DataLakeServiceClient(account_url= account_endpoint, credential=self.credential)
    # endregion

    # region Method(s)
    
    def read_file(self, container_name, file_path, file_name):
        """
        Reads the contents of a file from Azure Data Lake Storage Gen2.

        Parameters:
            container_name (str): Name of the container (file system) in the storage account.
            file_path (str): Path to the directory containing the file.
            file_name (str): Name of the file to read.

        Returns:
            str: Contents of the file as a UTF-8 decoded string.

        Raises:
            ValueError: If an HTTP or unexpected error occurs during file read.
        """
        try:
            container_client = self.client.get_file_system_client(container_name)
            file_client = container_client.get_file_client(file_path + '/' + file_name)
            download = file_client.download_file()
            downloaded_bytes = download.readall()
            file_content = downloaded_bytes.decode('utf-8')
            return file_content
        except HttpResponseError as e:
            raise ValueError(e)
        except Exception as e:
            raise ValueError(e)
        
    def upload_file(self, container_name, file_path, file_name, df):
        """
        Uploads a pandas DataFrame as a CSV file to Azure Data Lake Storage Gen2.

        Parameters:
            container_name (str): Name of the container (file system) in the storage account.
            file_path (str): Path to the directory where the file will be uploaded.
            file_name (str): Name of the file to create or overwrite.
            df (pandas.DataFrame): DataFrame to be written as a CSV file.

        Returns:
            None

        Raises:
            ValueError: If an HTTP or unexpected error occurs during file upload.
        """
        try:
            csv_buffer = BytesIO()
            df.to_csv(csv_buffer, index=False)  # write CSV into memory buffer
            csv_data = csv_buffer.getvalue()

            container_client = self.client.get_file_system_client(container_name)
            file_client = container_client.get_file_client(file_path + '/' + file_name)
            
            if file_client.exists():
                file_client.delete_file()

            file_client.create_file()
            file_client.append_data(data=csv_data, offset=0, length=len(csv_data))
            file_client.flush_data(len(csv_data))

        except HttpResponseError as e:
            raise ValueError(e)
        except Exception as e:
            raise ValueError(e)
    
    # endregion