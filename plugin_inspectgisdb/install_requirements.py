# -*- coding: utf-8 -*-

from gluon._compat import urlopen
from gluon.admin import plugin_install

def install_plugins(**urls):
    """ Installs required plugins from urls """
    for name, url in urls.items():
        plugin_install(request.application, urlopen(url), request, "web2py.plugin.%s.w2p" % name)
        print "Required plugin %s installed successfully!" % name

if __name__=="__main__":

    requirements = {
        "inspectdb": "https://github.com/manuelep/plugin_inspectdb/releases/download/v1.0/web2py.plugin.inspectdb.w2p"
    }
    
    install_plugins(**requirements)