import argparse
import advanced_functions

def run(argv=None):
    parser = argparse.ArgumentParser(prog='cli_and_dunder')
    parser.add_argument('--a', type=int, default=1)
    parser.add_argument('--b', type=int, default=2)
    ns = parser.parse_args(argv)
    print(advanced_functions.with_defaults(ns.a, ns.b))

if __name__ == '__main__':
    run()
