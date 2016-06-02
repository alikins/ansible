#!/usr/bin/python

import sys

class VarGen(object):
    def __init__(self, start=None, end=None, size=None, template=None):
        self.size = size or 0
        self.start = start or 0
        self.end = end or self.size
        self.template = template or 'some_var_%s: some_value_%s'
        self.generator = self.gen()

    def gen(self):
        for i in range(self.start, self.end):
            yield self.gen_var(i)

    def gen_var(self, index):
        return self.template % (index, index)

    def __iter__(self):
        return self.generator

def genvars(size=None, template=None):
    var_name_gen = VarGen(size=size, template=template)
    vars = []
    for name in var_name_gen:
        vars.append(name)

    return '\n'.join(vars)


def main(args):
    size = 1000
    template = 'some_var_%s: some_value_%s'
    if len(args) > 1:
        size = int(args[1])

    if len(args) > 2:
        template = args[2]

    print(genvars(size=size, template=template))


if __name__ == "__main__":
    ret = main(sys.argv[:])
    sys.exit(ret)
