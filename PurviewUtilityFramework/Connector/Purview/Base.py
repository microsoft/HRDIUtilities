from Connector.Base import ConnectorBaseClient
import logging
class PurviewBaseClient(ConnectorBaseClient):
    """
    Initialize the ConnectorBaseClient.

    Inherits authentication setup from AuthClient and serves as a base class
    for connector implementations.

    Parameters:
        *args: Positional arguments passed to the AuthClient.
        **kwargs: Keyword arguments passed to the AuthClient.
    """
    # region Contructor
    def __init__(self, auth_type, **kwargs):
        try:
            logging.info('Called PurviewBaseClient constuctor')
            super().__init__(auth_type, **kwargs)
            self.set_additional_attribute(**dict(kwargs, auth_type = auth_type))
        except Exception as e:
            raise ValueError(e)
    # endregion

    # region Method(s)
    
    # Purview common method(s) here

    # endregion