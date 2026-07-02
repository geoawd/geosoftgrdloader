# -*- coding: utf-8 -*-
def classFactory(iface):
    from .grd_loader_plugin import GeosoftGrdLoaderPlugin

    return GeosoftGrdLoaderPlugin(iface)
