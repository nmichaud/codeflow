#
# Canopy product code
#
# (C) Copyright 2011 Enthought, Inc., Austin, TX
# All right reserved.
#
# This file is confidential and NOT open source.  Do not distribute.
#

from traits.api import Interface

class IReactorTCP(Interface):

    def listenTCP(self, port, factory, backlog=50, interface=''):
        """
        Connects a given protocol factory to the given numeric TCP/IP port.

        @param port: a port number on which to listen

        @param factory: a L{twisted.internet.protocol.ServerFactory} instance

        @param backlog: size of the listen queue

        @param interface: the hostname to bind to, defaults to '' (all)

        @return: an object that provides L{IListeningPort}.

        @raise CannotListenError: as defined here
                                  L{twisted.internet.error.CannotListenError},
                                  if it cannot listen on this port (e.g., it
                                  cannot bind to the required port number)
        """

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        """
        Connect a TCP client.

        @param host: a host name

        @param port: a port number

        @param factory: a L{twisted.internet.protocol.ClientFactory} instance

        @param timeout: number of seconds to wait before assuming the
                        connection has failed.

        @param bindAddress: a (host, port) tuple of local address to bind
                            to, or None.

        @return: An object which provides L{IConnector}. This connector will
                 call various callbacks on the factory when a connection is
                 made, failed, or lost - see
                 L{ClientFactory<twisted.internet.protocol.ClientFactory>}
                 docs for details.
        """
