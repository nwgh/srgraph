import base64
import collections
import glob
import json
import os

import pygal

from flask import Flask
from flask import render_template
from flask import request

app = Flask(__name__)

def get_data():
    """Returns a 2-tuple. The first element is a dict containing all the
    choices available for each of firefox version, platform, test suite, and
    net configs. The second element is a list of the raw JSON objects as read
    in from disk.
    """
    versions = set()
    platforms = set()
    tests = set()
    netconfigs = set()
    runs = []

    files = glob.glob('data/*.json')
    for filename in files:
        with file(filename) as f:
            data = json.load(f)

        runs.append(data)
        platforms.add(data['test_machine']['os'])
        versions.add(data['test_build']['version'])
        tests.add(data['testrun']['suite'])
        netconfigs.add(data['test_build']['branch'])

    return ({'versions':sorted(list(versions)),
             'platforms':sorted(list(platforms)),
             'tests':sorted(list(tests)),
             'netconfigs':sorted(list(netconfigs))},
            runs)

def render_graph(data, checked, error=False):
    """Helper function to render a graph for us. This will render a partial
    page if we are rendering because of an AJAX call, otherwise it will have
    the index render fully, so we have the full page with the graph viewable.
    """
    if error:
        rendered_template = render_template('graph_error.html', message=data)
    else:
        rendered_template = render_template('graph.html', graph_uri=data)

    xreqwith = request.headers.get('X-Requested-With', None)
    ajax = True if xreqwith is not None else False
    if not ajax:
        return index(checked=checked, graph_data=rendered_template)

    return rendered_template

def get_date(buildid):
    """Turn a buildid into an integer date (YYYYmmdd)."""
    return int(buildid[:8])

def get_dates(graph_data):
    """Return a sorted list of all the dates for which we have data on ANY
    platform/version/netconfig combo.
    """
    dates = set()
    for platform, pdata in graph_data.iteritems():
        for version, vdata in pdata.iteritems():
            for netconfig, ndata in vdata.iteritems():
                dates.update(set((x['date'] for x in ndata)))
    return sorted(list(dates))

@app.route('/graph', methods=['POST'])
def graph():
    """URL endpoint for rendering a graph."""
    metadata, data = get_data()

    versions = request.form.get('version', None)
    platforms = request.form.get('platform', None)
    netconfigs = request.form.get('netconfig', None)
    test = request.form.get('test', None)
    checked = {'versions':collections.defaultdict(lambda: False),
               'platforms':collections.defaultdict(lambda: False),
               'netconfigs':collections.defaultdict(lambda: False),
               'test':collections.defaultdict(lambda: False)}

    # Herein lies error checking
    if versions:
        versions = versions.split(',')
        for v in versions:
            if v not in metadata['versions']:
                return render_graph('Invalid Version: %s' % (v,), checked,
                        error=True)
            checked['versions'][v] = True

    if platforms:
        platforms = platforms.split(',')
        for p in platforms:
            if p not in metadata['platforms']:
                return render_graph('Invalid Platform: %s' % (p,), checked,
                        error=True)
            checked['platforms'][p] = True

    if netconfigs:
        netconfigs = netconfigs.split(',')
        for n in netconfigs:
            if n not in metadata['netconfigs']:
                return render_graph('Invalid Network Config: %s' % (n,),
                        checked, error=True)
            checked['netconfigs'][n] = True

    if test:
        if test not in metadata['tests']:
            return render_graph('Invalid Test: %s' % (test,), checked,
                    error=True)
        checked['test'][test] = True

    if not versions or not platforms or not netconfigs or not test:
        return render_graph('Missing Input', checked, error=True)

    # Setup our intermediate data structure
    graph_data = {}
    for p in platforms:
        graph_data[p] = {}
        for v in versions:
            graph_data[p][v] = {}
            for n in netconfigs:
                graph_data[p][v][n] = []

    # Loop through all the data files we have, and sort the data into buckets
    # based on the platform/version/netconfig combo
    for d in data:
        platform = d['test_machine']['os']
        version = d['test_build']['version']
        netconfig = d['test_build']['branch']
        date = get_date(d['test_build']['original_buildid'])
        value = d['results_aux']['totals'][0]

        try:
            latest = graph_data[platform][version][netconfig][-1]['date']
        except IndexError:
            latest = -1

        if data <= latest:
            # Only want one date per platform/version/netconfig combo, so
            # let's skip this one
            continue

        graph_data[platform][version][netconfig].append({'date':date,
                                                     'value':value})

    # These allow us to get the data points per line on the graph (one line per
    # platform/version/netconfig combo) with empty points for a date on which
    # that combo has no data.
    dates = get_dates(graph_data)
    lines = get_lines(graph_data, dates)

    # Finally, we can have pygal do the graphing for us
    chart = pygal.Line()
    chart.title = 'Stone Ridge'
    chart.x_labels = map(lambda x: str(x)[-4:], dates)
    for line in lines:
        chart.add(line['name'], line['points'])

    svg = chart.render()

    # We use a data: URI to encode the graph, since we have no persistent
    # storage on heroku. Let's base64 encode it to make sure we have no HTML
    # SNAFUs.
    svg_base64 = base64.b64encode(svg)
    return render_graph(svg_base64, checked)

@app.route('/')
def index(checked=None, graph_data=None):
    """Main URL endpoint."""
    if checked is None:
        checked = collections.defaultdict(lambda: collections.defaultdict(lambda: False))
    metadata, _ = get_data()
    return render_template('index.html', versions=metadata['versions'],
            platforms=metadata['platforms'], tests=metadata['tests'],
            netconfigs=metadata['netconfigs'], checked=checked,
            graph_data=graph_data)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
