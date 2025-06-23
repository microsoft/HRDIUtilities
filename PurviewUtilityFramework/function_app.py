import logging
import azure.functions as func
from Config import *
import Utility.Purview.Operations as PurviewOperations

app = func.FunctionApp()

@app.timer_trigger(schedule=METADATA_CAPTURE_CRON, arg_name="captureTimer", run_on_startup=False, use_monitor=False) 
def TimedCaptureCatalogV1(captureTimer: func.TimerRequest) -> None:
    """
    Timer-triggered Azure Function to capture metadata from the source Purview catalog.

    Schedule:
        Runs daily at 12:00 PM UTC.

    Behavior:
        - Initializes the source Purview and Blob clients.
        - Extracts asset and column metadata from configured collections.
        - Uploads the metadata as CSV files to the configured blob storage location.

    Logs:
        Logs success or failure of the capture process.
    """
    try:
        logging.info('Timer trigger function TimedCaptureCatalogV1 started.')
        PurviewOperations.read_catalog()
    except Exception as e:
        logging.error(f"An error occurred while capturing catalog: {str(e)}")
    finally:
        logging.info('Timer trigger function TimedCaptureCatalogV1 completed.')

@app.timer_trigger(schedule=METADATA_PUBLISH_CRON, arg_name="publishTimer", run_on_startup=False, use_monitor=False) 
def TimedPublishCatalogV1(publishTimer: func.TimerRequest) -> None:
    """
    Timer-triggered Azure Function to publish metadata to the target Purview catalog.

    Schedule:
        Runs daily at 12:00 PM UTC and once on startup.

    Behavior:
        - Initializes the target Purview and Blob clients.
        - Reads asset and column metadata from blob storage.
        - Publishes the metadata to the configured target Purview collection.

    Logs:
        Logs success or failure of the publish process.
    """
    try:
        logging.info('Timer trigger function TimedPublishCatalogV1 started.')
        PurviewOperations.write_catalog()
    except Exception as e:
        logging.error(f"An error occurred while publishing catalog: {str(e)}")
    finally:
        logging.info('Timer trigger function TimedPublishCatalogV1 completed.') 