import requests
import shapefile
import os
import json
import zipfile
from cStringIO import StringIO
from itertools import izip_longest

ENDPOINT = 'http://www2.census.gov/geo/tiger/TIGER2010'
JOBS_ENDPOINT = 'http://ec2-54-212-141-93.us-west-2.compute.amazonaws.com'

SHAPE_LOOKUP = {
    'blocks': 'TABBLOCK',
    'tracts': 'TRACT'
}

def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return izip_longest(*args, fillvalue=fillvalue)

def dump_shapes(fips, shape_type, outdir, get_jobs=False):
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
                    fips_parts = geoid.split('.')
                    try:
                        tract_fips = ''.join([fips, fips_parts[0].zfill(4), fips_parts[1].zfill(2)])
                    except IndexError:
                        tract_fips = ''.join([fips, fips_parts[0].zfill(4), '00'])
                    dump = {
                        'type': 'Feature', 
                        'geometry': record.shape.__geo_interface__,
                        'id': i,
                        'properties': {
                            'tract_fips': tract_fips
                        }
                    }
                    if get_jobs:
                        dump = add_jobs(tract_fips, dump)
                    i += 1
                    geo['features'].append(dump)
        f = open('%s/%s_%s.geojson' % (outdir, fips, shape_type), 'wb')
        f.write(json.dumps(geo))
        return geo

def merge(shapes):
    out_geo = {'type': 'FeatureCollection', 'features': []}
    for shape in shapes:
        features = shape['features']
        for feature in features:
            out_geo['features'].append(feature)
    return out_geo

def add_jobs(fips, geo):
    u = '%s/tract-average/%s/' % (JOBS_ENDPOINT, fips)
    r = requests.get(u)
    if r.status_code is 200:
        if r.json():
            geo['properties']['2011'] = {'total_jobs': r.json()['2011']['total_jobs']}
        else:
            geo['properties']['2011'] = {'total_jobs': None}
        return geo
    else:
        print 'Got a %s from LODES endpoint when trying to get OD data for %s' % (r.status_code, fips)
        return geo

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
    parser.add_argument('--merge', action='store_true',
        help="""
            Merge all the shapefiles into one GeoJSON object.""")
    parser.add_argument('--get_jobs', action='store_true',
        help="""
            Attempt to fetch data about workers traveling to and from given tracts.
            Only works for tract level data. """)
    args = parser.parse_args()
    counties = args.counties.split(',')
    try:
        os.mkdir(args.outdir)
    except OSError:
        pass
    shape_type = SHAPE_LOOKUP[args.shape_type]
    all_shapes = []
    for fips in counties:
        all_shapes.append(dump_shapes(fips, shape_type, args.outdir, get_jobs=args.get_jobs))
    if args.merge:
        merged = merge(all_shapes)
        f = open('%s/merged.geojson' % args.outdir, 'wb')
        f.write(json.dumps(merged))
