from Config import *
import logging
from Connector.Purview.Catalog import PurviewCatalogClient
import jmespath
from azure.core.exceptions import HttpResponseError
import pandas as pd
from Connector.StorageAccount.Blob import BlobClient
from io import StringIO

def read_catalog():
    """
    Extracts asset and column metadata from specified Purview collections and uploads the results to Azure Blob Storage.

    This function:
    - Initializes clients for Purview Catalog and Blob Storage using managed identity.
    - Iterates through a list of source collections defined in the environment variable `SOURCE_COLLECTION_COMMA_SEPARATED`.
    - Queries assets and their associated schema and column metadata from each collection.
    - Transforms the metadata using JMESPath queries into structured formats.
    - Uploads the resulting asset and column data as CSV files to the specified blob container and directory.

    Output Files:
        - Assets.csv: Contains metadata for each asset (type, name, description, owner, etc.).
        - Columns.csv: Contains metadata for each column (type, name, data type, etc.).

    Raises:
        ValueError: If any exception occurs during the process.
    """
    try:
        #region Initializations & declarations
        assets = []
        columns = []
        asset_query = """
            [].{
                "Type Name": typeName,
                "Fully Qualified Name": attributes.qualifiedName,
                "Asset Name": attributes.name,
                "Display Text": displayText,
                "Description": attributes.description,
                "Relationship GUID": relationshipAttributes.tabular_schema.guid,
                "Owner": attributes.owner
            }
        """
        column_query = """
            [].{
                "Type Name": typeName,
                "Fully Qualified Name": attributes.qualifiedName,
                "Column Name": attributes.name,
                "Display Text": displayText,
                "Description": attributes.description,
                "Owner": attributes.owner,
                "Data Type": attributes.type
            }
        """
        source_purview_catalog_client = PurviewCatalogClient(
            purview_account_name = SOURCE_PURVIEW_ACCOUNT_NAME,
            auth_type = 'managed_identity'
        )
        blob_client  = BlobClient(
            storage_account_name = METADATA_WRITE_BLOB_ACCOUNT,
            auth_type = 'managed_identity'
        )
        logging.info(f'Initialized Purview catalog client.')
        #endregion

        # region Fetch assets from source
        # Fetch assets from each collection
        for value in [value.strip() for value in SOURCE_COLLECTION_COMMA_SEPARATED.split(",")]:
            query_filter = {"collectionId": value}
            assets_in_collection = source_purview_catalog_client.query_catalog(keyword="*", filter=query_filter)
            asset_guids = jmespath.search("[*].id", assets_in_collection)

            asset_data = source_purview_catalog_client.list_asset_by_guid(guids = asset_guids)
            assets = jmespath.search(asset_query, asset_data)

            relationship_guids = jmespath.search("[*].relationshipAttributes.tabular_schema.guid", asset_data)
            schema_data = source_purview_catalog_client.list_asset_by_guid(guids = relationship_guids)

            column_guids = jmespath.search("[*].relationshipAttributes.columns[*].guid[]", schema_data)
            column_data = source_purview_catalog_client.list_asset_by_guid(guids = column_guids)
            raw_columns = jmespath.search(column_query, column_data)

            for i, column in enumerate(column_data):
                column_relationship_guid = jmespath.search("relationshipAttributes.composeSchema.guid", column)

                matched_asset = jmespath.search(f"[?relationshipAttributes.tabular_schema.guid == '{column_relationship_guid}'] | [0]", asset_data)
                asset_name = jmespath.search('attributes.name' , matched_asset)
                # asset_name = matched_asset.get("attributes", {}).get("name") if matched_asset else None

                column_info = raw_columns[i]
                column_info["Asset Name"] = asset_name
                columns.append(column_info)


        df_asset = pd.DataFrame(assets)[["Type Name", "Fully Qualified Name", "Asset Name", "Display Text", "Description", "Owner"]]
        df_column = pd.DataFrame(columns)[["Type Name", "Asset Name", "Column Name", "Display Text", "Description", "Owner", "Data Type"]]

        blob_client.upload_file(container_name = METADATA_WRITE_BLOB_CONTAINER, file_path = METADATA_WRITE_BLOB_DIRECTORY, file_name = "Assets.csv", df = df_asset)  
        blob_client.upload_file(container_name = METADATA_WRITE_BLOB_CONTAINER, file_path = METADATA_WRITE_BLOB_DIRECTORY, file_name = "Columns.csv", df = df_column)  
        
        #endregion
    except Exception as e:
        logging.error(f'Error: {str(e)}')
        raise ValueError(e)
    

