# -*- coding: utf-8 -*-


import geojson, json, pyproj
import shapely.wkt
from dal import Expression
if not "jsmin" in vars():
    from jsmin import jsmin
from dal import geoPoint, geoLine, geoPolygon

def _plugin_inspectgisdb():

    from dal import Table
    from gluon.tools import PluginManager
    plugins = PluginManager('inspectgisdb')

    # WARNING! geometry_columns table will not be displayed in appadmin because got no id field
    geometry_columns = Table(None, "geometry_columns",
        Field("table_name", rname='"f_table_name"'),
        Field("table_catalog", rname='"f_table_catalog"'),
        Field("geometry_column", rname='"f_geometry_column"'),
        Field("srid", "integer"),
        Field("gtype", length=30, rname="type"),
        Field("dim", "integer", rname="coord_dimension"),
        primarykey = ["table_name", "geometry_column"]
    )

    for conn in odbs:
        if myconf.get(plugins.inspectdb.confkey+conn+".gis"):
            odbs[conn].define_table("geometry_columns", geometry_columns)
            yield conn

GISConns = list(_plugin_inspectgisdb())

response.menu += [
    (STRONG(SPAN(_class="glyphicon glyphicon-plane", **{"_aria-hidden": "true"}),
            " ", T("Inspect dbs"), _style="color: yellow;"), False, "#", [
                (conn, False, URL("plugin_inspectgisdb", "index", args=(conn,)),) \
                    for conn in GISConns],),
]

def getGeomProps(dbname, tablename, epsg=None):
    odb = odbs[dbname]
    foo = lambda s: s[s.find("(")+2:s.find(")")].split(",")
    geoms = odb(odb.geometry_columns.table_name==tablename).select(
        odb.geometry_columns.table_name,
        odb.geometry_columns.geometry_column,
        odb.geometry_columns.srid
    )
    assert len(geoms)==1, "This should never happen! Why it happens? (%s)" % tablename
    geom = geoms.first()
    _bbox = "ST_AsText(BOX2D(ST_Extent(%(table_name)s.%(geometry_column)s)))" % geom
    flt = "ST_Distance(%(geometry_column)s, ST_GeomFromText('POINT(0 0)',%(srid)s))>0" % geom
    res = odb((odb[tablename].id>0)&(flt)).select(_bbox).first()._extra.values()[0]

    extent = None
    if not res is None:
        bbox = foo(res)[:-1]
        if len(bbox)>=3:
            extent = bbox[0].split(" ")+bbox[2].split(" ")

    if not epsg is None:
        iproj = pyproj.Proj(init="epsg:%s" % geom.srid)
        oproj = pyproj.Proj(init="epsg:%s" % epsg)
        if not extent is None:
            extent = pyproj.transform(iproj, oproj, *extent[0:2])+pyproj.transform(iproj, oproj, *extent[2:]) 
        else:
            extent = pyproj.transform(iproj, oproj, '-180', '-75')+pyproj.transform(iproj, oproj, '180', '75')

    return dict(
        #bbox = bbox,
        srid = geoms.first().srid,
        extent = extent,
        geom = geom.geometry_column
    )

@service.run
def geom(conn, tablename, the_geom="geom", epsg=3857, bbox=None, **kw):

    session.forget(response)

    odb = odbs[conn]
    gid = filter(lambda f: f.type=="id", odb[tablename])[0]
    query = odb[tablename][gid.name]!=None

    srid = odb(odb.geometry_columns.table_name==tablename).select(odb.geometry_columns.srid).first().srid
    if not epsg is None:
        iproj = pyproj.Proj(init="epsg:%s" % srid)
        oproj = pyproj.Proj(init="epsg:%s" % epsg)

    if not bbox is None:
        a, b, c, d = map(float, bbox.split(','))
        query &= Expression(db, "%(tablename)s.geom && ST_MakeEnvelope(%(a)s, %(b)s, %(c)s, %(d)s, %(srid)s)" % vars())

    res = odb(query).select(
        #limitby=(0,10,),
        #cache=(cache.ram, 3600),
        cacheable=True
    )

    def _getFeat(row):
        geom = shapely.wkt.loads(row[the_geom])
        props = {'id': row.id} # dict([(k,v) for k,v in json.loads(row.as_json()).iteritems() if k!=the_geom])

        feat = geojson.Feature(geometry=geom, properties=props)

        if not epsg is None:
            if feat["geometry"]["type"] == "Point":
                feat["geometry"]["coordinates"] = pyproj.transform(iproj,oproj,*feat["geometry"]["coordinates"])
            elif feat["geometry"]["type"] == "LineString":
                feat["geometry"]["coordinates"] = map(lambda xy: pyproj.transform(iproj,oproj, *xy), feat["geometry"]["coordinates"])
            else:
                raise NotImplementedError

        return feat

    collection = geojson.FeatureCollection(map(_getFeat, res), sort_keys=True)
    collection["crs"] = {
        'type': 'name',
        'properties': {
            'name': 'EPSG:%s' % epsg
        }
    }

    response.headers['Content-Type'] = "application/json"
    return geojson.dumps(collection)

