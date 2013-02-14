#
# Canopy product code
#
# (C) Copyright 2011 Enthought, Inc., Austin, TX  
# All right reserved.  
#
# This file is confidential and NOT open source.  Do not distribute.
#

from envisage.api import Plugin, ServiceOffer
from traits.api import Any, HasTraits, List, Instance, implements
from pyface.util.guisupport import get_app_qt4

from ireactor import IReactorTCP

ID = 'envisage.plugins.twisted'

class TwistedPlugin(Plugin):
    """ Provides twisted integration for a canopy application
    """

    # Extension point IDs
    SERVICE_OFFERS         = 'envisage.service_offers'

    #### 'IPlugin' interface ##################################################

    # The plugin's unique identifier.
    id = ID

    # The plugin's name (suitable for displaying to the user).
    name = 'Twisted Networking'

    service_offers = List(contributes_to=SERVICE_OFFERS)

    reactor = Instance(IReactorTCP)

    ###########################################################################
    # 'IPlugin' interface.
    ###########################################################################

    def start(self):
        import qt4reactor
        app = get_app_qt4()
        qt4reactor.install()

        from twisted.internet import reactor
        self.reactor = reactor
        reactor.runReturn()

    def stop(self):
        self.reactor.stop()

    #### Contributions to extension points made by this plugin ################

    def _service_offers_default(self):
        twisted_service_offer = ServiceOffer(
            protocol = IReactorTCP,
            factory  = lambda: self.reactor,
        )
        return [twisted_service_offer]
