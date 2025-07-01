from abc import ABC
from Auth.Client import AuthClient


class ConnectorBaseClient(AuthClient, ABC):
    
    '''
        Abstract class for connectors.
        This is a blueprint for child classes.
    '''

    # region Method(s)
    
    def set_additional_attribute(self, **kwargs):
        '''
            Set additional parameters supplied while creating an object

            :return: None
            :rtype: None
        '''
        try:
            for key,val in kwargs.items():
                exec('self' + key + '=val')
        except Exception as e:
            raise ValueError(e)
    # endregion