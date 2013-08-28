import requests
import shapefile
import os
import json
import zipfile
from cStringIO import StringIO
from itertools import izip_longest

ENDPOINT = 'http://www2.census.gov/geo/tiger/TIGER2010'

SHAPE_LOOKUP = {
    'blocks': 'TABBLOCK',
    'tracts': 'TRACT'
}

def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return izip_longest(*args, fillvalue=fillvalue)

def dump_shapes(fips, shape_type, outdir):
    url = '%s/%s/2010/tl_2010_%s_%s10.zip' % (ENDPOINT, shape_type.upper(), fips, shape_type.lower())
    req = requests.get(url)
    if req.status_code != 200:
        print 'Unable to fetch census block shape data for %s from %s' % (fips, url)
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
            i = 0
            for record in records:
                if record:
                    geoid = record.record[4]
                    dump = {
                        'type': 'Feature', 
                        'geometry': record.shape.__geo_interface__,
                        'id': i,
                        'properties': {
                            'tract_fips': geoid
                        }
                    }
                    i += 1
                    geo['features'].append(dump)
        f = open('%s/%s_%s.geojson' % (outdir, fips, shape_type), 'wb')
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
    parser.add_argument('--shape_type', choices=['blocks', 'tracts'], required=True,
        help="""
            Type of shapes you want to dump.""")
    args = parser.parse_args()
    counties = args.counties.split(',')
    try:
        os.mkdir(args.outdir)
    except OSError:
        pass
    shape_type = SHAPE_LOOKUP[args.shape_type]
    for fips in counties:
        dump_shapes(fips, shape_type, args.outdir)
