import sys

from sphinx.ext.intersphinx import fetch_inventory
import warnings

#uri = 'http://docs.python.org/2.7/'
uri = sys.argv[1]
print(uri)
warnings.srcdir = '.'
# Read inventory into a dictionnary
inv = fetch_inventory(warnings, uri, uri + 'objects.inv')
import pprint
#pprint.pprint(inv)
#labels = inv['std:label']
#print inv.keys()
pprint.pprint(inv)
#for label in labels:
#    print(label)
#    print(dir(label))
#    print('python:%s' % label[0])
