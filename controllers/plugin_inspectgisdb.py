# -*- coding: utf-8 -*-
# try something like

@auth.requires(request.client=='127.0.0.1' or auth.is_logged_in(), requires_login=False)
def index():
    odb = odbs[request.args(0)]
    res = odb(odb.geometry_columns.geometry_column!=None).select(
        *[odb.geometry_columns[f] for f in odb.geometry_columns.fields if f!="id"]
    )
    return dict(tabinfos=res, odb=request.args(0))

@auth.requires(request.client=='127.0.0.1' or auth.is_logged_in(), requires_login=False)
def table():
    odb = odbs[request.args(0)]
    tn = request.args(1)
    geoms = odb(odb.geometry_columns.table_name==tn).select(
        odb.geometry_columns.table_name,
        odb.geometry_columns.geometry_column,
        odb.geometry_columns.srid
    )
    _bbox = "ST_AsText(BOX2D(ST_Extent(%(table_name)s.%(geometry_column)s)))"
    # Not considering points with 0,0 cooridnates
    flt = "ST_Distance(%(geometry_column)s, ST_GeomFromText('POINT(0 0)',%(srid)s))>0"
    envs = {row.geometry_column: odb((odb[tn].id>0)&(flt % row)).select(_bbox % row).first() \
        for row in geoms}

    def _table(odb, tablename):
        return locals()
    return dict(_table(*request.args), envs=envs, bbox=_bbox)