@service.run
def getmap(conn, tablename, the_geom="geom", bbox=''):
    """ """
    session.forget(response)
    js = """
var url = "%(url)s";
var gargs = "%(bbox)s" && '?bbox='+"%(bbox)s";
var dynSource = new ol.source.Vector({
  url: url + gargs,
  format: new ol.format.GeoJSON(),
  loader: function(extent, resolution, projection) {
    $.ajax({
      url: url + '?bbox=' + extent.join(','),
      success: function(data) {
        if (data.features.length>0) {
            dynSource.addFeatures(dynSource.getFormat().readFeatures(data));
        }
      }
    });
  },
  projection: 'EPSG:3857',
  strategy: ol.loadingstrategy.bbox
});
var map = new ol.Map({
    "target": "map",
    "layers": [
        new ol.layer.Tile({opacity: 0.3, source: new ol.source.OSM()}),
        new ol.layer.Vector({"source": dynSource})
    ],
    view: new ol.View({
      center: [0, 0],
      zoom: 2
    })
});
function fitmap (mymap) {
    if ( Number.isFinite(dynSource.getExtent()[0])!==false ) {
        mymap.getView().fit(dynSource.getExtent(), mymap.getSize())
    } else {
        setTimeout(function () {fitmap(mymap)}, 500)
    };
}
fitmap(map);
    """ % dict(
        url = URL("default", "call", args=("run", "geom", conn, tablename, the_geom,)),
        bbox = bbox
    )
    # DEBUG
    __js = """
var map = new ol.Map({
    layers: [
      new ol.layer.Tile({
        source: new ol.source.OSM()
      })
    ],
    target: 'map',
    }),
    view: new ol.View({
      center: [0, 0],
      zoom: 2
    })
});
    """
    response.js = jsmin(js)
    return DIV(_id="map", _style="height: 500px;")

class GDBService(DBService):

    @staticmethod
    def _insert(data, geomkey, geom, tab, GeomFromGeoJSON=False):
        """
        data @dict         : geojson record property;
        geom @dict/geojson : geojson geometry informations.
        """
        if GeomFromGeoJSON:
            data[geomkey] = json.dumps(geom)
            sql = tab._insert(**data)
            sql = sql.replace('ST_GeomFromText', 'ST_GeomFromGeoJSON')
            return odbs[dbname].executesql(sql)[0][0]
        else:
            if geom["geometry"]["type"] == "Point":
                data[geomkey] = geoPoint(*geom["geometry"]["coordinates"])
            elif geom["geometry"]["type"] == "Poligon":
                data[geomkey] = geoPolygon(*geom["geometry"]["coordinates"])
            else:
                raise NotImplementedError
            return tab.insert(**data)

    @classmethod
    def insert(cls, dbname, tablename, _data):
        """
        data @string/geojson : Data in geojson format. Properties will be distributed in fields using keys.
        """

        @auth.requires(request.is_local or auth.is_logged_in())
        def _main():
            session.forget(response)
            data = geojson.loads(_data) if isinstance(_data, basestring) else _data
            properties = data.pop("properties")

            tabprops = getGeomProps(dbname, tablename)
            tab = odbs[dbname][tablename]
            odata = {k: cls._cast(tab[k], v) for k,v in properties.iteritems()}

            return cls._insert(odata, tabprops["geom"], data, tab)

        return _main()

    @classmethod
    def bulk_insert(cls, dbname, tablename, _data):
        data = geojson.loads(_data) if isinstance(_data, basestring) else _data
        return map(lambda d: cls.insert(dbname, tablename, d), data)
            

@service.json
def gdb_insert(dbname, tablename, data):
    """ """
    return dict(id = GDBService.insert(dbname, tablename, data))

@service.json
def gdb_bulk_insert(dbname, tablename, data):
    """ """
    return dict(ids = GDBService.bulk_insert(dbname, tablename, data))