def write_catalog():
    """
    Reads asset and column metadata from Azure Blob Storage and writes it to the target Purview catalog collection.

    This function:
    - Initializes Purview and Blob clients using managed identity.
    - Reads `Assets.csv` and `Columns.csv` from the specified blob container and directory.
    - Renames and cleans up the data to match the expected schema for Purview ingestion.
    - Converts the data into the required JSON structure using JMESPath queries.
    - Uploads the column metadata (and optionally asset metadata) to the target Purview collection.

    Notes:
        - The asset upload line is currently commented out. Uncomment it to include asset metadata in the upload.
        - Owner fields are filled with empty strings if missing to avoid ingestion errors.

    Raises:
        ValueError: If an HTTP or unexpected error occurs during the process.
    """
    try:
        #region Initializations & declarations
        collection_name = TARGET_COLLECTION_NAME
        asset_query = """[].{
            typeName: typeName,
            attributes: {
                name: name,
                qualifiedName: qualifiedName,
                owner: owner,
                displayName: displayText,
                description: description
            }
        }"""
        column_query = """[].{
            typeName: typeName,
            attributes: {
                name: name,
                qualifiedName: qualifiedName,
                owner: owner,
                displayName: displayText,
                description: description,
                type: dataType
            }
        }"""
        target_purview_catalog_client = PurviewCatalogClient(
            purview_account_name = TARGET_PURVIEW_ACCOUNT_NAME,
            auth_type = 'managed_identity'
        ) 
        blob_client  = BlobClient(
            storage_account_name = METADATA_READ_BLOB_ACCOUNT,
            auth_type = 'managed_identity'
        )
        logging.info(f'Initialized Purview catalog clients')
        #endregion

        #region Publish Assets
        # Load assets
        assets_file_data = blob_client.read_file(container_name = METADATA_READ_BLOB_CONTAINER, file_path= METADATA_READ_BLOB_DIRECTORY, file_name="Assets.csv")        
        df_asset = pd.read_csv(StringIO(assets_file_data))
        df_asset_renamed = df_asset.rename(columns={
            "Type Name": "typeName",
            "Display Text": "displayText",
            "Fully Qualified Name": "qualifiedName",
            "Owner": "owner",
            "Asset Name": "name",
            "Description": "description"
        })
        df_asset_renamed = df_asset_renamed.fillna("")
        assets = df_asset_renamed.to_dict(orient='records')
        asset_payload = jmespath.search(asset_query, assets)
        target_purview_catalog_client.add_assets(entities = asset_payload, collection_name = collection_name)
        #endregion

        #region Publish Columns
        columns_file_data = blob_client.read_file(container_name = METADATA_READ_BLOB_CONTAINER, file_path= METADATA_READ_BLOB_DIRECTORY, file_name="Columns.csv")
        df_column = pd.read_csv(StringIO(columns_file_data))
        df_column_renamed = df_column.rename(columns={
            "Type Name": "typeName",
            "Display Text": "displayText",
            "Asset Name": "assetName",
            "Owner": "owner",
            "Column Name": "name",
            "Description": "description",
            "Data Type": "dataType"
        })
        df_column_renamed = df_column_renamed.fillna("")

        df_merged = df_column_renamed.merge(df_asset_renamed[["name", "qualifiedName"]],left_on="assetName",right_on="name",how="inner",suffixes=("", "_asset"))
        df_merged["columnPath"] = df_merged["qualifiedName"] + "#parquet_schema//" + df_merged["name"]
        df_merged = df_merged.drop(columns=["qualifiedName", "assetName", "name_asset"], errors="ignore")
        df_merged = df_merged.rename(columns={"columnPath": "qualifiedName"})
        df_merged["typeName"] = "parquet_schema_element"
        df_merged = df_merged.fillna("")

        columns = df_merged.to_dict(orient='records')
        column_payload = jmespath.search(column_query, columns)
        target_purview_catalog_client.add_assets(entities = column_payload, collection_name = collection_name)
        #endregion
    except HttpResponseError as e:
            raise ValueError(f"HTTP Error: {e}")
    except Exception as e:
        logging.error(f'Error: {str(e)}')
        raise ValueError(e)