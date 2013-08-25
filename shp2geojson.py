import requests
import shapefile
import os
import json
import zipfile
from cStringIO import StringIO
from itertools import izip_longest

def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return izip_longest(*args, fillvalue=fillvalue)

def dump_shapes(fips):
    u = 'http://www2.census.gov/geo/tiger/TIGER2010/TABBLOCK/2010'
    url = '%s/tl_2010_%s_tabblock10.zip' % (u, fips)
    req = requests.get(url)
    if req.status_code != 200:
        print 'Unable to fetch census block shape data for %s' % fips
    else:
        zf = StringIO(req.content)
        shp = StringIO()
        dbf = StringIO()
        shx = StringIO()
        with zipfile.ZipFile(zf) as f:
            for name in f.namelist():
                if name.endswith('.shp'):
                    shp.write(f.read(name))
                if name.endswith('.shx'):
                    shx.write(f.read(name))
                if name.endswith('.dbf'):
                    dbf.write(f.read(name))
        shape_reader = shapefile.Reader(shp=shp, dbf=dbf, shx=shx)
        records = shape_reader.shapeRecords()
        record_groups = grouper(records, 1000)
        geo = {'type': 'FeatureCollection', 'features': []}
        for records in record_groups:
            for record in records:
                if record:
                    geoid = record.record[4]
                    dump = {'type': 'Feature', 'geometry': record.shape.__geo_interface__}
                    geo['features'].append(dump)
        f = open('out/%s.geojson' % fips, 'wb')
        f.write(json.dumps(geo))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--counties', type=str, required=True,
        help="""
            Comma separated list of 5 digit FIPS codes for counties 
            you want to load the data for.""")
    parser.add_argument('--outdir', type=str, required=True,
        help="""
            Relative path to directory where you want to output GeoJSON.
            Created if it doens't already exist.""")
    args = parser.parse_args()
    counties = args.counties.split(',')
    try:
        os.mkdir(args.outdir)
    except OSError:
        pass
    for fips in counties:
        dump_shapes(fips)
