# -*- coding: utf-8 -*-

from gluon._compat import urlopen
from gluon.admin import plugin_install

requirements = {
    "inspectdb": "https://github.com/manuelep/plugin_inspectdb/releases/download/v1.0/web2py.plugin.inspectdb.w2p"
}

if __name__=="__main__":
    for name, url in requirements.items():
        plugin_install(request.application, urlopen(url), request, "web2py.plugin.%s.w2p" % name)
