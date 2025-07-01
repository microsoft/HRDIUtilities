from Connector.Base import ConnectorBaseClient
import logging
class StorageAccountBaseClient(ConnectorBaseClient):
    '''
        Provide communication between application and ADLS Gen2. 
        DO NOT instantiate this class directly. Instead, this should be accessed by child classes. 
        
        :param auth_type str:
            The method of authentication. e.g., managed_identity, service_principal etc.
        
        Kwargs:
            :param auth_type str:
                Type of authentication.
            :param tenant_id str: Service principal tenant id
                Required when auth_type = 'service_principal'.
            :param client_id str: 
                Service principal client id; Required when auth_type = 'service_principal'.
            :param client_secret str: 
                Service principal client secret; Required when auth_type = 'service_principal'.

        :return: None
        :rtype: None
    '''

    # region Contructor
    def __init__(self, auth_type, **kwargs):
        try:
            logging.info('Called StorageAccountBaseClient constuctor')
            super().__init__(auth_type, **kwargs)
            self.set_additional_attribute(**dict(kwargs, auth_type = auth_type))
        except Exception as e:
            raise ValueError(e)
    # endregion

    # region Method(s)
    
    # Purview common method(s) here

    # endregion